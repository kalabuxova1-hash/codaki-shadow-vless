#!/system/bin/sh
# Root-only zero-git bootstrap for Mini Codex. Source can be reviewed before running.
set -eu
[ "$(id -u)" = 0 ] || { echo "ERROR: root required"; exit 1; }
TMP=/data/local/tmp/codaki-shadow-vless-source-$$
RAW=https://raw.githubusercontent.com/kalabuxova1-hash/codaki-shadow-vless/main
mkdir -p "$TMP/src" "$TMP/scripts" "$TMP/magisk"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
for f in src/failover.py src/generate.py src/update.py src/manage.py src/dns_capture.py magisk/module.prop magisk/service.sh scripts/install.sh; do
    curl -fLsS --connect-timeout 12 --max-time 35 "$RAW/$f" -o "$TMP/$f"
    [ -s "$TMP/$f" ] || { echo "Source missing: $f"; exit 1; }
done
/system/bin/sh "$TMP/scripts/install.sh"
