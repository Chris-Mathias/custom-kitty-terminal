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
    "curl": '''echo "curl $*" >> "$LOG"
case "$*" in
  *kitty/installer.sh*) cat <<'SH'
echo kitty-installer-ran >> "$LOG"
mkdir -p "$HOME/.local/kitty.app/bin" "$HOME/.local/kitty.app/share/applications"
printf '#!/bin/sh\\necho kitty 0.49.0\\n' > "$HOME/.local/kitty.app/bin/kitty"
cp "$HOME/.local/kitty.app/bin/kitty" "$HOME/.local/kitty.app/bin/kitten"
chmod +x "$HOME/.local/kitty.app/bin/kitty" "$HOME/.local/kitty.app/bin/kitten"
printf '[Desktop Entry]\\nExec=kitty\\nIcon=kitty\\n' > "$HOME/.local/kitty.app/share/applications/kitty.desktop"
SH
  ;;
  *) echo "echo claude-installer-ran >> \\"$LOG\\"" ;;
esac''',
    "chsh": 'echo "chsh $*" >> "$LOG"',
    "gsettings": '''echo "gsettings $*" >> "$LOG"
case "$1 $3" in
  "get favorite-apps") echo "['org.gnome.Nautilus.desktop', 'org.gnome.Ptyxis.desktop']" ;;
  "get custom-keybindings") echo "@as []" ;;
esac''',
    "git": f'''echo "git $*" >> "$LOG"
if [ "$1" = clone ]; then
  dest=$(eval echo "\\${{$#}}"); url=$(eval echo "\\${{$(($# - 1))}}")
  case $url in
    *ohmyzsh*) mkdir -p "$dest/templates" "$dest/custom/plugins" && printf 'export ZSH="$HOME/.oh-my-zsh"\\nZSH_THEME="robbyrussell"\\nplugins=(git)\\nsource $ZSH/oh-my-zsh.sh\\n' > "$dest/templates/zshrc.zsh-template" ;;
    *zsh-*) mkdir -p "$dest" ;;
    *) cp -r "{REPO}" "$dest" && rm -rf "$dest/.git" && mkdir "$dest/.git" ;;
  esac
fi''',
    "kitty": 'echo "kitty ${KITTY_VERSION:-0.47.1}"',
    "pkill": "exit 0",
    "fc-list": "printf 'Adwaita Mono\\nSymbola\\n'",
    "zsh": "exit 0",
    "apt-get": 'echo "apt-get $*" >> "$LOG"',
    "dpkg": "exit 1",
    "pacman": 'echo "pacman $*" >> "$LOG"; [ "$1" = -Q ] && exit 1; exit 0',
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

    def only(self, *managers):
        """Hides the package managers that aren't wanted (dnf is a stub; others may be real)."""
        hidden = Path(self.tmp.name, "hidden")
        hidden.mkdir(exist_ok=True)
        stubs = Path(self.tmp.name, "stubs")
        for name in ("dnf", "rpm", "apt-get", "dpkg", "pacman"):
            if name not in managers and (stubs / name).exists():
                (stubs / name).rename(hidden / name)
        # Real package managers on this machine must not be found either.
        self.env["PATH"] = f"{stubs}:{self.tmp.name}/sysbin"
        sysbin = Path(self.tmp.name, "sysbin")
        sysbin.mkdir(exist_ok=True)
        for tool in ("bash", "sh", "env", "python3", "jq", "sed", "cp", "rm", "mkdir", "mv", "ln", "readlink", "date",
                     "dirname", "basename", "cat", "tr", "grep", "touch", "printf", "id", "realpath", "chmod", "ls"):
            real = subprocess.run(["bash", "-c", f"command -v {tool}"], capture_output=True, text=True).stdout.strip()
            if real and not (sysbin / tool).exists():
                (sysbin / tool).symlink_to(real)

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

    def test_zsh_like_the_authors_on_a_new_machine(self):
        _, calls = self.run_bootstrap("--yes", "--zsh")
        for repo in ("ohmyzsh/ohmyzsh", "zsh-users/zsh-autosuggestions", "zsh-users/zsh-syntax-highlighting"):
            self.assertIn(repo, calls)
        zshrc = (self.home / ".zshrc").read_text()
        self.assertIn('ZSH_THEME="bira"', zshrc)
        self.assertIn("plugins=(git zsh-autosuggestions zsh-syntax-highlighting)", zshrc)
        self.assertIn("# >>> custom-kitty-terminal >>>", zshrc)

    def test_existing_oh_my_zsh_gets_only_the_missing_plugins(self):
        (self.home / ".oh-my-zsh/custom/plugins/zsh-autosuggestions").mkdir(parents=True)
        (self.home / ".zshrc").write_text('export ZSH="$HOME/.oh-my-zsh"\nZSH_THEME="agnoster"\n'
                                          "plugins=(git zsh-autosuggestions)\nsource $ZSH/oh-my-zsh.sh\n")
        _, calls = self.run_bootstrap("--yes", "--zsh")
        self.assertNotIn("ohmyzsh/ohmyzsh", calls)
        self.assertNotIn("zsh-users/zsh-autosuggestions", calls)
        zshrc = (self.home / ".zshrc").read_text()
        self.assertIn('ZSH_THEME="agnoster"', zshrc)  # their theme stays
        self.assertIn("plugins=(git zsh-autosuggestions zsh-syntax-highlighting)", zshrc)

    def test_zshrc_without_oh_my_zsh_gets_a_block(self):
        (self.home / ".zshrc").write_text("alias ll='ls -l'\n")
        self.run_bootstrap("--yes", "--zsh")
        zshrc = (self.home / ".zshrc").read_text()
        self.assertIn("alias ll='ls -l'", zshrc)
        self.assertIn("source $ZSH/oh-my-zsh.sh", zshrc)
        self.assertIn("zsh-syntax-highlighting", zshrc)

    def test_oh_my_zsh_can_be_refused(self):
        _, calls = self.run_bootstrap("--yes", "--zsh", "--no-oh-my-zsh")
        self.assertIn("chsh -s", calls)
        self.assertNotIn("ohmyzsh", calls)

    def test_debian_and_ubuntu_use_apt(self):
        self.only("apt-get", "dpkg")
        _, calls = self.run_bootstrap("--yes", "--no-claude")
        line = next(l for l in calls.splitlines() if l.startswith("apt-get install -y"))
        self.assertIn("python3", line)
        self.assertNotIn("kitty", line)  # the distro's kitty is too old: the official one is used
        self.assertNotIn("dnf", calls)

    def test_old_kitty_gets_the_official_build(self):
        self.env["KITTY_VERSION"] = "0.32.2"
        out, calls = self.run_bootstrap("--yes", "--no-claude")
        self.assertIn("sw.kovidgoyal.net/kitty/installer.sh", calls)
        self.assertIn("kitty-installer-ran", calls)
        app = self.home / ".local/kitty.app"
        self.assertEqual(os.readlink(self.home / ".local/bin/kitty"), str(app / "bin/kitty"))
        desktop = (self.home / ".local/share/applications/kitty.desktop").read_text()
        self.assertIn(f"Exec={app}/bin/kitty", desktop)

    def test_recent_kitty_is_kept(self):
        _, calls = self.run_bootstrap("--yes", "--no-claude")
        self.assertNotIn("kitty/installer.sh", calls)

    def test_arch_uses_pacman(self):
        self.only("pacman")
        _, calls = self.run_bootstrap("--yes", "--no-claude")
        line = next(l for l in calls.splitlines() if l.startswith("pacman -S"))
        self.assertIn("--needed", line)
        self.assertIn(" python", line)
        self.assertNotIn("python3", line)

    def test_unknown_distro_still_installs_when_tools_exist(self):
        self.only()
        out, calls = self.run_bootstrap("--yes", "--no-claude")
        self.assertIn("install these yourself", out)
        self.assertTrue((self.home / ".config/kitty/kitty.conf").is_symlink())


if __name__ == "__main__":
    unittest.main()
