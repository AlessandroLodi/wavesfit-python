"""Compare native Go recovery to Python using the canonical fixtures."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from wavesfit import Model, fit

p = argparse.ArgumentParser()
p.add_argument("--go-binary", required=True)
args = p.parse_args()
fixture = json.loads(
    (Path(__file__).resolve().parents[1] / "shared/reference.json").read_text()
)
report = []
with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    for case in fixture["fit_cases"]:
        config = case["config"]
        config["fit"]["budget_seconds"] = 10
        (directory / "config.json").write_text(json.dumps(config))
        np.savetxt(
            directory / "spectrum.csv",
            np.column_stack([case["x"], case["y"]]),
            delimiter=",",
        )
        proc = subprocess.run(
            [
                args.go_binary,
                "fit",
                str(directory / "spectrum.csv"),
                "--config",
                str(directory / "config.json"),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode:
            raise RuntimeError(case["name"] + ": " + proc.stdout + proc.stderr)
        go = json.loads(proc.stdout)
        py = fit(
            case["x"], case["y"], Model.from_dict(config["model"]), **config["fit"]
        )
        assert py.success, (case["name"], py.status)
        deviation = float(np.max(np.abs(np.asarray(go["fitted"]) - py.fitted)))
        assert deviation < 1e-4, (case["name"], deviation)
        for key, value in case["truth"].items():
            assert abs(go["parameters"][key] - value) < 2e-4, (case["name"], key)
        report.append(
            {
                "model": case["name"],
                "curve_max_absolute_difference": deviation,
                "python_sse": py.sse,
                "go_sse": go["sse"],
            }
        )
print(json.dumps(report, indent=2))
