# WavesFit — Python

Composable spectroscopy models and live fitting while data are acquired. The Python and
[native Go implementation](https://github.com/AlessandroLodi/wavesfit-go) work independently
and share numerical conventions, fixtures, configuration, and an offline browser dashboard.

## Install and launch

Python 3.11 or later:

```sh
python -m pip install 'wavesfit[dashboard] @ git+https://github.com/AlessandroLodi/wavesfit-python@v0.1.0'
wavesfit demo
```

The command prints a local dashboard URL. Open it to see simulated growing scans and complete
spectra, fits, residuals, and parameter trends. No cloud account, Node.js, or network access is
needed after installation. Results are written to `outputs/<session>/` by default.

```python
import numpy as np
from wavesfit import default_model, fit, voigt

x = np.linspace(-5, 5, 501)
y = voigt(x, area=3, center=.4, gaussian_fwhm=.8, lorentzian_fwhm=.3)
model = default_model("voigt")
result = fit(x, y, model)
print(result.status, result.parameters, result.stderr)
```

## Real acquisition

Use the dashboard's Source panel to configure a growing file or finalized-file directory,
column mappings, scan boundaries, and units. Save the JSON preset and reuse it:

```sh
wavesfit serve --config acquisition.json
wavesfit fit spectrum.csv --config acquisition.json --output result.json
```

Growing files are UTF-8, newline-delimited CSV, TSV, or whitespace tables. A final partial
line is buffered. Set `source.expected_points`, map a `scan_id` column, or write explicit
`# scan_id=name` / `# end` lines. A pause does **not** finish a scan. Finalized-directory
sources require immutable files published by atomic rename (write `.part`, rename to `.csv`)
or a configured `done_suffix` marker. Do not point finalized mode at files still being written.
All completed scans are fitted in order; previews are coalesced. Raw source files are never
modified. Backlog is visible; fitting may lag acquisition on complex workloads.

See [the API and acquisition contract](docs/API.md), [numerical conventions](docs/NUMERICS.md),
[Igor migration inventory](docs/IGOR_MIGRATION.md), and [validation report](docs/VALIDATION.md).

## Development

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python scripts/benchmark.py
.venv/bin/python -m build
```

MIT licensed. Source provenance and scientific references are recorded in
[NOTICE](NOTICE). Instrument-specific loaders, transforms, satellite corrections, regional
smoothing, and graph exports are scheduled after v0.1.0.
