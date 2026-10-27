import argparse
import json
import signal
import sys
from pathlib import Path

from . import __version__
from .acquisition import DirectorySource
from .config import default_config, load_config
from .fitting import fit
from .models import Model
from .server import create_server


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Spectroscopy models and live file-stream fitting"
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("demo", "serve"):
        p = sub.add_parser(name)
        p.add_argument("--config")
        p.add_argument("--port", type=int, default=8765)
        p.add_argument(
            "--output", help="Result directory; an empty string disables exports"
        )
    p = sub.add_parser("fit")
    p.add_argument("input")
    p.add_argument("--config")
    p.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config) if args.config else default_config()
        if args.command == "fit":
            path = Path(args.input).resolve()
            source = dict(
                config["source"],
                mode="directory",
                path=str(path.parent),
                glob=path.name,
            )
            source.pop("done_suffix", None)
            scan = DirectorySource(source).poll()
            if scan is None or scan.error:
                raise ValueError(scan.error if scan else "Input file not found")
            result = fit(
                scan.x,
                scan.y,
                Model.from_dict(config["model"]),
                sigma=scan.sigma,
                background_config=config["background"],
                **config["fit"],
            )
            content = json.dumps(result.to_dict(), indent=2, allow_nan=False) + "\n"
            if args.output:
                Path(args.output).write_text(content)
            else:
                sys.stdout.write(content)
            return 0 if result.success else 2
        if args.command == "demo":
            config["source"] = {"mode": "demo", "points": 512, "pattern": "both"}
        if args.output is not None:
            config["output_dir"] = args.output
        server = create_server(config, args.port)
        print(
            f"WavesFit {__version__}: http://127.0.0.1:{server.server_port}", flush=True
        )
        print(
            "Press Ctrl-C to stop. Results: " + server.session.state()["output_dir"],
            flush=True,
        )

        def terminate(signum, frame):
            raise KeyboardInterrupt

        previous = signal.signal(signal.SIGTERM, terminate)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            signal.signal(signal.SIGTERM, previous)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as e:
        print(f"wavesfit: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
