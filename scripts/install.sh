#!/system/bin/sh
# Root Android installation of the owner's project. Root/Termux are prerequisites.
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
D=/data/adb/gpt-vless
MOD=/data/adb/modules/gpt_vless_router
PY=/data/data/com.termux/files/usr/bin/python
SB_VERSION=1.14.2
XRAY_VERSION=26.9.9
TMP=/data/local/tmp/codaki-shadow-vless-install-$$
[ "$(id -u)" = "0" ] || { echo "ERROR: Run as Android root"; exit 1; }
[ -x "$PY" ] || { echo "ERROR: Termux with Python is required (not installed by this script)"; exit 1; }
[ -d /data/adb/modules ] || { echo "ERROR: Magisk-compatible module directory missing"; exit 1; }
[ "$(getprop ro.product.cpu.abi)" = "arm64-v8a" ] || { echo "ERROR: v0.0.2 supports only Android arm64-v8a"; exit 1; }
[ ! -e "$D/config.json" ] && [ ! -e "$MOD/module.prop" ] || {
    echo "ERROR: Existing VLESS installation found; refusing to overwrite or disconnect it"
    exit 1
}
for p in src/failover.py src/generate.py src/update.py src/manage.py src/dns_capture.py magisk/module.prop magisk/service.sh; do
    [ -s "$BASE/$p" ] || { echo "ERROR: Missing $p"; exit 1; }
done
mkdir -p "$TMP" "$D" "$MOD"
chmod 700 "$D" "$MOD"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
SB_ARCHIVE=sing-box-$SB_VERSION-android-arm64.tar.gz
XR_ARCHIVE=Xray-android-arm64-v8a.zip
SB_URL=https://github.com/SagerNet/sing-box/releases/download/v1.14.2/sing-box-1.14.2-android-arm64.tar.gz
XR_URL=https://github.com/XTLS/Xray-core/releases/download/v26.9.9/Xray-android-arm64-v8a.zip
curl -fL --retry 3 --connect-timeout 15 --max-time 180 "$SB_URL" -o "$TMP/$SB_ARCHIVE"
curl -fL --retry 3 --connect-timeout 15 --max-time 180 "$XR_URL" -o "$TMP/$XR_ARCHIVE"
# Official GitHub release SHA-256 digests; fail closed when unavailable.
curl -fLsS --connect-timeout 10 --max-time 35 \
 "https://api.github.com/repos/SagerNet/sing-box/releases/tags/v1.14.2" -o "$TMP/sb-release.json"
curl -fLsS --connect-timeout 10 --max-time 35 \
 "https://api.github.com/repos/XTLS/Xray-core/releases/tags/v26.9.9" -o "$TMP/xray-release.json"
"$PY" - "$TMP" "$SB_ARCHIVE" "$XR_ARCHIVE" <<'PYTHON'
import hashlib,json,pathlib,sys
d=pathlib.Path(sys.argv[1])
for release,name in [('sb-release.json',sys.argv[2]),('xray-release.json',sys.argv[3])]:
    data=json.loads((d/release).read_text())
    assets=[x for x in data.get('assets',[]) if x.get('name')==name]
    if len(assets)!=1 or not assets[0].get('digest','').startswith('sha256:'):
        raise SystemExit('ERROR: Official release SHA-256 missing for '+name)
    expected=assets[0]['digest'].split(':',1)[1].lower()
    actual=hashlib.sha256((d/name).read_bytes()).hexdigest()
    if actual!=expected:
        raise SystemExit('ERROR: SHA-256 mismatch: '+name)
    print('Verified official release SHA-256:',name)
PYTHON
tar -xzf "$TMP/$SB_ARCHIVE" -C "$TMP"
unzip -oq "$TMP/$XR_ARCHIVE" xray -d "$TMP"
cp "$TMP/sing-box-$SB_VERSION-android-arm64/sing-box" "$D/core"
cp "$TMP/xray" "$D/xray"
chmod 700 "$D/core" "$D/xray"
for name in failover generate update manage dns_capture; do
    cp "$BASE/src/$name.py" "$D/$name.py"
    chmod 700 "$D/$name.py"
done
"$PY" - "$D" <<'PYTHON'
import os,pathlib,secrets,sys
d=pathlib.Path(sys.argv[1])
p=d/'api.secret'
if not p.exists():
    p.write_text(secrets.token_hex(24)+'\n')
    os.chmod(p,0o600)
PYTHON
cp "$BASE/magisk/module.prop" "$MOD/module.prop"
cp "$BASE/magisk/service.sh" "$MOD/service.sh"
chmod 600 "$MOD/module.prop"
chmod 700 "$MOD/service.sh"
cat > "$D/shadow-vless" <<'CLI'
#!/system/bin/sh
exec /data/data/com.termux/files/usr/bin/python /data/adb/gpt-vless/manage.py "$@"
CLI
chmod 700 "$D/shadow-vless"
"$D/core" version | head -1
"$D/xray" version | head -1
echo "Codaki Shadow VLESS framework installed (INACTIVE)."
echo "Next: shadow-vless preview-sub 'https://YOUR-PRIVATE-SUBSCRIPTION'"
echo "Then: shadow-vless set-sub 'https://YOUR-PRIVATE-SUBSCRIPTION' --mobile N"
echo "Root/Magisk/Termux were prerequisites, not installed by this project."
