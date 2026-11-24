#!/usr/bin/env python3
"""Best-effort external uptime probe for GitHub Actions.

The Cloudflare Worker ``seqchem-uptime`` and the on-host cron are the primary
checks. This script is only the secondary probe. It has no default URLs and
no default webhook, so tests and local runs cannot reach production or Feishu
unless every target is passed explicitly.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Honest identity for this secondary probe. It replaces urllib's default
# Python-urllib token, which Cloudflare Browser Integrity Check blocks.
# It is not a browser User-Agent.
MONITOR_USER_AGENT = "SeqChem-Uptime/1.0 (GitHub Actions secondary uptime probe)"


def _probe_headers(accept: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"User-Agent": MONITOR_USER_AGENT, "Accept": accept}
    if extra:
        headers.update(extra)
    return headers


def feishu_sign(timestamp: str, secret: str) -> str:
    """Feishu custom-bot signature: HMAC-SHA256 of an empty message.

    The key is ``timestamp + newline + secret``.
    """
    key = f"{timestamp}\n{secret}".encode()
    digest = hmac.new(key, b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _request(url: str, data: bytes | None, headers: dict[str, str], timeout: float):
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return exc.code, body


def _health_error(name: str, status: int, body: bytes) -> str | None:
    if status != 200:
        return f"{name} HTTP {status}"
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return f"{name} payload is not JSON"
    formats = payload.get("formats", 0) if isinstance(payload, dict) else 0
    formats_ok = isinstance(formats, (int, float)) and not isinstance(formats, bool) and formats > 0
    if not isinstance(payload, dict) or payload.get("ok") is not True or not formats_ok:
        return f"{name} payload invalid"
    return None


def run_checks(site: str, site_health: str, api_health: str, convert: str, timeout: float) -> list[str]:
    errors: list[str] = []
    try:
        status, _body = _request(site, None, _probe_headers("text/html"), timeout)
        if status != 200:
            errors.append(f"site HTTP {status}")
        else:
            print(f"site {status}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"site: {exc.__class__.__name__}")

    for name, url in (("site /health", site_health), ("api /health", api_health)):
        try:
            status, body = _request(url, None, _probe_headers("application/json"), timeout)
            error = _health_error(name, status, body)
            if error:
                errors.append(error)
            else:
                print(f"{name} {status}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{name}: {exc.__class__.__name__}")

    payload = json.dumps({"from": "smi", "to": "inchi", "data": "CCO"}).encode()
    try:
        status, body = _request(
            convert,
            payload,
            _probe_headers("application/json", {"Content-Type": "application/json"}),
            timeout,
        )
        if status != 200:
            errors.append(f"api convert HTTP {status}")
        else:
            try:
                parsed = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
            if not isinstance(parsed, dict) or parsed.get("ok") is not True:
                errors.append("api convert payload invalid")
            else:
                print(f"api convert {status}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"api convert: {exc.__class__.__name__}")
    return errors


def build_feishu_payload(text: str, secret: str, timestamp: str | None = None) -> dict:
    payload: dict = {"msg_type": "text", "content": {"text": text}}
    if secret:
        stamp = timestamp if timestamp is not None else str(int(time.time()))
        payload["timestamp"] = stamp
        payload["sign"] = feishu_sign(stamp, secret)
    return payload


def notify(webhook: str, secret: str, text: str, timeout: float) -> int:
    if not webhook:
        print("FEISHU_WEBHOOK is not configured; relying on GitHub Actions failure notifications.")
        return 0
    payload = build_feishu_payload(text, secret)
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", "replace")
        status = response.status
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        for key in ("StatusCode", "code"):
            if key in parsed and parsed[key] not in (0, "0"):
                print(f"feishu notify rejected {key}={parsed[key]}", file=sys.stderr)
                return 1
    print(f"feishu notify HTTP {status}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Secondary SeqChem uptime probe")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Probe explicitly provided URLs")
    check.add_argument("--site", required=True)
    check.add_argument("--site-health", required=True)
    check.add_argument("--api-health", required=True)
    check.add_argument("--convert", required=True)
    check.add_argument("--timeout", type=float, default=20)

    alert = sub.add_parser("notify", help="POST a failure text to a Feishu custom-bot webhook")
    alert.add_argument("--text", required=True)
    alert.add_argument("--webhook", default=os.environ.get("FEISHU_WEBHOOK", ""))
    alert.add_argument("--timeout", type=float, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "check":
        errors = run_checks(args.site, args.site_health, args.api_health, args.convert, args.timeout)
        if errors:
            print("uptime check failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        return 0
    secret = os.environ.get("FEISHU_WEBHOOK_SECRET", "")
    return notify(args.webhook, secret, args.text, args.timeout)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as exc:
        print(f"notify request failed: {exc.__class__.__name__}", file=sys.stderr)
        sys.exit(1)
