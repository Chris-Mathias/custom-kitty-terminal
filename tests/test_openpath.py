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


class CellTest(unittest.TestCase):
    def test_narrow_text_maps_one_to_one(self):
        self.assertEqual(op.index_at_cell("abc", 1), 1)

    def test_wide_characters_take_two_columns(self):
        line = "中文 src/a.rs"  # 中 and 文 take 2 columns each
        self.assertEqual(op.index_at_cell(line, 0), 0)
        self.assertEqual(op.index_at_cell(line, 1), 0)
        self.assertEqual(op.index_at_cell(line, 2), 1)
        self.assertEqual(op.target_at_cell(line, 7), op.Target("path", "src/a.rs"))

    def test_past_the_end(self):
        self.assertEqual(op.index_at_cell("ab", 5), 5)
        self.assertIsNone(op.target_at_cell("ab", 5))


class ImageThumbnailTest(unittest.TestCase):
    P = op.IMAGE_PLACEHOLDER + "\u0305\u0305"  # a placeholder cell with its row/column marks

    def rows(self):
        left = "chat text here".ljust(10)
        return [
            left + "│ IMAGES",
            left + "│ [Image #12]",
            left + "│ " + self.P * 6,
            left + "│ " + self.P * 6,
            left + "│",
            left + "│ [Image #11]",
            left + "│ " + self.P * 6,
        ]

    def test_click_on_the_thumbnail_finds_its_label(self):
        rows = self.rows()
        x = len("chat text here".ljust(10)) + 4  # inside the picture
        self.assertEqual(op.image_at_cell(rows, 3, x), op.Target("image", "12"))
        self.assertEqual(op.image_at_cell(rows, 6, x), op.Target("image", "11"))

    def test_not_on_a_thumbnail(self):
        rows = self.rows()
        self.assertIsNone(op.image_at_cell(rows, 4, 14))
        self.assertIsNone(op.image_at_cell(rows, 3, 2))  # the chat side of that row


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

    def test_project_folder_opens_with_the_file(self):
        cmd = op.editor_command("/r/src/a.rs", 3, "vscode", self.which("code"), root="/r")
        self.assertEqual(cmd, ["/usr/bin/code", "/r", "-g", "/r/src/a.rs:3"])
        self.assertEqual(op.editor_command("/r/a.rs", None, "zed", self.which("zed"), root="/r"),
                         ["/usr/bin/zed", "/r", "/r/a.rs"])

    def test_project_root_from_git(self):
        ok = lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "/r\n"})()  # noqa: E731
        no = lambda *a, **k: type("R", (), {"returncode": 128, "stdout": ""})()  # noqa: E731
        self.assertEqual(op.project_root("/r/src/a.rs", ok), "/r")
        self.assertIsNone(op.project_root("/tmp/a.rs", no))

    def test_chosen_editor_missing(self):
        self.assertIsNone(op.editor_command("/p/a.rs", 1, "sublime", self.which("code")))


class PanelFilesTest(unittest.TestCase):
    FILES = ["/r/apps/api/index.ts", "/r/apps/web/index.ts", "/r/yazi/yazi.toml"]

    def test_unique_name(self):
        self.assertEqual(op.match_panel_file("yazi.toml", "E yazi.toml yazi", self.FILES), "/r/yazi/yazi.toml")

    def test_same_name_uses_the_folder_on_the_row(self):
        self.assertEqual(op.match_panel_file("index.ts", " M index.ts web", self.FILES), "/r/apps/web/index.ts")

    def test_partial_path_and_missing(self):
        self.assertEqual(op.match_panel_file("api/index.ts", "", self.FILES), "/r/apps/api/index.ts")
        self.assertIsNone(op.match_panel_file("nope.rs", "", self.FILES))

    def test_reads_the_session_file(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "sid.json").write_text('{"files": ["/a/b.rs", 3]}')
            self.assertEqual(op.panel_files("sid", d), ["/a/b.rs"])
            self.assertEqual(op.panel_files("other", d), [])


class ImageTest(unittest.TestCase):
    def test_cache_then_claude_copy(self):
        with tempfile.TemporaryDirectory() as cache:
            os.makedirs(os.path.join(cache, "sid"))
            Path(cache, "sid", "2.png").write_text("png")
            self.assertEqual(op.image_for("sid", "2", cache), os.path.join(cache, "sid", "2.png"))
            self.assertIsNone(op.image_for("sid", "9", cache, uid=-1))

    def test_image_from_transcript(self):
        import base64
        import json as js
        png = base64.b64encode(b"\x89PNG fake").decode()
        msg = {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "[Image #3] [Image #4] look"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png}},
        ]}}
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "projects", "-p"))
            Path(root, "projects", "-p", "sid.jsonl").write_text('{"type": "x"}\n' + js.dumps(msg) + "\n")
            out = op.image_from_transcript("sid", "4", os.path.join(root, "projects"), os.path.join(root, "cache"))
            self.assertEqual(out, os.path.join(root, "cache", "sid", "4.png"))
            self.assertEqual(Path(out).read_bytes(), b"\x89PNG fake")
            self.assertIsNone(op.image_from_transcript("sid", "9", os.path.join(root, "projects"), os.path.join(root, "cache")))

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
