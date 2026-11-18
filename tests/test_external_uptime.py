import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "external_uptime.py"


def load_module():
    spec = importlib.util.spec_from_file_location("external_uptime", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


UPTIME = load_module()


class ProbeServer:
    def __init__(self, handler):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["paths"].append(self.path)
            if self.path == "/down":
                self._send(500, b"no")
                return
            if self.path == "/health-bad":
                self._send(200, b'{"ok": true, "formats": 0}')
                return
            if self.path == "/health":
                self._send(200, b'{"ok": true, "formats": 4}')
                return
            if self.path == "/":
                self._send(200, b"ok")
                return
            self._send(404, b"missing")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            state["posts"].append(json.loads(raw.decode()))
            if self.path == "/convert-bad":
                self._send(200, b'{"ok": false}')
                return
            if self.path == "/convert":
                self._send(200, b'{"ok": true}')
                return
            self._send(404, b"missing")

        def _send(self, status, body):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    return Handler


def run_cli(args, env=None):
    merged = os.environ.copy()
    merged.pop("FEISHU_WEBHOOK", None)
    merged.pop("FEISHU_WEBHOOK_SECRET", None)
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


def test_script_has_no_production_or_feishu_defaults():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "seqandchem.com" not in text
    assert "open.feishu.cn" not in text
    assert "FEISHU_APP_SECRET" not in text
    assert "FEISHU_APP_ID" not in text


def test_check_requires_explicit_urls():
    result = run_cli(["check"])
    assert result.returncode != 0
    assert "seqandchem.com" not in result.stdout + result.stderr


def test_successful_local_probe():
    state = {"paths": [], "posts": []}
    server = ProbeServer(make_handler(state))
    try:
        base = server.base
        result = run_cli(
            [
                "check",
                "--site",
                base + "/",
                "--site-health",
                base + "/health",
                "--api-health",
                base + "/health",
                "--convert",
                base + "/convert",
                "--timeout",
                "2",
            ]
        )
    finally:
        server.close()
    assert result.returncode == 0, result.stderr
    assert state["posts"] == [{"from": "smi", "to": "inchi", "data": "CCO"}]
    assert "api convert 200" in result.stdout


def test_failed_health_and_convert_do_not_pass():
    state = {"paths": [], "posts": []}
    server = ProbeServer(make_handler(state))
    try:
        base = server.base
        bad_health = run_cli(
            [
                "check",
                "--site",
                base + "/",
                "--site-health",
                base + "/health-bad",
                "--api-health",
                base + "/health",
                "--convert",
                base + "/convert",
                "--timeout",
                "2",
            ]
        )
        bad_convert = run_cli(
            [
                "check",
                "--site",
                base + "/",
                "--site-health",
                base + "/health",
                "--api-health",
                base + "/health",
                "--convert",
                base + "/convert-bad",
                "--timeout",
                "2",
            ]
        )
        refused = run_cli(
            [
                "check",
                "--site",
                "http://127.0.0.1:1/",
                "--site-health",
                "http://127.0.0.1:1/health",
                "--api-health",
                "http://127.0.0.1:1/health",
                "--convert",
                "http://127.0.0.1:1/convert",
                "--timeout",
                "1",
            ]
        )
    finally:
        server.close()
    assert bad_health.returncode == 1
    assert "site /health payload invalid" in bad_health.stderr
    assert bad_convert.returncode == 1
    assert "api convert payload invalid" in bad_convert.stderr
    assert refused.returncode == 1
    assert "seqandchem.com" not in refused.stderr


def test_feishu_sign_and_local_notify():
    sign = UPTIME.feishu_sign("1700000000", "test-secret")
    payload = UPTIME.build_feishu_payload("hello", "test-secret", timestamp="1700000000")
    assert payload["sign"] == sign
    assert payload["timestamp"] == "1700000000"
    assert payload["msg_type"] == "text"
    assert "sign" not in UPTIME.build_feishu_payload("hello", "")

    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            captured["body"] = json.loads(self.rfile.read(length).decode())
            captured["path"] = self.path
            body = b'{"StatusCode":0}'
            if self.path == "/reject":
                body = b'{"code":19001}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = ProbeServer(Handler)
    try:
        skipped = run_cli(["notify", "--text", "hello"])
        accepted = run_cli(
            ["notify", "--text", "hello", "--webhook", server.base + "/hook", "--timeout", "2"],
            env={"FEISHU_WEBHOOK_SECRET": "test-secret"},
        )
        accepted_body = dict(captured["body"])
        rejected = run_cli(
            ["notify", "--text", "hello", "--webhook", server.base + "/reject", "--timeout", "2"],
            env={"FEISHU_WEBHOOK_SECRET": "test-secret"},
        )
    finally:
        server.close()

    assert skipped.returncode == 0
    assert "FEISHU_WEBHOOK is not configured" in skipped.stdout
    assert accepted.returncode == 0, accepted.stderr
    assert accepted_body["content"]["text"] == "hello"
    assert accepted_body["sign"] == UPTIME.feishu_sign(accepted_body["timestamp"], "test-secret")
    assert "test-secret" not in accepted.stdout + accepted.stderr
    assert rejected.returncode == 1
    assert "code=19001" in rejected.stderr
