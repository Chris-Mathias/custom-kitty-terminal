import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


class ShellI18nTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name, "cfg")
        self.cfg.mkdir()
        self.env = dict(os.environ, HOME=self.tmp.name, CKT_CONFIG_DIR=str(self.cfg), COLUMNS="200")

    def tearDown(self):
        self.tmp.cleanup()

    def lang(self, lang):
        (self.cfg / "settings.json").write_text(json.dumps({"language": lang}))

    def run_script(self, path, stdin, args=()):
        r = subprocess.run(["bash", str(REPO / path), *args], input=stdin, capture_output=True,
                           text=True, env=self.env, timeout=20)
        return r.returncode, ANSI.sub("", r.stdout)

    STATUS = json.dumps({"workspace": {"current_dir": "/tmp/proj", "project_dir": "/tmp/proj"},
                         "rate_limits": {"seven_day": {"used_percentage": 15}}})

    def test_statusline_week_label(self):
        for lang, label in (("en", "wk "), ("pt", "sem ")):
            with self.subTest(lang=lang):
                self.lang(lang)
                self.assertIn(label, self.run_script("claude/statusline.sh", self.STATUS)[1])

    def test_statusline_corrupt_settings(self):
        (self.cfg / "settings.json").write_text("{nope")
        code, out = self.run_script("claude/statusline.sh", self.STATUS)
        self.assertEqual(code, 0)
        self.assertIn("proj", out)
        self.assertIn("wk ", out)

    def test_subagent_fallback_name(self):
        tasks = json.dumps({"cwd": "/tmp", "columns": 100, "tasks": [{"id": "1", "label": "doing"}]})
        for lang, name in (("en", "agent"), ("pt", "agente")):
            with self.subTest(lang=lang):
                self.lang(lang)
                line = json.loads(self.run_script("claude/subagent-statusline.sh", tasks)[1].splitlines()[0])
                self.assertTrue(ANSI.sub("", line["content"]).startswith(name + " "))

    def test_dialog_text(self):
        for lang, text in (("en", "Close this tab?"), ("pt", "Fechar esta aba?")):
            with self.subTest(lang=lang):
                self.lang(lang)
                env = dict(self.env, TERM="xterm", COLUMNS="80", LINES="24")
                r = subprocess.run(["bash", str(REPO / "kitty/close-tab-dialog.sh"), "tab:1", "claude"],
                                   input="\x1b", capture_output=True, text=True, env=env, timeout=20)
                self.assertIn(text, ANSI.sub("", r.stdout))

    def test_ct_help_mentions_config(self):
        self.lang("en")
        code, out = self.run_script("bin/ct", "", ["--help"])
        self.assertEqual(code, 0)
        self.assertIn("ct config", out)
        self.assertIn("ct ./config", out)


if __name__ == "__main__":
    unittest.main()
