from __future__ import annotations

import math
import operator
from collections import defaultdict
from typing import Callable, Optional

from .models import AnalysisResult, AsymmetryLevel, AthleteInfo, GaugeConfig, PriorityRule, Standards, TestRecord


EXPECTED_JOINTS = ["肩关节屈伸", "肩关节内外旋", "髋关节屈伸", "膝关节屈伸", "踝关节屈伸"]
EXPECTED_SPEEDS = ["慢速", "快速"]
WEAKNESS_MODULE_ORDER = [
    "肩关节屈伸",
    "肩关节内外旋",
    "肩关节外展内收",
    "肘关节屈伸",
    "上肢推拉",
    "髋关节屈伸",
    "髋关节外展内收",
    "膝关节屈伸",
    "踝关节屈伸",
    "躯干屈伸",
    "躯干旋转",
]
WEAKNESS_RATIO_RANGES = {
    "肩关节屈伸": (0.60, 0.70),
    "肩关节内外旋": (0.75, 0.85),
    "肩关节外展内收": (0.95, 1.05),
    "肘关节屈伸": (0.95, 1.05),
    "髋关节屈伸": (0.60, 0.70),
    "髋关节外展内收": (0.95, 1.05),
    "膝关节屈伸": (0.60, 0.70),
    "踝关节屈伸": (0.30, 0.40),
}
WEAKNESS_GROUP_NAMES = {
    "肩关节屈伸": "肩关节",
    "肩关节内外旋": "肩关节",
    "肩关节外展内收": "肩关节",
    "髋关节屈伸": "髋关节",
    "髋关节外展内收": "髋关节",
    "膝关节屈伸": "膝关节",
    "踝关节屈伸": "踝关节",
    "肘关节屈伸": "肘关节",
    "躯干屈伸": "躯干",
    "躯干旋转": "躯干",
}
RATIO_STATUS_LABELS = {
    "normal": "目标范围",
    "mild": "轻度偏离",
    "moderate": "中度偏离",
    "severe": "明显偏离",
    "missing": "缺失",
}


def calculate_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    value = numerator / denominator
    return value if math.isfinite(value) else None


