#!/usr/bin/env python3
"""Weekly SEO report: GSC + Bing + Cloudflare Web Analytics -> Feishu card."""
import datetime
import json
import os
import re
import time
import urllib.parse
from collections import Counter

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

SITE = "sc-domain:seqandchem.com"
GSC_KEY = os.environ.get("GSC_KEY", "/opt/seqchem-monitor/gsc-service-account.json")
FEISHU_ENV = os.environ.get("FEISHU_ENV", "/opt/seqchem-monitor/feishu.env")
BING_ENV = os.environ.get("BING_ENV", "/opt/seqchem-monitor/bing-webmaster.env")
CF_ENV = os.environ.get("CF_ENV", "/opt/seqchem-monitor/cloudflare-analytics.env")
CF_ACCOUNT = os.environ.get("CF_ACCOUNT", "4a63097fa96be9e4cddf77737be16c1c")
HISTORY = os.environ.get("SEO_HISTORY", "/opt/seqchem-monitor/seo-history.json")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
INSPECT_LIMIT = int(os.environ.get("INSPECT_LIMIT", "60"))

SPARK = "▁▂▃▄▅▆▇█"


def load_env(path):
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


def spark(values):
    if not values:
        return "—"
    lo, hi = min(values), max(values)
    if hi == lo:
        return SPARK[0] * len(values)
    return "".join(SPARK[round((v - lo) / (hi - lo) * (len(SPARK) - 1))] for v in values)


def progress(done, total, width=18):
    total = max(1, total)
    done = max(0, min(done, total))
    filled = round(done / total * width)
    return "█" * filled + "░" * (width - filled)


def load_history():
    try:
        with open(HISTORY, encoding="utf-8") as fh:
            value = json.load(fh)
            return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_history(entry):
    history = [h for h in load_history() if h.get("date") != entry.get("date")]
    history.append(entry)
    history = history[-12:]
    with open(HISTORY, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, indent=2)
    os.chmod(HISTORY, 0o600)
    return history


load_env(FEISHU_ENV)
load_env(BING_ENV)
load_env(CF_ENV)

today = datetime.date.today()
data = {
    "date": today.isoformat(),
    "total": 0, "indexed": 0, "discovered": 0, "unknown": 0,
    "issues": [], "canonical": [],
    "impressions": 0, "clicks": 0,
    "queries": [], "pages": [],
    "gsc_end": "",
    "daily_impressions": [], "daily_clicks": [],
    "sitemap": {},
    "bing": {},
    "cf_pv": 0, "cf_uv": 0, "cf_daily_pv": [], "cf_daily_uv": [],
}
errors = []

