"""Bounded weighted least-squares fitting with explicit diagnostic results."""

import time
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import least_squares

from .backgrounds import background
from .models import Model


@dataclass
class FitResult:
    success: bool
    status: str
    message: str
    parameters: dict
    stderr: dict
    x: list
    y: list
    fitted: list
    background: list
    components: dict
    residuals: list
    sse: float
    cost: float
    dof: int
    reduced_chi_square: float | None
    rank: int
    evaluations: int
    elapsed_seconds: float

    def to_dict(self):
        return asdict(self)


def fit(
    x,
    y,
    model: Model,
    *,
    sigma=None,
    interval=None,
    background_config=None,
    max_evaluations=300,
    budget_seconds=2.0,
    initial=None,
    cancel=None,
):
    start = time.monotonic()
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) < 2:
        raise ValueError(
            "x and y must be equal-length vectors with at least two points"
        )
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("Data contain nonfinite values")
    if not (np.all(np.diff(x) > 0) or np.all(np.diff(x) < 0)):
        raise ValueError("x must be strictly monotonic")
    if max_evaluations < 1 or budget_seconds <= 0:
        raise ValueError("Fitting budgets must be positive")
    sig = None if sigma is None else np.asarray(sigma, dtype=float)
    if sig is not None and (
        sig.shape != y.shape or np.any(sig <= 0) or not np.all(np.isfinite(sig))
    ):
        raise ValueError("sigma must be positive and match the data")
    if interval is not None:
        if len(interval) != 2 or interval[0] >= interval[1]:
            raise ValueError("interval must be [low, high]")
        mask = (x >= interval[0]) & (x <= interval[1])
        x, y = x[mask], y[mask]
        if sig is not None:
            sig = sig[mask]
    if len(x) < 2:
        raise ValueError("Fit interval contains fewer than two points")
    model = Model.from_dict(model.to_dict())
    parameters = model.parameters()
    values = {k: p.value for k, p in parameters.items()}
    if initial:
        for k, v in initial.items():
            if k in parameters and not parameters[k].fixed:
                p = parameters[k]
                values[k] = max(
                    p.min if p.min is not None else -np.inf,
                    min(p.max if p.max is not None else np.inf, float(v)),
                )
    names = [k for k, p in parameters.items() if not p.fixed]
    lower = [
        parameters[k].min if parameters[k].min is not None else -np.inf for k in names
    ]
    upper = [
        parameters[k].max if parameters[k].max is not None else np.inf for k in names
    ]
    bc = dict(background_config or {})
    kind = bc.pop("kind", "none")
    bg = background(x, y, kind, **bc)
    model.evaluate(x, values)  # invalid initial models are errors, not penalty plateaus
    count = 0
    last = None

    class Deadline(Exception):
        pass

    def residual(v):
        nonlocal count, last
        if time.monotonic() - start > budget_seconds or cancel is not None and cancel():
            raise Deadline()
        count += 1
        vals = dict(values, **dict(zip(names, v)))
        try:
            r = model.evaluate(x, vals) + bg - y
        except ValueError:
            return np.full(len(x), 1e20)
        if not np.all(np.isfinite(r)):
            return np.full(len(x), 1e20)
        last = v.copy()
        return r if sig is None else r / sig

    rank = 0
    jac = None
    status = "converged"
    message = "All parameters fixed"
    success = True
    if len(x) <= len(names):
        status = "insufficient_data"
        message = "More observations than free parameters are required"
        success = False
    elif names:
        try:
            opt = least_squares(
                residual,
                [values[k] for k in names],
                bounds=(lower, upper),
                max_nfev=max_evaluations,
                x_scale="jac",
                ftol=1e-9,
                xtol=1e-9,
                gtol=1e-9,
            )
            values.update(zip(names, opt.x))
            jac = opt.jac
            rank = int(np.linalg.matrix_rank(jac))
            success = bool(opt.success)
            status = "converged" if success else "max_evaluations"
            message = opt.message
            if rank < len(names):
                success = False
                status = "singular"
                message = "Parameters are not independently identifiable"
        except Deadline:
            # The last evaluation may be a finite-difference probe; it is diagnostic only.
            if last is not None:
                values.update(zip(names, last))
            status = "timeout"
            message = "Fitting time budget exceeded or cancelled"
            success = False
    parts = model.evaluate_components(x, values)
    pred = sum(parts.values()) + bg
    r = y - pred
    weighted = r if sig is None else r / sig
    sse = float(r @ r)
    cost = float(weighted @ weighted) / 2
    if not np.isfinite(sse) or not np.isfinite(cost):
        raise ValueError("Objective overflow; rescale observations or uncertainties")
    dof = len(x) - len(names)
    errors = {k: None for k in values}
    if success and jac is not None and rank == len(names) and dof > 0:
        _, s, vt = np.linalg.svd(jac, full_matrices=False)
        covariance = (vt.T / s**2) @ vt
        if sig is None:
            covariance *= sse / dof
        errors.update(zip(names, np.sqrt(np.maximum(np.diag(covariance), 0)).tolist()))
    # Boundary estimates do not have symmetric Gaussian uncertainties.
    for k, p in parameters.items():
        if p.fixed or any(
            b is not None and abs(values[k] - b) <= 1e-7 * max(1.0, abs(b))
            for b in (p.min, p.max)
        ):
            errors[k] = None
    return FitResult(
        success,
        status,
        str(message),
        values,
        errors,
        x.tolist(),
        y.tolist(),
        pred.tolist(),
        bg.tolist(),
        {k: v.tolist() for k, v in parts.items()},
        r.tolist(),
        sse,
        cost,
        dof,
        2 * cost / dof if sig is not None and dof > 0 else None,
        rank,
        count,
        time.monotonic() - start,
    )
