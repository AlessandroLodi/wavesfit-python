import json
import time
from pathlib import Path

import numpy as np

from wavesfit.acquisition import DirectorySource, Spectrum, TailSource
from wavesfit.config import default_config
from wavesfit.streaming import StreamingSession


def wait_until(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for acquisition")


def test_partial_line_pause_boundary_and_truncation(tmp_path):
    p = tmp_path / "live.csv"
    p.write_text("0,1\n1,")
    source = TailSource({"path": str(p), "expected_points": 3})
    s = source.poll()
    assert s.x == [0] and not s.complete
    assert source.poll() is None
    with p.open("a") as f:
        f.write("2\n2,3\n3,4\n")
    s = source.poll()
    assert s.complete and s.x == [0, 1, 2]
    s = source.poll()
    assert not s.complete and s.x == [3]
    p.write_text("0,7\n")
    assert "interrupted" in source.poll().error
    assert source.poll().y == [7]
    replacement = tmp_path / "replace"
    replacement.write_text("8,9\n")
    replacement.replace(p)
    assert "interrupted" in source.poll().error
    assert source.poll().x == [8]


def test_headers_scan_ids_markers_and_poisoned_scan(tmp_path):
    p = tmp_path / "live.csv"
    p.write_text(
        "energy,intensity,scan\n0,1,a\n1,2,a\n0,3,b\n1,4,b\n# end\n# scan_id=c\nbad,row,c\n# end\n"
    )
    source = TailSource(
        {
            "path": str(p),
            "columns": {"x": "energy", "y": "intensity", "scan_id": "scan"},
        }
    )
    a, b, c = source.poll(), source.poll(), source.poll()
    assert a.scan_id == "a" and a.complete and a.y == [1, 2]
    assert b.scan_id == "b" and b.complete and b.y == [3, 4]
    assert c.complete and c.error and c.scan_id == "c"


def test_finalized_directory_done_markers_and_failures(tmp_path):
    (tmp_path / "001.csv").write_text("0,1\n1,2\n")
    (tmp_path / "002.csv").write_text("bad\n")
    (tmp_path / "ignored.part").write_text("0,1\n")
    s = DirectorySource({"path": str(tmp_path), "done_suffix": ".done"})
    assert s.poll() is None
    (tmp_path / "001.csv.done").touch()
    (tmp_path / "002.csv.done").touch()
    assert s.poll().complete
    assert s.poll().error
    assert s.poll() is None


def test_bounded_completion_queue_preserves_all_scans(tmp_path, monkeypatch):
    from wavesfit import streaming

    original = streaming.fit

    def slow(*a, **k):
        time.sleep(0.08)
        return original(*a, **k)

    monkeypatch.setattr(streaming, "fit", slow)
    directory = tmp_path / "input"
    directory.mkdir()
    x = np.linspace(-6, 6, 64)
    for i in range(12):
        np.savetxt(
            directory / f"{i:03}.csv",
            np.column_stack([x, np.full(len(x), 2)]),
            delimiter=",",
        )
    c = default_config()
    c["model"] = {"components": [], "offset": {"value": 2, "fixed": True}}
    c["source"] = {"mode": "directory", "path": str(directory)}
    c["queue_size"] = 2
    c["output_dir"] = str(tmp_path / "out")
    session = StreamingSession(c)
    try:
        wait_until(lambda: len(session.state()["history"]) == 12)
        records = [
            json.loads(line)
            for line in (Path(session.state()["output_dir"]) / "results.jsonl")
            .read_text()
            .splitlines()
        ]
        assert len(records) == 12 and all(r["complete"] for r in records)
        assert [r["scan_id"] for r in records] == [f"{i:03}.csv" for i in range(12)]
        assert session.queue.maxsize == 2
    finally:
        session.close()


def test_coverage_failure_retention_and_reconfiguration(tmp_path):
    class Source:
        backlog = 0
        notice = ""

        def __init__(self):
            self.items = []

        def poll(self):
            return self.items.pop(0) if self.items else None

    source = Source()
    c = default_config()
    c["output_dir"] = ""
    x = np.linspace(-6, 6, 128)
    from wavesfit import Model

    y = Model.from_dict(c["model"]).evaluate(x).tolist()
    source.items = [Spectrum("partial", x[:16].tolist(), y[:16])]
    session = StreamingSession(c, source=source)
    try:
        wait_until(lambda: session.state()["latest"] is not None)
        assert session.state()["latest"]["status"] == "awaiting_coverage"
        assert session.state()["last_success"] is None
        source.items.append(Spectrum("good", x.tolist(), y, complete=True))
        wait_until(lambda: session.state()["last_success"] is not None)
        source.items.append(Spectrum("bad", [1, 1], [2, 3], complete=True))
        wait_until(lambda: session.state()["latest"]["scan_id"] == "bad")
        assert session.state()["latest"]["status"] == "invalid"
        assert session.state()["last_success"]["scan_id"] == "good"
        session.configure(c)
        assert session.state()["revision"] == 2
        assert session.state()["last_success"] is None
    finally:
        session.close()


def test_reconfiguration_accounts_for_cancelled_completed_scans(tmp_path, monkeypatch):
    from wavesfit import streaming

    original = streaming.fit

    def slow(*args, **kwargs):
        time.sleep(0.15)
        return original(*args, **kwargs)

    monkeypatch.setattr(streaming, "fit", slow)
    folder = tmp_path / "in"
    folder.mkdir()
    for i in range(8):
        (folder / f"{i:03}.csv").write_text("0,2\n1,2\n")
    c = default_config()
    c["source"] = {"mode": "directory", "path": str(folder)}
    c["model"] = {"components": [], "offset": {"value": 2, "fixed": True}}
    c["output_dir"] = str(tmp_path / "out")
    c["queue_size"] = 3
    session = StreamingSession(c)
    try:
        wait_until(lambda: session.queue.qsize() >= 2)
        session.configure(c)
        path = Path(session.state()["output_dir"]) / "results.jsonl"
        wait_until(lambda: path.exists() and len(path.read_text().splitlines()) == 8)
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert len({r["scan_id"] for r in records}) == 8
        assert any(r["status"] == "cancelled" for r in records)
        assert all(r["complete"] for r in records)
    finally:
        session.close()


def test_failed_export_preflight_keeps_session_running(tmp_path):
    c = default_config()
    c["output_dir"] = ""
    session = StreamingSession(c)
    occupied = tmp_path / "file"
    occupied.write_text("occupied")
    bad = dict(c, output_dir=str(occupied))
    import pytest

    try:
        with pytest.raises(OSError):
            session.configure(bad)
        assert not session.closed and session.revision == 1
        wait_until(lambda: session.state()["last_success"] is not None)
    finally:
        session.close()
