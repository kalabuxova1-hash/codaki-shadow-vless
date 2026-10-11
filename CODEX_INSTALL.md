# Codaki Shadow VLESS — instructions for Codex / Mini Codex

Version **0.0.2**. Repository: https://github.com/kalabuxova1-hash/codaki-shadow-vless

## Task for the installation agent

Install **this project's own root VLESS router** on the owner's Android device. Never root the device, install Magisk, disable root, alter the owner's unrelated VPNs or export their personal VLESS credentials.

1. Check Android root (id -u = 0), arm64-v8a (getprop ro.product.cpu.abi), /data/adb/modules (Magisk-compatible modules) and existing Termux Python at /data/data/com.termux/files/usr/bin/python. If missing, stop and report the unmet prerequisite.
2. Check /data/adb/gpt-vless/config.json and /data/adb/modules/gpt_vless_router/module.prop. If either already exists, **never overwrite the live installation**. Use its management CLI instead.
3. On a new phone, review and run bootstrap.sh as Android root. It retrieves project files and calls scripts/install.sh, which downloads pinned official sing-box/Xray releases with SHA-256 verification. PC Codex can clone the repository, upload it via ADB and run scripts/install.sh using adb shell su -c.
4. The framework installs INACTIVE. The owner must provide a private HTTPS VLESS subscription and designate a specific mobile server; never upload the URL or VLESS credentials to GitHub.
5. On the rooted phone run: shadow-vless preview-sub 'SUBSCRIPTION_URL'. List MOBILE (TLS/XHTTP) servers by number. WIFI (Reality/TCP) servers may use latency-based auto-selection.
6. Run: shadow-vless set-sub 'SUBSCRIPTION_URL' --mobile NUMBER. Configs must validate before activation. If selected cellular server is missing or changes in future subscription refreshes, stop rather than auto-select a replacement.
7. Check shadow-vless status, network reachability, TUN gpttun0, and report whether the service really works. Do not claim support for untested devices.

Executable path: /data/adb/gpt-vless/shadow-vless. Mini Codex uses its root shell; desktop Codex can use ADB plus su.

## Maintenance by Mini Codex (no reinstall)

- shadow-vless nodes — see local server labels and cellular numbers
- shadow-vless preview-sub 'https://...' — inspect an alternative subscription
- shadow-vless set-sub 'https://...' --mobile 2 — replace subscription and pin a specific mobile server
- shadow-vless select-mobile 1 — change mobile server within the current subscription
- shadow-vless refresh — refresh saved subscription, never change the pinned server silently
- shadow-vless status — show status and selected server
- shadow-vless start / stop — control service

## Architecture

Source is adapted directly from the owner's running /data/adb/gpt-vless and gpt_vless_router Magisk-compatible module, with all private configurations omitted. Uses sing-box 1.14.2 and Xray 26.9.9. Has automatic network-type selection, independent root TUN when no other Android VPN is active, standby while another Android VPN runs, DNS capture and process recovery. Cellular routing is explicitly pinned to one chosen XHTTP server; Wi-Fi Reality nodes may be automatically tested. This is NOT a standalone VPN APK.

Root/Magisk/Termux are PRE-EXISTING requirements; the project does not install or modify them. Version 0.0.2 targets ARM64 Android with compatible root, TUN/ip rules/iptables and Termux Python. Other ROMs are not yet validated.

## Upgrade of an existing installation (v0.0.2 source)

The existing-installation guard is intentional: do not rerun the fresh-install bootstrap. For an owner-authorized upgrade, compare the current and repository `failover.py`, back up the local original, copy only the verified generic source, run Python syntax/tests without touching `api.secret`, `subscription.raw`, `url.txt` or generated configs, and restart the supervisor only if a recoverable connectivity path is available. Verify VK UID direct routing on the active network and the continued VLESS routing of unrelated apps. Never publish logs or private node details. On existing devices, a repository source update alone does not update the running agent; report that limitation.
