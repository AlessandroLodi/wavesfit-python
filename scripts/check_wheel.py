"""Install a built wheel in an isolated temporary environment and exercise its CLI/UI."""

import json
import os
import subprocess
import tempfile
import time
import venv
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
wheel = sorted((root / "dist").glob("*.whl"))[-1]
with tempfile.TemporaryDirectory(prefix="wavesfit-install-") as temp:
    temp = Path(temp)
    venv.create(temp / "env", with_pip=True)
    python = temp / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    subprocess.run(
        [str(python), "-m", "pip", "install", str(wheel)],
        check=True,
        env=env,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [str(python), "-m", "wavesfit", "--version"], check=True, env=env, cwd=temp
    )
    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "wavesfit",
            "demo",
            "--port",
            "0",
            "--output",
            str(temp / "out"),
        ],
        cwd=temp,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        url = process.stdout.readline().strip().split(" ")[-1]
        if not url.startswith("http://127.0.0.1:"):
            raise RuntimeError("Dashboard failed to launch: " + url)
        for path in ["/", "/app.js", "/style.css", "/v1/models"]:
            with urlopen(url + path, timeout=10) as r:
                assert r.status == 200 and len(r.read()) > 10
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with urlopen(url + "/v1/state", timeout=10) as response:
                state = json.load(response)
            if state["last_success"] and state["last_success"]["complete"]:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Installed wheel did not fit a completed simulated scan")
        print("Installed wheel: dashboard assets and completed live fit verified")
    finally:
        process.terminate()
        process.wait(timeout=10)
