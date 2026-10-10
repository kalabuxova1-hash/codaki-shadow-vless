#!/usr/bin/env python3
"""Convert the owner's VLESS subscription into local sing-box + Xray configs.

No subscription or credentials are shipped with this project. The cellular
server is selected by a persistent SHA-256 fingerprint, never by urltest.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

D = Path(os.environ.get("SHADOW_VLESS_HOME", "/data/adb/gpt-vless"))
def atomic(name, data):
    path = D / name
    tmp = D / (name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)

def decoded():
    blob = (D / "subscription.raw").read_bytes().strip()
    try:
        raw = base64.b64decode(blob, validate=True).decode("utf-8")
        if "vless://" not in raw:
            raise ValueError()
        return raw
    except (ValueError, UnicodeDecodeError):
        return blob.decode("utf-8")

def nodes(text):
    result = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw.startswith("vless://"):
            continue
        try:
            p = urlsplit(raw)
            q = dict(parse_qsl(p.query))
            if not (p.username and p.hostname and p.port):
                continue
            transport = q.get("type", "tcp")
            security = q.get("security", "")
            if transport == "xhttp" and security == "tls":
                kind = "mobile"
            elif transport == "tcp" and security == "reality" and q.get("pbk"):
                kind = "wifi"
            else:
                continue
            result.append((raw, p, q, kind, unquote(p.fragment or "Unnamed")))
        except (ValueError, TypeError):
            continue
    return result

def main():
    D.mkdir(mode=0o700, parents=True, exist_ok=True)
    text = decoded()
    found = nodes(text)
    wifi_nodes = [entry for entry in found if entry[3] == "wifi"]
    mobile_nodes = [entry for entry in found if entry[3] == "mobile"]
    if not wifi_nodes or not mobile_nodes:
        raise SystemExit("Subscription requires Reality/TCP Wi-Fi and TLS/XHTTP mobile endpoints")
    choice = json.loads((D / "mobile-choice.json").read_text())
    fingerprint = choice.get("fingerprint")
    selected = [entry for entry in mobile_nodes if hashlib.sha256(entry[0].encode()).hexdigest() == fingerprint]
    if len(selected) != 1:
        raise SystemExit("Chosen cellular server is missing/changed: reselect it explicitly (never auto-pick)")
    raw, p, q, _, label = selected[0]
    tls_settings = {"serverName": q.get("sni", p.hostname), "fingerprint": q.get("fp", "chrome")}
    if q.get("alpn"):
        tls_settings["alpn"] = q["alpn"].split(",")
    xhttp = {"path": q.get("path", "/"), "mode": q.get("mode", "auto")}
    if q.get("host"):
        xhttp["host"] = q["host"]
    if q.get("extra"):
        xhttp["extra"] = json.loads(q["extra"])
    xray = {
        "log": {"loglevel": "warning"},
        "inbounds": [{"tag": "cell-socks", "listen": "127.0.0.1", "port": 17891,
                      "protocol": "socks", "settings": {"udp": True}}],
        "outbounds": [{"protocol": "vless", "tag": "chosen-cellular",
                       "settings": {"vnext": [{"address": p.hostname, "port": p.port,
                                                "users": [{"id": p.username, "encryption": "none"}]}]},
                       "streamSettings": {"network": "xhttp", "security": "tls",
                                          "tlsSettings": tls_settings, "xhttpSettings": xhttp}}],
        "routing": {"domainStrategy": "AsIs", "rules": [
            {"type": "field", "inboundTag": ["cell-socks"], "outboundTag": "chosen-cellular"}]}
    }
    out_wifi = []
    for idx, (raw, wp, wq, _, wname) in enumerate(wifi_nodes, 1):
        tls = {"enabled": True, "server_name": wq.get("sni", wp.hostname),
               "utls": {"enabled": True, "fingerprint": wq.get("fp", "chrome")},
               "reality": {"enabled": True, "public_key": wq["pbk"], "short_id": wq.get("sid", "")}}
        if wq.get("alpn"):
            tls["alpn"] = wq["alpn"].split(",")
        vless = {"type": "vless", "tag": f"w-{idx:02}", "server": wp.hostname,
                 "server_port": wp.port, "uuid": wp.username, "tls": tls}
        if wq.get("flow"):
            vless["flow"] = wq["flow"]
        out_wifi.append(vless)
    sb = {
        "log": {"level": "warn", "timestamp": True},
        "dns": {"servers": [{"type": "udp", "tag": "cf", "server": "1.1.1.1"},
                            {"type": "udp", "tag": "google", "server": "8.8.8.8"}],
                "final": "cf", "strategy": "prefer_ipv4"},
        "inbounds": [{"type": "mixed", "tag": "local-test", "listen": "127.0.0.1",
                      "listen_port": 17890}],
        "outbounds": [
            {"type": "urltest", "tag": "wifi", "outbounds": [n["tag"] for n in out_wifi],
             "url": "https://www.gstatic.com/generate_204", "interval": "3m", "tolerance": 50},
            {"type": "selector", "tag": "mobile", "outbounds": ["m-1"], "default": "m-1"},
            {"type": "socks", "tag": "m-1", "server": "127.0.0.1", "server_port": 17891},
            {"type": "direct", "tag": "direct"},
            *out_wifi],
        "route": {"final": "wifi", "auto_detect_interface": True,
                  "default_domain_resolver": "cf"},
        "experimental": {"clash_api": {"external_controller": "127.0.0.1:19090",
                       "secret": (D / "api.secret").read_text().strip()}}
    }
    atomic("sub.decoded", text)
    atomic("xray-config.json", json.dumps(xray, ensure_ascii=False, separators=(",", ":")))
    atomic("config.json", json.dumps(sb, ensure_ascii=False, separators=(",", ":")))
    print(f"validated_nodes: wifi={len(out_wifi)} cellular={len(mobile_nodes)} selected_cellular=explicit")
if __name__ == "__main__":
    main()
