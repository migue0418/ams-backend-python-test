"""Polls `docker-compose logs` until the pipeline finishes draining a load-test
run, then writes the full raw logs plus a summary.json with the time series.

Usage: python extract.py "<label>" <output_dir>
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

POLL_INTERVAL_SECONDS = 20


def docker_logs(service: str) -> str:
    result = subprocess.run(
        ["docker-compose", "logs", service],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout + result.stderr


def count(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: extract.py <label> <output_dir>", file=sys.stderr)
        raise SystemExit(1)

    label, output_dir = sys.argv[1], Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = []
    start = time.monotonic()
    app_log = provider_log = ""

    while True:
        app_log = docker_logs("app")
        provider_log = docker_logs("provider")

        total = count(app_log, r"POST /v1/requests HTTP")
        sent = count(provider_log, r"200 Success")
        failed = count(app_log, r"failed to deliver request")
        rate_limited = count(provider_log, r"429 Rate Limit")
        injected_500 = count(provider_log, r"500 Random Failure")
        done = sent + failed
        elapsed = round(time.monotonic() - start)

        sample = {
            "t": elapsed,
            "total": total,
            "sent": sent,
            "failed": failed,
            "rate_limited_429": rate_limited,
            "injected_500": injected_500,
        }
        samples.append(sample)
        print(
            f"t+{elapsed}s total={total} sent={sent} failed={failed} "
            f"done={done}/{total} (429={rate_limited} 500={injected_500})",
        )

        if total > 0 and done >= total:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    (output_dir / "provider.log").write_text(provider_log, encoding="utf-8")
    (output_dir / "app.log").write_text(app_log, encoding="utf-8")

    final = samples[-1]
    summary = {
        "label": label,
        "total_notifications": final["total"],
        "drain_seconds": final["t"],
        "final": {
            "sent": final["sent"],
            "failed": final["failed"],
            "rate_limited_429": final["rate_limited_429"],
            "injected_500": final["injected_500"],
        },
        "samples": samples,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {output_dir}/summary.json, provider.log, app.log")


if __name__ == "__main__":
    main()
