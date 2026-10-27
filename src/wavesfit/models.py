"""Named, composable profiles. Widths are in the same units as x."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
from scipy.special import erf, gamma, voigt_profile

# default value, physical lower bound, physical upper bound
DEFINITIONS = {
    "voigt": {
        "area": (1.0, 0.0, None),
        "center": (0.0, None, None),
        "gaussian_fwhm": (1.0, 0.0, None),
        "lorentzian_fwhm": (0.3, 0.0, None),
    },
    "ds": {
        "amplitude": (1.0, 0.0, None),
        "center": (0.0, None, None),
        "lorentzian_fwhm": (1.0, 1e-12, None),
        "asymmetry": (0.1, 0.0, 0.99),
    },
    "asymmetric_gaussian": {
        "height": (1.0, 0.0, None),
        "center": (0.0, None, None),
        "fwhm": (1.0, 1e-12, None),
        "slope": (0.0, None, None),
    },
    "gaussian_step": {
        "height": (1.0, 0.0, None),
        "center": (0.0, None, None),
        "gaussian_fwhm": (1.0, 1e-12, None),
        "decay": (0.0, 0.0, None),
    },
}
for _kind in ("voigt", "ds"):
    DEFINITIONS[_kind + "_doublet"] = dict(
        DEFINITIONS[_kind],
        branching_ratio=(0.5, 0.0, None),
        splitting=(1.5, None, None),
    )


@dataclass
class Parameter:
    value: float
    min: float | None = None
    max: float | None = None
    fixed: bool = False

    @classmethod
    def parse(cls, value, default=None):
        if isinstance(value, cls):
            return cls(**asdict(value))
        if isinstance(value, bool):
            raise ValueError("A parameter must be numeric")
        if isinstance(value, (int, float)):
            return cls(float(value))
        return cls(**(value if value is not None else {"value": default}))


@dataclass
class Component:
    kind: str
    prefix: str = "p1"
    parameters: dict[str, Parameter] = field(default_factory=dict)
    tail: str = "higher"

    def __post_init__(self):
        if self.kind not in DEFINITIONS:
            raise ValueError(f"Unknown component: {self.kind}")
        if not self.prefix or "." in self.prefix:
            raise ValueError("Component prefixes must be nonempty and contain no dots")
        if self.tail not in ("higher", "lower"):
            raise ValueError("tail must be higher or lower")
        unknown = set(self.parameters) - DEFINITIONS[self.kind].keys()
        if unknown:
            raise ValueError(f"Unknown parameters: {sorted(unknown)}")
        self.parameters = {
            k: Parameter.parse(self.parameters.get(k), d[0])
            for k, d in DEFINITIONS[self.kind].items()
        }
        for k, p in self.parameters.items():
            _, lo, hi = DEFINITIONS[self.kind][k]
            p.min = (
                lo if p.min is None else (max(lo, p.min) if lo is not None else p.min)
            )
            p.max = (
                hi if p.max is None else (min(hi, p.max) if hi is not None else p.max)
            )
            _validate_parameter(k, p)


def _validate_parameter(name, p):
    if (
        not isinstance(p.value, (int, float))
        or isinstance(p.value, bool)
        or not isinstance(p.fixed, bool)
    ):
        raise ValueError(f"{name}: expected a numeric value and boolean fixed flag")
    if any(
        v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool))
        for v in (p.min, p.max)
    ):
        raise ValueError(f"{name}: bounds must be numeric or null")
    if not math.isfinite(p.value) or any(
        v is not None and not math.isfinite(v) for v in (p.min, p.max)
    ):
        raise ValueError(f"{name}: parameters must be finite")
    if (p.min is not None and p.value < p.min) or (
        p.max is not None and p.value > p.max
    ):
        raise ValueError(f"{name}: initial value outside bounds")
    if p.min is not None and p.max is not None and p.min > p.max:
        raise ValueError(f"{name}: inverted bounds")
    if p.min == p.max and p.min is not None:
        p.fixed = True


def voigt(x, area=1.0, center=0.0, gaussian_fwhm=1.0, lorentzian_fwhm=0.3):
    """Unit-area Voigt times area. Both widths are full widths at half maximum."""
    if gaussian_fwhm < 0 or lorentzian_fwhm < 0 or gaussian_fwhm + lorentzian_fwhm <= 0:
        raise ValueError(
            "A Voigt width must be positive; neither width may be negative"
        )
    return area * voigt_profile(
        np.asarray(x) - center,
        gaussian_fwhm / math.sqrt(8 * math.log(2)),
        lorentzian_fwhm / 2,
    )


def doniach_sunjic(
    x, amplitude=1.0, center=0.0, lorentzian_fwhm=1.0, asymmetry=0.1, tail="higher"
):
    """DS with amplitude prefactor, not integrated area (tails are not integrable for alpha>0)."""
    if (
        lorentzian_fwhm <= 0
        or not 0 <= asymmetry < 1
        or tail not in ("higher", "lower")
    ):
        raise ValueError("Invalid DS width, asymmetry, or tail direction")
    e = (np.asarray(x) - center) * (-1 if tail == "higher" else 1)
    g = lorentzian_fwhm / 2
    return (
        amplitude
        * gamma(1 - asymmetry)
        * np.cos(math.pi * asymmetry / 2 + (1 - asymmetry) * np.arctan(e / g))
        / (e * e + g * g) ** ((1 - asymmetry) / 2)
    )


def _evaluate(c, x, p):
    kind = c.kind.removesuffix("_doublet")
    if kind == "voigt":
        y = voigt(x, **{k: p[k] for k in DEFINITIONS[kind]})
        if c.kind.endswith("_doublet"):
            q = {k: p[k] for k in DEFINITIONS[kind]}
            q["center"] += p["splitting"]
            y += p["branching_ratio"] * voigt(x, **q)
    elif kind == "ds":
        q = {k: p[k] for k in DEFINITIONS[kind]}
        y = doniach_sunjic(x, **q, tail=c.tail)
        if c.kind.endswith("_doublet"):
            q["center"] += p["splitting"]
            y += p["branching_ratio"] * doniach_sunjic(x, **q, tail=c.tail)
    elif kind == "asymmetric_gaussian":
        width = p["fwhm"] + p["slope"] * (x - p["center"])
        if np.any(width <= 0):
            raise ValueError(
                "Asymmetric Gaussian width is nonpositive on this interval"
            )
        y = p["height"] * np.exp(-4 * math.log(2) * ((x - p["center"]) / width) ** 2)
    else:
        width = p["gaussian_fwhm"]
        y = (
            p["height"]
            * 0.5
            * (1 + erf((x - p["center"]) / (width / math.sqrt(4 * math.log(2)))))
        )
        y *= np.exp(-p["decay"] * np.maximum(x - p["center"] - width, 0))
    return y


@dataclass
class Model:
    components: list[Component]
    offset: Parameter = field(default_factory=lambda: Parameter(0.0))

    def __post_init__(self):
        if not isinstance(self.components, list) or len(self.components) > 100:
            raise ValueError("components must be a list of at most 100 entries")
        self.components = [
            Component(**c) if isinstance(c, dict) else c for c in self.components
        ]
        self.offset = Parameter.parse(self.offset)
        _validate_parameter("offset", self.offset)
        if len({c.prefix for c in self.components}) != len(self.components):
            raise ValueError("Component prefixes must be unique")

    def parameters(self):
        return {
            "offset": self.offset,
            **{
                f"{c.prefix}.{k}": v
                for c in self.components
                for k, v in c.parameters.items()
            },
        }

    def evaluate_components(self, x, values=None):
        x = np.asarray(x, dtype=float)
        v = {k: p.value for k, p in self.parameters().items()}
        if values:
            v.update(values)
        out = {"offset": np.full_like(x, v["offset"])}
        for c in self.components:
            out[c.prefix] = _evaluate(
                c, x, {k: v[f"{c.prefix}.{k}"] for k in c.parameters}
            )
        return out

    def evaluate(self, x, values=None):
        return sum(self.evaluate_components(x, values).values())

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


def default_model(kind="voigt", count=1):
    if not isinstance(count, int) or not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100")
    return Model([Component(kind, f"p{i + 1}") for i in range(count)])


def nexafs(peaks=1, steps=1):
    """Composite model with explicitly specified Gaussian peak and step counts."""
    if (
        not isinstance(peaks, int)
        or not isinstance(steps, int)
        or min(peaks, steps) < 0
        or not 1 <= peaks + steps <= 100
    ):
        raise ValueError("Choose 1..100 total NEXAFS components")
    return Model(
        [Component("asymmetric_gaussian", f"peak{i + 1}") for i in range(peaks)]
        + [Component("gaussian_step", f"step{i + 1}") for i in range(steps)]
    )


def suggest(model, x, y):
    """Deterministic initial estimates. This does not choose the number or type of peaks."""
    from scipy.signal import find_peaks

    x, y = np.asarray(x), np.asarray(y)
    order = np.argsort(x)
    x, y = x[order], y[order]
    m = Model.from_dict(model.to_dict())
    if len(x) < 3:
        return m
    base = float(np.percentile(y, 10))
    span = float(x[-1] - x[0])
    if not m.offset.fixed:
        m.offset.value = max(
            m.offset.min or -math.inf, min(m.offset.max or math.inf, base)
        )
    peaks, _ = find_peaks(
        y,
        prominence=max(float(np.ptp(y)) * 0.05, 1e-12),
        distance=max(1, len(x) // (2 * len(m.components) + 1)),
    )
    peaks = sorted(peaks, key=lambda i: float(y[i]), reverse=True)[: len(m.components)]
    centers = sorted([float(x[i]) for i in peaks])
    for i, c in enumerate(m.components):
        center = (
            centers[i]
            if i < len(centers)
            else float(x[0] + span * (i + 1) / (len(m.components) + 1))
        )
        vals = {
            "center": center,
            "gaussian_fwhm": span / (8 * len(m.components)),
            "lorentzian_fwhm": span / (16 * len(m.components)),
            "fwhm": span / (8 * len(m.components)),
            "height": max(float(y.max() - base), 1e-9),
            "area": max(float(y.max() - base) * span / (8 * len(m.components)), 1e-9),
            "amplitude": max(
                float(y.max() - base) * span / (32 * len(m.components)), 1e-9
            ),
        }
        for k, v in vals.items():
            if k in c.parameters and not c.parameters[k].fixed:
                p = c.parameters[k]
                p.value = max(
                    p.min if p.min is not None else -math.inf,
                    min(p.max if p.max is not None else math.inf, v),
                )
    return m


def has_coverage(model, x, values=None):
    """A preview must observe both sides of all configured components before fitting."""
    if len(x) < max(
        16, len([p for p in model.parameters().values() if not p.fixed]) + 2
    ):
        return False
    lo, hi = min(x), max(x)
    for c in model.components:
        v = {k: p.value for k, p in c.parameters.items()}
        for k in v:
            if values and f"{c.prefix}.{k}" in values:
                v[k] = values[f"{c.prefix}.{k}"]
        width = max(
            v.get("gaussian_fwhm", 0), v.get("lorentzian_fwhm", 0), v.get("fwhm", 0)
        )
        centers = [v["center"]]
        if "splitting" in v:
            centers.append(v["center"] + v["splitting"])
        if any(lo > center - width or hi < center + width for center in centers):
            return False
    return True
