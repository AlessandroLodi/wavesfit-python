"""Bounded completion queue, coalesced previews, and append-only result exports."""

import csv
import json
import queue
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .acquisition import make_source
from .config import validate_config
from .fitting import fit
from .models import Model, has_coverage


class StreamingSession:
    def __init__(self, config, *, source=None):
        self.lock = threading.RLock()
        self.configure_lock = threading.RLock()
        self.revision = 0
        self.sequence = 0
        self.history = deque(maxlen=200)
        self.latest = None
        self.last_success = None
        self.latest_data = None
        self.notice = ""
        self.paused = False
        self.closed = True
        self.stop_event = threading.Event()
        self.threads = []
        self.source = source
        self._provided_source = source
        self.session_id = uuid.uuid4().hex[:12]
        self.configure(config)

    def configure(self, config):
        with self.configure_lock:
            self._configure(config)

    def _configure(self, config):
        config = validate_config(config)
        output = (
            Path(config["output_dir"]) / self.session_id
            if config["output_dir"]
            else None
        )
        if output:
            output.mkdir(parents=True, exist_ok=True)
            (output / f"config-{self.revision + 1}.json").write_text(
                json.dumps(config, indent=2) + "\n"
            )
        old_config = getattr(self, "config", None)
        old_source = self.source
        self.close()
        with self.lock:
            self.config = config
            self.revision += 1
            self.preview = None
            self.warm = None
            self.last_success = None
            self.latest = None
            self.latest_data = None
            self.history.clear()
            self.queue = queue.Queue(config["queue_size"])
            self.stop_event = threading.Event()
            self.closed = False
            self.source = (
                old_source
                if old_config
                and old_config["source"] == config["source"]
                and config["source"]["mode"] != "demo"
                else (self._provided_source or make_source(config))
            )
            self.notice = "Waiting for acquisition"
            self.paused = False
            self.output = output
            revision = self.revision
            stop = self.stop_event
        self.threads = [
            threading.Thread(target=self._acquire, args=(revision, stop), daemon=True),
            threading.Thread(target=self._work, args=(revision, stop), daemon=True),
        ]
        for t in self.threads:
            t.start()

    def close(self):
        with self.configure_lock:
            self.closed = True
            self.stop_event.set()
            for t in self.threads:
                t.join()
            while hasattr(self, "queue"):
                try:
                    scan = self.queue.get_nowait()
                except queue.Empty:
                    break
                record = self._record(scan, self.revision)
                record.update(
                    status="cancelled",
                    result=None,
                    error="Session closed or reconfigured before fitting",
                )
                self._publish(record, scan)

    def _record(self, s, revision):
        return {
            "schema_version": "1.0",
            "version": __version__,
            "session_id": self.session_id,
            "revision": revision,
            "scan_id": s.scan_id,
            "complete": s.complete,
            "acquired_at": s.acquired_at,
            "source": s.source,
            "config": self.config,
            "processed_at": time.time(),
            "lag_seconds": time.time() - s.acquired_at,
        }

    def _acquire(self, revision, stop):
        last = 0.0
        while not stop.is_set():
            if self.paused or self.queue.full():
                stop.wait(0.03)
                continue
            try:
                s = self.source.poll()
                with self.lock:
                    if revision != self.revision:
                        return
                    if getattr(self.source, "notice", ""):
                        self.notice = self.source.notice
                if s is not None:
                    with self.lock:
                        self.latest_data = asdict(s)
                    if s.complete or s.error:
                        self.queue.put(s)
                        with self.lock:
                            if self.preview and self.preview.scan_id == s.scan_id:
                                self.preview = None
                    elif time.monotonic() - last >= self.config["cadence_seconds"]:
                        with self.lock:
                            self.preview = s
                        last = time.monotonic()
            except (OSError, ValueError) as e:
                with self.lock:
                    self.notice = str(e)
            stop.wait(0.025)

    def _work(self, revision, stop):
        while not stop.is_set():
            try:
                s = self.queue.get_nowait()
            except queue.Empty:
                with self.lock:
                    s = self.preview
                    self.preview = None
                if s is None:
                    stop.wait(0.025)
                    continue
            record = self._record(s, revision)
            try:
                if s.error:
                    raise ValueError(s.error)
                model = Model.from_dict(self.config["model"])
                if not s.complete and not has_coverage(model, s.x, self.warm):
                    record.update(
                        result=None,
                        status="awaiting_coverage",
                        error="Waiting for data on both sides of the configured peaks",
                    )
                else:
                    result = fit(
                        s.x,
                        s.y,
                        model,
                        sigma=s.sigma,
                        background_config=self.config["background"],
                        initial=self.warm,
                        cancel=stop.is_set,
                        **self.config["fit"],
                    )
                    record["result"] = result.to_dict()
                    record["status"] = result.status
            except (ValueError, ArithmeticError) as e:
                record.update(status="invalid", error=str(e), result=None)
            with self.lock:
                if revision != self.revision:
                    return
                if stop.is_set():
                    record.update(
                        status="cancelled",
                        result=None,
                        error="Session closed or reconfigured during fitting",
                    )
                self._publish(record, s)

    def _publish(self, record, s):
        with self.lock:
            self.sequence += 1
            record["sequence"] = self.sequence
            record["processed_at"] = time.time()
            record["lag_seconds"] = time.time() - s.acquired_at
            self.latest = record
            if record["result"] and record["result"]["success"]:
                self.warm = record["result"]["parameters"]
                self.last_success = record
            self.history.append(
                {
                    "scan_id": s.scan_id,
                    "complete": s.complete,
                    "status": record["status"],
                    "parameters": record["result"]["parameters"]
                    if record["result"]
                    else {},
                    "sequence": self.sequence,
                }
            )
            if self.output:
                try:
                    self._export(record)
                except OSError as e:
                    self.notice = f"Export failed: {e}"

    def _export(self, record):
        with (self.output / "results.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, allow_nan=False, separators=(",", ":")) + "\n")
        path = self.output / "parameters.csv"
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(
                    [
                        "sequence",
                        "scan_id",
                        "revision",
                        "complete",
                        "status",
                        "parameter",
                        "value",
                        "stderr",
                    ]
                )
            r = record["result"]
            for k, v in r["parameters"].items() if r else [("", "")]:
                w.writerow(
                    [
                        record["sequence"],
                        record["scan_id"],
                        record["revision"],
                        record["complete"],
                        record["status"],
                        k,
                        v,
                        r["stderr"].get(k) if r else "",
                    ]
                )

    def state(self):
        with self.lock:
            return {
                "schema_version": "1.0",
                "version": __version__,
                "revision": self.revision,
                "sequence": self.sequence,
                "config": self.config,
                "latest": self.latest,
                "last_success": self.last_success,
                "data": self.latest_data,
                "history": list(self.history),
                "queue_depth": self.queue.qsize(),
                "source_backlog": getattr(self.source, "backlog", 0),
                "paused": self.paused,
                "notice": self.notice,
                "output_dir": str(self.output) if self.output else "",
            }
