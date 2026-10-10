"""Capture Android app DNS before private LAN routes bypass the TUN."""
import subprocess
from pathlib import Path
CHAIN='GCV_DNS'
MARKER=Path('/data/adb/gpt-vless/dns-capture-owned')
def run(binary,args,check=False):
    p=subprocess.run([binary,'-w','5','-t','nat']+args,capture_output=True,timeout=8)
    if check and p.returncode:raise RuntimeError('DNS interception firewall command failed')
    return p.returncode==0
def set_enabled(enabled):
    for binary in ['/system/bin/iptables','/system/bin/ip6tables']:
        if not run(binary,['-S']):continue  # IPv6 NAT is absent on this Android kernel.
        exists=run(binary,['-S',CHAIN])
        if exists and not MARKER.exists():
            raise RuntimeError('DNS interception chain belongs to another service')
        while run(binary,['-C','OUTPUT','-j',CHAIN]):
            run(binary,['-D','OUTPUT','-j',CHAIN],True)
        if exists:
            run(binary,['-F',CHAIN],True)
            if not enabled:run(binary,['-X',CHAIN],True)
        if enabled:
            MARKER.touch(mode=0o600)
            if not exists:run(binary,['-N',CHAIN],True)
            run(binary,['-A',CHAIN,'-m','owner','--uid-owner','0','-j','RETURN'],True)
            for protocol in ['udp','tcp']:
                run(binary,['-A',CHAIN,'-p',protocol,'--dport','53','-j','REDIRECT','--to-ports','15353'],True)
            run(binary,['-I','OUTPUT','1','-j',CHAIN],True)

