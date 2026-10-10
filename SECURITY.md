# Security and privacy

This is a root networking module. It can change Android routing, TUN interfaces,
policy rules and DNS interception. Review the code and maintain a device backup.

## Never submit these to GitHub
Subscription URLs, VLESS UUIDs, Reality keys, server addresses, logs with
connection identifiers, generated JSON configs, Clash API secrets, tokens,
or screenshots containing subscription links. Sensitive runtime files belong
only in /data/adb/gpt-vless, mode 0600, owned by root.

Report potential vulnerabilities privately to the maintainer through GitHub's
security reporting options if enabled, rather than sharing credentials in issues.

## Operational notes
- Install with pre-existing root and a compatible Magisk module implementation.
- Do not install to a phone that already has a gpt_vless_router module without
  reviewing and explicitly migrating its existing configuration.
- A pinned cellular node is never replaced by a different node during refresh.
- This is not a guaranteed kill switch. During a failover/standby recovery,
  non-VPN direct connectivity may be restored by Android.
- Upstream engines are independently maintained software, not bundled here.
