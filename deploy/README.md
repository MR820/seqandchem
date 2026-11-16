# Deployment

Production runs on a single Debian/Ubuntu host.

| File | Goes to | Notes |
|---|---|---|
| `chemtools.service` | `/etc/systemd/system/` | gunicorn, 2 workers, `127.0.0.1:8080`, 900 MB memory cap |
| `nginx.conf` | `/etc/nginx/sites-available/seqchem` | TLS termination, headers, proxies to gunicorn |
| `nginx-main.conf` | `/etc/nginx/nginx.conf` | stream layer: SNI routing on 443 + PROXY protocol |
| `daily-report.sh` | `/opt/seqchem-monitor/` | cron `0 1 * * *`; needs `feishu.env` alongside |
| `backup.sh` | `/opt/seqchem-monitor/` | cron `30 1 * * *`; SQLite + configs, newest 7 in `/var/backups/seqchem` |
| `uptime-check.sh` | `/opt/seqchem-monitor/` | cron `*/5 * * * *`; main site + api `/health` + services, Feishu on state change |
| `seo-weekly.py` | `/opt/seqchem-monitor/` | cron `0 2 * * 1`; GSC + Bing + GoatCounter → Feishu interactive card; needs `gsc-service-account.json` and `bing-webmaster.env` |
| `feedback-digest.py` | `/opt/seqchem-monitor/` | cron `15 1 * * *`; yesterday's feedback → Feishu, only when count > 0 |

## First-time setup

```bash
apt install openbabel nginx python3-venv
useradd -r -s /usr/sbin/nologin chemtools
mkdir -p /opt/chemtools
# copy app.py bio.py formula.py guides.py presets.py templates/ static/
python3 -m venv /opt/chemtools/venv
/opt/chemtools/venv/bin/pip install -r requirements.txt
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

`deploy/github-actions/uptime.yml` is the external monitor template. Copy it to
`.github/workflows/uptime.yml` after enabling a GitHub token with `workflow` scope. It runs on
GitHub-hosted infrastructure every 15 minutes, so it still works when the SeqChem host or its
network is down. It checks the public homepage, both `/health`
endpoints and a real `/api/v1/convert` call. Add the repository secret `FEISHU_WEBHOOK` (a Feishu custom-bot webhook) to receive a text alert
on failure; without the secret, the failed GitHub
Actions run is still visible in the repository. Use “Run workflow” on the workflow page for a
manual check.

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
real client address. GeoIP is still unavailable — GoatCounter needs a MaxMind database
(`-geodb`) for country data.

## Cloudflare CDN

Production is fronted by Cloudflare (`seqandchem.com`, `www`, `stats`). `nginx-main.conf`:

- trusts the published Cloudflare IPv4/IPv6 ranges
- uses `CF-Connecting-IP` as `real_ip_header`
- direct traffic still arrives through the PROXY protocol and is unaffected

Cloudflare-side settings:

- SSL/TLS: Full (strict), Always Use HTTPS
- Brotli and HTTP/3 on; Rocket Loader off
- Cache Rule: bypass `/api/*`, `/count`, `/count.js`, `/user/*`, `/health`
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
- GoatCounter: last-7-day PV/UV sparklines, top-page bars and tool events
- 12-week indexing history from `/opt/seqchem-monitor/seo-history.json` (mode 600)

Credentials live outside the repo, both mode 600:

```
/opt/seqchem-monitor/gsc-service-account.json   # GSC Full user on sc-domain:seqandchem.com
/opt/seqchem-monitor/bing-webmaster.env         # BING_WEBMASTER_API_KEY=...
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
