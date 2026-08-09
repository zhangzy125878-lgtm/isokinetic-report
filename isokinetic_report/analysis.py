from __future__ import annotations

import math
import operator
from collections import defaultdict
from typing import Callable, Optional

from .models import AnalysisResult, AsymmetryLevel, AthleteInfo, GaugeConfig, PriorityRule, Standards, TestRecord


EXPECTED_JOINTS = ["肩关节屈伸", "肩关节内外旋", "髋关节屈伸", "膝关节屈伸", "踝关节屈伸"]
EXPECTED_SPEEDS = ["慢速", "快速"]
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
    severe: list[str] = []
    attention: list[str] = []
    for record in records:
        for side, status in [("左", record.left_ratio_status), ("右", record.right_ratio_status)]:
            text = f"{record.joint}{record.speed}{side}侧{record.muscle_a}/{record.muscle_b}比例"
            if status == "severe":
                severe.append(f"优先复核并改善{text}的明显偏离")
            elif status in {"mild", "moderate"}:
                attention.append(f"关注{text}的偏离")
        for muscle, state in [(record.muscle_a, record.a_asymmetry_state), (record.muscle_b, record.b_asymmetry_state)]:
            text = f"{record.joint}{record.speed}{muscle}双侧差异"
            if state == "明显偏大":
                severe.append(f"优先复核并改善{text}")
            elif state and state != "正常":
                attention.append(f"关注{text}")
    recommendations: list[str] = []
    for item in severe + attention:
        if item not in recommendations:
            recommendations.append(item)
        if len(recommendations) == max_items:
            break
    return recommendations or ["当前配置标准下未发现需要优先提示的比例或双侧差异"]


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
    recommendations = generate_recommendations(current) if standards.complete else []
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
        recommendations=["Sheet 3 判定阈值尚未配置，本页仅展示重新计算的比例与双侧差异数值"],
        warnings=result.warnings,
        original_comments=result.original_comments,
    )
