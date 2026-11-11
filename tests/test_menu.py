import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import ckt  # noqa: E402
from menu import Menu  # noqa: E402

FONTS = ["Adwaita Mono", "JetBrains Mono", "Source Code Pro"]


def menu(**kw):
    return Menu(dict(ckt.DEFAULTS, **kw), FONTS)


class MenuTest(unittest.TestCase):
    def test_top_level_lists_four_items(self):
        m = menu()
        self.assertEqual([label for label, _ in m.items()], ["Language", "Theme", "Font", "Font size"])
        self.assertEqual([value for _, value in m.items()], ["English", "Fedora", "Adwaita Mono", "12"])
        self.assertEqual(m.view()["level"], "top")

    def test_choose_theme(self):
        m = menu()
        self.assertIsNone(m.key("down"))
        self.assertIsNone(m.key("enter"))
        self.assertEqual(m.view()["level"], "sub")
        for _ in range(3):
            m.key("down")
        self.assertEqual(m.key("enter"), "apply")
        self.assertEqual(m.settings["theme"], "dracula")
        self.assertEqual(m.view()["level"], "top")
        self.assertEqual(m.view()["cursor"], 1)

    def test_choosing_current_value_is_not_a_change(self):
        m = menu()
        m.key("enter")
        self.assertIsNone(m.key("enter"))
        self.assertEqual(m.view()["level"], "top")

    def test_back_from_sub_without_change(self):
        m = menu()
        m.key("enter")
        m.key("down")
        self.assertIsNone(m.key("back"))
        self.assertEqual(m.view()["level"], "top")
        self.assertEqual(m.settings, ckt.DEFAULTS)

    def test_quit_and_back_at_top(self):
        self.assertEqual(menu().key("quit"), "quit")
        self.assertEqual(menu().key("back"), "quit")

    def test_language_switch_relabels(self):
        m = menu()
        m.key("enter")
        m.key("down")
        self.assertEqual(m.key("enter"), "apply")
        self.assertEqual(m.settings["language"], "pt")
        self.assertEqual([label for label, _ in m.items()], ["Idioma", "Tema", "Fonte", "Tamanho da fonte"])
        self.assertEqual(m.items()[0][1], "Português")

    def test_font_size_bounds(self):
        m = menu(font_size=14)
        m.key("up")  # wraps to the last item
        m.key("enter")
        v = m.view()
        self.assertEqual(v["rows"], [f"{'●' if n == 14 else '○'} {n}" for n in range(8, 25)])
        self.assertEqual(v["cursor"], 6)

    def test_current_value_marked(self):
        m = menu(theme="gruvbox")
        m.key("down")
        m.key("enter")
        rows = m.view()["rows"]
        self.assertEqual(rows[4], "● Gruvbox")
        self.assertTrue(all(r.startswith("○ ") for i, r in enumerate(rows) if i != 4))
        self.assertEqual(m.view()["title"], "Theme")

    def test_unknown_current_font_still_listed(self):
        m = menu(font_family="Fira Code")
        m.key("down")
        m.key("down")
        m.key("enter")
        self.assertIn("● Fira Code", m.view()["rows"])

    def test_cursor_wraps_in_sub_list(self):
        m = menu()
        m.key("enter")
        m.key("up")
        self.assertEqual(m.view()["cursor"], 1)


if __name__ == "__main__":
    unittest.main()
