import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import ckt  # noqa: E402


class SettingsModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("CKT_CONFIG_DIR")
        os.environ["CKT_CONFIG_DIR"] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("CKT_CONFIG_DIR", None)
        else:
            os.environ["CKT_CONFIG_DIR"] = self.old
        self.tmp.cleanup()

    def load(self, data):
        Path(self.tmp.name, "settings.json").write_text(json.dumps(data))
        return ckt.load_settings()

    def test_new_defaults(self):
        d = ckt.DEFAULTS
        self.assertEqual(d["line_height"], 115)
        self.assertEqual(d["padding"], "normal")
        self.assertEqual(d["tab_style"], "slanted")
        self.assertEqual(d["tab_position"], "top")
        self.assertEqual(d["opacity"], 100)
        self.assertEqual(d["cursor_shape"], "block")
        self.assertIs(d["cursor_blink"], True)
        self.assertEqual(d["title_bar"], "gnome")
        self.assertIs(d["ligatures"], True)
        self.assertEqual(d["response_style"], {"enabled": False, "language": "pt", "length": "short", "previous": None})
        self.assertEqual(d["spinner"], "ours")
        self.assertEqual(d["status_line"], {k: True for k in ckt.STATUS_ITEMS})
        self.assertEqual(d["panel"], {"sections": ["sessions", "agents", "git", "tasks", "files"], "auto_open": True})
        self.assertIs(d["subagent_rows"], True)
        self.assertIs(d["reopen_tabs"], True)
        self.assertEqual(d["confirm_close"], "running")
        self.assertIs(d["kitty_ctrl_keys"], True)
        self.assertEqual(d["scrollback"], 20000)
        self.assertIs(d["bell"], False)
        self.assertEqual(d["shortcuts"], {})

    def test_old_file_gets_new_defaults(self):
        s = self.load({"language": "pt", "theme": "dracula", "font_family": "Adwaita Mono", "font_size": 13})
        self.assertEqual(s["theme"], "dracula")
        for key in ckt.DEFAULTS:
            if key not in ("language", "theme", "font_family", "font_size"):
                self.assertEqual(s[key], ckt.DEFAULTS[key], key)

    def test_scalar_choices_validated(self):
        s = self.load({"line_height": 117, "padding": "huge", "opacity": 85, "scrollback": 50000, "tab_style": "round"})
        self.assertEqual(s["line_height"], 115)
        self.assertEqual(s["padding"], "normal")
        self.assertEqual(s["opacity"], 85)
        self.assertEqual(s["scrollback"], 50000)
        self.assertEqual(s["tab_style"], "round")

    def test_bool_keys_reject_strings(self):
        s = self.load({"ligatures": "no", "bell": 1, "reopen_tabs": False})
        self.assertIs(s["ligatures"], True)
        self.assertIs(s["bell"], False)
        self.assertIs(s["reopen_tabs"], False)

    def test_bad_nested_field_falls_back(self):
        s = self.load({"status_line": {"model": "x", "weekly": False},
                       "response_style": {"enabled": True, "length": "huge", "previous": 3}})
        self.assertIs(s["status_line"]["model"], True)
        self.assertIs(s["status_line"]["weekly"], False)
        self.assertIs(s["response_style"]["enabled"], True)
        self.assertEqual(s["response_style"]["length"], "short")
        self.assertIsNone(s["response_style"]["previous"])

    def test_panel_sections_validated(self):
        self.assertEqual(self.load({"panel": {"sections": ["git", "nope", "git"]}})["panel"]["sections"], ["git"])
        self.assertEqual(self.load({"panel": {"sections": []}})["panel"]["sections"], [])
        self.assertEqual(self.load({"panel": {"sections": "git"}})["panel"]["sections"], list(ckt.PANEL_SECTIONS))

    def test_previous_style_string_kept(self):
        s = self.load({"response_style": {"previous": "Explanatory"}})
        self.assertEqual(s["response_style"]["previous"], "Explanatory")

    def test_shortcut_overrides_validated(self):
        s = self.load({"shortcuts": {"old_id": "ctrl+x", "settings": "foo bar", "tab_1": "Alt+9"}})
        self.assertEqual(s["shortcuts"], {"tab_1": "alt+9"})


if __name__ == "__main__":
    unittest.main()
