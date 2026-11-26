#!/usr/bin/env python3
"""Print 'PV visits' for one UTC date from Cloudflare Web Analytics."""
import datetime
import os
import sys

import requests

ENV = os.environ.get("CF_ENV", "/opt/seqchem-monitor/cloudflare-analytics.env")
ACCOUNT = os.environ.get("CF_ACCOUNT", "4a63097fa96be9e4cddf77737be16c1c")
SITE_TAG = os.environ.get("CF_SITE_TAG", "7561aa3ebc5d42ac8dccbbba58973506")
QUERY = """
query($acc: String!, $day: Date!, $tag: String!) {
  viewer {
    accounts(filter: {accountTag: $acc}) {
      rumPageloadEventsAdaptiveGroups(
        limit: 1, filter: {date_geq: $day, date_leq: $day, siteTag: $tag}
      ) { count sum { visits } }
    }
  }
}
"""


def load_env():
    try:
        with open(ENV, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


def main():
    load_env()
    day = (sys.argv[1] if len(sys.argv) > 1
           else (datetime.date.today() - datetime.timedelta(days=1)).isoformat())
    token = os.environ.get("CF_ANALYTICS_TOKEN", "").strip()
    if not token:
        print("0 0")
        return
    try:
        r = requests.post(
            "https://api.cloudflare.com/client/v4/graphql",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"query": QUERY, "variables": {"acc": ACCOUNT, "day": day, "tag": SITE_TAG}},
            timeout=20,
        )
        data = r.json()
        accounts = ((data.get("data") or {}).get("viewer") or {}).get("accounts") or []
        total = ((accounts[0].get("rumPageloadEventsAdaptiveGroups") or [{}])[0]
                 if accounts else {})
        print(f'{int(total.get("count", 0))} {int((total.get("sum") or {}).get("visits", 0))}')
    except Exception:
        print("0 0")


if __name__ == "__main__":
    main()
