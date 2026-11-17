#!/bin/bash
# Delete the temporary Cloudflare token created for this deployment and
# remove local credential files. The Worker itself stays deployed.
set -euo pipefail
work="$(cd "$(dirname "$0")" && pwd)"
set -a; source ~/.cloudflare-api.env; set +a

if [ -f "$work/temp-token-id" ]; then
  id="$(cat "$work/temp-token-id")"
  echo "deleting temporary token $id"
  curl -sS -X DELETE -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    "https://api.cloudflare.com/client/v4/user/tokens/$id" \
    | jq -c '{success, errors}'
fi
rm -f "$work/temp-token" "$work/temp-token-id" \
  "$work/token-request.json" "$work/token-response.json" \
  "$work/secret-FEISHU_APP_ID" "$work/secret-FEISHU_APP_SECRET" \
  "$work/secret-FEISHU_OPEN_ID" "$work/feishu.env" "$work/metadata.json"
echo "local credential files removed"
