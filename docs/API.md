# API and acquisition contract · schema 1.0

Python and Go use the same JSON configuration, model names, and result fields. Numerical
optimizers differ, so fitted coefficients need not be bit-identical. See NUMERICS.md.

## Library APIs

Python: `Model`, `Component`, `Parameter`, `fit(x, y, model, sigma=None, interval=None,
background_config=None, max_evaluations=300, budget_seconds=2, initial=None)`.
Models expose `evaluate`, `evaluate_components`, `parameters`, and JSON-compatible
`to_dict`/`from_dict`. `default_model(kind, count)` and `nexafs(peaks, steps)` create models.
`suggest` in `wavesfit.models` estimates starting values for an explicitly chosen model.
`background(x, y, kind, **options)` is also independently usable.

Go: `DefaultModel`, `NEXAFS`, `Model.Normalize`, `Model.Evaluate`, `Model.EvaluateComponents`,
`Suggest`, `Background`, and `Fit(ctx, x, y, sigma, model, background, options, initial)`.
Normalize manually constructed models before evaluating; `Fit` normalizes automatically.
An independent `Session` / `StreamingSession` owns acquisition and processing. Close sessions
when finished. Python sources expose `poll`; Go sources implement `Source` with `Poll/Stats`.
Custom pull adapters can use Python's `StreamingSession(config, source=adapter)` or Go's
`NewSessionWithSource(config, adapter)`. Adapter polling must return promptly rather than
blocking indefinitely; acquisition controls and shutdown wait for a poll to return.

Fits return named parameters, per-parameter standard errors (null when unavailable), x/y,
fitted/background/component arrays, residuals, SSE, weighted half-squared cost, degrees of
freedom, optional reduced chi-square, Jacobian rank, evaluations, duration, and status.
Invalid batch inputs raise an error; invalid scans produce explicit streaming failure records.
Solver timeouts and nonconvergence return diagnostic fits with `success=false`.

## Configuration

`examples/demo.json` is a full editable preset; `shared/config.schema.json` describes the
wire format. `schema_version` is required and must equal `"1.0"`. Unknown versions are errors.
Component prefixes are unique, nonempty, and contain no dot; flattened names are `p1.center`.
Parameters accept a number or `{ "value": 1, "min": 0, "max": null, "fixed": false }`.
Physical bounds are enforced even when user bounds are wider. Equal bounds fix a parameter.

`fit.interval` is an increasing `[low, high]` pair independent of input order; result arrays
contain only observations inside that interval. `fit.max_evaluations` is a solver work limit
(SciPy function iterations / Go damped-step iterations; finite-difference probes are additional).
`evaluations` counts actual residual evaluations. `budget_seconds` bounds optimization work;
file reading, background setup, and an individual numerical operation may add latency.

Source modes:

- `demo`: `points` (16–100000), `pattern` (`both`, `growing`, or `complete`). Model-driven
  synthetic spectra include small drift and noise; random generators differ between languages.
- `tail`: `path`, `columns`, `delimiter`, `header`, optional `expected_points`, `max_points`.
- `directory`: `path`, `glob` (default `*.csv`), optional `done_suffix`, columns/delimiter/header,
  optional expected point count. Every finalized file contains one spectrum.

`columns` maps `x`, `y`, optional `sigma` (positive standard deviation), and optional `scan_id`
to zero-based indices or header names. Named mappings consume the first non-comment row as a
header. Delimiters are `auto`, `whitespace`, or a single character. Text is UTF-8. Blank rows
and `#` comments are ignored. Tail input requires newline-terminated records; partial trailing
lines remain buffered. Finalized files may omit their final newline.

Growing scans finish at `expected_points`, when a scan_id changes, at `# scan_id=new-id`, or
at `# end`. Idle time does not finish a scan. A final scan with only a scan_id column needs
an explicit end marker or the next scan's first row. A partial scan interrupted by rotation
or detected truncation produces a failure; a new scan begins from byte zero. Maximum default
scan size is one million points. A malformed row poisons that scan rather than silently
dropping observations; subsequent scans can proceed after an explicit boundary.

Completed files must be published immutably by atomic rename, or have a done marker created
only after the data file is closed. Filename order determines initial processing order.
Changed file versions are processed again. Do not overwrite files while they are being
processed. Queue capacity applies to loaded spectra; undispatched files remain on disk.

## Streaming behavior

Acquisition and fitting run independently with one fitting worker and a bounded completion
queue. Complete scans take priority over coalesced previews. Both sides of all configured
peaks must be observed before a preview is fitted (`awaiting_coverage` otherwise). Every
complete scan is attempted even when preview coverage is insufficient. Only successful fits
seed warm starts. Convergence does not establish physical model adequacy.

Reconfiguration creates a revision, clears warm starts, trend history, and displayed fits.
For the same real source, the ingestion cursor is preserved; changes to the source restart
reading. The next observations use the new model. Pending old-revision work is cancelled or
recorded as cancelled, and revisioned configuration snapshots remain in exports. Closing a
session also records cancellation for every accepted completed scan still waiting or running.
Invalid configurations or export-path preflight failures leave the existing session running.
Pause stops ingestion;
already queued fits finish. Resume continues from the same source position.

Exports default to `outputs/<session-id>/`: `config-<revision>.json`, append-only
`results.jsonl` (including configuration, source identity, scan identity, timing, and results),
and a long-form `parameters.csv`. Empty `output_dir` disables export. Histories in the browser
are limited to 200 updates; persisted results remain available for replay. Source files are
authoritative raw data and are never rewritten. An export failure is shown in session notices.

## Local HTTP and CLI

- `GET /v1/models`: model definitions and default configuration.
- `GET /v1/state`: current revision, data, latest result, last success, bounded history,
  queue depth, source backlog, acquisition notice, and export path.
- `GET /v1/events`: SSE `state` events with the same state shape, approximately every 500 ms.
- `POST /v1/config`: replace configuration; returns revision.
- `POST /v1/control`: `{ "action": "pause" }` or `resume`.
- `POST /v1/suggest`: `{ "model": ... }`; returns suggested model, without applying it.

Mutation errors return HTTP 400 with `error`. Cross-origin mutations return 403. CLI servers
bind to 127.0.0.1; if the requested port is occupied they print an available port. SSE is for
local monitoring; data and plotting assets do not require external services.

Commands: `wavesfit demo`, `wavesfit serve --config preset.json`,
`wavesfit fit spectrum.csv --config preset.json --output result.json`.
Go uses the same subcommands with executable `wavesfit-go`. Batch exit codes: 0 success,
2 diagnostic nonconvergence, 1 invalid input or execution failure. Both support `--version`.
