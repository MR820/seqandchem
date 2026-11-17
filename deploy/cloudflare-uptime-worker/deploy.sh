#!/bin/bash
# Deploy the SeqChem external uptime Worker.
# Requires a Cloudflare API token with:
#   Account: Workers Scripts (Read+Write), Workers KV Storage (Read+Write)
# and either $work/temp-token (created by the temporary-token step) or
# CLOUDFLARE_WORKERS_TOKEN in ~/.cloudflare-api.env.
set -euo pipefail
umask 077

work="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HOME/.cloudflare-api.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$HOME/.cloudflare-api.env"
  set +a
fi
account="${CLOUDFLARE_ACCOUNT_ID:?Set CLOUDFLARE_ACCOUNT_ID to your Cloudflare account ID}"
script="seqchem-uptime"
namespace_title="seqchem_uptime"
api="https://api.cloudflare.com/client/v4"

if [ -n "${CLOUDFLARE_WORKERS_TOKEN:-}" ]; then
  tok="$CLOUDFLARE_WORKERS_TOKEN"
elif [ -f "$work/temp-token" ]; then
  tok="$(cat "$work/temp-token")"
else
  echo "No Cloudflare token found (set CLOUDFLARE_WORKERS_TOKEN or create $work/temp-token)" >&2
  exit 1
fi

auth=(-H "Authorization: Bearer $tok")

echo "== KV namespace =="
ns="$(curl -sS "${auth[@]}" "$api/accounts/$account/storage/kv/namespaces?per_page=100" \
  | jq -r --arg t "$namespace_title" '[.result[]? | select(.title == $t) | .id][0] // empty')"
if [ -z "$ns" ]; then
  ns="$(curl -sS -X POST "${auth[@]}" -H "Content-Type: application/json" \
    --data "{\"title\":\"$namespace_title\"}" \
    "$api/accounts/$account/storage/kv/namespaces" | jq -r '.result.id // empty')"
  [ -n "$ns" ] || { echo "Failed to create KV namespace" >&2; exit 1; }
  echo "created: $ns"
else
  echo "reusing: $ns"
fi

echo "== metadata =="
jq -n --arg ns "$ns" '{
  main_module: "worker.mjs",
  compatibility_date: "2025-01-01",
  bindings: [{type: "kv_namespace", name: "UPTIME_KV", namespace_id: $ns}]
}' > "$work/metadata.json"
cat "$work/metadata.json"

echo "== upload script =="
curl -sS -X PUT "${auth[@]}" \
  -F "metadata=@$work/metadata.json;type=application/json" \
  -F "worker.mjs=@$work/worker.mjs;type=application/javascript+module" \
  "$api/accounts/$account/workers/scripts/$script" \
  | jq -c '{success, errors, id: .result.id, modified_on: .result.modified_on}'

echo "== secrets =="
for name in FEISHU_APP_ID FEISHU_APP_SECRET FEISHU_OPEN_ID; do
  [ -f "$work/secret-$name" ] || { echo "missing $work/secret-$name" >&2; exit 1; }
  jq -n --arg n "$name" --rawfile t "$work/secret-$name" \
    '{name: $n, text: $t, type: "secret_text"}' > "$work/secret-$name.json"
  curl -sS -X PUT "${auth[@]}" -H "Content-Type: application/json" \
    --data-binary @"$work/secret-$name.json" \
    "$api/accounts/$account/workers/scripts/$script/secrets" \
    | jq -c --arg n "$name" '{name: $n, success, errors}'
  rm -f "$work/secret-$name.json"
done

echo "== schedule =="
curl -sS -X PUT "${auth[@]}" -H "Content-Type: application/json" \
  --data-binary '[{"cron":"*/5 * * * *"}]' \
  "$api/accounts/$account/workers/scripts/$script/schedules" \
  | jq -c '{success, errors, schedules: .result.schedules}'

echo "== verify =="
curl -sS "${auth[@]}" "$api/accounts/$account/workers/scripts" \
  | jq -c --arg s "$script" '{success, errors, script: [(.result // [])[] | select(.id == $s) | {id, modified_on}]}'
curl -sS "${auth[@]}" "$api/accounts/$account/workers/scripts/$script/schedules" \
  | jq -c '{success, errors, schedules: .result.schedules}'
curl -sS "${auth[@]}" "$api/accounts/$account/workers/scripts/$script/secrets" \
  | jq -c '{success, errors, names: [.result[]?.name]}'

echo "== workers.dev =="
sub="$(curl -sS "${auth[@]}" "$api/accounts/$account/workers/subdomain" | jq -r '.result.subdomain // empty')"
if [ -n "$sub" ]; then
  echo "account subdomain: $sub (Worker is cron-only; no public HTTP route)"
else
  echo "workers.dev subdomain not created yet"
fi
