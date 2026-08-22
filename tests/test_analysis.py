import unittest

from isokinetic_report.analysis import (
    calculate_bilateral_difference,
    calculate_bilateral_differences,
    calculate_ratio,
    calculate_ratios,
    classify_asymmetry,
    classify_joint_priority,
    classify_ratio,
    generate_recommendations,
)
from isokinetic_report.models import AsymmetryLevel, GaugeConfig, PriorityRule, TestRecord


def gauge() -> GaugeConfig:
    return GaugeConfig(1, "测试关节", 0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 1.0, 1.3, "测试", True)


class CalculationTests(unittest.TestCase):
    def _record(self, joint, speed, muscle_a, muscle_b, left_a, left_b, right_a, right_b):
        record = TestRecord(4, "7.3", True, joint, speed, muscle_a, muscle_b, left_a, left_b, right_a, right_b)
        calculate_ratios(record)
        calculate_bilateral_differences(record)
        return record

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

    def test_priority_accepts_slow_and_fast_abnormal_metric(self):
        records = []
        for speed in ["慢速", "快速"]:
            record = TestRecord(4, "7.3", True, "测试关节", speed, "A", "B", 1, 1, 1, 1)
            record.left_ratio_status = "severe"
            record.right_ratio_status = "normal"
            records.append(record)
        rules = [PriorityRule("重点", 1, "关注比值", "慢速和快速异常项数", ">=", 2, "任一", "#EF4444")]
        self.assertEqual(classify_joint_priority(records, rules), "关注比值")

    def test_weaknesses_merge_speeds_and_ratio_overrides_asymmetry(self):
        records = [
            self._record("肩关节内外旋", "慢速", "外旋肌", "内旋肌", 60, 100, 74, 100),
            self._record("肩关节内外旋", "快速", "外旋肌", "内旋肌", 55, 100, 70, 100),
            self._record("膝关节屈伸", "慢速", "屈肌", "伸肌", 60, 100, 70, 100),
            self._record("膝关节屈伸", "快速", "屈肌", "伸肌", 60, 100, 70, 100),
        ]
        summaries = generate_recommendations(records)
        self.assertEqual(
            summaries,
            [
                "（1）肩关节：双侧外旋肌最大力量和快速力量不足；",
                "（2）膝关节：左侧屈肌最大力量和快速力量不足；",
            ],
        )
        self.assertFalse(any(word in "".join(summaries) for word in ["加强", "改善", "训练", "提升", "复核", "建议"]))

    def test_weaknesses_are_empty_when_no_exception_exists(self):
        records = [self._record("肩关节内外旋", "慢速", "外旋肌", "内旋肌", 80, 100, 80, 100)]
        self.assertEqual(generate_recommendations(records), [])


if __name__ == "__main__":
    unittest.main()
