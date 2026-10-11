#!/usr/bin/env python3
import json, os, pathlib, re, subprocess, urllib.parse
D=pathlib.Path('/data/adb/gpt-vless')
PY='/data/data/com.termux/files/usr/bin/python'
subprocess.run([PY,str(D/'update.py')],check=True,stdout=subprocess.DEVNULL)
base=json.loads((D/'config.json').read_text())
base['inbounds']=[x for x in base['inbounds'] if x.get('type')!='tun']
base['route']={'auto_detect_interface':True,'default_domain_resolver':'bootstrap','final':'auto-choice'}
# Use every compatible VLESS Reality endpoint from the user's own subscription.
wifi_tags=[]
lines=(D/'sub.decoded').read_text().splitlines()
counter=0
for line in lines:
 try:
  p=urllib.parse.urlsplit(line.strip())
  if p.scheme!='vless':continue
  params=dict(urllib.parse.parse_qsl(p.query))
  if params.get('type','tcp')!='tcp' or params.get('security')!='reality':continue
  counter+=1
  wifi_tags.append(f'w-{counter:02}')
 except:continue
if not wifi_tags: raise RuntimeError('Subscription must have at least one VLESS Reality TCP node')
base['outbounds']=[o for o in base['outbounds'] if o.get('tag')!='auto-choice']
for o in base['outbounds']:
 if o.get('tag')=='wifi':o['outbounds']=wifi_tags
base['outbounds'].insert(0,{'type':'selector','tag':'auto-choice','outbounds':['wifi','mobile'],'default':'wifi','interrupt_exist_connections':True})
base['route'].pop('rules',None)
base['inbounds'] += [
 {'type':'direct','tag':'app-dns-v4','listen':'127.0.0.1','listen_port':15353},
 {'type':'direct','tag':'app-dns-v6','listen':'::1','listen_port':15353}]
base['route']['rules']=[{'inbound':['app-dns-v4','app-dns-v6'],'action':'hijack-dns'}]

# Bootstrap VPN endpoints on the underlying network; resolve app names via DoH.
base['dns']={
 'servers':[
  {'type':'https','tag':'bootstrap','server':'1.1.1.1','tls':{'enabled':True,'server_name':'cloudflare-dns.com'}},
  {'type':'https','tag':'secure','server':'1.1.1.1',
   'tls':{'enabled':True,'server_name':'cloudflare-dns.com'},
   'detour':'auto-choice'}],
 'final':'secure','strategy':'prefer_ipv4','timeout':'8s'}

globalcfg=json.loads(json.dumps(base))
globalcfg['route']['rules']=[{'inbound':['app-dns-v4','app-dns-v6'],'action':'hijack-dns'},{'port':53,'action':'hijack-dns'},{'protocol':'dns','action':'hijack-dns'},{'network':'udp','port':443,'action':'reject','no_drop':True}]
globalcfg['inbounds'].append({
 'type':'tun','tag':'global','interface_name':'gpttun0',
 'address':['172.19.0.1/30','fd00:0419:0419::1/126'],
 'mtu':1400,'auto_route':True,'auto_redirect':True,'stack':'mixed',
 'exclude_uid':[0],
 'route_exclude_address':['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16','224.0.0.0/4','fc00::/7','fe80::/10','ff00::/8']})
import ru_direct
ru_direct.patch_tun(globalcfg)
for name,obj in [('standby.json',base),('fallback.json',globalcfg)]:
 p=D/name
 tmp=p.with_name(name+'.tmp')
 tmp.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')))
 os.chmod(tmp,0o600);os.replace(tmp,p)
 subprocess.run([str(D/'core'),'check','-c',str(p)],check=True,stdout=subprocess.DEVNULL)
subprocess.run([str(D/'xray'),'run','-test','-config',str(D/'xray-config.json')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('configs_valid standby=true fallback=true wifi_safe_nodes='+str(len(wifi_tags))+' mobile_xhttp_nodes=2')
