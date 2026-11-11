import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import ckt  # noqa: E402


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "CKT_CONFIG_DIR")}
        os.environ["HOME"] = str(self.home)
        os.environ["CKT_CONFIG_DIR"] = str(self.home / "cfg")
        self.claude = self.home / ".claude/settings.json"

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def settings(self, **kw):
        return dict(ckt.DEFAULTS, **kw)

    def test_generates_kitty_includes(self):
        ckt.apply(self.settings(theme="dracula", font_family="JetBrains Mono", font_size=14), reload=False)
        gen = self.home / ".config/kitty/generated"
        font = (gen / "font.conf").read_text()
        self.assertIn("font_family JetBrains Mono\n", font)
        self.assertIn("font_size 14.0\n", font)
        self.assertEqual((gen / "theme.conf").read_text(), (REPO / "themes/dracula/kitty.conf").read_text())

    def test_merge_preserves_other_keys(self):
        self.claude.parent.mkdir(parents=True)
        self.claude.write_text(json.dumps({"model": "opus", "enabledPlugins": {"a": True}, "theme": "dark"}))
        self.assertEqual(ckt.apply(self.settings(theme="dracula", language="pt"), reload=False), [])
        data = json.loads(self.claude.read_text())
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["enabledPlugins"], {"a": True})
        self.assertEqual(data["theme"], "custom:dracula")
        self.assertEqual(data["outputStyle"], "Português conciso")
        self.assertEqual(data["statusLine"]["command"], "~/.claude/statusline.sh")
        self.assertEqual(data["subagentStatusLine"]["command"], "~/.claude/subagent-statusline.sh")

    def test_merge_creates_when_absent(self):
        ckt.apply(self.settings(), reload=False)
        self.assertEqual(json.loads(self.claude.read_text())["theme"], "custom:fedora")

    def test_invalid_claude_settings_left_untouched(self):
        self.claude.parent.mkdir(parents=True)
        self.claude.write_text("{bad")
        messages = ckt.apply(self.settings(), reload=False)
        self.assertEqual(len(messages), 1)
        self.assertEqual(self.claude.read_text(), "{bad")

    def test_language_switch_changes_verbs(self):
        ckt.apply(self.settings(language="en"), reload=False)
        verbs = json.loads(self.claude.read_text())["spinnerVerbs"]
        self.assertEqual(verbs, {"mode": "replace", "verbs": ckt.t("spinner.verbs", "en")})

    def test_merge_reports_change(self):
        self.assertTrue(ckt.merge_claude_settings(self.settings()))
        self.assertFalse(ckt.merge_claude_settings(self.settings()))


if __name__ == "__main__":
    unittest.main()
