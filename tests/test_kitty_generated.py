import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import ckt  # noqa: E402


def settings(**kw):
    return dict(ckt.DEFAULTS, **kw)


def lines(text):
    return {line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")}


class GeneratedKittyTest(unittest.TestCase):
    def test_defaults_match_today(self):
        got = lines(ckt.appearance_conf(settings())) | lines(ckt.behavior_conf(settings()))
        for expected in ("modify_font cell_height 115%", "window_padding_width 4 8", "tab_powerline_style slanted",
                         "tab_bar_edge top", "background_opacity 1.0", "cursor_shape block",
                         "cursor_blink_interval -1", "linux_display_server x11", "hide_window_decorations no",
                         "disable_ligatures never", "startup_session last-session.kitty-session",
                         "watcher save_session.py", "scrollback_lines 20000", "enable_audio_bell no"):
            self.assertIn(expected, got)

    def test_appearance_options(self):
        cases = [
            (dict(line_height=125), "modify_font cell_height 125%"),
            (dict(padding="compact"), "window_padding_width 2 4"),
            (dict(padding="roomy"), "window_padding_width 8 16"),
            (dict(tab_style="round"), "tab_powerline_style round"),
            (dict(tab_style="separators"), "tab_powerline_style slanted"),
            (dict(tab_position="bottom"), "tab_bar_edge bottom"),
            (dict(opacity=85), "background_opacity 0.85"),
            (dict(cursor_shape="beam"), "cursor_shape beam"),
            (dict(cursor_blink=False), "cursor_blink_interval 0"),
            (dict(title_bar="kitty"), "linux_display_server auto"),
            (dict(title_bar="none"), "hide_window_decorations yes"),
            (dict(ligatures=False), "disable_ligatures always"),
        ]
        for kw, expected in cases:
            with self.subTest(**kw):
                self.assertIn(expected, lines(ckt.appearance_conf(settings(**kw))))

    def test_behavior_options(self):
        off = lines(ckt.behavior_conf(settings(reopen_tabs=False)))
        self.assertIn("startup_session none", off)
        self.assertFalse(any(l.startswith("watcher") for l in off))
        self.assertIn("scrollback_lines 5000", lines(ckt.behavior_conf(settings(scrollback=5000))))
        self.assertIn("enable_audio_bell yes", lines(ckt.behavior_conf(settings(bell=True))))

    def test_fixed_kitty_conf_has_no_generated_settings(self):
        conf = lines((REPO / "kitty/kitty.conf").read_text())
        for prefix in ("linux_display_server", "hide_window_decorations", "modify_font", "window_padding_width",
                       "startup_session", "watcher", "scrollback_lines", "enable_audio_bell", "disable_ligatures"):
            self.assertFalse(any(l.startswith(prefix) for l in conf), prefix)
        self.assertIn("dynamic_background_opacity yes", conf)
        ordered = (REPO / "kitty/kitty.conf").read_text().splitlines()
        includes = [l for l in ordered if l.startswith("include generated/")]
        self.assertEqual(includes, ["include generated/theme.conf", "include generated/font.conf",
                                    "include generated/appearance.conf", "include generated/behavior.conf",
                                    "include generated/shortcuts.conf"])

    @unittest.skipUnless(shutil.which("kitty"), "kitty not installed")
    def test_every_value_is_valid_kitty_config(self):
        samples = [settings()]
        for key, values in ckt.CHOICES.items():
            if key in ("language", "theme", "font_size"):
                continue
            samples += [settings(**{key: v}) for v in values]
        with tempfile.TemporaryDirectory() as d:
            check = []
            for i, s in enumerate(samples):
                folder = Path(d, str(i))
                (folder / "generated").mkdir(parents=True)
                shutil.copy(REPO / "kitty/kitty.conf", folder)
                shutil.copy(REPO / "kitty/tabs.conf", folder)
                (folder / "generated/theme.conf").write_text((REPO / "themes/fedora/kitty.conf").read_text())
                (folder / "generated/font.conf").write_text("font_family Adwaita Mono\nfont_size 12.0\n")
                (folder / "generated/appearance.conf").write_text(ckt.appearance_conf(s))
                (folder / "generated/behavior.conf").write_text(ckt.behavior_conf(s))
                (folder / "generated/shortcuts.conf").write_text("")
                check.append(str(folder / "kitty.conf"))
            script = Path(d, "check.py")
            script.write_text("import sys\nfrom kitty.config import load_config\nbad = 0\n"
                              f"for p in {check!r}:\n    errs = []\n    load_config(p, accumulate_bad_lines=errs)\n"
                              "    bad += len(errs)\n    [print(p, e.line) for e in errs]\nprint('BAD', bad)\n")
            r = subprocess.run(["kitty", "+runpy", f"exec(open({str(script)!r}).read())"],
                               capture_output=True, text=True, timeout=120)
            self.assertIn("BAD 0", r.stdout, r.stdout + r.stderr)


class CloseDecisionTest(unittest.TestCase):
    def test_close_decision(self):
        self.assertEqual(ckt.close_decision("running", []), "close")
        self.assertEqual(ckt.close_decision("running", ["vim"]), "ask")
        self.assertEqual(ckt.close_decision("always", []), "ask")
        self.assertEqual(ckt.close_decision("never", ["vim"]), "close")


if __name__ == "__main__":
    unittest.main()
