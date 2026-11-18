import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_VERSIONS = {
    "backports-zstd": "1.8.0",
    "blinker": "1.9.0",
    "brotli": "1.2.1",
    "click": "8.5.1",
    "flask": "3.1.3",
    "flask-compress": "1.26",
    "gunicorn": "26.2.0",
    "itsdangerous": "2.2.0",
    "jinja2": "3.1.6",
    "markupsafe": "3.0.4",
    "werkzeug": "3.1.9",
}
DEV_EXTRA = {
    "iniconfig": "2.3.1",
    "packaging": "26.3",
    "pluggy": "1.7.0",
    "pygments": "2.21.0",
    "pytest": "9.2.0",
}


def parse_lock(path: Path):
    packages = {}
    buffer = []

    def flush():
        if not buffer:
            return
        joined = " ".join(part.strip().removesuffix("\\").strip() for part in buffer)
        buffer.clear()
        if "==" not in joined or joined.lstrip().startswith("#"):
            return
        name, rest = joined.split("==", 1)
        version = rest.split()[0]
        hashes = [token.split("=", 1)[1] for token in rest.split() if token.startswith("--hash=")]
        packages[name.lower()] = {"version": version, "hashes": hashes}

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            flush()
            continue
        buffer.append(line)
        if not stripped.endswith("\\"):
            flush()
    flush()
    return packages


def test_hashed_locks_match_the_already_resolved_ci_set():
    runtime = parse_lock(ROOT / "requirements.txt")
    dev = parse_lock(ROOT / "requirements-dev.txt")
    assert set(runtime) == set(RUNTIME_VERSIONS)
    assert set(dev) == set(RUNTIME_VERSIONS) | set(DEV_EXTRA)
    for name, version in {**RUNTIME_VERSIONS, **DEV_EXTRA}.items():
        locked = dev[name]
        assert locked["version"] == version
        assert locked["hashes"], name
        assert all(item.startswith("sha256:") and len(item) == 7 + 64 for item in locked["hashes"])
        if name in runtime:
            assert runtime[name]["version"] == version
    for path in (ROOT / "requirements.txt", ROOT / "requirements-dev.txt"):
        header = path.read_text(encoding="utf-8").splitlines()[4]
        assert "pip-compile --generate-hashes" in header
        assert "openbabel" not in path.read_text(encoding="utf-8").lower()


def test_direct_inputs_do_not_pin_openbabel_or_float_ranges():
    runtime_in = [
        line.strip()
        for line in (ROOT / "requirements.in").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    dev_in = [
        line.strip()
        for line in (ROOT / "requirements-dev.in").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert runtime_in == ["Flask==3.1.3", "Flask-Compress==1.26", "gunicorn==26.2.0"]
    assert dev_in == ["-r requirements.in", "pytest==9.2.0"]
    combined = "\n".join(runtime_in + dev_in).lower()
    assert "openbabel" not in combined
    assert ">=" not in combined


def test_dependabot_is_narrow_and_does_not_disable_updates():
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert text.startswith("version: 2\n")
    assert text.count('package-ecosystem: pip') == 1
    assert text.count('package-ecosystem: github-actions') == 1
    assert "interval: weekly" in text
    assert "interval: daily" not in text
    assert "open-pull-requests-limit: 2" in text
    assert "open-pull-requests-limit: 1" in text
    assert 'directory: "/"' in text
    assert "openbabel" not in text.lower()


def test_ci_installs_the_hashed_dev_lock():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python -m pip install --require-hashes -r requirements-dev.txt" in text
    assert "pip install -r requirements.txt -r requirements-dev.txt" not in text
    assert "cache-dependency-path:" in text
    assert "requirements-dev.txt" in text
    assert 'python-version: "3.12"' in text


def _cron_fields(workflow: str):
    crons = re.findall(r'cron:\s*"([^"]+)"', workflow)
    assert crons
    parsed = []
    for cron in crons:
        fields = cron.split()
        assert len(fields) == 5, cron
        minute, hour, day, month, weekday = fields
        assert minute not in {"*", "0"}
        assert not minute.startswith("*/")
        minutes = [int(part) for part in minute.split(",")]
        assert all(1 <= value <= 59 for value in minutes)
        assert day == "*" and month == "*" and weekday == "*"
        parsed.append((cron, minutes, hour))
    return parsed


def test_uptime_workflow_is_secondary_best_effort():
    text = (ROOT / ".github" / "workflows" / "uptime.yml").read_text(encoding="utf-8")
    assert "*/15 * * * *" not in text
    crons = _cron_fields(text)
    assert [item[0] for item in crons] == ["17 */3 * * *", "47 1,7,13,19 * * *"]
    assert "workflow_dispatch:" in text
    assert "group: external-uptime" in text
    assert "cancel-in-progress: false" in text
    assert "contents: read" in text
    assert "persist-credentials: false" in text
    assert "secrets.FEISHU_WEBHOOK" in text
    assert "secrets.FEISHU_WEBHOOK_SECRET" in text
    assert "FEISHU_APP_SECRET" not in text
    assert "CLOUDFLARE" not in text
    assert "deploy/external_uptime.py check" in text
    assert "deploy/external_uptime.py notify" in text
    assert "if: failure()" in text
    assert "timeout-minutes: 5" in text
    assert "seqchem-uptime" in text
    # The failure alert stays on the existing custom-bot secrets; no second channel.
    assert text.count("secrets.") == 2
