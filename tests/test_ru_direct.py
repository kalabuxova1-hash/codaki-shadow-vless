import importlib.util,unittest
from unittest.mock import patch,MagicMock
spec=importlib.util.spec_from_file_location('ru_direct','src/ru_direct.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class TestRouting(unittest.TestCase):
 def test_uid_selection(self):
  sample='package:com.vkontakte.android uid:10371\npackage:ru.sberbankmobile uid:10368\npackage:com.openai.chatgpt uid:10382\n'
  with patch.object(m.subprocess,'run',return_value=MagicMock(returncode=0,stdout=sample)):
   self.assertEqual(set(m.app_uids().values()),{10368,10371})
 def test_tun_only(self):
  cfg={'inbounds':[{'type':'tun','exclude_uid':[0]},{'type':'mixed'}]}
  with patch.object(m,'excluded_uids',return_value=[0,10371]):m.patch_tun(cfg)
  self.assertEqual(cfg['inbounds'][0]['exclude_uid'],[0,10371])
  self.assertNotIn('exclude_uid',cfg['inbounds'][1])
 def test_rule_collision(self):
  with patch.object(m,'_output',return_value='8997: from all lookup main'):
   with self.assertRaisesRegex(RuntimeError,'owned'):m._owned_rules('-4')
 def test_ipv6_no_route(self):
  calls=[]
  def output(cmd):
   if cmd[2:]==['rule','show']:
    return '8997: from all iif lo uidrange 10371-10371 unreachable' if calls else ''
   if cmd[2:]==['route','show','table','rmnet_data4']:return ''
   raise ValueError(cmd)
  with patch.object(m,'_output',side_effect=output),patch.object(m.subprocess,'run',side_effect=lambda cmd,**kw:calls.append(cmd)):
   self.assertEqual(m._update_rules('-6',[10371],'rmnet_data4'),1)
  self.assertIn('unreachable',calls[0])
 def test_missing_network(self):
  with patch.object(m,'app_uids',return_value={'ru.yandex.taxi':10373}),patch.object(m,'_physical_interface',return_value=None):
   with self.assertRaisesRegex(RuntimeError,'No confirmed physical'):m.sync()
if __name__=='__main__':unittest.main()
