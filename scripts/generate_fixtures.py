"""Regenerate canonical model/fit cases; independent checks live in test_numerics.py."""

import json
from pathlib import Path

import numpy as np

from wavesfit import default_model, nexafs
from wavesfit.config import default_config

root = Path(__file__).resolve().parents[1]
cases = []
for kind in [
    "voigt",
    "voigt_doublet",
    "ds",
    "ds_doublet",
    "asymmetric_gaussian",
    "gaussian_step",
    "nexafs",
]:
    m = nexafs(2, 1) if kind == "nexafs" else default_model(kind)
    if kind == "asymmetric_gaussian":
        m.components[0].parameters["slope"].value = 0.03
    x = np.array([-4.0, -1.7, -0.5, 0.0, 0.5, 1.3, 2.0, 5.0])
    cases.append(
        {
            "name": kind,
            "model": m.to_dict(),
            "x": x.tolist(),
            "expected": m.evaluate(x).tolist(),
        }
    )
fitcases = []
for kind in [
    "voigt",
    "voigt_doublet",
    "ds",
    "ds_doublet",
    "asymmetric_gaussian",
    "gaussian_step",
]:
    m = default_model(kind)
    x = np.linspace(-5, 6, 201)
    truth = {"p1.center": 0.25}
    if "area" in m.components[0].parameters:
        truth["p1.area"] = 2.3
    if "amplitude" in m.components[0].parameters:
        truth["p1.amplitude"] = 1.7
    if "height" in m.components[0].parameters:
        truth["p1.height"] = 1.7
    truth["offset"] = 0.07
    fitcases.append(
        {
            "name": kind,
            "config": dict(default_config(), model=m.to_dict(), output_dir=""),
            "x": x.tolist(),
            "y": m.evaluate(x, truth).tolist(),
            "truth": truth,
        }
    )
(root / "shared/reference.json").write_text(
    json.dumps(
        {
            "schema_version": "1.0",
            "rtol": 1e-10,
            "atol": 1e-12,
            "cases": cases,
            "fit_cases": fitcases,
        },
        indent=2,
    )
    + "\n"
)
(root / "examples/demo.json").write_text(json.dumps(default_config(), indent=2) + "\n")
