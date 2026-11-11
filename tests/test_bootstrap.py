"""Runs bootstrap.sh with stand-ins for dnf, sudo, git, curl, gsettings and chsh."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

STUBS = {
    # sudo runs the command; dnf/curl/chsh/gsettings only write down how they were called
    "sudo": 'exec "$@"',
    "dnf": 'echo "dnf $*" >> "$LOG"',
    "rpm": 'exit 1',  # nothing installed yet
    "curl": 'echo "curl $*" >> "$LOG"; echo "echo claude-installer-ran >> \\"$LOG\\""',
    "chsh": 'echo "chsh $*" >> "$LOG"',
    "gsettings": '''echo "gsettings $*" >> "$LOG"
case "$1 $3" in
  "get favorite-apps") echo "['org.gnome.Nautilus.desktop', 'org.gnome.Ptyxis.desktop']" ;;
  "get custom-keybindings") echo "@as []" ;;
esac''',
    "git": f'''echo "git $*" >> "$LOG"
if [ "$1" = clone ]; then cp -r "{REPO}" "$3" && rm -rf "$3/.git" && mkdir "$3/.git"; fi''',
    "kitty": "exit 0",
    "pkill": "exit 0",
    "fc-list": "printf 'Adwaita Mono\\nSymbola\\n'",
    "zsh": "exit 0",
}


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name, "home")
        self.home.mkdir()
        stubs = Path(self.tmp.name, "stubs")
        stubs.mkdir()
        for name, body in STUBS.items():
            f = stubs / name
            f.write_text(f"#!/bin/sh\n{body}\n")
            f.chmod(0o755)
        self.log = Path(self.tmp.name, "calls.log")
        self.log.write_text("")
        self.env = {"HOME": str(self.home), "PATH": f"{stubs}:/usr/bin:/bin", "TERM": "dumb", "SHELL": "/bin/bash",
                    "LOG": str(self.log), "CKT_REPO_URL": "https://example.invalid/ckt.git"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_bootstrap(self, *args):
        r = subprocess.run(["bash", str(REPO / "bootstrap.sh"), *args], capture_output=True, text=True,
                           env=self.env, stdin=subprocess.DEVNULL, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout, self.log.read_text()

    def test_fresh_machine_with_defaults(self):
        out, calls = self.run_bootstrap("--yes")
        self.assertIn("dnf install -y", calls)
        for pkg in ("kitty", "jq", "git", "python3", "adwaita-mono-fonts", "gdouros-symbola-fonts"):
            self.assertIn(pkg, calls)
        self.assertIn("curl -fsSL https://claude.ai/install.sh", calls)
        self.assertIn("claude-installer-ran", calls)
        target = self.home / ".local/share/custom-kitty-terminal"
        self.assertIn(f"git clone https://example.invalid/ckt.git {target}", calls)
        self.assertEqual(Path(os.path.realpath(self.home / ".config/kitty/kitty.conf")), target / "kitty/kitty.conf")
        self.assertIn("# >>> custom-kitty-terminal >>>", (self.home / ".bashrc").read_text())
        # kitty as the default terminal
        self.assertEqual((self.home / ".config/xdg-terminals.list").read_text().splitlines()[0], "kitty.desktop")
        self.assertIn("x-scheme-handler/terminal=kitty.desktop", (self.home / ".config/mimeapps.list").read_text())
        self.assertIn("gsettings set org.gnome.shell favorite-apps ['org.gnome.Nautilus.desktop', 'kitty.desktop']",
                      calls)
        # zsh is opt-in
        self.assertNotIn("chsh", calls)
        self.assertNotIn(" zsh", calls.split("dnf install -y", 1)[1].splitlines()[0])

    def test_existing_clone_is_updated(self):
        target = self.home / ".local/share/custom-kitty-terminal"
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cp", "-r", str(REPO), str(target)], check=True)
        _, calls = self.run_bootstrap("--yes")
        self.assertIn(f"git -C {target} pull --ff-only", calls)
        self.assertNotIn("git clone", calls)

    def test_zsh_on_request(self):
        _, calls = self.run_bootstrap("--yes", "--zsh")
        self.assertIn("zsh", calls.split("dnf install -y", 1)[1].splitlines()[0])
        self.assertIn("chsh -s", calls)
        self.assertIn("# >>> custom-kitty-terminal >>>", (self.home / ".zshrc").read_text())

    def test_skips(self):
        _, calls = self.run_bootstrap("--yes", "--no-claude", "--no-default-terminal")
        self.assertNotIn("claude.ai/install.sh", calls)
        self.assertFalse((self.home / ".config/xdg-terminals.list").exists())

    def test_existing_terminal_list_keeps_others(self):
        (self.home / ".config").mkdir()
        (self.home / ".config/xdg-terminals.list").write_text("org.gnome.Ptyxis.desktop\nkitty.desktop\n")
        self.run_bootstrap("--yes")
        self.assertEqual((self.home / ".config/xdg-terminals.list").read_text(),
                         "kitty.desktop\norg.gnome.Ptyxis.desktop\n")


if __name__ == "__main__":
    unittest.main()
