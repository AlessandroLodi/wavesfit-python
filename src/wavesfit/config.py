"""Versioned configuration shared with the independent Go implementation."""

import json
import math
from copy import deepcopy

from .models import Component, Model, Parameter


def default_config():
    model = Model(
        [
            Component(
                "voigt",
                "p1",
                {
                    "area": 4.0,
                    "center": -1.3,
                    "gaussian_fwhm": 0.65,
                    "lorentzian_fwhm": 0.35,
                },
            ),
            Component(
                "voigt",
                "p2",
                {
                    "area": 2.5,
                    "center": 1.3,
                    "gaussian_fwhm": 1.0,
                    "lorentzian_fwhm": 0.35,
                },
            ),
        ],
        Parameter(0.03),
    )
    return {
        "schema_version": "1.0",
        "model": model.to_dict(),
        "background": {"kind": "none"},
        "fit": {"max_evaluations": 300, "budget_seconds": 2.0},
        "source": {"mode": "demo", "points": 512, "pattern": "both"},
        "cadence_seconds": 0.25,
        "queue_size": 4,
        "output_dir": "outputs",
        "units": {"x": "eV", "y": "intensity"},
    }


def validate_config(c):
    if not isinstance(c, dict) or c.get("schema_version") != "1.0":
        raise ValueError("schema_version must be 1.0")
    known = set(default_config())
    if set(c) - known:
        raise ValueError(f"Unknown configuration keys: {sorted(set(c) - known)}")
    out = default_config()
    out.update(deepcopy(c))
    try:
        out["model"] = Model.from_dict(out["model"]).to_dict()
    except (TypeError, KeyError, AttributeError) as e:
        raise ValueError(f"Invalid model: {e}") from e
    if any(
        not isinstance(out[k], dict) for k in ("source", "fit", "background", "units")
    ):
        raise ValueError("source, fit, background, and units must be objects")
    s = out["source"]
    if set(s) - {
        "mode",
        "path",
        "glob",
        "delimiter",
        "header",
        "columns",
        "expected_points",
        "done_suffix",
        "max_points",
        "points",
        "pattern",
    }:
        raise ValueError("Unknown source options")
    if s.get("mode") not in ("demo", "tail", "directory"):
        raise ValueError("source.mode must be demo, tail, or directory")
    if s["mode"] != "demo" and not s.get("path"):
        raise ValueError("A source path is required")
    if any(
        k in s and not isinstance(s[k], str)
        for k in ("path", "glob", "delimiter", "done_suffix")
    ):
        raise ValueError(
            "Source paths, globs, delimiters, and suffixes must be strings"
        )
    if "header" in s and not isinstance(s["header"], bool):
        raise ValueError("header must be boolean")
    delimiter = s.get("delimiter", "auto")
    if delimiter not in ("auto", "whitespace") and len(delimiter) != 1:
        raise ValueError("delimiter must be one character, auto, or whitespace")
    if "max_points" in s and (type(s["max_points"]) is not int or s["max_points"] < 2):
        raise ValueError("max_points must be >=2")
    if s.get("expected_points") is not None and (
        not isinstance(s["expected_points"], int) or s["expected_points"] < 2
    ):
        raise ValueError("expected_points must be an integer >=2")
    if s["mode"] == "demo" and (
        not isinstance(s.get("points", 512), int)
        or not 16 <= s.get("points", 512) <= 100000
    ):
        raise ValueError("demo points must be between 16 and 100000")
    if s.get("pattern", "both") not in ("both", "growing", "complete"):
        raise ValueError("Invalid demo pattern")
    if not isinstance(out["queue_size"], int) or not 1 <= out["queue_size"] <= 256:
        raise ValueError("queue_size must be 1..256")
    if (
        not isinstance(out["cadence_seconds"], (int, float))
        or not math.isfinite(out["cadence_seconds"])
        or out["cadence_seconds"] < 0.01
    ):
        raise ValueError("cadence_seconds must be >=0.01")
    f = out["fit"]
    if set(f) - {"interval", "max_evaluations", "budget_seconds"}:
        raise ValueError("Unknown fit options")
    if (
        type(f.get("max_evaluations", 300)) is not int
        or f.get("max_evaluations", 300) < 1
        or not isinstance(f.get("budget_seconds", 2), (int, float))
        or not math.isfinite(f.get("budget_seconds", 2))
        or f.get("budget_seconds", 2) <= 0
    ):
        raise ValueError("Fit budgets must be positive")
    interval = f.get("interval")
    if interval is not None and (
        len(interval) != 2
        or not all(math.isfinite(v) for v in interval)
        or interval[0] >= interval[1]
    ):
        raise ValueError("fit.interval must be [low, high]")
    if out["background"].get("kind", "none") not in (
        "none",
        "linear",
        "exponential",
        "shirley",
        "tougaard",
    ):
        raise ValueError("Unknown background")
    bg = out["background"]
    if any(
        k in bg and bg[k] is None for k in ("curvature", "kernel_c", "max_iterations")
    ):
        raise ValueError("Background shape options must be numeric, not null")
    if set(bg) - {"kind", "left", "right", "curvature", "kernel_c", "max_iterations"}:
        raise ValueError("Unknown background options")
    for k in ("left", "right", "curvature", "kernel_c"):
        v = bg.get(k)
        if v is not None and (not isinstance(v, (int, float)) or not math.isfinite(v)):
            raise ValueError(f"{k} must be finite")
    if "max_iterations" in bg and (
        type(bg["max_iterations"]) is not int or bg["max_iterations"] < 1
    ):
        raise ValueError("max_iterations must be positive")
    if bg.get("curvature") is not None and abs(bg["curvature"]) > 100:
        raise ValueError("curvature must be within [-100,100]")
    if bg.get("kernel_c") is not None and bg["kernel_c"] <= 0:
        raise ValueError("kernel_c must be positive")
    columns = s.get("columns", {"x": 0, "y": 1})
    if not isinstance(columns, dict):
        raise ValueError("columns must be an object")
    if not {"x", "y"}.issubset(columns) or set(columns) - {
        "x",
        "y",
        "sigma",
        "scan_id",
    }:
        raise ValueError("columns must map x/y and optionally sigma/scan_id")
    if not isinstance(columns, dict) or any(
        not isinstance(v, (int, str))
        or isinstance(v, bool)
        or isinstance(v, int)
        and v < 0
        for v in columns.values()
    ):
        raise ValueError("Column mappings must be nonnegative indices or header names")
    if not isinstance(out["output_dir"], str):
        raise ValueError("output_dir must be a path or empty string")
    if set(out["units"]) != {"x", "y"} or any(
        not isinstance(v, str) for v in out["units"].values()
    ):
        raise ValueError("units must map x and y to strings")
    return out


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return validate_config(json.load(f))
