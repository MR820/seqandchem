#!/bin/bash
# SeqChem uptime check -> Feishu alert on state change / hourly reminder.
# Usage: seqchem-uptime.sh [url]   |   seqchem-uptime.sh --test
set -uo pipefail

source /opt/seqchem-monitor/feishu.env

STATE=/var/lib/seqchem-uptime.state
URL="${1:-https://seqandchem.com/}"
API_URL="${API_URL:-https://api.seqandchem.com/health}"
ALERT_EVERY=3600   # repeat while still down: once per hour

log() { echo "$(date '+%F %T') $*"; }

feishu_token() {
    curl -sS -m 15 -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
        -H "Content-Type: application/json" \
        -d "{\"app_id\":\"${FEISHU_APP_ID}\",\"app_secret\":\"${FEISHU_APP_SECRET}\"}" \
        | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tenant_access_token",""))'
}

send_feishu() {  # $1 = text
    if [ "${DRY_RUN:-}" = "1" ]; then
        log "DRY_RUN would send: $1"
        return 0
    fi
    local token body
    token=$(feishu_token)
    [ -z "$token" ] && { log "FEISHU token failed"; return 1; }
    body=$(mktemp)
    python3 - "$body" "$FEISHU_OPEN_ID" "$1" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump({"receive_id": sys.argv[2], "msg_type": "text",
               "content": json.dumps({"text": sys.argv[3]}, ensure_ascii=False)}, fh, ensure_ascii=False)
PY
    curl -sS -m 20 -X POST "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id" \
        -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
        --data-binary "@$body" \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print("feishu:",d.get("msg"),d.get("code"))'
    rm -f "$body"
}

if [ "${1:-}" = "--test" ]; then
    send_feishu "✅ SeqChem 告警链路测试

这是一条测试消息，说明服务器可以主动推送到你的飞书。
监控项：主站 https://seqandchem.com/ + api.seqandchem.com/health，每 5 分钟检查一次。"
    exit $?
fi

exec 9>/var/lock/seqchem-uptime.lock
flock -n 9 || exit 0

prev_ts=0
prev_status=ok
if [ -f "$STATE" ]; then
    read -r prev_ts prev_status < "$STATE" || true
fi

probe() {
    curl -sS -o /dev/null -w '%{http_code} %{time_total}' -m 15 "$1" 2>/dev/null
}
check() {
    local out code rt
    out=$(probe "$1") || out="000 0"
    code=${out%% *}; rt=${out##* }
    if [ "$code" != "200" ]; then
        sleep 2
        out=$(probe "$1") || out="000 0"
        code=${out%% *}; rt=${out##* }
    fi
    printf '%s %s\n' "$code" "$rt"
}
read -r code rt < <(check "$URL")
read -r api_code api_rt < <(check "$API_URL")
svc_app=$(systemctl is-active chemtools 2>/dev/null || echo inactive)
svc_web=$(systemctl is-active nginx 2>/dev/null || echo inactive)
svc_gc=$(systemctl is-active goatcounter 2>/dev/null || echo inactive)
now=$(date +%s)

if [ "$code" = "200" ] && [ "$api_code" = "200" ] && [ "$svc_app" = "active" ] && [ "$svc_web" = "active" ] && [ "$svc_gc" = "active" ]; then
    if [ "$prev_status" = "fail" ]; then
        send_feishu "✅ SeqChem 已恢复

主站: $URL → $code (${rt}s)
API:  $API_URL → $api_code (${api_rt}s)
服务: chemtools=$svc_app nginx=$svc_web goatcounter=$svc_gc
时间: $(date '+%F %T %Z')"
        echo "$now ok" > "$STATE"
        log "RECOVERED main=$code api=$api_code"
    else
        [ "$prev_status" != "ok" ] && echo "$now ok" > "$STATE"
        log "OK main=$code api=$api_code rt=${rt}s/${api_rt}s"
    fi
    exit 0
fi

log "FAIL main=$code api=$api_code app=$svc_app web=$svc_web gc=$svc_gc"
if [ "$prev_status" != "fail" ] || [ $((now - prev_ts)) -ge "$ALERT_EVERY" ]; then
    send_feishu "🚨 SeqChem 告警

主站: $URL → $code (${rt}s)
API:  $API_URL → $api_code (${api_rt}s)
服务: chemtools=$svc_app nginx=$svc_web goatcounter=$svc_gc
时间: $(date '+%F %T %Z')
将每 5 分钟重试，1 小时提醒一次。"
    echo "$now fail" > "$STATE"
fi
exit 1
