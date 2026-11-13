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
The subdomain sends `X-Robots-Tag: noindex` and returns 404 for non-API paths.
