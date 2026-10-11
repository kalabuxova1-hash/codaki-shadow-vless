"""Pure unit tests for Codaki Shadow VLESS VK bypass without an Android device."""
import ast
from pathlib import Path
import re
import subprocess
import time
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1]/"src"/"failover.py"

class FakeNetwork:
 def __init__(self):
  self.rules={"-4":None,"-6":None}
  self.routes={"-4":True,"-6":True}
  self.calls=[]
  self.foreign=None
 def check_output(self, command, **kwargs):
  if command[0]=="/system/bin/dumpsys":
   return b"NetworkAgentInfo{network{114} ni{MOBILE} lp{{InterfaceName: rmnet_data4 LinkAddresses: []}}\n"
  if command[0]=="/system/bin/pm":
   return b"package:com.vkontakte.android uid:10371\n"
  if command[:1]==["/system/bin/ip"]:
   family=command[1]
   if command[2]=="rule":
    current=self.foreign or self.rules[family]
    return (current+"\n").encode() if current else b"8999: from all iif lo uidrange 1-2147483647 lookup 2022\n"
   if command[2]=="route":
    return b"default via 192.0.2.1\n" if self.routes[family] else b""
  raise AssertionError(command)
 def run(self,command,**kwargs):
  self.calls.append(command)
  family=command[1]
  if command[3]=="add":
   self.rules[family]="8998: from all iif lo uidrange 10371-10371 lookup "+command[-1]
  elif command[3]=="del":
   self.rules[family]=None
  else:
   raise AssertionError(command)

class BypassTests(unittest.TestCase):
 def setUp(self):
  tree=ast.parse(SRC.read_text())
  func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="vk_direct_bypass")
  self.log=[]
  env={"vk_bypass_state":None,"vk_bypass_last_check":0,"subprocess":subprocess,"re":re,"time":time,"log":self.log.append}
  exec(compile(ast.Module(body=[func],type_ignores=[]),str(SRC),"exec"),env)
  self.env=env
  self.net=FakeNetwork()
  self.p1=patch.object(subprocess,"check_output",self.net.check_output)
  self.p2=patch.object(subprocess,"run",self.net.run)
  self.p1.start();self.p2.start()
  self.addCleanup(self.p1.stop);self.addCleanup(self.p2.stop)
 def test_wifi_exempt_vk_uid_only(self):
  self.env["vk_direct_bypass"]("wifi","113")
  self.assertTrue(all("uidrange 10371-10371 lookup wlan0" in str(x) for x in self.net.rules.values()))
  self.assertEqual(len(self.net.calls),2)
  self.env["vk_direct_bypass"]("wifi","113")
  self.assertEqual(len(self.net.calls),2)
 def test_handover_to_mobile_with_no_ipv6_default(self):
  self.env["vk_direct_bypass"]("wifi","113")
  self.net.routes["-6"]=False
  self.env["vk_direct_bypass"]("mobile","114")
  self.assertIn("lookup rmnet_data4",self.net.rules["-4"])
  self.assertIsNone(self.net.rules["-6"])
 def test_retry_until_default_route_exists(self):
  self.net.routes={"-4":False,"-6":False}
  self.env["vk_direct_bypass"]("mobile","114")
  self.assertIsNone(self.env["vk_bypass_state"])
  self.assertEqual(self.net.calls,[])
  self.net.routes["-4"]=True
  self.env["vk_direct_bypass"]("mobile","114")
  self.assertIn("lookup rmnet_data4",self.net.rules["-4"])
 def test_do_not_modify_foreign_priority(self):
  self.net.foreign="8998: from all iif lo uidrange 55555-55555 lookup wlan0"
  self.env["vk_direct_bypass"]("wifi","113")
  self.assertFalse(self.net.calls)
  self.assertTrue(any("failed" in x for x in self.log))

if __name__=="__main__":
 unittest.main()
