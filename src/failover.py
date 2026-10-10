#!/usr/bin/env python3
import fcntl,json,os,pathlib,re,signal,subprocess,time,urllib.request,urllib.error
D=pathlib.Path('/data/adb/gpt-vless')
LOCK=open(D/'failover.lock','a+')
try: fcntl.flock(LOCK,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError: raise SystemExit(0)
os.umask(0o077)
PY='/data/data/com.termux/files/usr/bin/python'
CORE=str(D/'core')
XRAY=str(D/'xray')
secret=(D/'api.secret').read_text().strip()
cp=None;xp=None
def log(s):
 p=D/'failover.log'
 if p.exists() and p.stat().st_size>500000: p.rename(D/'failover.log.1')
 with open(p,'a') as f:f.write(time.strftime('%Y-%m-%d %H:%M:%S ')+s+'\n')
def save(obj):
 p=D/'status.json.tmp'
 p.write_text(json.dumps(obj))
 os.replace(p,D/'status.json')
def spawn(name,args):
 log('start_'+name)
 f=open(D/(name+'.log'),'ab',buffering=0)
 p=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
 (D/(name+'.pid')).write_text(str(p.pid))
 return p
def stop(p,name):
 if not p:return
 try:
  p.terminate()
  p.wait(timeout=5)
 except Exception:
  try:p.kill();p.wait(timeout=2)
  except Exception:pass
 log('stop_'+name)
def network():
 try:
  s=subprocess.check_output(['/system/bin/dumpsys','connectivity'],timeout=5,stderr=subprocess.DEVNULL).decode(errors='replace')
  vpn=bool(re.search(r'VPN CONNECTED extra: VPN:',s))
  happ=('VPN CONNECTED extra: VPN:su.happ.proxyutility' in s)
  m=re.search(r'Active default network:\s*(\d+)',s)
  kind=None
  if m:
   a=re.search(r'NetworkAgentInfo\{network\{'+m.group(1)+r'\}[^\n]*?ni\{(WIFI|MOBILE)',s)
   if a:kind='wifi' if a.group(1)=='WIFI' else 'mobile'
  return vpn,happ,kind,(m.group(1) if m else None)
 except Exception:return None,None,None,None
def selected(mode):
 req=urllib.request.Request('http://127.0.0.1:19090/proxies/auto-choice',
   data=json.dumps({'name':mode}).encode(),
   headers={'Authorization':'Bearer '+secret,'Content-Type':'application/json'},method='PUT')
 try:
  with urllib.request.urlopen(req,timeout=2) as resp:return resp.status in (200,204)
 except Exception:return False
def proxy_ok():
 # 401 proves the unauthenticated mobile GPT API is reachable.
 import concurrent.futures
 opener=urllib.request.build_opener(urllib.request.ProxyHandler(
   {'https':'http://127.0.0.1:17890'}))
 def check(item):
  url,accepted=item
  try:
   with opener.open(url,timeout=7) as response:code=response.status
  except urllib.error.HTTPError as error:code=error.code
  except Exception:return False
  return code in accepted
 targets=[('https://www.gstatic.com/generate_204',{204}),
          ('https://www.cloudflare.com/cdn-cgi/trace',{200})]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  return all(pool.map(check,targets))

policy_state=None
def tun_policy(enabled):
 global policy_state
 if enabled==policy_state:return
 # Android may pre-bind a socket's source address. Cover those local sockets,
 # while excluding UID 0 to keep the VPN transport out of its own tunnel.
 for family in ['-4','-6']:
  command=['/system/bin/ip',family,'rule']
  existing=subprocess.check_output(command+['show']).decode()
  owned_old=['pref','8999','not','uidrange','0-0','iif','lo','lookup','2022']
  owned_new=['pref','8999','iif','lo','uidrange','1-2147483647','lookup','2022']
  lines=[line for line in existing.splitlines() if line.startswith('8999:')]
  for line in lines:
   if 'uidrange 0-0' in line and 'not from all' in line and 'lookup 2022' in line:
    subprocess.run(command+['del']+owned_old,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   elif 'uidrange 1-2147483647' in line and 'iif lo' in line and 'lookup 2022' in line:
    if not enabled:
     subprocess.run(command+['del']+owned_new,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   else:raise RuntimeError('Policy priority already belongs to another service')
  if enabled:
   existing=subprocess.check_output(command+['show']).decode()
   if not any(line.startswith('8999:') for line in existing.splitlines()):
    subprocess.run(command+['add']+owned_new,check=True)
 import dns_capture
 dns_capture.set_enabled(enabled)
 policy_state=enabled
 log('android_bound_socket_capture='+str(enabled))

def current_tun():
 return pathlib.Path('/sys/class/net/gpttun0').exists()
def generate():
 a=subprocess.run([PY,str(D/'generate.py')],capture_output=True,timeout=40)
 if a.returncode:
  log('generate_failed '+a.stderr.decode(errors='replace')[-200:])
  raise RuntimeError('invalid configs')
def startcore(mode):
 # Set the correct initial outbound before exposing the TUN to Android.
 source=D/('fallback.json' if mode=='fallback' else 'standby.json')
 config=json.loads(source.read_text())
 for outbound in config['outbounds']:
  if outbound.get('tag')=='auto-choice':outbound['default']=preferred
 runtime=D/('runtime-'+mode+'.json')
 temp=runtime.with_suffix('.tmp')
 temp.write_text(json.dumps(config,ensure_ascii=False,separators=(',',':')))
 os.chmod(temp,0o600);os.replace(temp,runtime)
 return spawn('core-'+mode,[CORE,'run','-c',str(runtime)])
def exit_handler(*args):
 global stop_requested
 stop_requested=True
stop_requested=False
signal.signal(signal.SIGTERM,exit_handler)
signal.signal(signal.SIGINT,exit_handler)
log('supervisor_boot')
tun_policy(False)
generate()
xp=spawn('xray',[XRAY,'run','-config',str(D/'xray-config.json')])
mode=None;netmode=None;failures=0;failed_until=0;lastcheck=0;netid=None;preferred='wifi';alternate=False
try:
 while not stop_requested and not (D/'manual-stop').exists():
  vpn,happ,kind,current_netid=network()
  if kind is None:
   time.sleep(2)
   continue
  preferred='mobile' if kind=='mobile' else 'wifi'
  if current_netid!=netid:
   if netid is not None:
    tun_policy(False)
    stop(cp,'core-network-change');cp=None;mode=None
    log('underlying_network_changed; rebuilding routes and DNS')
   netid=current_netid;netmode=None;alternate=False;failed_until=0;lastcheck=0
  target='standby' if vpn or time.monotonic()<failed_until else 'fallback'
  if target!=mode:
   tun_policy(False)
   stop(cp,'core-'+str(mode))
   time.sleep(0.3)
   cp=startcore(target);mode=target;netmode=None;failures=0;lastcheck=time.monotonic()-13
   log('route_mode='+mode+' observed_vpn='+str(vpn)+' happ='+str(happ))
  if xp.poll() is not None:
   xp=spawn('xray',[XRAY,'run','-config',str(D/'xray-config.json')]);log('xray_restart')
  if cp.poll() is not None:
   tun_policy(False)
   cp=startcore(mode);netmode=None;lastcheck=time.monotonic()-13;log('core_restart')
  sel=preferred
  if sel!=netmode and selected(sel):
   netmode=sel;log('selected_'+sel)
  tun_policy(mode=='fallback' and current_tun())
  if mode=='fallback' and not current_tun():
   log('tun_missing')
  if time.monotonic()-lastcheck>18:
   lastcheck=time.monotonic()
   healthy=proxy_ok()
   if mode=='fallback' and (not healthy or not current_tun()):
    failures+=1
    log('fallback_health_bad attempt='+str(failures))
    if failures>=4:
     log('fallback_health_failed_direct_recovery_30s')
     failed_until=time.monotonic()+30
     alternate=False;failures=0
   else:failures=0
   save({'mode':mode,'underlying':kind,'happ_vpn':bool(happ),'any_android_vpn':bool(vpn),
         'healthy_proxy':healthy,'system_tun':current_tun(),
         'server_group':sel,'repair_version':2,'last_check':time.strftime('%Y-%m-%d %H:%M:%S')})
  time.sleep(1.5)
finally:
 tun_policy(False)
 stop(cp,'core');stop(xp,'xray');log('supervisor_stopped')
