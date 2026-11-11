import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import ckt  # noqa: E402

HEX = re.compile(r"^#[0-9a-f]{6}$")
PALETTE_KEYS = {"accent", "accent_bg", "fg", "bg", "dim", "surface",
                "green", "yellow", "red", "magenta", "cyan", "orange"}


class ConfigDirTest(unittest.TestCase):
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

    def write_settings(self, text):
        Path(self.tmp.name, "settings.json").write_text(text)


class SettingsTest(ConfigDirTest):
    def test_defaults_when_missing(self):
        self.assertEqual(ckt.load_settings(), ckt.DEFAULTS)

    def test_defaults_values(self):
        self.assertEqual(ckt.DEFAULTS, {"language": "en", "theme": "fedora",
                                        "font_family": "Adwaita Mono", "font_size": 12})

    def test_corrupt_file_gives_defaults(self):
        self.write_settings("{nope")
        self.assertEqual(ckt.load_settings(), ckt.DEFAULTS)

    def test_invalid_values_replaced(self):
        self.write_settings(json.dumps({"language": "fr", "theme": "x", "font_size": 99,
                                        "font_family": "JetBrains Mono"}))
        s = ckt.load_settings()
        self.assertEqual(s["language"], "en")
        self.assertEqual(s["theme"], "fedora")
        self.assertEqual(s["font_size"], 12)
        self.assertEqual(s["font_family"], "JetBrains Mono")

    def test_save_roundtrip(self):
        s = dict(ckt.DEFAULTS, language="pt", theme="dracula", font_size=14)
        ckt.save_settings(s)
        self.assertEqual(ckt.load_settings(), s)


class I18nTest(unittest.TestCase):
    def test_t_falls_back_to_key(self):
        self.assertEqual(ckt.t("no.such.key", "pt"), "no.such.key")

    def test_t_falls_back_to_en(self):
        en = json.loads((REPO / "i18n/en.json").read_text())
        key = next(iter(en))
        self.assertEqual(ckt.t(key, "xx"), en[key])

    def test_output_style_names(self):
        self.assertEqual(ckt.t("output_style", "en"), "Concise English")
        self.assertEqual(ckt.t("output_style", "pt"), "Português conciso")

    def test_spinner_verbs_are_lists(self):
        for lang in ckt.LANGUAGES:
            verbs = ckt.t("spinner.verbs", lang)
            self.assertIsInstance(verbs, list)
            self.assertEqual(len(verbs), 14)

    def test_i18n_key_sets_match(self):
        en = json.loads((REPO / "i18n/en.json").read_text())
        pt = json.loads((REPO / "i18n/pt.json").read_text())
        self.assertEqual(set(en), set(pt))

    def test_output_style_files_exist(self):
        for lang in ckt.LANGUAGES:
            name = ckt.t("output_style", lang)
            files = list((REPO / "claude/output-styles").glob("*.md"))
            self.assertTrue(any(f"name: {name}\n" in f.read_text() for f in files), name)


class ThemeTest(unittest.TestCase):
    def test_theme_ids(self):
        self.assertEqual(ckt.THEMES, ("fedora", "catppuccin", "tokyo-night", "dracula", "gruvbox", "light"))

    def test_every_theme_complete(self):
        for theme in ckt.THEMES:
            with self.subTest(theme=theme):
                pal = ckt.palette(theme)
                self.assertEqual(set(pal), PALETTE_KEYS)
                for v in pal.values():
                    self.assertRegex(v, HEX)
                conf = (REPO / "themes" / theme / "kitty.conf").read_text()
                keys = {line.split()[0] for line in conf.splitlines() if line.strip() and not line.startswith("#")}
                needed = {"foreground", "background", "active_tab_background", "inactive_tab_background",
                          "tab_bar_background"} | {f"color{i}" for i in range(16)}
                self.assertLessEqual(needed, keys)
                claude = json.loads((REPO / "themes" / theme / "claude.json").read_text())
                self.assertIn(claude["base"], ("dark", "light"))
                self.assertTrue(claude["name"])
                self.assertIsInstance(claude["overrides"], dict)

    def test_light_theme_is_light(self):
        self.assertEqual(json.loads((REPO / "themes/light/claude.json").read_text())["base"], "light")

    def test_theme_label(self):
        self.assertEqual(ckt.theme_label("fedora"), "Fedora")
        self.assertEqual(ckt.theme_label("tokyo-night"), "Tokyo Night")


class FontsTest(unittest.TestCase):
    def test_mono_fonts_dedup_and_skip_emoji(self):
        with tempfile.TemporaryDirectory() as d:
            stub = Path(d, "fc-list")
            stub.write_text("#!/bin/sh\nprintf 'Source Code Pro,Source Code Pro Light\\nAdwaita Mono\\n"
                            "Noto Color Emoji\\nSource Code Pro\\n'\n")
            stub.chmod(0o755)
            old = os.environ["PATH"]
            os.environ["PATH"] = f"{d}:{old}"
            try:
                self.assertEqual(ckt.mono_fonts(), ["Adwaita Mono", "Source Code Pro"])
            finally:
                os.environ["PATH"] = old


class ShellTest(ConfigDirTest):
    def sh(self, cmd):
        return subprocess.run(["bash", "-c", f"source {REPO}/lib/ckt.sh; {cmd}"],
                              capture_output=True, text=True, env=os.environ.copy()).stdout

    def test_shell_lookup_matches_python(self):
        for lang in ckt.LANGUAGES:
            self.write_settings(json.dumps({"language": lang}))
            self.assertEqual(self.sh("ckt_t output_style"), ckt.t("output_style", lang))

    def test_shell_corrupt_settings(self):
        self.write_settings("{nope")
        self.assertEqual(self.sh("ckt_lang; echo; ckt_theme"), "en\nfedora")

    def test_shell_unknown_key(self):
        self.assertEqual(self.sh("ckt_t no.such.key"), "no.such.key")

    def test_shell_color(self):
        self.write_settings(json.dumps({"theme": "dracula"}))
        r, g, b = (int(ckt.palette("dracula")["red"][i:i + 2], 16) for i in (1, 3, 5))
        self.assertEqual(self.sh("ckt_color red"), f"\x1b[38;2;{r};{g};{b}m")
        self.assertEqual(self.sh("ckt_bg red"), f"\x1b[48;2;{r};{g};{b}m")



class PanelStringsTest(unittest.TestCase):
    def test_panel_builtin_english_matches_en_json(self):
        src = (REPO / "claude/session-panel/hooks/register.tsx").read_text()
        block = src[src.index("const EN = {"):src.index("}\ntype Strings")]
        builtin = dict(re.findall(r"""'(panel\.[a-z_]+)': ['"](.*?)['"],""", block))
        en = json.loads((REPO / "i18n/en.json").read_text())
        self.assertEqual(builtin, {k: v for k, v in en.items() if k.startswith("panel.")})


if __name__ == "__main__":
    unittest.main()
