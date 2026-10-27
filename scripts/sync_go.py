"""Copy canonical contract/dashboard files to Go and record content digests."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--target", type=Path, required=True)
p.add_argument("--check", action="store_true")
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
paths = {
    f"static/{f.name}": f
    for f in (root / "src/wavesfit/static").iterdir()
    if f.is_file()
}
paths.update(
    {
        str(f.relative_to(root)): f
        for folder in ["shared", "docs", "examples"]
        for f in (root / folder).glob("*")
        if f.is_file()
    }
)
paths.update(
    {name: root / name for name in ["LICENSE", "NOTICE", "THIRD_PARTY_NOTICES"]}
)
manifest = {
    "canonical_repository": "AlessandroLodi/wavesfit-python",
    "contract_version": "1.0",
    "release": "0.1.0",
    "files": {},
}
for name, source in sorted(paths.items()):
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest["files"][name] = digest
    target = a.target / name
    if a.check:
        if (
            not target.exists()
            or hashlib.sha256(target.read_bytes()).hexdigest() != digest
        ):
            raise SystemExit("Out of sync: " + name)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
if not a.check:
    (a.target / "CANONICAL.json").write_text(json.dumps(manifest, indent=2) + "\n")
else:
    if json.loads((a.target / "CANONICAL.json").read_text()) != manifest:
        raise SystemExit("Out of sync: CANONICAL.json")
print(
    f"{len(paths)} canonical files synchronized"
    if not a.check
    else "Canonical files match"
)
