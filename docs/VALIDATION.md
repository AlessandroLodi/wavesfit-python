# Validation report · v0.1.0

Validated on 2026-10-28 using macOS 26.7.1, Intel Core i7-9750H (2.60 GHz),
Python 3.13.7, NumPy 2.5.4, SciPy 1.18.1, and Go 1.27.3 (darwin/amd64).

## Numerical evidence

- Python independent checks compare Voigt values with numerical Gaussian/Cauchy convolution
  and integrate its unit area. Gaussian and Cauchy half-maximum limits are tested in both
  languages. DS is checked against its Lorentzian limit and explicit tail reversal.
- Both languages validate six individual profile families, NEXAFS composition, all four
  backgrounds, fixed parameters, active bounds, reversed/nonuniform axes, invalid data,
  insufficient observations, deadlines, and rank deficiency.
- Native Go analytic Voigt/doublet derivatives are checked against central differences.
- Six deterministic recovery cases compare Python and native Go. Maximum absolute fitted
  curve differences range from about 1.8e-13 to 5.1e-8 (Gaussian step), within the 1e-4
  acceptance bound. Named truth parameters are recovered within 2e-4.
- Canonical profile fixtures use relative tolerance 1e-10 plus absolute tolerance 1e-12.
  Fixtures alone are not treated as independent proof; analytic/convolution checks are separate.

## Acquisition and packaging evidence

Tests cover incomplete lines, scan-id/header mapping, end markers, acquisition pauses,
truncation, replacement, done markers, malformed files, bounded completion queues,
last-success retention, configuration revisions, cancellation accounting on close/reconfiguration,
export-path preflight failures, HTTP/SSE, and cross-origin mutation rejection.
Every finalized input in overload tests receives a completed result or explicit failure.
Go tests run under the race detector. The common dashboard is inspected against both engines.
Wheel installation tests run the packaged application outside its source tree. Release
archives contain embedded offline assets, license notices, and example configurations.

## Performance

Ten warmed fits of 4,096 samples and five Voigt peaks, with small peak drift and Gaussian
noise, gave these observations. Other programs and both demo servers were running during
measurement. Python and Go random generators differ; this is a workload benchmark, not a
controlled comparison of language speed.

| Implementation | Median | 95th percentile | Median updates/second |
|---|---:|---:|---:|
| Python | 0.250 s | 0.359 s | 4.00 |
| Native Go with analytic Voigt Jacobian | 0.337 s | 0.413 s | 2.97 |

Reproduce with `python scripts/benchmark.py --repeats 10` in Python and
`go run ./scripts/benchmark.go` in Go. First fits, poor initial values, other models,
background estimation, or more overlap can be substantially slower. The 1–10 Hz target is
an intended operating range, not a guaranteed acquisition rate or hard real-time deadline.

No real instrument stream or independently exported Igor golden data was available. Hardware
acceptance and exact legacy-output characterization remain unverified. Deliberate corrections
mean exact legacy equality is not expected; see NUMERICS.md and IGOR_MIGRATION.md.
