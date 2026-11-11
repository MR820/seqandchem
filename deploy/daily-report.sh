#!/bin/bash
# SeqChem daily health report (yesterday, Asia/Shanghai) -> Feishu
set -euo pipefail
source /opt/seqchem-monitor/feishu.env

DOMAIN="seqandchem.com"
DB="/opt/goatcounter/goatcounter-data/db.sqlite3"

DAY=$(TZ=Asia/Shanghai date -d "yesterday" +%F)
START=$(TZ=Asia/Shanghai date -d "$DAY 00:00:00" -u +"%Y-%m-%d %H:%M:%S")
END=$(TZ=Asia/Shanghai date -d "$DAY 23:59:59" -u +"%Y-%m-%d %H:%M:%S")

code=$(curl -sS -o /dev/null -w "%{http_code}" -m 15 "https://$DOMAIN/" || echo 000)
rt=$(curl -sS -o /dev/null -w "%{time_total}" -m 15 "https://$DOMAIN/" || echo 0)
end=$(echo | timeout 15 openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
cert_days=$(( ( $(date -d "$end" +%s 2>/dev/null || echo 0) - $(date +%s) ) / 86400 ))
svc_app=$(systemctl is-active chemtools 2>/dev/null || echo inactive)
svc_web=$(systemctl is-active nginx 2>/dev/null || echo inactive)
svc_gc=$(systemctl is-active goatcounter 2>/dev/null || echo inactive)
mem=$(free -m | awk '/^Mem:/{print $7}')
disk=$(df -h / | awk 'NR==2{print $5}')

pv=$(sqlite3 "$DB" "select coalesce(sum(total),0) from hit_counts where hour >= '$START' and hour <= '$END';" 2>/dev/null || echo 0)
uv=$(sqlite3 "$DB" "select count(distinct session) from hits where created_at >= '$START' and created_at <= '$END';" 2>/dev/null || echo 0)
top=$(sqlite3 "$DB" "select p.path || ' (' || sum(hc.total) || ')' from hit_counts hc join paths p on p.path_id = hc.path_id where hc.hour >= '$START' and hc.hour <= '$END' group by p.path order by sum(hc.total) desc limit 5;" 2>/dev/null | paste -sd'|' - || echo "")
refs=$(sqlite3 "$DB" "select r.ref || ' (' || sum(rc.total) || ')' from ref_counts rc join refs r on r.ref_id = rc.ref_id where rc.hour >= '$START' and rc.hour <= '$END' and r.ref != '' group by r.ref order by sum(rc.total) desc limit 3;" 2>/dev/null | paste -sd'|' - || echo "")

LOG="/var/log/nginx/seqchem.access.log"
CRAWL=$(python3 - "$LOG" "$START" "$END" <<'PYEOF'
import sys, re, datetime
log, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
s = datetime.datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
e = datetime.datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
g = b = errs = 0
seen = set()
try:
    with open(log, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.search(r"\[([^\]]+)\]", line)
            if not m:
                continue
            try:
                ts = datetime.datetime.strptime(m.group(1).split()[0], "%d/%b/%Y:%H:%M:%S")
            except ValueError:
                continue
            if not (s <= ts <= e):
                continue
            low = line.lower()
            if "googlebot" in low:
                g += 1
            elif "bingbot" in low:
                b += 1
            else:
                continue
            pm = re.search(r'"(?:GET|HEAD) ([^ ]+) ', line)
            if pm:
                seen.add(pm.group(1).split("?")[0])
            if re.search(r'" 40[34] ', line):
                errs += 1
except OSError:
    pass
print(f"{g}|{b}|{len(seen)}|{errs}")
PYEOF
)
CRAW_G=${CRAWL%%|*}
_rest=${CRAWL#*|}; CRAW_B=${_rest%%|*}
_rest=${_rest#*|}; CRAW_P=${_rest%%|*}; CRAW_E=${_rest#*|}

# ---- 收录覆盖：sitemap 页面 vs 爬虫实际抓过的路径（全量日志，含轮转） ----
INDEX_COV=$(python3 - <<'PYEOF'
import glob, gzip, re, subprocess

def sitemap_paths():
    try:
        xml = subprocess.run(["curl", "-sS", "-m", "20",
                              "https://seqandchem.com/sitemap.xml"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return []
    out = []
    for u in re.findall(r"<loc>([^<]+)</loc>", xml):
        p = re.sub(r"^https?://[^/]+", "", u.strip())
        out.append(p or "/")
    return out

def crawled():
    g, b = set(), set()
    files = sorted(glob.glob("/var/log/nginx/seqchem.access.log*"))
    for fn in files:
        try:
            op = gzip.open if fn.endswith(".gz") else open
            with op(fn, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    low = line.lower()
                    if "googlebot" in low:
                        tgt = g
                    elif "bingbot" in low:
                        tgt = b
                    else:
                        continue
                    m = re.search(r'"(?:GET|HEAD) ([^ ]+) ', line)
                    if m:
                        tgt.add(m.group(1).split("?")[0])
        except OSError:
            continue
    return g, b

paths = sitemap_paths()
g, b = crawled()

def hit(path, seen):
    if path in seen:
        return True
    alt = path.rstrip("/") or "/"
    return alt in seen

g_hit = [p for p in paths if hit(p, g)]
b_hit = [p for p in paths if hit(p, b)]
missing = [p for p in paths if not hit(p, g) and not hit(p, b)]

# 新增内容优先展示（guides / 长尾页）
def prio(p):
    return (0 if p.startswith("/guides") else 1, len(p))

missing.sort(key=prio)
print("|".join([
    str(len(paths)), str(len(g_hit)), str(len(b_hit)), str(len(missing)),
    ",".join(missing[:6]),
]))
PYEOF
)
COV_T=${INDEX_COV%%|*}
_rest=${INDEX_COV#*|}; COV_G=${_rest%%|*}
_rest=${_rest#*|}; COV_B=${_rest%%|*}
_rest=${_rest#*|}; COV_MISS=${_rest%%|*}; COV_LIST=${_rest#*|}

# ---- 安全巡检 ----
SEC_UPD=$(apt list --upgradable 2>/dev/null | grep -ci security || true); SEC_UPD=${SEC_UPD:-0}
FAIL_LOGIN=$(journalctl -u ssh --since "-24 hours" 2>/dev/null | grep -ci "failed password" || true); FAIL_LOGIN=${FAIL_LOGIN:-0}
F2B_BAN=$(fail2ban-client status sshd 2>/dev/null | sed -n "s/.*Currently banned:[[:space:]]*//p" | tr -dc "0-9" | head -c 4); F2B_BAN=${F2B_BAN:-0}
REBOOT_REQ=$([ -f /var/run/reboot-required ] && echo "yes" || echo "no")
KERNEL=$(uname -r)

TMPJSON=$(mktemp)
python3 - "$TMPJSON" "$DAY" "$code" "$rt" "$cert_days" "$svc_app" "$svc_web" "$svc_gc" "$pv" "$uv" "$top" "$refs" "$mem" "$disk" "$CRAW_G" "$CRAW_B" "$CRAW_P" "$CRAW_E" "$SEC_UPD" "$FAIL_LOGIN" "$F2B_BAN" "$REBOOT_REQ" "$KERNEL" "$COV_T" "$COV_G" "$COV_B" "$COV_MISS" "$COV_LIST" <<'PY'
import json, sys
(out, day, code, rt, cert, app, web, gc, pv, uv, top, refs, mem, disk, cg, cb, cp, ce,
 sec_upd, fail_login, f2b, reboot_req, kernel, cov_t, cov_g, cov_b, cov_miss, cov_list) = sys.argv[1:29]

def num(x):
    try:
        return int(str(x).strip().split()[0])
    except Exception:
        return 0


def short(label, value, color=None):
    v = f"<font color='{color}'>{value}</font>" if color else str(value)
    return {"is_short": True, "text": {"tag": "lark_md", "content": f"{label}\n**{v}**"}}

problems = []
if code != "200":
    problems.append(f"site returned {code}")
if app != "active":
    problems.append("app not running")
if web != "active":
    problems.append("nginx not running")
if gc != "active":
    problems.append("goatcounter not running")
if int(cert or 0) < 14:
    problems.append(f"cert expires in {cert} days")
if num(sec_upd) > 0:
    problems.append(f"{sec_upd} security updates pending")
if reboot_req == "yes":
    problems.append("reboot required")
if num(fail_login) > 300:
    problems.append(f"{fail_login} failed SSH logins in 24h")

elements = [
    {"tag": "div", "text": {"tag": "lark_md",
        "content": f"**{day}（北京时间）**　https://seqandchem.com · HTTP {code} · {float(rt):.2f}s"}},
    {"tag": "hr"},
    {"tag": "div", "fields": [
        short("📄 PV", num(pv)),
        short("👤 UV", num(uv), "green" if num(uv) > 0 else None),
        short("🔐 证书剩余", f"{cert} 天", "red" if int(cert or 0) < 14 else None),
        short("💾 磁盘使用", disk),
    ]},
    {"tag": "hr"},
    {"tag": "div", "fields": [
        short("App", app, "green" if app == "active" else "red"),
        short("Nginx", web, "green" if web == "active" else "red"),
        short("GoatCounter", gc, "green" if gc == "active" else "red"),
        short("内存可用", f"{mem}MB"),
    ]},
]
if top:
    elements += [{"tag": "hr"},
                 {"tag": "div", "text": {"tag": "lark_md",
                  "content": "**热门页面**　" + top.replace("|", "  ·  ")}}]
if refs:
    elements.append({"tag": "div", "text": {"tag": "lark_md",
                     "content": "**访问来源**　" + refs.replace("|", "  ·  ")}})
crawl_line = f"**爬虫抓取**　Google {cg} 次 · Bing {cb} 次 · 覆盖 {cp} 个页面"
if int(ce or 0) > 0:
    crawl_line += f" · <font color='red'>{ce} 个 4xx</font>"
elements += [{"tag": "hr"}, {"tag": "div", "text": {"tag": "lark_md", "content": crawl_line}}]

# 收录覆盖
if num(cov_t) > 0:
    cov_line = (f"**收录覆盖**　Google {cov_g}/{cov_t} · Bing {cov_b}/{cov_t}"
                f" · 未抓取 <font color='{'orange' if num(cov_miss) > 0 else 'green'}>{cov_miss}</font>")
    if cov_list:
        shown = cov_list.split(",")[:5]
        cov_line += "\n未抓取示例：<font color='#8b8b8b'>" + " · ".join(shown) + "</font>"
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": cov_line}})
sec_line = (f"**安全**　待更新 {sec_upd} · SSH失败 {fail_login} · 封禁 {f2b}"
            f" · 内核 {kernel}" + ("　<font color='red'>⚠️ 需重启</font>" if reboot_req == "yes" else ""))
elements += [{"tag": "div", "text": {"tag": "lark_md", "content": sec_line}}]
if problems:
    elements.append({"tag": "note", "elements": [
        {"tag": "plain_text", "content": "⚠️ " + " · ".join(problems)}]})

with open(out, "w", encoding="utf-8") as fh:
    json.dump({
        "config": {"wide_screen_mode": True},
        "header": {"template": "red" if problems else "blue",
                   "title": {"tag": "plain_text", "content": "🧪 SeqChem · 每日体检"}},
        "elements": elements,
    }, fh, ensure_ascii=False)
PY

CARD=$(cat "$TMPJSON")
rm -f "$TMPJSON"

TOKEN=$(curl -sS -m 15 -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d "{\"app_id\":\"${FEISHU_APP_ID}\",\"app_secret\":\"${FEISHU_APP_SECRET}\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tenant_access_token",""))')
[ -z "$TOKEN" ] && { echo "$(date '+%F %T') token failed" >&2; exit 1; }

BODY=$(mktemp)
python3 - "$BODY" "$FEISHU_OPEN_ID" "$CARD" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump({"receive_id": sys.argv[2], "msg_type": "interactive", "content": sys.argv[3]}, fh)
PY
curl -sS -m 20 -X POST "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data-binary "@$BODY" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("sent:", d.get("msg"), d.get("code"))'
rm -f "$BODY"
