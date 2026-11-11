"""Runs kitty/save_session.py inside kitty's own Python (kitty +runpy)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SCRIPT = r"""
import json, runpy, sys
from types import SimpleNamespace as NS
m = runpy.run_path(sys.argv[-1])
print(json.dumps([m['_tab_line'](NS(name='Incerti')), m['_tab_line'](NS(name='')),
                  m['_tab_line'](NS(name='two\nlines'))]))
"""


@unittest.skipUnless(shutil.which("kitty"), "kitty not installed")
class SaveSessionTest(unittest.TestCase):
    def test_renamed_tab_keeps_its_name(self):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d, "t.py")
            script.write_text(SCRIPT)
            runner = f"exec(open({str(script)!r}).read(), {{'__name__': 't'}})"
            r = subprocess.run(["kitty", "+runpy", runner, str(REPO / "kitty/save_session.py")],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            renamed, plain, multiline = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(renamed, "new_tab Incerti")
        self.assertEqual(plain, "new_tab")
        self.assertEqual(multiline, "new_tab two lines")


if __name__ == "__main__":
    unittest.main()
