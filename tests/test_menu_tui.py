"""Drives bin/ct-config in a pseudo-terminal, like a person would."""
import fcntl
import json
import os
import pty
import signal
import select
import struct
import tempfile
import termios
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOWN, ENTER = b"\x1bOB", b"\r"


class MenuTuiTest(unittest.TestCase):
    def run_menu(self, keys, prepare=None, hangup_after=None):
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "CKT_CONFIG_DIR": f"{home}/cfg", "TERM": "xterm-256color", "PATH": "/usr/bin:/bin"}
            if prepare:
                env.update(prepare(home) or {})
            pid, fd = pty.fork()
            if pid == 0:
                os.execve("/usr/bin/python3", ["python3", str(REPO / "bin/ct-config")], env)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
            out = b""

            def pump(seconds=0.5):
                nonlocal out
                end = time.time() + seconds
                while time.time() < end:
                    if select.select([fd], [], [], 0.05)[0]:
                        try:
                            out += os.read(fd, 65536)
                        except OSError:
                            return

            pump(1.0)
            for n, k in enumerate(keys):
                os.write(fd, k)
                pump(0.3)
                if hangup_after == n:
                    os.kill(pid, signal.SIGHUP)  # the window is closed mid-recording
                    break
            for _ in range(50):  # a menu stuck waiting for keys fails the test instead of hanging it
                if os.waitpid(pid, os.WNOHANG) != (0, 0):
                    break
                pump(0.1)
            else:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            self.kitten_log = Path(home, "kitten.log").read_text() if Path(home, "kitten.log").exists() else ""
            path = Path(home, "cfg/settings.json")
            settings = json.loads(path.read_text()) if path.exists() else None
            return settings, out.decode("utf8", "replace")

    def test_turn_ligatures_off(self):
        # Appearance → Ligatures (12th item) → Off
        keys = [ENTER] + [DOWN] * 11 + [ENTER, DOWN, ENTER, b"q"]
        settings, screen = self.run_menu(keys)
        self.assertIn("Appearance", screen)
        self.assertIs(settings["ligatures"], False)

    def test_order_editor_moves_a_section(self):
        # Claude Code → Side panel → Order: pick Sessions up, move it down once, drop.
        keys = [DOWN, ENTER, DOWN, DOWN, ENTER] + [DOWN] * 4 + [ENTER, ENTER, DOWN, ENTER, b"q"]
        settings, _ = self.run_menu(keys)
        self.assertEqual(settings["panel"]["sections"], ["git", "sessions", "tasks", "files"])

    def test_record_a_shortcut(self):
        # Shortcuts → Settings menu (21st row) → Record new keys → Ctrl+Alt+Y
        keys = [DOWN] * 3 + [ENTER] + [DOWN] * 20 + [ENTER, ENTER, b"\x1b[121;7u", b"q"]
        settings, screen = self.run_menu(keys)
        self.assertEqual(settings["shortcuts"], {"settings": "ctrl+alt+y"})
        self.assertIn("\x1b[>1u", screen)  # asked kitty for modifier key codes
        self.assertIn("\x1b[<u", screen)  # and gave them back

    def test_escape_cancels_recording(self):
        keys = [DOWN] * 3 + [ENTER] + [DOWN] * 20 + [ENTER, ENTER, b"\x1b[27u", b"q"]
        settings, screen = self.run_menu(keys)
        self.assertTrue(settings is None or settings["shortcuts"] == {})
        self.assertNotIn("Use at least one", screen)

    def test_kitty_shortcuts_come_back_when_the_menu_is_closed(self):
        def fake_kitten(home):
            stub = Path(home, "bin/kitten")
            stub.parent.mkdir()
            stub.write_text(f'#!/bin/sh\necho "$*" >> {home}/kitten.log\n')
            stub.chmod(0o755)
            return {"PATH": f"{home}/bin:/usr/bin:/bin", "KITTY_LISTEN_ON": "unix:@test"}

        keys = [DOWN] * 3 + [ENTER] + [DOWN] * 20 + [ENTER, ENTER]
        self.run_menu(keys, prepare=fake_kitten, hangup_after=len(keys) - 1)
        self.assertIn("push_keyboard_mode ckt-capture", self.kitten_log)
        self.assertIn("pop_keyboard_mode", self.kitten_log)


if __name__ == "__main__":
    unittest.main()
