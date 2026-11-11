import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

STUBS = {
    "kitty": "exit 0",
    "claude": "exit 0",
    "pkill": "exit 0",
    "fc-list": "printf 'Adwaita Mono\\n'",
}

OLD_ZSHRC = """export PATH="$HOME/.local/bin:$PATH"

# Claude Code com o painel lateral (custom-kitty-terminal)
claude() {
  local painel="$HOME/.local/share/claude-mods/painel-sessao"
  if [[ -d $painel ]]; then command claude --plugin-dir "$painel" "$@"
  else command claude "$@"; fi
}
alias ll='ls -l'
"""


class InstallTest(unittest.TestCase):
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
        self.env = {"HOME": str(self.home), "PATH": f"{stubs}:/usr/bin:/bin", "TERM": "dumb",
                    "SHELL": "/usr/bin/zsh"}

    def tearDown(self):
        self.tmp.cleanup()

    def install(self):
        r = subprocess.run(["bash", str(REPO / "install.sh")], capture_output=True, text=True,
                           env=self.env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def p(self, rel):
        return self.home / rel

    def settings(self):
        return json.loads(self.p(".config/custom-kitty-terminal/settings.json").read_text())

    def tree(self):
        out = {}
        for root, dirs, files in os.walk(self.home):
            for name in dirs + files:
                f = Path(root, name)
                rel = str(f.relative_to(self.home))
                out[rel] = os.readlink(f) if f.is_symlink() else (f.read_text() if f.is_file() else "<dir>")
        return out

    def test_fresh_install_links_and_english_default(self):
        self.install()
        for rel, target in [
            (".config/kitty/kitty.conf", "kitty/kitty.conf"),
            (".config/kitty/tabs.conf", "kitty/tabs.conf"),
            (".config/kitty/close_tab.py", "kitty/close_tab.py"),
            (".local/bin/ct-config", "bin/ct-config"),
            (".local/bin/claude-restore", "bin/claude-restore"),
            (".claude/statusline.sh", "claude/statusline.sh"),
            (".claude/themes/dracula.json", "themes/dracula/claude.json"),
            (".claude/output-styles/concise-english.md", "claude/output-styles/concise-english.md"),
            (".local/share/claude-mods/session-panel", "claude/session-panel"),
        ]:
            with self.subTest(rel=rel):
                self.assertEqual(Path(os.path.realpath(self.p(rel))), REPO / target)
        self.assertEqual(self.settings()["language"], "en")
        zshrc = self.p(".zshrc").read_text()
        self.assertEqual(zshrc.count("# >>> custom-kitty-terminal >>>"), 1)
        self.assertIn("claude-mods/session-panel", zshrc)
        self.assertTrue(self.p(".config/kitty/generated/theme.conf").exists())
        claude = json.loads(self.p(".claude/settings.json").read_text())
        self.assertEqual(claude["outputStyle"], "Concise English")
        self.assertTrue(self.p(".config/kitty/last-session.kitty-session").exists())

    def test_migrates_old_layout(self):
        kitty = self.p(".config/kitty")
        kitty.mkdir(parents=True)
        for old in ("abas.conf", "fechar_aba.py", "fechar-aba-dialogo.sh", "salvar_sessao.py"):
            (kitty / old).symlink_to(REPO / "kitty" / old)  # dangling now: the repo renamed them
        (kitty / "ultima-sessao.kitty-session").write_text(
            "new_tab\nlaunch /usr/bin/zsh -ic '/home/x/.local/bin/claude-restaurar abc'\n")
        bin_ = self.p(".local/bin")
        bin_.mkdir(parents=True)
        (bin_ / "claude-painel").symlink_to(REPO / "bin/claude-painel")
        (bin_ / "claude-restaurar").symlink_to(REPO / "bin/claude-restaurar")
        mods = self.p(".local/share/claude-mods")
        mods.mkdir(parents=True)
        (mods / "painel-sessao").symlink_to(REPO / "claude/painel-sessao")
        self.p(".claude/themes").mkdir(parents=True)
        self.p(".claude/themes/fedora.json").symlink_to(REPO / "claude/themes/fedora.json")  # old location
        self.p(".claude/settings.json").write_text(json.dumps({"model": "opus", "outputStyle": "Português conciso"}))
        self.p(".zshrc").write_text(OLD_ZSHRC)

        self.install()

        for gone in (".config/kitty/abas.conf", ".config/kitty/fechar_aba.py", ".config/kitty/salvar_sessao.py",
                     ".local/bin/claude-painel", ".local/bin/claude-restaurar",
                     ".local/share/claude-mods/painel-sessao", ".config/kitty/ultima-sessao.kitty-session"):
            with self.subTest(gone=gone):
                self.assertFalse(os.path.lexists(self.p(gone)))
        dangling = [str(f) for f in self.home.rglob("*") if f.is_symlink() and not f.exists()]
        self.assertEqual(dangling, [])
        self.assertEqual(list(self.p(".claude/themes").glob("*.bak-*")), [])
        session = self.p(".config/kitty/last-session.kitty-session").read_text()
        self.assertIn("claude-restore abc", session)
        self.assertNotIn("claude-restaurar", session)
        self.assertEqual(self.settings()["language"], "pt")
        zshrc = self.p(".zshrc").read_text()
        self.assertNotIn("painel-sessao", zshrc)
        self.assertNotIn("Claude Code com o painel lateral", zshrc)
        self.assertEqual(zshrc.count("# >>> custom-kitty-terminal >>>"), 1)
        self.assertIn("alias ll='ls -l'", zshrc)
        claude = json.loads(self.p(".claude/settings.json").read_text())
        self.assertEqual(claude["model"], "opus")
        self.assertEqual(claude["outputStyle"], "Português conciso")
        self.assertEqual(len(list(self.p(".claude").glob("settings.json.bak-*"))), 1)

    def test_idempotent(self):
        self.install()
        first = self.tree()
        self.install()
        self.assertEqual(self.tree(), first)

    def test_foreign_file_not_removed(self):
        kitty = self.p(".config/kitty")
        kitty.mkdir(parents=True)
        (kitty / "abas.conf").write_text("mine\n")
        out = self.install()
        self.assertEqual((kitty / "abas.conf").read_text(), "mine\n")
        self.assertIn("abas.conf", out)

    def test_existing_file_backed_up(self):
        kitty = self.p(".config/kitty")
        kitty.mkdir(parents=True)
        (kitty / "kitty.conf").write_text("old\n")
        self.install()
        backups = list(kitty.glob("kitty.conf.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "old\n")


if __name__ == "__main__":
    unittest.main()
