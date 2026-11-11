import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import openpath as op  # noqa: E402


class TargetAtTest(unittest.TestCase):
    def test_path_with_line(self):
        line = "  Update(src/units/path.rs:42) done"
        t = op.target_at(line, line.index("units"))
        self.assertEqual(t, op.Target("path", "src/units/path.rs", 42, None))

    def test_path_with_line_and_column(self):
        line = "error at lib/ckt.py:10:5: bad"
        self.assertEqual(op.target_at(line, line.index("ckt")), op.Target("path", "lib/ckt.py", 10, 5))

    def test_plain_file_name(self):
        line = "edited README.md and more"
        self.assertEqual(op.target_at(line, line.index("READ") + 2), op.Target("path", "README.md"))

    def test_trailing_punctuation(self):
        line = "see kitty/tabs.conf."
        self.assertEqual(op.target_at(line, line.index("tabs")).value, "kitty/tabs.conf")

    def test_plain_word_is_nothing(self):
        line = "nothing to open here"
        self.assertIsNone(op.target_at(line, line.index("open")))

    def test_space_is_nothing(self):
        self.assertIsNone(op.target_at("a b", 1))

    def test_out_of_range(self):
        self.assertIsNone(op.target_at("abc", 10))

    def test_image(self):
        line = "  [Image #3] what is this?"
        self.assertEqual(op.target_at(line, line.index("#")), op.Target("image", "3"))
        self.assertEqual(op.target_at(line, line.index("[")), op.Target("image", "3"))

    def test_url(self):
        line = "open https://example.com/a?b=1 now"
        self.assertEqual(op.target_at(line, line.index("example")), op.Target("url", "https://example.com/a?b=1"))


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "src"))
        Path(self.root, "src", "a.rs").write_text("x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_relative_in_dirs(self):
        self.assertEqual(op.resolve("src/a.rs", ["/nowhere", self.root]), os.path.join(self.root, "src", "a.rs"))

    def test_absolute(self):
        p = os.path.join(self.root, "src", "a.rs")
        self.assertEqual(op.resolve(p, []), p)

    def test_git_diff_prefix(self):
        self.assertEqual(op.resolve("b/src/a.rs", [self.root]), os.path.join(self.root, "src", "a.rs"))

    def test_missing(self):
        self.assertIsNone(op.resolve("src/nope.rs", [self.root]))


class EditorCommandTest(unittest.TestCase):
    def which(self, *found):
        return lambda name: f"/usr/bin/{name}" if name in found else None

    def test_auto_prefers_vscode(self):
        cmd = op.editor_command("/p/a.rs", 3, "auto", self.which("code", "zed"))
        self.assertEqual(cmd, ["/usr/bin/code", "-g", "/p/a.rs:3"])

    def test_auto_falls_back_to_zed_then_desktop(self):
        self.assertEqual(op.editor_command("/p/a.rs", None, "auto", self.which("zed")), ["/usr/bin/zed", "/p/a.rs"])
        self.assertIsNone(op.editor_command("/p/a.rs", 3, "auto", self.which()))

    def test_system_is_desktop(self):
        self.assertIsNone(op.editor_command("/p/a.rs", 3, "system", self.which("code")))

    def test_terminal_uses_editor_env(self):
        cmd = op.editor_command("/p/a.rs", 7, "terminal", self.which(), env={"EDITOR": "nvim"})
        self.assertEqual(cmd, ["nvim", "+7", "/p/a.rs"])
        self.assertEqual(op.editor_command("/p/a.rs", None, "terminal", self.which(), env={}), ["nano", "/p/a.rs"])

    def test_chosen_editor_missing(self):
        self.assertIsNone(op.editor_command("/p/a.rs", 1, "sublime", self.which("code")))


class ImageTest(unittest.TestCase):
    def test_cache_then_claude_copy(self):
        with tempfile.TemporaryDirectory() as cache:
            os.makedirs(os.path.join(cache, "sid"))
            Path(cache, "sid", "2.png").write_text("png")
            self.assertEqual(op.image_for("sid", "2", cache), os.path.join(cache, "sid", "2.png"))
            self.assertIsNone(op.image_for("sid", "9", cache, uid=-1))

    def test_is_image(self):
        self.assertTrue(op.is_image("/a/B.PNG"))
        self.assertFalse(op.is_image("/a/b.rs"))

    def test_claude_session_for(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "42.json").write_text('{"sessionId": "abc"}')
            self.assertEqual(op.claude_session_for([7, 42], d), "abc")
            self.assertIsNone(op.claude_session_for([7], d))


if __name__ == "__main__":
    unittest.main()