# ---------- GSC ----------
try:
    creds = service_account.Credentials.from_service_account_file(
        GSC_KEY, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    session = AuthorizedSession(creds)
    enc = urllib.parse.quote(SITE, safe="")

    sitemaps = session.get(
        f"https://searchconsole.googleapis.com/webmasters/v3/sites/{enc}/sitemaps", timeout=30
    ).json().get("sitemap", [])
    sm = sitemaps[0] if sitemaps else {}
    data["sitemap"] = {
        "path": sm.get("path", ""),
        "errors": sm.get("errors", "?"),
        "warnings": sm.get("warnings", "?"),
        "downloaded": sm.get("lastDownloaded", "?"),
    }

    end = today - datetime.timedelta(days=3)
    start = end - datetime.timedelta(days=27)
    data["gsc_end"] = end.isoformat()
    analytics_url = (
        f"https://searchconsole.googleapis.com/webmasters/v3/sites/{enc}/searchAnalytics/query"
    )

    def analytics(dimensions, limit):
        return session.post(
            analytics_url,
            json={"startDate": start.isoformat(), "endDate": end.isoformat(),
                  "dimensions": dimensions, "rowLimit": limit},
            timeout=30,
        ).json().get("rows", [])

    data["queries"] = analytics(["query"], 10)
    data["pages"] = analytics(["page"], 10)
    daily = analytics(["date"], 30)
    daily_map = {row.get("keys", [""])[0]: row for row in daily}
    dates = [(start + datetime.timedelta(days=offset)).isoformat() for offset in range(28)]
    data["daily_impressions"] = [
        int(daily_map.get(day, {}).get("impressions", 0)) for day in dates
    ]
    data["daily_clicks"] = [int(daily_map.get(day, {}).get("clicks", 0)) for day in dates]
    data["impressions"] = sum(data["daily_impressions"])
    data["clicks"] = sum(data["daily_clicks"])

    xml = requests.get("https://seqandchem.com/sitemap.xml", timeout=20).text
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    data["total"] = len(urls[:INSPECT_LIMIT])
    counts = Counter()
    inspect_url = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
    for index, url in enumerate(urls[:INSPECT_LIMIT]):
        body = {"inspectionUrl": url, "siteUrl": SITE, "languageCode": "en-US"}
        r = session.post(inspect_url, json=body, timeout=30)
        if not r.ok:
            errors.append(f"inspect {url}: {r.status_code}")
            continue
        idx = (r.json().get("inspectionResult") or {}).get("indexStatusResult") or {}
        cov = idx.get("coverageState") or idx.get("verdict") or "unknown"
        counts[cov] += 1
        if cov != "Submitted and indexed":
            data["issues"].append(f"{url.replace('https://seqandchem.com', '') or '/'} ({cov})")
        gc, uc = idx.get("googleCanonical"), idx.get("userCanonical")
        if gc and uc and gc.rstrip("/") != uc.rstrip("/"):
            data["canonical"].append(
                f"{url.replace('https://seqandchem.com', '') or '/'}: "
                f"google={gc} user={uc}"
            )
        if index < INSPECT_LIMIT - 1:
            time.sleep(0.1)
    data["indexed"] = counts.get("Submitted and indexed", 0)
    data["discovered"] = counts.get("Discovered - currently not indexed", 0)
    data["unknown"] = counts.get("URL is unknown to Google", 0)
except Exception as exc:
    errors.append(f"GSC: {exc}")

# ---------- Bing ----------
try:
    bing_key = os.environ.get("BING_WEBMASTER_API_KEY", "")
    bing_base = "https://ssl.bing.com/webmaster/api.svc/json/"
    bing_site = "https://seqandchem.com/"

    def bing(method, **params):
        p = {"apikey": bing_key, "siteUrl": bing_site}
        p.update(params)
        r = requests.get(bing_base + method, params=p, timeout=30)
        r.raise_for_status()
        return r.json().get("d")

    feeds = bing("GetFeeds") or []
    qstats = bing("GetQueryStats") or []
    traffic = bing("GetRankAndTrafficStats") or []
    crawl = bing("GetCrawlIssues") or []
    quota = bing("GetUrlSubmissionQuota") or {}
    feed = feeds[0] if feeds else {}
    data["bing"] = {
        "status": feed.get("Status", "?"),
        "urls": feed.get("UrlCount", "?"),
        "last_crawled": feed.get("LastCrawled", "?"),
        "queries": len(qstats),
        "traffic": len(traffic),
        "crawl": len(crawl),
        "quota": f"{quota.get('DailyQuota', '?')}/{quota.get('MonthlyQuota', '?')}",
        "top_query": qstats[0].get("Query", "") if qstats else "",
    }
except Exception as exc:
    errors.append(f"Bing: {exc}")

# ---------- Cloudflare Web Analytics ----------
try:
    cf_token = os.environ.get("CF_ANALYTICS_TOKEN", "").strip()
    if not cf_token:
        raise RuntimeError("CF_ANALYTICS_TOKEN missing")
    start_cf = today - datetime.timedelta(days=6)
    cf_query = """
query($acc: String!, $start: Date!, $end: Date!) {
  viewer {
    accounts(filter: {accountTag: $acc}) {
      total: rumPageloadEventsAdaptiveGroups(
        limit: 1, filter: {date_geq: $start, date_leq: $end}
      ) { count sum { visits } }
      daily: rumPageloadEventsAdaptiveGroups(
        limit: 100, filter: {date_geq: $start, date_leq: $end}, orderBy: [date_ASC]
      ) { count sum { visits } dimensions { date } }
    }
  }
}
"""
    cf_resp = requests.post(
        "https://api.cloudflare.com/client/v4/graphql",
        headers={"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"},
        json={"query": cf_query,
              "variables": {"acc": CF_ACCOUNT, "start": start_cf.isoformat(),
                            "end": today.isoformat()}},
        timeout=30,
    )
    cf_json = cf_resp.json()
    if cf_resp.status_code != 200 or cf_json.get("errors"):
        raise RuntimeError(str(cf_json.get("errors") or cf_resp.status_code))
    accounts = ((cf_json.get("data") or {}).get("viewer") or {}).get("accounts") or []
    if not accounts:
        raise RuntimeError("no account data")
    total = (accounts[0].get("total") or [{}])[0]
    data["cf_pv"] = int(total.get("count", 0))
    data["cf_uv"] = int((total.get("sum") or {}).get("visits", 0))
    daily = {row.get("dimensions", {}).get("date"): row
             for row in accounts[0].get("daily", [])}
    dates = [(start_cf + datetime.timedelta(days=i)).isoformat() for i in range(7)]
    data["cf_daily_pv"] = [int(daily.get(d, {}).get("count", 0)) for d in dates]
    data["cf_daily_uv"] = [int((daily.get(d, {}).get("sum") or {}).get("visits", 0))
                           for d in dates]
except Exception as exc:
    errors.append(f"Cloudflare: {exc}")

# ---------- History / previous week ----------
history = load_history()
previous = next((h for h in reversed(history) if h.get("date", "") < data["date"]), None)
if not DRY_RUN and not any(error.startswith("GSC:") for error in errors):
    history = save_history({
        "date": data["date"],
        "indexed": data["indexed"],
        "total": data["total"],
        "impressions": data["impressions"],
        "clicks": data["clicks"],
        "cf_pv": data["cf_pv"],
        "cf_uv": data["cf_uv"],
    })

# ---------- Text log ----------
lines = [
    f"📊 SeqChem SEO 周报 · {data['date']}",
    "",
    f"Google 收录: {data['indexed']}/{data['total']} "
    f"· discovered={data['discovered']} · unknown={data['unknown']}",
    f"GSC 28d: 展示={data['impressions']} · 点击={data['clicks']}",
]
if data["queries"]:
    q = data["queries"][0]
    lines.append(
        f"Top query: {q.get('keys', ['?'])[0]} "
        f"(imp={q.get('impressions', 0)}, pos={round(q.get('position', 0), 1)})"
    )
if data["pages"]:
    p = data["pages"][0]
    lines.append(f"Top page: {p.get('keys', ['?'])[0]} (imp={p.get('impressions', 0)})")
lines += [
    f"Bing: sitemap={data['bing'].get('status', '?')} "
    f"URLs={data['bing'].get('urls', '?')} quota={data['bing'].get('quota', '?')}",
    f"Cloudflare 7d: PV={data['cf_pv']} · visits={data['cf_uv']}",
]
if errors:
    lines.append("⚠️ " + " · ".join(errors[:4]))
text = "\n".join(lines)
print(text)

# ---------- Feishu card ----------
def build_card(data, errors):
    delta = ""
    if previous:
        diff = data["indexed"] - previous.get("indexed", 0)
        if diff:
            delta = f" ({diff:+d})"
    kpi = [
        {"is_short": True, "text": {"tag": "lark_md",
         "content": f"**Google 收录**\n**{data['indexed']}/{data['total']}**{delta}"}},
        {"is_short": True, "text": {"tag": "lark_md",
         "content": f"**GSC 28 天**\n**{data['impressions']}** 展示 · **{data['clicks']}** 点击"}},
        {"is_short": True, "text": {"tag": "lark_md",
         "content": f"**Bing**\nSitemap {data['bing'].get('status', '?')} · "
                    f"quota {data['bing'].get('quota', '?')}"}},
        {"is_short": True, "text": {"tag": "lark_md",
         "content": f"**Cloudflare 7 天**\n**{data['cf_pv']}** PV · "
                    f"**{data['cf_uv']}** visits"}},
    ]

    recent_impressions = data["daily_impressions"][-7:]
    recent_clicks = data["daily_clicks"][-7:]
    period = f"（至 {data['gsc_end']}）" if data["gsc_end"] else ""

    elements = [
        {"tag": "div", "fields": kpi},
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**收录进度**  {progress(data['indexed'], data['total'])}  "
                    f"{data['indexed']}/{data['total']}\n"
                    f"discovered {data['discovered']} · unknown {data['unknown']}"}},
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**Google · 近 7 天趋势**{period}\n"
                    f"展示 {sum(recent_impressions)}  {spark(recent_impressions)}\n"
                    f"点击 {sum(recent_clicks)}  {spark(recent_clicks)}"}},
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**Cloudflare · 近 7 天**\n"
                    f"PV {data['cf_pv']}  {spark(data['cf_daily_pv'])}\n"
                    f"visits {data['cf_uv']}  {spark(data['cf_daily_uv'])}"}},
    ]

    if data["queries"]:
        q = data["queries"][0]
        elements.append({"tag": "div", "text": {"tag": "lark_md",
            "content": f"**Top query**  {q.get('keys', ['?'])[0]}\n"
                       f"imp {q.get('impressions', 0)} · pos {round(q.get('position', 0), 1)}"}})
    if data["pages"]:
        p = data["pages"][0]
        page_path = urllib.parse.urlparse(p.get("keys", [""])[0]).path or "/"
        elements.append({"tag": "div", "text": {"tag": "lark_md",
            "content": f"**Top page**  {page_path}\n"
                       f"imp {p.get('impressions', 0)} · clicks {p.get('clicks', 0)}"}})
    if data["issues"]:
        elements.append({"tag": "div", "text": {"tag": "lark_md",
            "content": "**优先未收录**\n" + "\n".join("• " + x for x in data["issues"][:5])}})
    if data["canonical"]:
        elements.append({"tag": "div", "text": {"tag": "lark_md",
            "content": "**Canonical 提示**\n" + "\n".join("• " + x for x in data["canonical"][:3])}})

    elements += [
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**Bing**\nSitemap {data['bing'].get('status', '?')} · "
                    f"URLs {data['bing'].get('urls', '?')} · "
                    f"queries {data['bing'].get('queries', 0)} · "
                    f"crawl issues {data['bing'].get('crawl', 0)}"}},
    ]
    if len(history) >= 2:
        elements.append({"tag": "div", "text": {"tag": "lark_md",
            "content": "**周度收录趋势**  " + spark([h.get("indexed", 0) for h in history])}})
    if errors:
        elements.append({"tag": "note", "elements": [
            {"tag": "plain_text", "content": "⚠️ " + " · ".join(errors[:4])}]})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "red" if errors else "blue",
            "title": {"tag": "plain_text", "content": f"📊 SeqChem SEO 周报 · {data['date']}"},
        },
        "elements": elements,
    }


card = build_card(data, errors)

if DRY_RUN:
    print("\n--- FEISHU CARD ---")
    print(json.dumps(card, ensure_ascii=False, indent=2))
    print("\n[DRY_RUN] not sending to Feishu")
else:
    try:
        app_id = os.environ["FEISHU_APP_ID"]
        app_secret = os.environ["FEISHU_APP_SECRET"]
        open_id = os.environ["FEISHU_OPEN_ID"]
        token = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret}, timeout=20,
        ).json().get("tenant_access_token", "")
        if not token:
            raise RuntimeError("no tenant_access_token")
        body = {
            "receive_id": open_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        }
        r = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            data=json.dumps(body, ensure_ascii=False), timeout=20,
        )
        result = r.json()
        print("feishu:", result.get("msg"), result.get("code"))
        if result.get("code") != 0:
            # Fallback to plain text if the card schema is rejected.
            fallback = requests.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                data=json.dumps({"receive_id": open_id, "msg_type": "text",
                                 "content": json.dumps({"text": text}, ensure_ascii=False)},
                                ensure_ascii=False), timeout=20,
            ).json()
            print("feishu fallback:", fallback.get("msg"), fallback.get("code"))
    except Exception as exc:
        print("feishu send failed:", exc)
        raise
