import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
UPDATE = REPO / "src" / "update.py"
WIFI = "vless://11111111-1111-4111-8111-111111111111@wifi.example.org:443?type=tcp&security=reality&pbk=abcdef&flow=xtls-rprx-vision#WIFI-Reality"
CELL_A = "vless://22222222-2222-4222-8222-222222222222@mobile1.example.org:443?type=xhttp&security=tls&path=%2Fvless#CELL-A"
CELL_B = "vless://33333333-3333-4333-8333-333333333333@mobile2.example.org:443?type=xhttp&security=tls&path=%2Fpath#CELL-B"

class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d / "api.secret").write_text("test-secret")
        (self.d / "mobile-choice.json").write_text(json.dumps({
            "fingerprint": hashlib.sha256(CELL_B.encode()).hexdigest(),
            "label": "CELL-B",
        }))
        self.env = dict(os.environ, SHADOW_VLESS_HOME=str(self.d))

    def generate(self):
        return subprocess.run([sys.executable, str(UPDATE)], env=self.env,
                              capture_output=True, text=True)

    def test_only_explicit_cellular_server_used(self):
        (self.d / "subscription.raw").write_text(WIFI + "\n" + CELL_A + "\n" + CELL_B + "\n")
        p = self.generate()
        self.assertEqual(p.returncode, 0, p.stderr)
        xr = json.loads((self.d / "xray-config.json").read_text())
        self.assertEqual(len(xr["outbounds"]), 1)
        self.assertEqual(xr["outbounds"][0]["settings"]["vnext"][0]["address"], "mobile2.example.org")
        sb = json.loads((self.d / "config.json").read_text())
        self.assertEqual(next(x for x in sb["outbounds"] if x["tag"] == "mobile")["outbounds"], ["m-1"])

    def test_reordering_never_changes_pinned_cellular_node(self):
        sub = (CELL_B + "\n" + WIFI + "\n" + CELL_A + "\n").encode()
        (self.d / "subscription.raw").write_bytes(base64.b64encode(sub))
        p = self.generate()
        self.assertEqual(p.returncode, 0, p.stderr)
        xr = json.loads((self.d / "xray-config.json").read_text())
        self.assertEqual(xr["outbounds"][0]["settings"]["vnext"][0]["address"], "mobile2.example.org")

    def test_missing_mobile_choice_fails_closed(self):
        (self.d / "subscription.raw").write_text(WIFI + "\n" + CELL_A + "\n")
        p = self.generate()
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse((self.d / "config.json").exists())

    def test_raw_text_not_mistaken_for_base64(self):
        (self.d / "subscription.raw").write_text(WIFI + "\n" + CELL_B + "\n")
        p = self.generate()
        self.assertEqual(p.returncode, 0, p.stderr)

if __name__ == "__main__":
    unittest.main()
