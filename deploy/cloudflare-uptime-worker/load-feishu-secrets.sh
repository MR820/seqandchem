#!/bin/bash
# Pull the three Feishu credentials from the production server into 0600 files
# under this directory. The values are never printed.
set -euo pipefail
umask 077
work="$(cd "$(dirname "$0")" && pwd)"

: "${SEQCHEM_HOST:?Set SEQCHEM_HOST to the production host}"
: "${SEQCHEM_SSH_KEY:?Set SEQCHEM_SSH_KEY to the SSH private key path}"

ssh -i "$SEQCHEM_SSH_KEY" -o BatchMode=yes "root@$SEQCHEM_HOST" \
  'cat /opt/seqchem-monitor/feishu.env' > "$work/feishu.env"

python3 - "$work/feishu.env" "$work" <<'PY'
import pathlib, sys
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
env = {}
for line in src.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    env[key.strip()] = value.strip().strip('"').strip("'")
for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_OPEN_ID"):
    if not env.get(key):
        raise SystemExit(f"missing {key} in feishu.env")
    (out / f"secret-{key}").write_text(env[key])
print("loaded Feishu secrets from production server")
PY
rm -f "$work/feishu.env"
