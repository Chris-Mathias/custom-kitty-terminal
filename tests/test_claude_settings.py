import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import ckt  # noqa: E402

ON = {"enabled": True, "language": "pt", "length": "short", "previous": None}


class ClaudeSettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "CKT_CONFIG_DIR")}
        os.environ["HOME"] = str(self.home)
        os.environ["CKT_CONFIG_DIR"] = str(self.home / "cfg")
        self.claude = self.home / ".claude/settings.json"
        self.claude.parent.mkdir(parents=True)
        self.style = self.home / ".claude/output-styles/custom-kitty-terminal.md"

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def write(self, data):
        self.claude.write_text(json.dumps(data))

    def data(self):
        return json.loads(self.claude.read_text())

    def apply(self, **kw):
        s = dict(ckt.DEFAULTS, **kw)
        ckt.save_settings(s)
        ckt.apply(s, reload=False)
        return ckt.load_settings()

    def test_style_off_writes_nothing(self):
        self.write({"model": "opus"})
        self.apply()
        self.assertNotIn("outputStyle", self.data())
        self.assertFalse(self.style.exists())

    def test_style_names(self):
        self.assertEqual(ckt.style_name(ON), "Terminal — Português, curto")
        self.assertEqual(ckt.style_name(dict(ON, language="en", length="detailed")), "Terminal — English, detailed")

    def test_enable_saves_previous_and_sets_name(self):
        self.write({"outputStyle": "Explanatory"})
        s = self.apply(response_style=ON)
        self.assertEqual(self.data()["outputStyle"], "Terminal — Português, curto")
        self.assertEqual(s["response_style"]["previous"], "Explanatory")
        text = self.style.read_text()
        self.assertIn("name: Terminal — Português, curto\n", text)
        self.assertIn("português", text.lower())

    def test_changing_length_keeps_previous(self):
        self.write({"outputStyle": "Explanatory"})
        s = self.apply(response_style=ON)
        s = self.apply(response_style=dict(s["response_style"], length="detailed"))
        self.assertEqual(self.data()["outputStyle"], "Terminal — Português, detalhado")
        self.assertEqual(s["response_style"]["previous"], "Explanatory")

    def test_disable_restores_previous(self):
        self.write({"outputStyle": "Explanatory"})
        s = self.apply(response_style=ON)
        s = self.apply(response_style=dict(s["response_style"], enabled=False))
        self.assertEqual(self.data()["outputStyle"], "Explanatory")
        self.assertIsNone(s["response_style"]["previous"])
        self.assertFalse(self.style.exists())

    def test_disable_removes_key_when_no_previous(self):
        self.write({})
        s = self.apply(response_style=ON)
        self.apply(response_style=dict(s["response_style"], enabled=False))
        self.assertNotIn("outputStyle", self.data())

    def test_disable_leaves_hand_changed_style(self):
        self.write({})
        s = self.apply(response_style=ON)
        self.write({"outputStyle": "Learning"})
        self.apply(response_style=dict(s["response_style"], enabled=False))
        self.assertEqual(self.data()["outputStyle"], "Learning")

    def test_spinner_claude_removes_only_ours(self):
        self.apply()
        self.assertIn("spinnerVerbs", self.data())
        self.apply(spinner="claude")
        self.assertNotIn("spinnerVerbs", self.data())

    def test_spinner_claude_keeps_user_list(self):
        mine = {"mode": "append", "verbs": ["Vibing"]}
        self.write({"spinnerVerbs": mine})
        self.apply(spinner="claude")
        self.assertEqual(self.data()["spinnerVerbs"], mine)


if __name__ == "__main__":
    unittest.main()
