"""Record source provenance without distributing private paths or experiment data."""

import argparse
import hashlib
import json
import re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("source", type=Path)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
mapping = {
    "AsymGauss.ipf": ("v0.1.0", "asymmetric_gaussian"),
    "StepGauss.ipf": ("v0.1.0", "gaussian_step"),
    "DoniachSunjic.ipf": ("v0.1.0", "ds"),
    "DoniachSunjicDoublet.ipf": ("v0.1.0", "ds_doublet"),
    "VoigtFit_singlets.ipf": ("v0.1.0", "voigt"),
    "VoigtFit_doublets.ipf": ("v0.1.0", "voigt_doublet"),
    "NEXAFS_fits_LP_tab.ipf": ("v0.1.0", "nexafs model and dashboard"),
    "linear_background_samehorizscale.ipf": ("v0.1.0", "linear background"),
    "exponential_background.ipf": (
        "v0.1.0",
        "explicit-curvature exponential background",
    ),
    "shirley_background_samehorizscale.ipf": ("v0.1.0", "iterative Shirley background"),
    "tougaard_background_samehorizscale.ipf": (
        "v0.1.0",
        "physical-axis Tougaard background",
    ),
    "Photoemission_singlets_LP.ipf": (
        "v0.1.0",
        "Voigt model, named parameters, bounds, dashboard",
    ),
    "Photoemission_doublets_LP.ipf": (
        "v0.1.0",
        "Voigt doublets, named parameters, bounds, dashboard",
    ),
    "Photoemission_DoniachSunjic_singlets_LP.ipf": (
        "v0.1.0",
        "DS model, named parameters, bounds, dashboard",
    ),
    "Photoemission_DonjachSunjic_doublets_LP.ipf": (
        "v0.1.0",
        "DS doublets, named parameters, bounds, dashboard",
    ),
    "doublets from fit.ipf": (
        "v0.1.0",
        "evaluate_components and dashboard doublet display",
    ),
    "APE dichr every point load.ipf": (
        "follow-up",
        "APE dichroism reader and normalization",
    ),
    "APE hyst load.ipf": ("follow-up", "APE hysteresis reader and normalization"),
    "BL7A hyst load.ipf": ("follow-up", "BL7A paired pre-edge/edge reader"),
    "BearDataNew.ipf": (
        "follow-up",
        "BEAR multi-scan/dark/current readers and scaling",
    ),
    "BearDataPhotonScan.ipf": ("follow-up", "BEAR photon scan reader"),
    "XPS_G6_Data.ipf": ("follow-up", "XPS G6 reader"),
    "XPS_G6_Data_binding energy.ipf": ("follow-up", "XPS G6 binding-energy conversion"),
    "betterhilbert.ipf": ("follow-up", "odd/even extension and Hilbert transforms"),
    "kkimg2real.ipf": ("follow-up", "Kramers–Kronig transform with explicit alpha"),
    "subtract satellites.ipf": ("follow-up", "direct satellite correction"),
    "subtract satellites 2.ipf": ("follow-up", "recursive satellite correction"),
    "smooth part of spectrum.ipf": (
        "follow-up",
        "regional Hill-curve replacement and smoothing",
    ),
    "SaveAllActiveGraphs.ipf": (
        "follow-up",
        "graph export without hardcoded local paths",
    ),
}
inventory = []
for f in sorted(a.source.glob("*.ipf")):
    raw = f.read_bytes()
    text = raw.decode("mac_roman").replace("\r\n", "\n").replace("\r", "\n")
    release, target = mapping[f.name]
    routines = [
        line.strip()
        for line in text.splitlines()
        if re.match(r"^\s*(?:function(?:/\w+)?|macro|proc)\b", line, re.IGNORECASE)
    ]
    inventory.append(
        {
            "file": f.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "lines": len(text.splitlines()),
            "routines": routines,
            "release": release,
            "replacement": target,
        }
    )
if len(inventory) != 29:
    raise ValueError(f"Expected 29 source scripts, found {len(inventory)}")
(root / "shared/igor-inventory.json").write_text(
    json.dumps(
        {
            "source_format": "Igor Pro .ipf",
            "original_author": "not reliably identified in supplied headers",
            "files": inventory,
        },
        indent=2,
    )
    + "\n"
)
rows = [
    "# Igor migration inventory",
    "",
    f"All {len(inventory)} supplied scripts are accounted for. Byte hashes and routine signatures are in `shared/igor-inventory.json`.",
    "",
    "| Source procedure | Availability | Replacement / follow-up |",
    "|---|---|---|",
]
rows += [f"| {i['file']} | {i['release']} | {i['replacement']} |" for i in inventory]
rows += [
    "",
    "The GUI macros are replaced by reusable APIs and the common dashboard. Numerical changes are explained in NUMERICS.md.",
    "Legacy loaders are deliberately not advertised as supported by the generic CSV/TSV reader.",
    "The source Kramers–Kronig implementation forces alpha=0 and omits an upper integration endpoint in an inner loop; these are documented follow-up corrections, not v0.1.0 capabilities.",
    "The source Hilbert helper indexes x[numpnts(x)] rather than the final valid point. The deferred port will validate interpolation boundaries explicitly.",
    "BEAR references an additional photon-energy/time division procedure that is not present in the supplied collection; that feature needs its own specification and fixtures.",
    "",
]
(root / "docs/IGOR_MIGRATION.md").write_text("\n".join(rows))
