#!/usr/bin/env python3
"""Safe subscription and server management for Codaki Shadow VLESS.

CLI: shadow-vless preview-sub URL
     shadow-vless set-sub URL --mobile N
     shadow-vless nodes | select-mobile N | refresh | start | stop | status
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.request

D = Path(os.environ.get("SHADOW_VLESS_HOME", "/data/adb/gpt-vless"))
PY = "/data/data/com.termux/files/usr/bin/python"
SERVICE = "/data/adb/modules/gpt_vless_router/service.sh"
FILES = ["subscription.raw", "url.txt", "mobile-choice.json", "sub.decoded",
         "config.json", "xray-config.json", "standby.json", "fallback.json"]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update import decoded, nodes

def write(name, value):
    raw = value.encode("utf-8") if isinstance(value, str) else value
    tmp = D / (name + ".new")
    tmp.write_bytes(raw)
    os.chmod(tmp, 0o600)
    os.replace(tmp, D / name)

def download(url):
    if not url.startswith("https://"):
        raise RuntimeError("Subscription URL must start with https://")
    request = urllib.request.Request(url, headers={"User-Agent": "Codaki-Shadow-VLESS/0.0.3"})
    with urllib.request.urlopen(request, timeout=25) as resp:
        if not resp.url.startswith("https://"):
            raise RuntimeError("Refusing a non-HTTPS redirect")
        data = resp.read(2_000_001)
    if not 10 <= len(data) <= 2_000_000:
        raise RuntimeError("Subscription size is invalid")
    return data

def text_of(raw):
    import base64
    import binascii
    try:
        s = base64.b64decode(raw.strip(), validate=True).decode("utf-8")
        if "vless://" in s:
            return s
    except (ValueError, UnicodeDecodeError, binascii.Error):
        pass
    return raw.decode("utf-8")

def mobile_nodes(raw):
    return [x for x in nodes(text_of(raw)) if x[3] == "mobile"]

def show_nodes(raw):
    found = nodes(text_of(raw))
    n = 0
    for _, _, _, kind, label in found:
        if kind == "mobile":
            n += 1
            print(f"MOBILE {n}: {label}")
        else:
            print(f"WIFI: {label}")
    if not n:
        print("No TLS/XHTTP cellular nodes found")
    return n

def commit_subscription(raw, url=None, mobile_index=None):
    candidates = mobile_nodes(raw)
    if not candidates:
        raise RuntimeError("Subscription contains no VLESS TLS/XHTTP mobile server")
    if mobile_index is not None:
        if not 1 <= mobile_index <= len(candidates):
            raise RuntimeError(f"--mobile must be from 1 to {len(candidates)}")
        selected = candidates[mobile_index - 1]
        choice = {"fingerprint": hashlib.sha256(selected[0].encode()).hexdigest(),
                  "label": selected[4]}
    else:
        choice = json.loads((D / "mobile-choice.json").read_text())
        hashes = [hashlib.sha256(n[0].encode()).hexdigest() for n in candidates]
        if choice.get("fingerprint") not in hashes:
            raise RuntimeError("Pinned mobile node changed. Use set-sub URL --mobile N explicitly")
    old = {name: (D / name).read_bytes() if (D / name).exists() else None
           for name in FILES}
    try:
        write("subscription.raw", raw)
        if url is not None:
            write("url.txt", url + "\n")
        write("mobile-choice.json", json.dumps(choice, ensure_ascii=False))
        subprocess.run([PY, str(D / "generate.py")], check=True, timeout=65,
                       stdout=subprocess.DEVNULL)
        (D / "ready").touch(mode=0o600)
    except Exception:
        for name, data in old.items():
            path = D / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                write(name, data)
        raise
    print("Subscription and both VPN configs validated. Cellular server:", choice["label"])

def supervisor_pids():
    result = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="replace")
            if "python" in cmd and str(D / "failover.py") in cmd:
                result.append(int(entry.name))
        except (OSError, PermissionError):
            pass
    return result

def stop_service():
    (D / "manual-stop").touch(mode=0o600)
    for pid in supervisor_pids():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(15):
        if not supervisor_pids():
            break
        time.sleep(0.5)
    print("VPN supervisor stopped")

def start_service():
    if not (D / "ready").exists():
        raise RuntimeError("First set a VLESS subscription and explicitly select the mobile server")
    if supervisor_pids():
        print("VPN supervisor already running")
        return
    (D / "manual-stop").unlink(missing_ok=True)
    logfile = open(D / "boot.log", "ab", buffering=0)
    subprocess.Popen(["/system/bin/sh", SERVICE], stdin=subprocess.DEVNULL,
                     stdout=logfile, stderr=subprocess.STDOUT,
                     close_fds=True, start_new_session=True)
    logfile.close()
    print("VPN supervisor launched")

def main():
    if os.geteuid() != 0:
        raise SystemExit("Root is REQUIRED. Run via su -c or a root Mini Codex agent.")
    parser = argparse.ArgumentParser(prog="shadow-vless")
    subs = parser.add_subparsers(dest="command", required=True)
    for cmd in ["status", "nodes", "refresh", "start", "stop"]:
        subs.add_parser(cmd)
    preview = subs.add_parser("preview-sub")
    preview.add_argument("url")
    setsub = subs.add_parser("set-sub")
    setsub.add_argument("url")
    setsub.add_argument("--mobile", type=int, required=True)
    choose = subs.add_parser("select-mobile")
    choose.add_argument("index", type=int)
    args = parser.parse_args()
    D.mkdir(parents=True, exist_ok=True)
    os.chmod(D, 0o700)
    if args.command == "preview-sub":
        show_nodes(download(args.url))
    elif args.command == "set-sub":
        commit_subscription(download(args.url), args.url, args.mobile)
        stop_service()
        start_service()
    elif args.command == "select-mobile":
        commit_subscription((D / "subscription.raw").read_bytes(), mobile_index=args.index)
        stop_service()
        start_service()
    elif args.command == "refresh":
        url = (D / "url.txt").read_text().strip()
        commit_subscription(download(url))
        stop_service()
        start_service()
    elif args.command == "nodes":
        show_nodes((D / "subscription.raw").read_bytes())
    elif args.command == "stop":
        stop_service()
    elif args.command == "start":
        start_service()
    elif args.command == "status":
        p = D / "status.json"
        print(p.read_text() if p.exists() else '{"state":"not_running"}')
        choice = D / "mobile-choice.json"
        if choice.exists():
            print("Pinned cellular node:", json.loads(choice.read_text()).get("label", "(unnamed)"))
        print("Configured:", (D / "ready").exists(), "Running:", bool(supervisor_pids()))
if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SystemExit("Error: " + str(exc))
