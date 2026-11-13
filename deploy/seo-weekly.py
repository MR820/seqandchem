#!/usr/bin/env python3
"""Weekly SEO report: GSC index/performance + Bing + GoatCounter -> Feishu."""
import datetime
import json
import os
import re
import sqlite3
import time
import urllib.parse
from collections import Counter

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

SITE = "sc-domain:seqandchem.com"
GSC_KEY = os.environ.get("GSC_KEY", "/opt/seqchem-monitor/gsc-service-account.json")
GC_DB = os.environ.get("GC_DB", "/opt/goatcounter/goatcounter-data/db.sqlite3")
FEISHU_ENV = os.environ.get("FEISHU_ENV", "/opt/seqchem-monitor/feishu.env")
BING_ENV = os.environ.get("BING_ENV", "/opt/seqchem-monitor/bing-webmaster.env")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
INSPECT_LIMIT = int(os.environ.get("INSPECT_LIMIT", "49"))


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


load_env(FEISHU_ENV)
load_env(BING_ENV)

lines = []
errors = []


def section(title):
    lines.append("")
    lines.append(title)


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

    today = datetime.date.today()
    end = today - datetime.timedelta(days=3)
    start = end - datetime.timedelta(days=27)
    analytics_url = (
        f"https://searchconsole.googleapis.com/webmasters/v3/sites/{enc}/searchAnalytics/query"
    )
    queries = session.post(
        analytics_url,
        json={"startDate": start.isoformat(), "endDate": end.isoformat(),
              "dimensions": ["query"], "rowLimit": 10},
        timeout=30,
    ).json().get("rows", [])
    pages = session.post(
        analytics_url,
        json={"startDate": start.isoformat(), "endDate": end.isoformat(),
              "dimensions": ["page"], "rowLimit": 10},
        timeout=30,
    ).json().get("rows", [])

    sm = sitemaps[0] if sitemaps else {}
    section("Google Search Console")
    lines.append(
        f"Sitemap: {sm.get('path', 'n/a')} · errors={sm.get('errors', '?')} "
        f"· warnings={sm.get('warnings', '?')} · downloaded={sm.get('lastDownloaded', '?')}"
    )

    # Inspect every sitemap URL (limit for dry runs)
    xml = requests.get("https://seqandchem.com/sitemap.xml", timeout=20).text
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    counts = Counter()
    issues = []
    canonical = []
    inspect_url = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
    for u in urls[:INSPECT_LIMIT]:
        body = {"inspectionUrl": u, "siteUrl": SITE, "languageCode": "en-US"}
        r = session.post(inspect_url, json=body, timeout=30)
        if not r.ok:
            errors.append(f"inspect {u}: {r.status_code}")
            continue
        idx = (r.json().get("inspectionResult") or {}).get("indexStatusResult") or {}
        cov = idx.get("coverageState") or idx.get("verdict") or "unknown"
        counts[cov] += 1
        if cov != "Submitted and indexed":
            issues.append(f"{u} ({cov})")
        gc, uc = idx.get("googleCanonical"), idx.get("userCanonical")
        if gc and uc and gc != uc:
            canonical.append(f"{u}: google={gc} user={uc}")
        time.sleep(0.1)
    lines.append(
        f"Indexed: {counts.get('Submitted and indexed', 0)}/{len(urls[:INSPECT_LIMIT])} "
        f"· discovered: {counts.get('Discovered - currently not indexed', 0)} "
        f"· unknown: {counts.get('URL is unknown to Google', 0)}"
    )
    if queries:
        top = queries[0]
        lines.append(
            f"28d: impressions={sum(q.get('impressions', 0) for q in queries)} "
            f"clicks={sum(q.get('clicks', 0) for q in queries)} "
            f"· top query: {top.get('keys', ['?'])[0]} "
            f"(imp={top.get('impressions', 0)}, pos={round(top.get('position', 0), 1)})"
        )
    else:
        lines.append("28d: no search analytics rows yet")
    if pages:
        top_page = pages[0]
        lines.append(
            f"Top page: {top_page.get('keys', ['?'])[0]} "
            f"(imp={top_page.get('impressions', 0)}, clicks={top_page.get('clicks', 0)})"
        )
    if issues:
        lines.append("Unindexed priority: " + " · ".join(issues[:5]))
    if canonical:
        lines.append("Canonical mismatch: " + " · ".join(canonical[:3]))
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
    section("Bing Webmaster")
    lines.append(
        f"Sitemap: {feed.get('Status', '?')} · URLs={feed.get('UrlCount', '?')} "
        f"· lastCrawled={feed.get('LastCrawled', '?')}"
    )
    lines.append(
        f"Queries={len(qstats)} · traffic rows={len(traffic)} · crawl issues={len(crawl)} "
        f"· quota={quota.get('DailyQuota', '?')}/{quota.get('MonthlyQuota', '?')}"
    )
    if qstats:
        lines.append(f"Top Bing query: {qstats[0].get('Query', '?')}")
except Exception as exc:
    errors.append(f"Bing: {exc}")

# ---------- GoatCounter ----------
try:
    conn = sqlite3.connect(GC_DB)
    cur = conn.cursor()
    pv, uv = cur.execute(
        "select count(*), count(distinct session) from hits "
        "where created_at >= datetime('now','-7 days')"
    ).fetchone()
    top = cur.execute(
        "select p.path, count(*) c from hits h join paths p on p.path_id=h.path_id "
        "where h.created_at >= datetime('now','-7 days') group by p.path order by c desc limit 5"
    ).fetchall()
    events = cur.execute(
        "select p.path, count(*) c from hits h join paths p on p.path_id=h.path_id "
        "where h.created_at >= datetime('now','-7 days') and p.event=1 "
        "group by p.path order by c desc limit 5"
    ).fetchall()
    conn.close()
    section("GoatCounter 7d")
    lines.append(f"PV={pv} · UV={uv}")
    if top:
        lines.append("Top: " + " · ".join(f"{p} ({c})" for p, c in top))
    if events:
        lines.append("Events: " + " · ".join(f"{p} ({c})" for p, c in events))
except Exception as exc:
    errors.append(f"GoatCounter: {exc}")

# ---------- Send ----------
lines.insert(0, f"📊 SeqChem SEO 周报 · {datetime.date.today().isoformat()}")
if errors:
    lines.append("")
    lines.append("⚠️ " + " · ".join(errors[:4]))
text = "\n".join(lines)
print(text)

if DRY_RUN:
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
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        r = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            data=json.dumps(body, ensure_ascii=False), timeout=20,
        )
        print("feishu:", r.json().get("msg"), r.json().get("code"))
    except Exception as exc:
        print("feishu send failed:", exc)
        raise
