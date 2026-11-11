# Deployment

Production runs on a single Debian/Ubuntu host.

| File | Goes to | Notes |
|---|---|---|
| `chemtools.service` | `/etc/systemd/system/` | gunicorn, 2 workers, `127.0.0.1:8080`, 400 MB memory cap |
| `nginx.conf` | `/etc/nginx/sites-available/seqchem` | TLS termination, proxies to gunicorn |
| `daily-report.sh` | `/opt/seqchem-monitor/` | cron `0 1 * * *`; needs `feishu.env` alongside |

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
