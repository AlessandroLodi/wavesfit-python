# WavesFit v0.1.0

First public release of independent Python and native Go spectroscopy fitting packages.

- Voigt and Doniach–Šunjić singlets/doublets, asymmetric Gaussians, Gaussian steps, and NEXAFS composites.
- Four endpoint-anchored backgrounds, bounded/fixed-parameter fitting, uncertainties and diagnostics.
- Growing file and finalized-directory acquisition, coalesced previews, and completed-scan queues.
- Offline local dashboard with guided parameter editing, residuals, trends, presets, and JSONL/CSV exports.
- Shared schema, numerical fixtures, source inventory, scientific correction notes, and validation suite.

Known limits: generic text tables only; specialized Igor instrument readers and transforms
are deferred. Real hardware integration and direct Igor-output parity have not been validated.
The Go executable requires neither Python nor CGO. Archives are unsigned; platform operating
system download prompts may apply. Python wheels contain original code/assets and use separately
installed NumPy/SciPy. No PyPI publication is required; install the wheel or directly from GitHub.
