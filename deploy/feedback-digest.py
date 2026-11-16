#!/usr/bin/env python3
"""Send yesterday's new SeqChem feedback to Feishu (only when there is any)."""
import datetime
import json
import os
import sqlite3
import urllib.request
from zoneinfo import ZoneInfo

DB = "/opt/chemtools/data/feedback.sqlite3"
ENV = "/opt/seqchem-monitor/feishu.env"
TZ = ZoneInfo("Asia/Shanghai")
MAX_ROWS = 5
MAX_CHARS = 300


def load_env(path):
    out = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def post_json(url, payload, headers=None):
    data = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def main():
    now = datetime.datetime.now(TZ)
    day = (now - datetime.timedelta(days=1)).date()
    start = datetime.datetime.combine(day, datetime.time.min, tzinfo=TZ).astimezone(datetime.timezone.utc)
    end = datetime.datetime.combine(day, datetime.time.max, tzinfo=TZ).astimezone(datetime.timezone.utc)
    start_s, end_s = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn = sqlite3.connect(DB, timeout=10)
        count = conn.execute(
            "select count(*) from feedback where created_at >= ? and created_at <= ?",
            (start_s, end_s),
        ).fetchone()[0]
        rows = conn.execute(
            "select category, page, message from feedback "
            "where created_at >= ? and created_at <= ? order by id desc limit ?",
            (start_s, end_s, MAX_ROWS),
        ).fetchall()
        conn.close()
    except sqlite3.Error as exc:
        print(f"{datetime.datetime.now(TZ):%F %T} feedback db error: {exc}")
        return 1

    if count == 0:
        print(f"{datetime.datetime.now(TZ):%F %T} no feedback for {day}")
        return 0

    text = f"📝 SeqChem 用户反馈 · {day}（{count} 条）"
    for category, page, message in rows:
        clean = " ".join((message or "").split())[:MAX_CHARS]
        text += f"\n\n[{category}] {page or '/'}\n{clean}"
    if count > len(rows):
        text += f"\n\n… 另有 {count - len(rows)} 条，稍后在服务器查看。"

    env = load_env(ENV)
    try:
        token = post_json(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            {"app_id": env["FEISHU_APP_ID"], "app_secret": env["FEISHU_APP_SECRET"]},
        ).get("tenant_access_token", "")
        if not token:
            raise RuntimeError("no tenant_access_token")
        result = post_json(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            {"receive_id": env["FEISHU_OPEN_ID"], "msg_type": "text",
             "content": json.dumps({"text": text}, ensure_ascii=False)},
            {"Authorization": "Bearer " + token},
        )
        print(f"{datetime.datetime.now(TZ):%F %T} sent: {result.get('msg')} {result.get('code')}")
        return 0
    except Exception as exc:
        print(f"{datetime.datetime.now(TZ):%F %T} send failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
