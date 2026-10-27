"""Pull-based acquisition. A poll returns at most one spectrum snapshot.

Completed files must be atomically published or accompanied by a done marker.
Growing files need expected_points, a scan_id column, '# scan_id=...', or '# end'.
"""

import csv
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .models import Model


@dataclass
class Spectrum:
    scan_id: str
    x: list = field(default_factory=list)
    y: list = field(default_factory=list)
    sigma: list | None = None
    complete: bool = False
    acquired_at: float = field(default_factory=time.time)
    source: str = ""
    error: str = ""


class TableParser:
    def __init__(self, config):
        self.config = config
        self.header = None

    def row(self, line):
        delim = self.config.get("delimiter", "auto")
        if delim == "auto":
            delim = "," if "," in line else ("\t" if "\t" in line else "whitespace")
        cells = (
            line.split()
            if delim == "whitespace"
            else next(csv.reader([line], delimiter=delim))
        )
        columns = self.config.get("columns", {"x": 0, "y": 1})
        if self.header is None and (
            self.config.get("header", False)
            or any(isinstance(v, str) for v in columns.values())
        ):
            self.header = [s.strip() for s in cells]
            return None
        result = {}
        for k, col in columns.items():
            i = self.header.index(col) if isinstance(col, str) else col
            value = cells[i].strip()
            result[k] = value if k == "scan_id" else float(value)
            if k != "scan_id" and (
                not math.isfinite(result[k]) or k == "sigma" and result[k] <= 0
            ):
                raise ValueError("Data must be finite and sigma positive")
        return result


class TailSource:
    def __init__(self, config):
        self.config = config
        self.path = Path(config["path"])
        self.offset = 0
        self.identity = None
        self.buffer = b""
        self.parser = TableParser(config)
        self.number = 1
        self.current = None
        self.pending = None
        self.last_count = 0
        self.notice = ""
        self.backlog = 0

    def _new(self, scan_id=None):
        self.current = Spectrum(
            str(scan_id or f"{self.path.name}:{self.number}"),
            source=str(self.path),
            sigma=[] if "sigma" in self.config.get("columns", {}) else None,
        )
        self.number += 1
        self.last_count = 0

    def _finish(self):
        result = self.current
        result.complete = True
        self.current = None
        self.last_count = 0
        return result

    def poll(self):
        stat = self.path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if self.identity is not None and (
            identity != self.identity or stat.st_size < self.offset
        ):
            interrupted = self.current
            self.offset = 0
            self.buffer = b""
            self.parser = TableParser(self.config)
            self.current = None
            self.last_count = 0
            self.identity = identity
            self.notice = "Source rotated or truncated"
            if interrupted is not None and interrupted.x:
                interrupted.error = "Scan interrupted by source rotation/truncation"
                return interrupted
        self.identity = identity
        if self.pending is not None:
            row = self.pending
            self.pending = None
            self._new(row.get("scan_id"))
            self._append(row)
            if self.config.get("expected_points") == len(self.current.x):
                return self._finish()
        if b"\n" not in self.buffer:
            with self.path.open("rb") as f:
                f.seek(self.offset)
                chunk = f.read(65536)
                self.offset += len(chunk)
                self.buffer += chunk
            if len(self.buffer) > 1048576:
                raise ValueError("Input line exceeds 1 MiB")
        while b"\n" in self.buffer:
            raw, self.buffer = self.buffer.split(b"\n", 1)
            try:
                line = raw.decode("utf-8-sig").strip()
            except UnicodeDecodeError as e:
                self._poison(f"Invalid UTF-8: {e}")
                continue
            if not line:
                continue
            if line.startswith("#"):
                if line.startswith("# scan_id="):
                    name = line.split("=", 1)[1].strip()
                    if self.current is not None and (
                        self.current.x or self.current.error
                    ):
                        old = self._finish()
                        self._new(name)
                        return old
                    self._new(name)
                elif (
                    line == "# end"
                    and self.current is not None
                    and (self.current.x or self.current.error)
                ):
                    return self._finish()
                continue
            try:
                row = self.parser.row(line)
            except (ValueError, IndexError, csv.Error) as e:
                self._poison(
                    f"Malformed row near byte {self.offset - len(self.buffer)}: {e}"
                )
                continue
            if row is None:
                continue
            if self.current is None:
                self._new(row.get("scan_id"))
            elif (
                row.get("scan_id") is not None
                and str(row["scan_id"]) != self.current.scan_id
            ):
                old = self._finish()
                self.pending = row
                return old
            self._append(row)
            if self.config.get("expected_points") == len(self.current.x):
                return self._finish()
        if self.current is not None and len(self.current.x) != self.last_count:
            self.last_count = len(self.current.x)
            return Spectrum(
                self.current.scan_id,
                self.current.x.copy(),
                self.current.y.copy(),
                None if self.current.sigma is None else self.current.sigma.copy(),
                False,
                self.current.acquired_at,
                self.current.source,
                self.current.error,
            )
        return None

    def _poison(self, error):
        self.notice = error
        if self.current is None:
            self._new()
        self.current.error = error

    def _append(self, row):
        if len(self.current.x) >= self.config.get("max_points", 1000000):
            raise ValueError(
                "Scan exceeds max_points; configure an explicit scan boundary"
            )
        self.current.x.append(row["x"])
        self.current.y.append(row["y"])
        if self.current.sigma is not None:
            self.current.sigma.append(row["sigma"])


