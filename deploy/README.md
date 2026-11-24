# Deployment

Production runs on a single Debian/Ubuntu host.

| File | Goes to | Notes |
|---|---|---|
| `chemtools.service` | `/etc/systemd/system/` | gunicorn, 2 workers, `127.0.0.1:8080`, 900 MB memory cap |
| `nginx.conf` | `/etc/nginx/sites-available/seqchem` | TLS termination, headers, proxies to gunicorn |
| `nginx-main.conf` | `/etc/nginx/nginx.conf` | stream layer: SNI routing on 443 + PROXY protocol |
| `daily-report.sh` | `/opt/seqchem-monitor/` | cron `0 1 * * *`; includes Cloudflare PV/visits; needs `feishu.env` and `cloudflare-analytics.env` |
| `cf_daily.py` | `/opt/seqchem-monitor/` | helper: Cloudflare page views/visits for one UTC date |
| `backup.sh` | `/opt/seqchem-monitor/` | cron `30 1 * * *`; SQLite + configs, newest 7 in `/var/backups/seqchem` |
| `uptime-check.sh` | `/opt/seqchem-monitor/` | cron `*/5 * * * *`; main site + api `/health` + services, Feishu on state change |
| `seo-weekly.py` | `/opt/seqchem-monitor/` | cron `0 2 * * 1`; GSC + Bing + Cloudflare Web Analytics → Feishu interactive card; needs `gsc-service-account.json`, `bing-webmaster.env` and `cloudflare-analytics.env` |
| `feedback-digest.py` | `/opt/seqchem-monitor/` | cron `15 1 * * *`; yesterday's feedback → Feishu, only when count > 0 |
| `cloudflare-uptime-worker/` | Cloudflare account (Worker + KV) | Worker `seqchem-uptime`, KV `seqchem_uptime`, cron `*/5 * * * *`; primary external check |

## First-time setup

```bash
apt install openbabel nginx python3-venv
useradd -r -s /usr/sbin/nologin chemtools
mkdir -p /opt/chemtools
# copy app.py bio.py formula.py guides.py presets.py templates/ static/
python3 -m venv /opt/chemtools/venv
/opt/chemtools/venv/bin/python -m pip install --upgrade pip
/opt/chemtools/venv/bin/pip install --require-hashes -r requirements.txt
chown -R chemtools:chemtools /opt/chemtools
systemctl enable --now chemtools
```

TLS is terminated by nginx (certbot webroot at `/var/www/acme`). If the host routes TLS by SNI
in an nginx `stream` block, point the domain at its `127.0.0.1:8444` listener as in `nginx.conf`.

## Updating

```bash
scp app.py templates/*.html root@HOST:/opt/chemtools/
ssh root@HOST 'chown -R chemtools:chemtools /opt/chemtools && cd /opt/chemtools \
  && venv/bin/python -c "import app" && systemctl restart chemtools'
```

Always run the `import app` check before restarting — it catches syntax and import errors that
would otherwise take the service down.

Deploys stay manual. The GitHub Actions workflows in this repository declare `contents: read`
and are not a deploy path: do not put production SSH keys, Cloudflare tokens, or the Feishu app
credentials (`FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_OPEN_ID`) into Actions. Those app
credentials stay in `/opt/seqchem-monitor/feishu.env` (mode 600) and in the Worker secrets.
The secondary uptime workflow uses only the existing repository secrets `FEISHU_WEBHOOK` and
`FEISHU_WEBHOOK_SECRET`.

If the update changes HTML, Cloudflare may serve the previous page for up to 5 minutes
(`s-maxage=300`); purge the affected URLs after the deploy or wait for the cache to expire.

## Monitoring

`daily-report.sh` pushes a Feishu card once a day with: uptime and latency, certificate expiry,
PV/UV, top pages and referrers, crawler activity, sitemap index coverage, pending security
updates, failed SSH logins and fail2ban bans.

Credentials live in `/opt/seqchem-monitor/feishu.env` (mode 600, not in this repo):

```
FEISHU_APP_ID=...
FEISHU_APP_SECRET=...
FEISHU_OPEN_ID=...
```

## External uptime

Two primary checks already run every 5 minutes:

- Cloudflare Worker `seqchem-uptime` (`cloudflare-uptime-worker/`), cron `*/5 * * * *`, from
  Cloudflare's edge. It checks both `/health` endpoints and one `/api/v1/convert` call, and sends
  a Feishu message on OK → DOWN and DOWN → OK, with a 6-hour reminder while down.
