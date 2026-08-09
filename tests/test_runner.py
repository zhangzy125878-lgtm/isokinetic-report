import tempfile
import unittest
from pathlib import Path

from run_report import _excel_candidates


class RunnerTests(unittest.TestCase):
    def test_does_not_select_unrelated_excel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "unrelated.xlsx").touch()
            self.assertEqual(_excel_candidates(root, root / "preferred"), [])

    def test_selects_isokinetic_excel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            expected = root / "新运动员_等速肌力输入.xlsx"
            expected.touch()
            self.assertEqual(_excel_candidates(root, root / "preferred"), [expected])

    def test_preferred_directory_has_priority(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            preferred = root / "preferred"
            preferred.mkdir()
            expected = preferred / "首选_等速肌力输入.xlsx"
            expected.touch()
            (root / "项目_等速肌力输入.xlsx").touch()
            self.assertEqual(_excel_candidates(root, preferred)[0], expected)

    def test_full_template_has_priority(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            preferred = root / "preferred"
            preferred.mkdir()
            full = preferred / "等速肌力报告_Codex输入模板_按当前脚本完整版.xlsx"
            old = preferred / "等速肌力报告_Codex输入模板_周建伟.xlsx"
            old.touch()
            full.touch()
            self.assertEqual(_excel_candidates(root, preferred)[0], full)


if __name__ == "__main__":
    unittest.main()
