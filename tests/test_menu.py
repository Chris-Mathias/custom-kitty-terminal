import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import ckt  # noqa: E402
import shortcuts as sc  # noqa: E402
from menu import Menu  # noqa: E402

FONTS = ["Adwaita Mono", "JetBrains Mono", "Source Code Pro"]
KITTY = {"ctrl+shift+c": "copy_to_clipboard"}


def menu(**kw):
    s = copy.deepcopy(ckt.DEFAULTS)
    s.update(kw)
    return Menu(s, FONTS, kitty_action=KITTY.get)


def go(m, *labels):
    """Opens rows by label, one level at a time."""
    for label in labels:
        rows = [r.split("  ")[0].lstrip("●○ ").strip() for r in m.view()["rows"]]
        while m.view()["rows"][m.view()["cursor"]].split("  ")[0].lstrip("●○ ").strip() != label:
            assert label in rows, (label, rows)
            m.key("down")
        result = m.key("enter")
    return result


class MenuTest(unittest.TestCase):
    def test_top_level(self):
        m = menu()
        self.assertEqual(m.labels(), ["Appearance", "Claude Code", "Behavior", "Shortcuts", "Language"])
        self.assertEqual(m.view()["values"][-1], "English")

    def test_choose_theme(self):
        m = menu()
        self.assertEqual(go(m, "Appearance", "Theme", "Dracula"), "apply")
        self.assertEqual(m.settings["theme"], "dracula")
        self.assertEqual(m.view()["title"], "Appearance")

    def test_back_goes_up_one_level(self):
        m = menu()
        go(m, "Appearance", "Theme")
        m.key("back")
        self.assertEqual(m.view()["title"], "Appearance")
        m.key("back")
        self.assertEqual(m.view()["title"], "Settings")
        self.assertEqual(m.key("back"), "quit")

    def test_toggle_ligatures(self):
        m = menu()
        self.assertEqual(go(m, "Appearance", "Ligatures", "Off"), "apply")
        self.assertIs(m.settings["ligatures"], False)

    def test_values_are_labelled(self):
        m = menu()
        go(m, "Appearance")
        values = dict(zip(m.labels(), m.view()["values"]))
        self.assertEqual(values["Line height"], "115%")
        self.assertEqual(values["Transparency"], "100%")
        self.assertEqual(values["Tab style"], "Slanted")
        self.assertEqual(values["Ligatures"], "On")

    def test_response_style_flow(self):
        m = menu()
        self.assertEqual(go(m, "Claude Code", "Response style", "Enabled", "On"), "apply")
        self.assertIs(m.settings["response_style"]["enabled"], True)
        self.assertEqual(go(m, "Length", "Detailed"), "apply")
        self.assertEqual(m.settings["response_style"]["length"], "detailed")

    def test_hide_subagent_rows(self):
        m = menu()
        self.assertEqual(go(m, "Claude Code", "Subagent list below the prompt", "Off"), "apply")
        self.assertIs(m.settings["subagent_rows"], False)

    def test_close_buttons(self):
        m = menu()
        self.assertEqual(go(m, "Behavior", "Close button on tabs", "On"), "apply")
        self.assertIs(m.settings["tab_close_buttons"], True)
        self.assertEqual(go(m, "Close button on panel sessions", "On"), "apply")
        self.assertIs(m.settings["panel_close_buttons"], True)

    def test_status_line_toggle(self):
        m = menu()
        self.assertEqual(go(m, "Claude Code", "Status line", "Weekly limit", "Off"), "apply")
        self.assertIs(m.settings["status_line"]["weekly"], False)
        self.assertIs(m.settings["status_line"]["model"], True)

    def test_panel_order_move(self):
        m = menu()
        go(m, "Claude Code", "Side panel", "Order")
        for _ in range(4):
            m.key("down")
        self.assertIsNone(m.key("enter"))  # picks "Files" up
        self.assertTrue(m.view()["moving"])
        for _ in range(4):
            m.key("up")
        self.assertEqual(m.key("enter"), "apply")  # drops it first
        self.assertEqual(m.settings["panel"]["sections"], ["files", "sessions", "agents", "tasks", "git", "images"])

    def test_panel_section_visibility(self):
        m = menu()
        self.assertEqual(go(m, "Claude Code", "Side panel", "Git", "Off"), "apply")
        self.assertEqual(m.settings["panel"]["sections"], ["sessions", "agents", "tasks", "files", "images"])
        self.assertEqual(go(m, "Git", "On"), "apply")
        self.assertEqual(m.settings["panel"]["sections"], ["sessions", "agents", "tasks", "files", "images", "git"])

    def test_shortcut_capture(self):
        m = menu()
        self.assertEqual(go(m, "Shortcuts", "Settings menu", "Record new keys"), "capture")
        self.assertEqual(m.captured("ctrl+alt+y"), "apply")
        self.assertEqual(sc.keys_for(m.settings)["settings"], "ctrl+alt+y")

    def test_shortcut_conflict_swaps_after_confirm(self):
        m = menu()
        go(m, "Shortcuts", "Settings menu", "Record new keys")
        self.assertEqual(m.captured("ctrl+w"), "confirm")
        self.assertIn("Close the tab", m.view()["message"])
        self.assertEqual(m.key("enter"), "apply")
        keys = sc.keys_for(m.settings)
        self.assertEqual(keys["settings"], "ctrl+w")
        self.assertEqual(keys["close_tab"], "ctrl+shift+f2")

    def test_kitty_default_conflict_can_be_cancelled(self):
        m = menu()
        go(m, "Shortcuts", "Settings menu", "Record new keys")
        self.assertEqual(m.captured("ctrl+shift+c"), "confirm")
        self.assertIn("copy_to_clipboard", m.view()["message"])
        self.assertIsNone(m.key("back"))
        self.assertEqual(sc.keys_for(m.settings)["settings"], "ctrl+shift+f2")

    def test_ctrl_keys_refused_when_given_to_the_shell(self):
        m = menu(kitty_ctrl_keys=False)
        go(m, "Shortcuts", "Settings menu", "Record new keys")
        self.assertIsNone(m.captured("ctrl+n"))
        self.assertTrue(m.view()["message"])
        self.assertEqual(sc.keys_for(m.settings)["settings"], "ctrl+shift+f2")

    def test_reset_shortcut(self):
        m = menu(shortcuts={"settings": "ctrl+alt+s"})
        self.assertEqual(go(m, "Shortcuts", "Settings menu", "Reset to default"), "apply")
        self.assertEqual(m.settings["shortcuts"], {})

    def test_reset_all_shortcuts(self):
        m = menu(shortcuts={"settings": "ctrl+alt+s", "tab_1": "alt+9"})
        self.assertEqual(go(m, "Shortcuts", "Reset all"), "apply")
        self.assertEqual(m.settings["shortcuts"], {})

    def test_language_switch_relabels(self):
        m = menu()
        self.assertEqual(go(m, "Language", "Português"), "apply")
        self.assertEqual(m.labels(), ["Aparência", "Claude Code", "Comportamento", "Atalhos", "Idioma"])

    def test_font_list_keeps_unknown_current_font(self):
        m = menu(font_family="Fira Code")
        go(m, "Appearance", "Font")
        self.assertIn("● Fira Code", m.view()["rows"])

    def test_restart_note_for_title_bar(self):
        m = menu()
        go(m, "Appearance", "Title bar", "kitty's own")
        self.assertIn("restart", m.view()["message"].lower())


if __name__ == "__main__":
    unittest.main()