def calculate_bilateral_difference(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None
    denominator = max(left, right)
    if denominator == 0:
        return None
    value = abs(left - right) / denominator
    return value if math.isfinite(value) else None


def calculate_ratios(record: TestRecord) -> None:
    record.left_ratio = calculate_ratio(record.left_a, record.left_b)
    record.right_ratio = calculate_ratio(record.right_a, record.right_b)


def calculate_bilateral_differences(record: TestRecord) -> None:
    record.a_asymmetry = calculate_bilateral_difference(record.left_a, record.right_a)
    record.b_asymmetry = calculate_bilateral_difference(record.left_b, record.right_b)


def validate_existing_values(record: TestRecord, tolerance: float = 0.01) -> list[str]:
    warnings: list[str] = []
    pairs = [
        ("左比例", record.left_ratio, record.existing_left_ratio),
        ("右比例", record.right_ratio, record.existing_right_ratio),
        ("A双侧差异", record.a_asymmetry, record.existing_a_asymmetry),
        ("B双侧差异", record.b_asymmetry, record.existing_b_asymmetry),
    ]
    for label, calculated, existing in pairs:
        if existing is None:
            warnings.append(f"Sheet 2 第 {record.row_number} 行 {label} 没有可校验值，程序将使用重新计算结果")
        elif calculated is not None and abs(calculated - existing) > tolerance:
            warnings.append(
                f"Sheet 2 第 {record.row_number} 行 {label} 校验差异 {abs(calculated - existing):.3f} > {tolerance:.2f}，程序使用重新计算结果"
            )
    return warnings


def classify_ratio(value: Optional[float], config: GaugeConfig) -> str:
    if value is None:
        return "missing"
    if value < config.low_red_upper or value > config.high_orange_upper:
        return "severe"
    if value < config.low_orange_upper or value > config.high_yellow_upper:
        return "moderate"
    if value < config.target_low or value > config.target_high:
        return "mild"
    return "normal"


def classify_asymmetry(value: Optional[float], levels: list[AsymmetryLevel]) -> Optional[AsymmetryLevel]:
    if value is None:
        return None
    for level in sorted((level for level in levels if level.enabled), key=lambda item: item.order):
        if value >= level.minimum_inclusive and (level.maximum_exclusive is None or value < level.maximum_exclusive):
            return level
    return None


def _compare(value: float, operator_text: str, threshold: float) -> bool:
    operations: dict[str, Callable[[float, float], bool]] = {
        ">=": operator.ge,
        ">": operator.gt,
        "==": operator.eq,
        "=": operator.eq,
        "<=": operator.le,
        "<": operator.lt,
    }
    if operator_text not in operations:
        raise ValueError(f"不支持的比较符：{operator_text}")
    return operations[operator_text](value, threshold)


def _is_ratio_abnormal(status: str) -> bool:
    return status not in {"normal", "missing"}


def joint_metrics(records: list[TestRecord]) -> dict[str, int]:
    ratio_statuses = [status for r in records for status in [r.left_ratio_status, r.right_ratio_status]]
    asymmetry_states = [state for r in records for state in [r.a_asymmetry_state, r.b_asymmetry_state] if state]
    fast_abnormal = 0
    both_sides = 0
    for record in records:
        ratio_pair = [record.left_ratio_status, record.right_ratio_status]
        asym_pair = [record.a_asymmetry_state, record.b_asymmetry_state]
        if record.speed == "快速":
            fast_abnormal += sum(_is_ratio_abnormal(status) for status in ratio_pair)
            fast_abnormal += sum(state not in {None, "正常"} for state in asym_pair)
        if all(_is_ratio_abnormal(status) for status in ratio_pair):
            both_sides += 1
    ratio_deviation = sum(_is_ratio_abnormal(status) for status in ratio_statuses)
    asym_deviation = sum(state != "正常" for state in asymmetry_states)
    return {
        "比值红色项数": sum(status == "severe" for status in ratio_statuses),
        "比值偏离项数": ratio_deviation,
        "双侧差异↑项数": sum(state == "明显偏大" for state in asymmetry_states),
        "双侧差异！或↑项数": asym_deviation,
        "快速异常项数": fast_abnormal,
        "同速双侧比值异常次数": both_sides,
        "总异常项数": ratio_deviation + asym_deviation,
    }


def classify_joint_priority(records: list[TestRecord], rules: list[PriorityRule]) -> Optional[str]:
    metrics = joint_metrics(records)
    groups: dict[tuple[str, str], list[PriorityRule]] = defaultdict(list)
    for rule in rules:
        if rule.enabled:
            groups[(rule.output_label, rule.group)].append(rule)
    ordered_groups = sorted(groups.items(), key=lambda item: min(rule.order for rule in item[1]))
    for (output_label, _group), group_rules in ordered_groups:
        results = [_compare(metrics[rule.metric], rule.operator, rule.threshold) for rule in group_rules]
        relation = group_rules[0].group_relation
        matched = all(results) if relation == "全部" else any(results)
        if matched:
            return output_label
    return None


def _missing_value_warnings(record: TestRecord) -> list[str]:
    warnings: list[str] = []
    values = {
        "左A峰力矩": record.left_a,
        "左B峰力矩": record.left_b,
        "右A峰力矩": record.right_a,
        "右B峰力矩": record.right_b,
    }
    for label, value in values.items():
        if value is None:
            warnings.append(f"Sheet 2 第 {record.row_number} 行 {label} 缺失，报告对应位置将显示“—”")
    if record.left_b == 0:
        warnings.append(f"Sheet 2 第 {record.row_number} 行左B峰力矩为 0，左比例无法计算")
    if record.right_b == 0:
        warnings.append(f"Sheet 2 第 {record.row_number} 行右B峰力矩为 0，右比例无法计算")
    if record.left_a == record.right_a == 0:
        warnings.append(f"Sheet 2 第 {record.row_number} 行 A 肌群双侧均为 0，双侧差异无法计算")
    if record.left_b == record.right_b == 0:
        warnings.append(f"Sheet 2 第 {record.row_number} 行 B 肌群双侧均为 0，双侧差异无法计算")
    return warnings


def _dataset_warnings(records: list[TestRecord], standards: Standards) -> list[str]:
    warnings: list[str] = []
    current = [record for record in records if record.is_current]
    if not current:
        return ["Sheet 2 没有“是否本次=是”的记录"]
    dates = sorted({record.date_label for record in current})
    if len(dates) > 1:
        warnings.append(f"本次记录包含多个日期标签：{', '.join(dates)}")
    seen: set[tuple[str, str]] = set()
    for record in current:
        key = (record.joint, record.speed)
        if key in seen:
            warnings.append(f"本次记录存在重复组合：{record.joint}/{record.speed}")
        seen.add(key)
    expected_joints = list(standards.gauges) if standards.gauges else EXPECTED_JOINTS
    for joint in expected_joints:
        for speed in EXPECTED_SPEEDS:
            if (joint, speed) not in seen:
                warnings.append(f"本次记录缺少：{joint}/{speed}，报告对应位置将显示“—”")
    return warnings


def generate_recommendations(records: list[TestRecord], max_items: int = 4) -> list[str]:
    """按关节模块合并比例异常和双侧差异，生成关键薄弱环节。"""
    def muscle_name(value: str) -> str:
        return value if value.endswith(("肌", "肌群")) else f"{value}肌"

    module_rank = {name: index for index, name in enumerate(WEAKNESS_MODULE_ORDER)}
    grouped: dict[str, dict[tuple[str, str], set[str]]] = defaultdict(lambda: defaultdict(set))
    group_rank: dict[str, int] = {}
    muscle_rank: dict[tuple[str, str], int] = {}

    ordered_records = sorted(
        enumerate(records),
        key=lambda item: (
            module_rank.get(item[1].joint, len(module_rank)),
            EXPECTED_SPEEDS.index(item[1].speed) if item[1].speed in EXPECTED_SPEEDS else len(EXPECTED_SPEEDS),
            item[0],
        ),
    )
    for record_index, record in ordered_records:
        group_name = WEAKNESS_GROUP_NAMES.get(record.joint, record.joint)
        group_rank[group_name] = min(group_rank.get(group_name, len(module_rank)), module_rank.get(record.joint, len(module_rank)))
        strength_type = "最大力量" if record.speed == "慢速" else "快速力量"
        ratio_covered_muscles: set[str] = set()

        ratio_range = WEAKNESS_RATIO_RANGES.get(record.joint)
        ratio_findings: list[tuple[str, str]] = []
        if ratio_range:
            low, high = ratio_range
            for side, value in (("左侧", record.left_ratio), ("右侧", record.right_ratio)):
                if value is not None and value < low:
                    ratio_findings.append((side, muscle_name(record.muscle_a)))
                elif value is not None and value > high:
                    ratio_findings.append((side, muscle_name(record.muscle_b)))
        if len(ratio_findings) == 2 and ratio_findings[0][1] == ratio_findings[1][1]:
            ratio_findings = [("双侧", ratio_findings[0][1])]
        for side, muscle in ratio_findings:
            grouped[group_name][(side, muscle)].add(strength_type)
            ratio_covered_muscles.add(muscle)
            muscle_rank.setdefault((group_name, muscle), record_index)

        asymmetry_values = [
            (muscle_name(record.muscle_a), record.a_asymmetry, record.left_a, record.right_a),
            (muscle_name(record.muscle_b), record.b_asymmetry, record.left_b, record.right_b),
        ]
        for muscle, difference, left_value, right_value in asymmetry_values:
            if muscle in ratio_covered_muscles or difference is None or difference <= 0.10:
                continue
            if left_value is None or right_value is None or left_value == right_value:
                continue
            side = "左侧" if left_value < right_value else "右侧"
            grouped[group_name][(side, muscle)].add(strength_type)
            muscle_rank.setdefault((group_name, muscle), record_index)

    summaries: list[str] = []
    side_order = {"双侧": 0, "左侧": 1, "右侧": 2}
    strength_order = {"最大力量": 0, "快速力量": 1}
    for group_name in sorted(grouped, key=lambda name: group_rank[name]):
        by_muscle_strength: dict[tuple[str, str], set[str]] = defaultdict(set)
        for (side, muscle), strengths in grouped[group_name].items():
            for strength in strengths:
                by_muscle_strength[(muscle, strength)].add(side)

        normalized: dict[tuple[str, str], set[str]] = defaultdict(set)
        for (muscle, strength), sides in by_muscle_strength.items():
            if "双侧" in sides or {"左侧", "右侧"}.issubset(sides):
                normalized[("双侧", muscle)].add(strength)
            else:
                for side in sides:
                    normalized[(side, muscle)].add(strength)

        combined: dict[tuple[str, tuple[str, ...]], list[str]] = defaultdict(list)
        for (side, muscle), strengths in normalized.items():
            ordered_strengths = tuple(sorted(strengths, key=strength_order.get))
            combined[(side, ordered_strengths)].append(muscle)

        clauses: list[tuple[int, int, str]] = []
        for (side, strengths), muscles in combined.items():
            muscles.sort(key=lambda muscle: muscle_rank.get((group_name, muscle), len(records)))
            strength_text = "和".join(strengths)
            clause = f"{side}{'、'.join(muscles)}{strength_text}不足"
            clauses.append((side_order.get(side, 9), muscle_rank.get((group_name, muscles[0]), len(records)), clause))
        clauses.sort()
        if clauses:
            summaries.append(f"（{len(summaries) + 1}）{group_name}：{'；'.join(item[2] for item in clauses)}；")
        if len(summaries) == max_items:
            break
    return summaries


def analyze(
    athlete: AthleteInfo,
    all_records: list[TestRecord],
    standards: Standards,
    original_comments: Optional[dict[str, str]] = None,
) -> AnalysisResult:
    current = [record for record in all_records if record.is_current]
    warnings = _dataset_warnings(all_records, standards)
    for record in current:
        warnings.extend(_missing_value_warnings(record))
        calculate_ratios(record)
        calculate_bilateral_differences(record)
        warnings.extend(validate_existing_values(record))
        config = standards.gauges.get(record.joint)
        if config:
            record.left_ratio_status = classify_ratio(record.left_ratio, config)
            record.right_ratio_status = classify_ratio(record.right_ratio, config)
        level_a = classify_asymmetry(record.a_asymmetry, standards.asymmetry_levels)
        level_b = classify_asymmetry(record.b_asymmetry, standards.asymmetry_levels)
        record.a_asymmetry_state = level_a.state if level_a else None
        record.b_asymmetry_state = level_b.state if level_b else None

    grouped: dict[str, list[TestRecord]] = defaultdict(list)
    for record in current:
        grouped[record.joint].append(record)
    priorities = {
        joint: classify_joint_priority(records, standards.priority_rules) if standards.priority_rules else None
        for joint, records in grouped.items()
    }
    recommendations = generate_recommendations(current)
    return AnalysisResult(
        athlete=athlete,
        records=current,
        standards=standards,
        joint_priorities=priorities,
        recommendations=recommendations,
        warnings=warnings,
        original_comments=original_comments or {},
    )


def build_preview_result(result: AnalysisResult) -> AnalysisResult:
    """构建不含医学/训练判定的中性预览结果。"""
    preview = Standards(
        palette={
            "主色": "#123B8F",
            "边框色": "#A8C8FF",
            "目标范围": "#159A36",
            "轻度偏离": "#E2E8F0",
            "中度偏离": "#E2E8F0",
            "明显偏离": "#E2E8F0",
            "缺失": "#9AA4B2",
            "重点": "#9AA4B2",
            "关注": "#9AA4B2",
        },
        preview=True,
    )
    for joint, (order, target_low, target_high) in result.standards.target_ranges.items():
        values = [
            value
            for record in result.records
            if record.joint == joint
            for value in (record.left_ratio, record.right_ratio)
            if value is not None
        ]
        span = target_high - target_low
        observed_min = min(values) if values else target_low
        observed_max = max(values) if values else target_high
        gauge_min = max(0.0, min(target_low - 3 * span, observed_min - 0.2 * span))
        gauge_max = max(target_high + 3 * span, observed_max + 0.2 * span)
        low_width = target_low - gauge_min
        high_width = gauge_max - target_high
        preview.gauges[joint] = GaugeConfig(
            display_order=order,
            joint=joint,
            gauge_min=gauge_min,
            low_red_upper=gauge_min + low_width / 3,
            low_orange_upper=gauge_min + 2 * low_width / 3,
            target_low=target_low,
            target_high=target_high,
            high_yellow_upper=target_high + high_width / 3,
            high_orange_upper=target_high + 2 * high_width / 3,
            gauge_max=gauge_max,
            source_status="预览：仅使用现有目标区间",
            enabled=True,
        )
    if not preview.gauges:
        raise ValueError("Sheet 3 没有可用于预览的关节目标区间")
    return AnalysisResult(
        athlete=result.athlete,
        records=result.records,
        standards=preview,
        joint_priorities={},
        recommendations=result.recommendations,
        warnings=result.warnings,
        original_comments=result.original_comments,
    )
