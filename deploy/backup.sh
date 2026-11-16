#!/bin/bash
# SeqChem daily backup: GoatCounter + feedback SQLite, configs and app source.
# Backups stay on this server, newest 7 kept.
set -euo pipefail
umask 077

DEST=/var/backups/seqchem
DATE=$(date +%F_%H%M%S)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DEST"

# 1) Consistent SQLite snapshot (WAL-safe)
sqlite3 /opt/goatcounter/goatcounter-data/db.sqlite3 ".backup '$TMP/goatcounter.sqlite3'"
if [ "$(sqlite3 "$TMP/goatcounter.sqlite3" 'PRAGMA integrity_check;')" != "ok" ]; then
    echo "$(date '+%F %T') FAIL goatcounter integrity_check" >&2
    exit 1
fi
if [ -f /opt/chemtools/data/feedback.sqlite3 ]; then
    sqlite3 /opt/chemtools/data/feedback.sqlite3 ".backup '$TMP/feedback.sqlite3'"
    if [ "$(sqlite3 "$TMP/feedback.sqlite3" 'PRAGMA integrity_check;')" != "ok" ]; then
        echo "$(date '+%F %T') FAIL feedback integrity_check" >&2
        exit 1
    fi
fi

# 2) Config + app source (no venv, no caches)
crontab -l > "$TMP/root-crontab.txt" 2>/dev/null || true
tar -czf "$TMP/config.tar.gz" --ignore-failed-read \
    --exclude='/opt/seqchem-monitor/venv' \
    --exclude='__pycache__' \
    /etc/nginx/nginx.conf \
    /etc/nginx/sites-available/seqchem \
    /etc/nginx/sites-available/stats \
    /etc/resolv.conf \
    /etc/systemd/system/chemtools.service \
    /etc/systemd/system/goatcounter.service \
    /opt/seqchem-monitor \
    /opt/chemtools/app.py \
    /opt/chemtools/bio.py \
    /opt/chemtools/formula.py \
    /opt/chemtools/guides.py \
    /opt/chemtools/presets.py \
    /opt/chemtools/templates \
    /opt/chemtools/static \
    /etc/letsencrypt/renewal/seqandchem.com.conf \
    /etc/letsencrypt/renewal/stats.seqandchem.com.conf \
    /etc/letsencrypt/renewal/api.seqandchem.com.conf \
    /etc/logrotate.d/seqchem-monitor \
    -C "$TMP" root-crontab.txt \
    2>/dev/null

# 3) Single archive + checksum
tar -czf "$DEST/seqchem-$DATE.tar.gz" -C "$TMP" .
( cd "$DEST" && sha256sum "seqchem-$DATE.tar.gz" > "seqchem-$DATE.tar.gz.sha256" )
ln -sfn "seqchem-$DATE.tar.gz" "$DEST/latest.tar.gz"

# 4) Retention: keep only the newest 7 archives (+ their checksums)
ls -1t "$DEST"/seqchem-*.tar.gz 2>/dev/null | tail -n +8 | while read -r old; do
    rm -f "$old" "$old.sha256"
done

SIZE=$(du -h "$DEST/seqchem-$DATE.tar.gz" | cut -f1)
COUNT=$(ls -1 "$DEST"/seqchem-*.tar.gz 2>/dev/null | wc -l)
echo "$(date '+%F %T') OK $SIZE archives=$COUNT file=seqchem-$DATE.tar.gz"