class DirectorySource:
    def __init__(self, config):
        self.config = config
        self.path = Path(config["path"])
        self.done = set()
        self.backlog = 0
        self.notice = ""

    def poll(self):
        if not self.path.is_dir():
            raise FileNotFoundError(f"Not a directory: {self.path}")
        files = sorted(
            p
            for p in self.path.glob(self.config.get("glob", "*.csv"))
            if p.is_file()
            and not p.name.endswith((".part", ".tmp"))
            and (
                not self.config.get("done_suffix")
                or Path(str(p) + self.config["done_suffix"]).exists()
            )
        )
        candidates = []
        for p in files:
            st = p.stat()
            key = (str(p), st.st_ino, st.st_size, st.st_mtime_ns)
            if key not in self.done:
                candidates.append((p, key))
        self.backlog = len(candidates)
        if not candidates:
            return None
        p, key = candidates[0]
        parser = TableParser(self.config)
        result = Spectrum(
            p.name,
            complete=True,
            source=str(p),
            sigma=[] if "sigma" in self.config.get("columns", {}) else None,
        )
        try:
            with p.open(encoding="utf-8-sig") as f:
                for line in f:
                    if len(line) > 1048576:
                        raise ValueError("Input line exceeds 1 MiB")
                    if not line.strip() or line.lstrip().startswith("#"):
                        continue
                    row = parser.row(line)
                    if row is None:
                        continue
                    if len(result.x) >= self.config.get("max_points", 1000000):
                        raise ValueError("File exceeds max_points")
                    result.x.append(row["x"])
                    result.y.append(row["y"])
                    if result.sigma is not None:
                        result.sigma.append(row["sigma"])
            if (
                self.config.get("expected_points") is not None
                and len(result.x) != self.config["expected_points"]
            ):
                raise ValueError("Finalized file has an unexpected point count")
        except (ValueError, IndexError, UnicodeDecodeError, csv.Error) as e:
            result.error = f"Malformed finalized file: {e}"
        st = p.stat()
        if (str(p), st.st_ino, st.st_size, st.st_mtime_ns) != key:
            self.notice = "File changed during read; waiting for finalized publication"
            return None
        self.done.add(key)
        self.backlog -= 1
        return result


class DemoSource:
    def __init__(self, config, model):
        self.config = config
        self.model = Model.from_dict(model)
        self.index = 0
        self.count = 0
        self.next_at = 0.0
        self.backlog = 0
        self.notice = "Simulated acquisition"
        self.current = None

    def poll(self):
        if time.monotonic() < self.next_at:
            return None
        self.next_at = time.monotonic() + 0.08
        n = self.config.get("points", 512)
        if self.current is None:
            x = np.linspace(-6, 6, n)
            values = {k: p.value for k, p in self.model.parameters().items()}
            for k in values:
                if k.endswith(".center"):
                    values[k] += 0.1 * math.sin(self.index * 0.15)
            y = self.model.evaluate(x, values) + np.random.default_rng(
                100 + self.index
            ).normal(0, 0.02, n)
            self.current = Spectrum(
                f"demo:{self.index + 1}", x.tolist(), y.tolist(), source="simulator"
            )
            self.count = 0
            self.index += 1
        pattern = self.config.get("pattern", "both")
        full = pattern == "complete" or pattern == "both" and self.index % 2 == 0
        self.count = n if full else min(n, self.count + max(8, n // 8))
        s = Spectrum(
            self.current.scan_id,
            self.current.x[: self.count],
            self.current.y[: self.count],
            complete=self.count == n,
            source="simulator",
            acquired_at=self.current.acquired_at,
        )
        if s.complete:
            self.current = None
        return s


def make_source(config):
    s = config["source"]
    if s["mode"] == "demo":
        return DemoSource(s, config["model"])
    return TailSource(s) if s["mode"] == "tail" else DirectorySource(s)