- On-host `uptime-check.sh`, cron `*/5 * * * *`, which also sees systemd state for chemtools,
  nginx and goatcounter.

`.github/workflows/uptime.yml` is a secondary probe from a GitHub-hosted runner, so it is a
different network path. It is best-effort only. The probe names itself
`SeqChem-Uptime/1.0 (GitHub Actions secondary uptime probe)` and sends an `Accept` header,
instead of the default Python-urllib client; an HTTP 403 is still a failed check.
GitHub documents that `schedule` events can be delayed when Actions is under load, that the
start of every hour is a high-load time, and that
queued jobs may be dropped. On `main` the workflow was active and its cron was valid. Schedule
runs that GitHub did emit were created and started in the same second and then succeeded; the
multi-hour gaps were events that were not emitted. That is scheduler delay and drop, not a
failed check.

The workflow therefore does not request a 15-minute cadence. It asks for twelve runs per day,
none of them at minute 0:

- `17 */3 * * *` (minute 17 every third hour)
- `47 1,7,13,19 * * *`

A concurrency group named `external-uptime` keeps an in-progress probe running (so a failure can
still notify) and drops older queued duplicates. `workflow_dispatch` remains for a manual run.
Failure notification still uses the repository secrets `FEISHU_WEBHOOK` and
`FEISHU_WEBHOOK_SECRET` and stays silent when the webhook secret is unset. This does not add
another notification service, and it does not replace either primary check.

## Dependencies

`requirements.in` lists the direct runtime pins (Flask 3.1.3, Flask-Compress 1.26, gunicorn
26.2.0). `requirements.txt` is the hashed pip-compile lock, including the transitive set already
resolved by CI on 2026-11-18. Tests install `requirements-dev.txt`, which adds pytest 9.2.0 and
its dependencies. Regenerate with the commands in the `.in` files; do not hand-edit the locks.

OpenBabel stays the OS package installed above. Do not add the PyPI `openbabel` distribution.

`.github/dependabot.yml` opens at most two pip update PRs and one GitHub Actions update PR per
week, so version updates are reviewed individually instead of applied as a broad bump. This
change does not modify GitHub secret scanning.

## Cloudflare cache

The zone has a Cache Rule that makes public HTML eligible for edge caching with
`edge_ttl=respect_origin`; the app sends `Cache-Control: public, max-age=60, s-maxage=300`.
After deploying an HTML change, purge the affected URLs (or the zone cache) or wait up to
5 minutes. Example:

```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/purge_cache" \
  -H "Authorization: Bearer $CLOUDFLARE_ZONE_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"files":["https://seqandchem.com/","https://seqandchem.com/privacy"]}'
```

## Cloudflare Web Analytics

The Web Analytics site (`seqandchem.com`) exists in the Cloudflare account and its
`auto_install` setting is **false**. The beacon is injected by the app instead, so it works
regardless of edge cache state:

- `/opt/chemtools/cf_beacon_token` (mode 600) contains the public site token.
- `base.html` injects the beacon only when that file (or `CF_BEACON_TOKEN`) is present.
- If the token changes, update the file and restart `chemtools`.

The nginx CSP allows the beacon explicitly:

- `script-src` includes `https://static.cloudflareinsights.com`
- `connect-src` includes `https://cloudflareinsights.com`

Both are present in `deploy/nginx.conf`. Web Analytics is cookie-free and does not use local
storage or cross-site identifiers; EU visitors are included in the aggregate counts. It is not an
EU-only data-localization product. Keep `/privacy` disclosed for Cloudflare Web Analytics.

## Real client IPs

TLS is routed by SNI in an nginx `stream` block, so without help every request reaches the HTTP
layer as `127.0.0.1`. `nginx-main.conf` fixes that with the PROXY protocol:

- the `stream` server listening on 443 has `proxy_protocol on;`
- every HTTP listener that receives that traffic must opt in:
  `listen 127.0.0.1:8444 ssl http2 proxy_protocol;`
- `set_real_ip_from 127.0.0.1;` + `real_ip_header proxy_protocol;` in the `http` block turns the
  header back into `$remote_addr`

**Any new vhost behind the stream layer must add `proxy_protocol` to its `listen` line**, or it
will answer with `400 Bad Request`.

The xboard node does not speak PROXY protocol (it resets the connection), so its SNI entry points
at `127.0.0.1:12100` — a local stream listener that accepts the header and forwards plain TCP to
`127.0.0.1:12005`.

Result: nginx access logs, `fail2ban`-style analysis and the app's per-IP rate limiter all see the
real client address. GeoIP is not available (no MaxMind database).

