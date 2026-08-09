import unittest

from isokinetic_report.analysis import (
    calculate_bilateral_difference,
    calculate_ratio,
    classify_asymmetry,
    classify_joint_priority,
    classify_ratio,
)
from isokinetic_report.models import AsymmetryLevel, GaugeConfig, PriorityRule, TestRecord


def gauge() -> GaugeConfig:
    return GaugeConfig(1, "测试关节", 0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 1.0, 1.3, "测试", True)


class CalculationTests(unittest.TestCase):
    def test_ratio_and_bilateral_difference(self):
        self.assertAlmostEqual(calculate_ratio(72, 136), 72 / 136)
        self.assertAlmostEqual(calculate_bilateral_difference(72, 94), 22 / 94)
        self.assertIsNone(calculate_ratio(1, 0))
        self.assertIsNone(calculate_bilateral_difference(0, 0))

    def test_ratio_classification_both_directions(self):
        config = gauge()
        self.assertEqual(classify_ratio(0.65, config), "normal")
        self.assertEqual(classify_ratio(0.55, config), "mild")
        self.assertEqual(classify_ratio(0.85, config), "moderate")
        self.assertEqual(classify_ratio(1.10, config), "severe")
        self.assertEqual(classify_ratio(0.20, config), "severe")

    def test_asymmetry_half_open_intervals(self):
        levels = [
            AsymmetryLevel(1, "正常", 0, 0.15, "√", "#00AA00"),
            AsymmetryLevel(2, "关注", 0.15, 0.25, "！", "#FF9900"),
            AsymmetryLevel(3, "明显偏大", 0.25, None, "↑", "#FF0000"),
        ]
        self.assertEqual(classify_asymmetry(0.149, levels).state, "正常")
        self.assertEqual(classify_asymmetry(0.15, levels).state, "关注")
        self.assertEqual(classify_asymmetry(0.25, levels).state, "明显偏大")

    def test_priority_uses_sheet_rules(self):
        record = TestRecord(4, "7.3", True, "测试关节", "快速", "A", "B", 1, 1, 1, 1)
        record.left_ratio_status = "severe"
        record.right_ratio_status = "normal"
        record.a_asymmetry_state = "正常"
        record.b_asymmetry_state = "正常"
        rules = [PriorityRule("重点一", 1, "重点", "比值红色项数", ">=", 1, "任一", "#FF0000")]
        self.assertEqual(classify_joint_priority([record], rules), "重点")


if __name__ == "__main__":
    unittest.main()
