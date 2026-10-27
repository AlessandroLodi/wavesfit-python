"""Repeatable warm-start fitting benchmark; prints machine and latency distributions."""

import argparse
import json
import platform
import time

import numpy as np
import scipy

from wavesfit import default_model, fit

p = argparse.ArgumentParser()
p.add_argument("--repeats", type=int, default=10)
a = p.parse_args()
m = default_model(count=5)
for i, c in enumerate(m.components):
    c.parameters["center"].value = -4 + 2 * i
x = np.linspace(-8, 8, 4096)
truth = {k: v.value for k, v in m.parameters().items()}
rng = np.random.default_rng(123)
warm = None
times = []
for i in range(a.repeats + 1):
    values = dict(truth)
    for k in values:
        if k.endswith(".center"):
            values[k] += 0.002 * np.sin(i * 0.3)
    y = m.evaluate(x, values) + rng.normal(0, 0.002, len(x))
    start = time.perf_counter()
    r = fit(x, y, m, initial=warm, budget_seconds=10)
    elapsed = time.perf_counter() - start
    if not r.success:
        raise RuntimeError(r.status + ": " + r.message)
    warm = r.parameters
    if i:
        times.append(elapsed)
print(
    json.dumps(
        {
            "machine": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "points": len(x),
            "peaks": 5,
            "warm_repeats": len(times),
            "median_seconds": float(np.median(times)),
            "p95_seconds": float(np.percentile(times, 95)),
            "fits_per_second_median": float(1 / np.median(times)),
        },
        indent=2,
    )
)
