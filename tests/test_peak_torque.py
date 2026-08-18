import tempfile
import unittest
from pathlib import Path

from PIL import Image

from isokinetic_report.analysis import analyze
from isokinetic_report.excel_io import load_workbook_data
from isokinetic_report.models import TestRecord
from isokinetic_report.render_peak_torque import _report_joints, _torque_lines, generate_report
from tests import test_end_to_end


class PeakTorqueReportTests(unittest.TestCase):
    def test_torque_lines_include_both_muscles_and_units(self):
        record = TestRecord(4, "7.3", True, "膝关节屈伸", "慢速", "屈肌", "伸肌", 99, 163, 69, 103)
        self.assertEqual(_torque_lines(record, "左侧"), ("屈 99 Nm", "伸 163 Nm"))
        self.assertEqual(_torque_lines(record, "右侧"), ("屈 69 Nm", "伸 103 Nm"))

    def test_single_muscle_torque_omits_empty_second_line(self):
        record = TestRecord(18, "8.10", True, "躯干旋转", "慢速", "旋转", "", 111, None, 105, None)
        self.assertEqual(_torque_lines(record, "左侧"), ("旋转 111 Nm", ""))

    def test_sheet_two_only_joint_is_appended_to_peak_torque_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workbook_path = root / "input_4.xlsx"
            test_end_to_end.EndToEndTests()._make_workbook(workbook_path, joint_count=4)
            athlete, records, standards, comments = load_workbook_data(workbook_path)
            records.append(TestRecord(18, "8.10", True, "躯干旋转", "慢速", "旋转", "", 111, None, 105, None))
            result = analyze(athlete, records, standards, comments)
            self.assertEqual(_report_joints(result)[-1], ("躯干旋转", 5))

    def test_four_joint_peak_torque_report_uses_separate_taller_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workbook_path = root / "input_4.xlsx"
            test_end_to_end.EndToEndTests()._make_workbook(workbook_path, joint_count=4)
            athlete, records, standards, comments = load_workbook_data(workbook_path)
            paths = generate_report(analyze(athlete, records, standards, comments), root / "output")
            self.assertIn("峰力矩版", paths.png.name)
            with Image.open(paths.png) as image:
                self.assertEqual(image.size, (1600, 1872))


if __name__ == "__main__":
    unittest.main()
