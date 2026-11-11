import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

import ckt  # noqa: E402
import shortcuts as sc  # noqa: E402

# The maps kitty.conf had before shortcuts became settings: the defaults must match.
TODAY = {
    'map alt+1 goto_tab 1',
    'map alt+2 goto_tab 2',
    'map alt+3 goto_tab 3',
    'map alt+4 goto_tab 4',
    'map alt+5 goto_tab 5',
    'map alt+6 goto_tab 6',
    'map alt+left previous_tab',
    'map alt+right next_tab',
    'map alt+t new_tab_with_cwd',
    'map ctrl+shift+t new_tab_with_cwd',
    'map ctrl+n new_tab_with_cwd',
    'map ctrl+w kitten close_tab.py',
    'map ctrl+alt+w kitten close_tab.py window',
    'map ctrl+alt+n combine | goto_layout stack | launch --type=window --cwd=current sh -c \'exec "${SHELL:-/bin/bash}" -ic "$HOME/.local/bin/claude-panel"\'',
    'map ctrl+alt+t launch --type=tab --cwd=current sh -c \'exec "${SHELL:-/bin/bash}" -ic "$HOME/.local/bin/claude-panel"\'',
    'map alt+up previous_window',
    'map alt+down next_window',
    'map ctrl+alt+z toggle_layout stack',
    'map ctrl+shift+f2 launch --type=overlay sh -c \'exec "$HOME/.local/bin/ct-config"\'',
    'map ctrl+shift+enter launch --cwd=current --location=vsplit',
    'map ctrl+shift+minus launch --cwd=current --location=hsplit',
}


def settings(**kw):
    return dict(ckt.DEFAULTS, **kw)


def maps(text):
    return {l for l in text.splitlines() if l.startswith("map ") and "--mode" not in l and "--new-mode" not in l}


class ShortcutsTest(unittest.TestCase):
    def test_default_conf_matches_today(self):
        self.assertEqual(maps(sc.shortcuts_conf(settings())), TODAY)

    def test_capture_mode_defined(self):
        conf = sc.shortcuts_conf(settings())
        self.assertIn("--new-mode ckt-capture --on-unknown passthrough", conf)
        self.assertIn("--timeout 30", conf)  # safety net: kitty leaves the mode by itself

    def test_override(self):
        conf = maps(sc.shortcuts_conf(settings(shortcuts={"claude_tab": "ctrl+alt+y"})))
        self.assertTrue(any(l.startswith("map ctrl+alt+y launch --type=tab") for l in conf))
        self.assertFalse(any(l.startswith("map ctrl+alt+t ") for l in conf))

    def test_assign_swaps_with_the_owner(self):
        s, other = sc.assign(settings(), "claude_tab", "ctrl+alt+n")
        self.assertEqual(other, "claude_stack")
        keys = sc.keys_for(s)
        self.assertEqual(keys["claude_tab"], "ctrl+alt+n")
        self.assertEqual(keys["claude_stack"], "ctrl+alt+t")

    def test_no_duplicate_keys(self):
        s = settings(shortcuts={"tab_1": "alt+2"})  # hand-edited clash
        keys = [l.split()[1] for l in maps(sc.shortcuts_conf(s))]
        self.assertEqual(len(keys), len(set(keys)))

    def test_reset(self):
        s, _ = sc.assign(settings(), "settings", "ctrl+alt+s")
        self.assertEqual(sc.keys_for(sc.reset(s, "settings"))["settings"], "ctrl+shift+f2")
        self.assertEqual(sc.reset_all(s)["shortcuts"], {})

    def test_ctrl_keys_off_drops_ctrl_w_and_ctrl_n(self):
        keys = [l.split()[1] for l in maps(sc.shortcuts_conf(settings(kitty_ctrl_keys=False)))]
        self.assertNotIn("ctrl+w", keys)
        self.assertNotIn("ctrl+n", keys)
        self.assertIn("ctrl+alt+w", keys)

    def test_unknown_override_ids_dropped(self):
        self.assertEqual(maps(sc.shortcuts_conf(settings(shortcuts={"nope": "ctrl+q"}))), TODAY)

    def test_normalize(self):
        self.assertEqual(sc.normalize("Shift+Ctrl+T"), "ctrl+shift+t")
        self.assertEqual(sc.normalize("alt+ctrl+super+x"), "ctrl+alt+super+x")

    def test_from_csi_u(self):
        self.assertEqual(sc.from_csi_u(b"\x1b[116;7u"), "ctrl+alt+t")
        self.assertEqual(sc.from_csi_u(b"\x1b[1;3A"), "alt+up")
        self.assertEqual(sc.from_csi_u(b"\x1b[13;6u"), "ctrl+shift+enter")
        self.assertEqual(sc.from_csi_u(b"\x1b[45;6u"), "ctrl+shift+minus")
        self.assertEqual(sc.from_csi_u(b"\x1b[50;3u"), "alt+2")
        self.assertEqual(sc.from_csi_u(b"\x1b[1;6Q"), "ctrl+shift+f2")
        self.assertIsNone(sc.from_csi_u(b"\x1b[57441;2u"))  # a modifier key on its own
        self.assertIsNone(sc.from_csi_u(b"garbage"))

    def test_every_action_has_labels(self):
        for a in sc.ACTIONS:
            for lang in ckt.LANGUAGES:
                self.assertNotEqual(ckt.t(a.label_key, lang), a.label_key, a.id)

    def test_reset_after_swap_keeps_keys_unique(self):
        s, _ = sc.assign(settings(), "close_tab", "alt+1")  # swaps with "go to tab 1"
        s = sc.reset(s, "close_tab")
        keys = sc.keys_for(s)
        self.assertEqual(keys["close_tab"], "ctrl+w")
        self.assertEqual(len(set(keys.values())), len(keys))
        conf = {l.split()[1]: l for l in maps(sc.shortcuts_conf(s))}
        self.assertIn("close_tab.py", conf["ctrl+w"])
        self.assertIn("goto_tab 1", conf["alt+1"])

    def test_assign_ignores_unknown_ids(self):
        s, _ = sc.assign(settings(shortcuts={"old_id": "ctrl+x"}), "settings", "ctrl+alt+s")
        self.assertEqual(sc.keys_for(s)["settings"], "ctrl+alt+s")

    @unittest.skipUnless(shutil.which("kitty"), "kitty not installed")
    def test_kitty_can_parse_every_action(self):
        with tempfile.TemporaryDirectory() as d:
            conf = Path(d, "kitty.conf")
            conf.write_text(sc.shortcuts_conf(settings()))
            script = Path(d, "check.py")
            script.write_text(
                "from kitty.config import load_config\n"
                f"o = load_config({str(conf)!r})\nbad = []\n"
                "for mode in o.keyboard_modes.values():\n"
                "    for defs in mode.keymap.values():\n"
                "        for kd in defs:\n"
                "            try:\n"
                "                o.alias_map.resolve_aliases(kd.definition, 'map')\n"
                "            except Exception as e:\n"
                "                bad.append(f'{kd.definition} -> {e}')\n"
                "print('BAD', len(bad)); [print(b) for b in bad]\n")
            r = subprocess.run(["kitty", "+runpy", f"exec(open({str(script)!r}).read())"],
                               capture_output=True, text=True, timeout=60)
            self.assertIn("BAD 0", r.stdout, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
