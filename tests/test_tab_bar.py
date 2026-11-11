"""Runs kitty/tab_bar.py inside kitty's own Python (kitty +runpy) with a fake tab manager."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SCRIPT = r"""
import json, os, runpy, sys
home = sys.argv[-1]
os.environ['HOME'] = home
from kitty.fast_data_types import GLFW_MOUSE_BUTTON_LEFT as LEFT, GLFW_RELEASE as RELEASE
from kitty.tabs import TabManager
calls = []
def original(self, *args, **kwargs):
    calls.append([list(args), sorted(kwargs)])
TabManager.handle_tab_bar_mouse = original
if '_ckt_original_mouse' in TabManager.__dict__:
    del TabManager._ckt_original_mouse
m = runpy.run_path(sys.argv[-2])
wrapper = TabManager.handle_tab_bar_mouse
opened = []
wrapper.__globals__['_open_menu'] = lambda tm: opened.append(1)

from types import SimpleNamespace as NS
tm = NS(tab_bar=NS(window_geometry=NS(left=0), cell_width=10, screen=NS(columns=100)))
gear_x = 10.0 * (m['gear_start'](100) + 1)
out = {'enabled': m['GEAR_ENABLED']}
wrapper(tm, gear_x, 5.0, LEFT, 0, RELEASE)
out['not_drawn'] = [len(opened), len(calls)]
wrapper.__globals__['_set_gear_drawn'](tm.tab_bar.screen, True)
wrapper(tm, gear_x, 5.0, LEFT, 0, RELEASE)
out['drawn'] = [len(opened), len(calls)]
wrapper(tm, 5.0, 5.0, LEFT, 0, RELEASE, 'extra', new_kw=1)
out['new_signature'] = calls[-1]
out['draw'] = m['TAB_DRAW'].__name__
print(json.dumps(out))
"""


@unittest.skipUnless(shutil.which("kitty"), "kitty not installed")
class TabBarHookTest(unittest.TestCase):
    def run_hook(self, settings=None):
        with tempfile.TemporaryDirectory() as home:
            if settings is not None:
                cfg = Path(home, ".config/custom-kitty-terminal")
                cfg.mkdir(parents=True)
                (cfg / "settings.json").write_text(json.dumps(settings))
            menu = Path(home, ".local/bin/ct-config")
            menu.parent.mkdir(parents=True)
            menu.write_text("#!/bin/sh\n")
            script = Path(home, "hook_test.py")
            script.write_text(SCRIPT)
            runner = f"exec(open({str(script)!r}).read(), {{'__name__': 'hook_test'}})"
            r = subprocess.run(["kitty", "+runpy", runner, str(REPO / "kitty/tab_bar.py"), home],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout.strip().splitlines()[-1])

    def test_gear_click_only_when_drawn(self):
        out = self.run_hook()
        self.assertTrue(out["enabled"])
        self.assertEqual(out["not_drawn"], [0, 1])  # passed on to kitty: it's a tab or "+" there
        self.assertEqual(out["drawn"], [1, 1])  # opened the menu, kitty didn't see it

    def test_passes_unknown_arguments_through(self):
        args, kwargs = self.run_hook()["new_signature"]
        self.assertEqual(args[-1], "extra")
        self.assertEqual(kwargs, ["new_kw"])

    def test_tab_style_picks_the_drawing(self):
        self.assertEqual(self.run_hook()["draw"], "draw_tab_with_powerline")
        self.assertEqual(self.run_hook({"tab_style": "separators"})["draw"], "draw_tab_with_separator")


if __name__ == "__main__":
    unittest.main()
