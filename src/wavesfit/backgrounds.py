"""Endpoint-anchored backgrounds on increasing or decreasing, nonuniform axes."""

import math

import numpy as np
from scipy.integrate import cumulative_trapezoid, trapezoid


def background(x, y, kind="none", **options):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if (
        len(x) != len(y)
        or len(x) < 2
        or not np.all(np.isfinite(x))
        or not np.all(np.isfinite(y))
    ):
        raise ValueError(
            "Background requires finite, equal-length arrays of at least two points"
        )
    d = np.diff(x)
    if not (np.all(d > 0) or np.all(d < 0)):
        raise ValueError("x must be strictly monotonic")
    reverse = d[0] < 0
    if reverse:
        x, y = x[::-1], y[::-1]
    left = float(y[0] if options.get("left") is None else options["left"])
    right = float(y[-1] if options.get("right") is None else options["right"])
    if not math.isfinite(left + right):
        raise ValueError("Background anchors must be finite")
    t = (x - x[0]) / (x[-1] - x[0])
    linear = left + (right - left) * t
    if kind == "none":
        b = np.zeros_like(y)
    elif kind == "linear":
        b = linear
    elif kind == "exponential":
        k = float(options.get("curvature", 1.0))
        if not math.isfinite(k) or abs(k) > 100:
            raise ValueError("curvature must be finite and within [-100,100]")
        b = (
            linear
            if abs(k) < 1e-8
            else left + (right - left) * np.expm1(k * t) / np.expm1(k)
        )
    elif kind == "shirley":
        b = linear.copy()
        if abs(left - right) < 1e-14:
            b[:] = left
        else:
            for _ in range(int(options.get("max_iterations", 200))):
                integ = cumulative_trapezoid(np.maximum(y - b, 0), x, initial=0)
                tail = integ[-1] - integ
                if abs(tail[0]) < 1e-14:
                    raise ValueError("Shirley normalization is zero")
                new = right + (left - right) * tail / tail[0]
                if np.max(np.abs(new - b)) < 1e-8 * max(1.0, np.max(np.abs(y))):
                    b = new
                    break
                b = 0.5 * (b + new)
            else:
                raise ValueError("Shirley background did not converge")
    elif kind == "tougaard":
        c = float(options.get("kernel_c", 1643.0))
        if not math.isfinite(c) or c <= 0:
            raise ValueError("kernel_c must be positive")
        integ = np.zeros_like(y)
        for i in range(len(x) - 1):
            loss = x[i:] - x[i]
            integ[i] = trapezoid((y[i:] - right) * loss / (c + loss * loss) ** 2, x[i:])
        if abs(left - right) < 1e-14:
            b = np.full_like(y, left)
        elif abs(integ[0]) < 1e-30:
            raise ValueError("Tougaard normalization is zero")
        else:
            b = right + (left - right) * integ / integ[0]
    else:
        raise ValueError(f"Unknown background: {kind}")
    return b[::-1] if reverse else b
