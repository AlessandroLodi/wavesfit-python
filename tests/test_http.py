import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from wavesfit.config import default_config, validate_config
from wavesfit.server import create_server


def test_http_dashboard_config_sse_and_origin():
    c = default_config()
    c["output_dir"] = ""
    server = create_server(c, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for path in ["/", "/app.js", "/style.css", "/v1/state", "/v1/models"]:
            with urlopen(base + path, timeout=3) as r:
                assert r.status == 200 and len(r.read()) > 10
        with urlopen(base + "/v1/events", timeout=3) as r:
            assert r.readline().strip() == b"event: state"
            assert (
                json.loads(r.readline().removeprefix(b"data: "))["schema_version"]
                == "1.0"
            )
        req = Request(
            base + "/v1/config",
            json.dumps(c).encode(),
            {"Content-Type": "application/json"},
        )
        assert json.load(urlopen(req))["revision"] == 2
        req = Request(
            base + "/v1/control",
            b'{"action":"pause"}',
            {"Origin": "https://example.com"},
        )
        with pytest.raises(HTTPError) as e:
            urlopen(req)
        assert e.value.code == 403
        req = Request(
            base + "/v1/control",
            b'{"action":"pause"}',
            {"Content-Type": "application/json"},
        )
        assert json.load(urlopen(req))["paused"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_invalid_configuration():
    for key, value in [
        ("queue_size", 0),
        ("schema_version", "9"),
        ("cadence_seconds", 0),
    ]:
        c = default_config()
        c[key] = value
        with pytest.raises(ValueError):
            validate_config(c)