## Cloudflare CDN

Production is fronted by Cloudflare (`seqandchem.com`, `www`, `stats`). `nginx-main.conf`:

- trusts the published Cloudflare IPv4/IPv6 ranges
- uses `CF-Connecting-IP` as `real_ip_header`
- direct traffic still arrives through the PROXY protocol and is unaffected

Cloudflare-side settings:

- SSL/TLS: Full (strict), Always Use HTTPS
- Brotli and HTTP/3 on; Rocket Loader off
- Cache Rule: bypass `/api/*`, `/health`
- Optional HTML cache: the app sends `s-maxage=300` on HTML; add a Cache Rule for
  `text/html` (edge TTL 5 minutes, browser TTL 60 seconds) and purge the zone after a deploy
- Versioned assets (`?v=...`) are served with one-year `immutable` caching; unversioned
  static files keep the one-day default
- update the trusted ranges from <https://www.cloudflare.com/ips/> when Cloudflare changes them

Cloudflare nameservers: `coby.ns.cloudflare.com`, `walk.ns.cloudflare.com`.

The origin's `/etc/resolv.conf` uses `1.1.1.1` and `9.9.9.9`; the host network blocks
`8.8.8.8`, which caused intermittent DNS failures. It is included in the daily backup.

## Direct API subdomain

`api.seqandchem.com` is a **DNS-only** record (no Cloudflare proxy) that serves only `/api/*` and
`/health` from the same gunicorn app. It exists because Cloudflare's free plan times out proxied
origin responses after 100 seconds, while `/api/v1/batch` can run longer. Certbot issues a separate
Let's Encrypt certificate for it; the main site, `www` and `stats` stay proxied.

Long batch clients can call `https://api.seqandchem.com/api/v1/batch` to bypass the CDN timeout.
The subdomain sends `X-Robots-Tag: noindex` and returns 404 for non-API paths. Batch requests are
allowed up to 64 MB; other API bodies are capped at 8 MB and feedback at 16 KB. The application's
batch timeout is 840 seconds, below the 900-second gunicorn/nginx proxy timeout.

nginx also enforces API fair use in `nginx-main.conf`: 120 requests/minute per client IP and
300/minute per vhost, with a small burst allowance. These are shared across gunicorn workers;
the Flask limiter remains as a second layer and returns `X-RateLimit-*` headers.

## Weekly SEO report

`seo-weekly.py` runs Mondays at 02:00 UTC and pushes a Feishu **interactive card** with:

- Google Search Console: indexed progress bar, 28-day totals, 7-day impression/click
  sparklines, top query/page, URL Inspection failures
- Bing Webmaster: sitemap status, queries, crawl issues, submission quota
- Cloudflare Web Analytics: 7-day page views/visits with sparklines (Analytics Read token)
- 12-week indexing history from `/opt/seqchem-monitor/seo-history.json` (mode 600)

Credentials live outside the repo, all mode 600:

```
/opt/seqchem-monitor/gsc-service-account.json      # GSC Full user on sc-domain:seqandchem.com
/opt/seqchem-monitor/bing-webmaster.env            # BING_WEBMASTER_API_KEY=...
/opt/seqchem-monitor/cloudflare-analytics.env      # CF_ANALYTICS_TOKEN=... (Account Analytics Read)
```

Dependencies are installed in `/opt/seqchem-monitor/venv`. Run manually with:

```bash
/opt/seqchem-monitor/venv/bin/python /opt/seqchem-monitor/seo-weekly.py
# dry run, no Feishu message:
DRY_RUN=1 /opt/seqchem-monitor/venv/bin/python /opt/seqchem-monitor/seo-weekly.py
```

## Anonymous feedback

The floating form on every page posts to `POST /api/feedback`. Rows are stored in
`/opt/chemtools/data/feedback.sqlite3` and contain only timestamp, category, page path and
message — no IP address, user agent or email. The database is included in the daily backup.

Read the latest entries with:

```bash
sqlite3 -header -column /opt/chemtools/data/feedback.sqlite3 \
  "select id, created_at, category, page, message from feedback order by id desc limit 50;"
```

The endpoint has a 2,000-character limit, a hidden honeypot field and an in-memory limit of
10 messages per client per hour.

`feedback-digest.py` runs at 01:15 UTC (09:15 Asia/Shanghai) and pushes yesterday's messages to
Feishu. It stays silent when there are zero new messages. Each message is normalised to one line
and truncated to 300 characters; at most five are included per digest.
