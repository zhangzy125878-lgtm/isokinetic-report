from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, FancyBboxPatch, Wedge
from matplotlib.transforms import Bbox

from .analysis import RATIO_STATUS_LABELS
from .models import AnalysisResult, AsymmetryLevel, GaugeConfig, ReportPaths, TestRecord


VISUAL_BAND_KEYS = (
    "明显偏离",
    "中度偏离",
    "轻度偏离",
    "目标范围",
    "轻度偏离",
    "中度偏离",
    "明显偏离",
)


def _configure_chinese_font() -> None:
    preferred = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def _box(fig, x: float, y: float, width: float, height: float, edge: str, face: str = "#FFFFFF", radius: float = 0.012, lw: float = 1.0) -> None:
    fig.add_artist(
        FancyBboxPatch(
            (x, y), width, height,
            boxstyle=f"round,pad=0.006,rounding_size={radius}",
            transform=fig.transFigure,
            facecolor=face,
            edgecolor=edge,
            linewidth=lw,
            zorder=0,
        )
    )


def _fmt(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:.2f}"


def _visual_edges() -> list[float]:
    segment_width = 220 / len(VISUAL_BAND_KEYS)
    return [200 - index * segment_width for index in range(len(VISUAL_BAND_KEYS) + 1)]


def _angle(value: float, config: GaugeConfig) -> float:
    numeric_edges = [
        config.gauge_min,
        config.low_red_upper,
        config.low_orange_upper,
        config.target_low,
        config.target_high,
        config.high_yellow_upper,
        config.high_orange_upper,
        config.gauge_max,
    ]
    visual_edges = _visual_edges()
    clamped = min(max(value, numeric_edges[0]), numeric_edges[-1])
    for index, (low, high) in enumerate(zip(numeric_edges, numeric_edges[1:])):
        if clamped <= high or index == len(numeric_edges) - 2:
            fraction = (clamped - low) / (high - low)
            return visual_edges[index] + fraction * (visual_edges[index + 1] - visual_edges[index])
    return visual_edges[-1]


def _visual_segment_angles() -> list[tuple[float, float]]:
    edges = _visual_edges()
    return [(edges[index + 1], edges[index]) for index in range(len(VISUAL_BAND_KEYS))]


def draw_gauge(fig, rect: tuple[float, float, float, float], value: Optional[float], config: GaugeConfig, palette: dict[str, str], side: str) -> None:
    ax = fig.add_axes(rect, zorder=2)
    ax.set_aspect("equal")
    ax.axis("off")
    for (theta1, theta2), color_key in zip(_visual_segment_angles(), VISUAL_BAND_KEYS):
        ax.add_patch(Wedge((0, 0), 1.0, theta1, theta2, width=0.28, facecolor=palette[color_key], edgecolor="white", linewidth=0.8))
    if value is not None:
        angle = math.radians(_angle(value, config))
        ax.plot([0, 0.68 * math.cos(angle)], [0, 0.68 * math.sin(angle)], color=palette["主色"], linewidth=2.3, solid_capstyle="round")
        ax.add_patch(Circle((0, 0), 0.07, color=palette["主色"]))
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-0.45, 1.08)
    ax.text(0, 1.07, side, ha="center", va="bottom", fontsize=7.5, color="#172033")
    ax.text(0, -0.35, _fmt(value), ha="center", va="center", fontsize=9, fontweight="bold", color=palette["主色"] if value is not None else palette["缺失"])


def _asymmetry_level(state: Optional[str], levels: list[AsymmetryLevel]) -> Optional[AsymmetryLevel]:
    return next((level for level in levels if level.state == state), None)


def _draw_asymmetry(fig, x: float, y: float, width: float, height: float, record: Optional[TestRecord], palette: dict[str, str], levels: list[AsymmetryLevel]) -> None:
    _box(fig, x, y, width, height, palette["边框色"], radius=0.006, lw=0.7)
    fig.text(x + width / 2, y + height - 0.012, "双侧差异", ha="center", va="top", fontsize=7.2, color="#172033")
    if record is None:
        fig.text(x + width / 2, y + height * 0.38, "—", ha="center", va="center", fontsize=10, color=palette["缺失"])
        return
    items = [
        (record.muscle_a[:1], record.a_asymmetry, record.a_asymmetry_state),
        (record.muscle_b[:1], record.b_asymmetry, record.b_asymmetry_state),
    ]
    for index, (label, value, state) in enumerate(items):
        level = _asymmetry_level(state, levels)
        symbol = level.symbol if level else "—"
        color = level.color if level else palette["缺失"]
        fig.text(x + 0.014, y + height * (0.50 - index * 0.26), label, fontsize=7.4, color="#172033", va="center")
        fig.text(x + width * 0.48, y + height * (0.50 - index * 0.26), _fmt(value), fontsize=7.4, color="#172033", ha="center", va="center")
        fig.text(x + width - 0.014, y + height * (0.50 - index * 0.26), symbol, fontsize=8.5, fontweight="bold", color=color, ha="right", va="center")


def _record_for(records: list[TestRecord], joint: str, speed: str) -> Optional[TestRecord]:
    return next((record for record in records if record.joint == joint and record.speed == speed), None)


def _draw_speed_block(fig, x: float, y: float, width: float, height: float, record: Optional[TestRecord], config: GaugeConfig, palette: dict[str, str], levels: list[AsymmetryLevel]) -> None:
    speed = record.speed if record else "—"
    label_w = width * 0.12
    gauge_w = width * 0.24
    asym_w = width * 0.25
    fig.text(x + label_w * 0.48, y + height * 0.55, speed, ha="center", va="center", fontsize=8, fontweight="bold", color=palette["主色"], bbox={"boxstyle": "round,pad=0.35", "facecolor": "#F1F6FF", "edgecolor": palette["边框色"], "linewidth": 0.6})
    left = record.left_ratio if record else None
    right = record.right_ratio if record else None
    draw_gauge(fig, (x + label_w, y + 0.002, gauge_w, height - 0.004), left, config, palette, "左侧")
    draw_gauge(fig, (x + label_w + gauge_w + width * 0.02, y + 0.002, gauge_w, height - 0.004), right, config, palette, "右侧")
    _draw_asymmetry(fig, x + width - asym_w, y + height * 0.08, asym_w, height * 0.84, record, palette, levels)


def draw_joint_panel(fig, rect: tuple[float, float, float, float], joint: str, result: AnalysisResult, horizontal: bool = False) -> None:
    x, y, width, height = rect
    palette = result.standards.palette
    config = result.standards.gauges[joint]
    _box(fig, x, y, width, height, palette["边框色"], radius=0.012, lw=0.75)
    fig.text(x + 0.012, y + height - 0.018, f"{config.display_order}. {joint}", ha="left", va="center", fontsize=11, fontweight="bold", color=palette["主色"])
    fig.text(x + width * 0.55, y + height - 0.018, f"目标区间  {config.target_low:.2f}–{config.target_high:.2f}", ha="center", va="center", fontsize=7.5, color=palette["主色"], bbox={"boxstyle": "round,pad=0.25", "facecolor": "#F1F6FF", "edgecolor": palette["边框色"], "linewidth": 0.5})
    priority = result.joint_priorities.get(joint)
    if priority:
        matching_rule = next(
            (rule for rule in result.standards.priority_rules if rule.enabled and rule.output_label == priority and rule.label_color),
            None,
        )
        color = matching_rule.label_color if matching_rule else palette.get(priority, palette["关注"])
        fig.text(x + width - 0.014, y + height - 0.018, priority, ha="right", va="center", fontsize=8.5, fontweight="bold", color="white", bbox={"boxstyle": "round,pad=0.35", "facecolor": color, "edgecolor": color})
    header_h = 0.036
    if horizontal:
        block_width = (width - 0.026) / 2
        for index, speed in enumerate(["慢速", "快速"]):
            record = _record_for(result.records, joint, speed)
            _draw_speed_block(fig, x + 0.008 + index * (block_width + 0.010), y + 0.008, block_width, height - header_h - 0.012, record, config, palette, result.standards.asymmetry_levels)
    else:
        block_height = (height - header_h - 0.018) / 2
        for index, speed in enumerate(["慢速", "快速"]):
            block_y = y + height - header_h - (index + 1) * block_height - index * 0.004
            record = _record_for(result.records, joint, speed)
            _draw_speed_block(fig, x + 0.006, block_y, width - 0.012, block_height, record, config, palette, result.standards.asymmetry_levels)
            if index == 0:
                fig.add_artist(plt.Line2D([x + 0.012, x + width - 0.012], [block_y - 0.002, block_y - 0.002], transform=fig.transFigure, color="#D8E2F2", linewidth=0.6, linestyle="--"))


def _draw_header(fig, result: AnalysisResult, page_number: int = 1, total_pages: int = 1) -> None:
    palette = result.standards.palette
    title = "等速肌力综合报告（预览版）" if result.standards.preview else "等速肌力综合报告"
    if total_pages > 1:
        title += f"  {page_number}/{total_pages}"
    fig.text(0.5, 0.958, title, ha="center", va="center", fontsize=22 if total_pages > 1 or result.standards.preview else 25, fontweight="bold", color=palette["主色"])
    fig.add_artist(plt.Line2D([0.08, 0.23], [0.958, 0.958], transform=fig.transFigure, color=palette["边框色"], linewidth=1.0))
    fig.add_artist(plt.Line2D([0.77, 0.92], [0.958, 0.958], transform=fig.transFigure, color=palette["边框色"], linewidth=1.0))
    _box(fig, 0.035, 0.825, 0.46, 0.095, palette["边框色"])
    athlete = result.athlete
    info = [
        ("姓名", athlete.name), ("项目", athlete.sport),
        ("测试日期", athlete.test_date), ("报告类型", athlete.report_type),
    ]
    for index, (label, value) in enumerate(info):
        row, col = divmod(index, 2)
        fig.text(0.06 + col * 0.22, 0.886 - row * 0.036, f"{label}：{value}", fontsize=8.5, color="#172033", va="center")
    _box(fig, 0.515, 0.825, 0.45, 0.095, palette["边框色"])
    fig.text(0.74, 0.902, "判读说明", ha="center", va="center", fontsize=10, fontweight="bold", color=palette["主色"])
    legend_config = next(iter(sorted(result.standards.gauges.values(), key=lambda item: item.display_order)))
    demo = (legend_config.target_low + legend_config.target_high) / 2
    draw_gauge(fig, (0.535, 0.834, 0.13, 0.07), demo, legend_config, palette, "示例")
    legend = [("目标范围", "目标范围"), ("轻/中度偏离", "中度偏离"), ("明显偏离", "明显偏离")]
    for index, (text, key) in enumerate(legend):
        fig.text(0.69, 0.883 - index * 0.022, "●", fontsize=9, color=palette[key], va="center")
        fig.text(0.71, 0.883 - index * 0.022, text, fontsize=7.5, color="#172033", va="center")


def _emphasized_parts(text: str, emphasized: set[str]) -> list[str]:
    tokens = sorted((token for token in emphasized if token), key=len, reverse=True)
    parts = re.split(f"({'|'.join(re.escape(token) for token in tokens)})", text) if tokens else [text]
    return [part for part in parts if part]


def _fit_emphasized_font_size(fig, text: str, emphasized: set[str], max_width: float, max_font_size: float) -> float:
    parts = _emphasized_parts(text, emphasized)
    renderer = fig.canvas.get_renderer()
    font_sizes = [max_font_size - 0.5 * index for index in range(int((max_font_size - 5.5) / 0.5) + 1)]
    selected_size = font_sizes[-1]
    for size in font_sizes:
        width = 0.0
        for part in parts:
            weight = "bold" if part in emphasized else "normal"
            prop = font_manager.FontProperties(family=plt.rcParams["font.sans-serif"], size=size, weight=weight)
            width += renderer.get_text_width_height_descent(part, prop, ismath=False)[0] / fig.bbox.width
        selected_size = size
        if width <= max_width:
            break
    return selected_size


def _draw_emphasized_line(
    fig,
    x: float,
    y: float,
    text: str,
    emphasized: set[str],
    font_size: float,
) -> None:
    parts = _emphasized_parts(text, emphasized)
    renderer = fig.canvas.get_renderer()

    cursor = x
    for part in parts:
        is_emphasized = part in emphasized
        prop = font_manager.FontProperties(
            family=plt.rcParams["font.sans-serif"],
            size=font_size,
            weight="bold" if is_emphasized else "normal",
        )
        width = renderer.get_text_width_height_descent(part, prop, ismath=False)[0] / fig.bbox.width
        fig.text(cursor, y, part, ha="left", va="center", fontproperties=prop, color="#172033")
        if is_emphasized:
            fig.add_artist(
                plt.Line2D(
                    [cursor, cursor + width],
                    [y - 0.004, y - 0.004],
                    transform=fig.transFigure,
                    color="#172033",
                    linewidth=0.55,
                )
            )
        cursor += width


def _draw_weaknesses(fig, result: AnalysisResult, box_y: float, max_font_size: float) -> None:
    palette = result.standards.palette
    box_height = 0.105
    _box(fig, 0.035, box_y, 0.93, box_height, palette["边框色"])
    fig.text(0.06, box_y + box_height - 0.022, "关键薄弱环节", fontsize=12 if max_font_size >= 8.5 else 11, fontweight="bold", color=palette["主色"], va="center")
    items = result.recommendations[:4]
    emphasized = {
        "左侧",
        "右侧",
        "双侧",
        "最大力量",
        "快速力量",
        *(record.muscle_a if record.muscle_a.endswith(("肌", "肌群")) else f"{record.muscle_a}肌" for record in result.records),
        *(record.muscle_b if record.muscle_b.endswith(("肌", "肌群")) else f"{record.muscle_b}肌" for record in result.records),
    }
    item_emphasis = [emphasized | {item.split("）", 1)[-1].split("：", 1)[0]} for item in items]
    uniform_font_size = min(
        (_fit_emphasized_font_size(fig, item, item_emphasis[index], 0.88, max_font_size) for index, item in enumerate(items)),
        default=max_font_size,
    )
    for index, item in enumerate(items):
        line_y = box_y + box_height - 0.047 - index * 0.0185
        _draw_emphasized_line(fig, 0.06, line_y, item, item_emphasis[index], uniform_font_size)


def _page_layout(joint_count: int) -> tuple[list[tuple[float, float, float, float]], float, float, float]:
    half_width = 0.465
    top_left = (0.025, 0.595, half_width, 0.205)
    top_right = (0.51, 0.595, half_width, 0.205)
    middle_left = (0.025, 0.370, half_width, 0.205)
    middle_right = (0.51, 0.370, half_width, 0.205)
    top_full = (0.035, 0.595, 0.93, 0.205)
    middle_full = (0.035, 0.370, 0.93, 0.205)
    bottom_full = (0.035, 0.155, 0.93, 0.190)
    if joint_count == 1:
        return [top_full], 0.455, 0.44, 10.0
    if joint_count == 2:
        return [top_left, top_right], 0.455, 0.44, 9.0
    if joint_count == 3:
        return [top_left, top_right, middle_full], 0.235, 0.22, 8.5
    if joint_count == 4:
        return [top_left, top_right, middle_left, middle_right], 0.235, 0.22, 8.0
    return [top_left, top_right, middle_left, middle_right, bottom_full], 0.025, 0.0, 7.5


def _safe_filename_part(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "", value)


def generate_report(result: AnalysisResult, output_dir: Path, include_pdf: bool = True) -> ReportPaths:
    if not result.standards.complete:
        raise ValueError("Sheet 3 配置不完整，不能生成正式判读报告")
    _configure_chinese_font()
    joints = sorted(result.standards.gauges.values(), key=lambda item: item.display_order)
    if not joints:
        raise ValueError("没有可绘制的关节配置")
    if len(joints) > 10:
        raise ValueError(f"当前版本最多支持 10 个关节，实际读取到 {len(joints)} 个")
    pages = [joints[index:index + 5] for index in range(0, len(joints), 5)]
    output_dir.mkdir(parents=True, exist_ok=True)
    date_part = _safe_filename_part(result.athlete.test_date.replace("-", ""))
    base = f"{_safe_filename_part(result.athlete.name)}_等速肌力综合报告_{date_part}"
    if result.standards.preview:
        base += "_预览版"
    pdf_path = output_dir / f"{base}.pdf" if include_pdf else None
    png_paths: list[Path] = []
    figures: list[tuple[object, Optional[Bbox]]] = []
    for page_index, page_joints in enumerate(pages, start=1):
        fig = plt.figure(figsize=(8, 10), dpi=200, facecolor="white")
        _draw_header(fig, result, page_index, len(pages))
        panel_rects, weakness_y, crop_bottom, weakness_font_size = _page_layout(len(page_joints))
        for index, config in enumerate(page_joints):
            draw_joint_panel(fig, panel_rects[index], config.joint, result, horizontal=panel_rects[index][2] > 0.8)
        _draw_weaknesses(fig, result, weakness_y, weakness_font_size)
        suffix = f"_第{page_index}页" if len(pages) > 1 else ""
        png_path = output_dir / f"{base}{suffix}.png"
        crop_box = Bbox.from_bounds(0, 10 * crop_bottom, 8, 10 * (1 - crop_bottom)) if crop_bottom else None
        fig.savefig(png_path, dpi=200, facecolor="white", bbox_inches=crop_box)
        png_paths.append(png_path)
        figures.append((fig, crop_box))
    if pdf_path:
        with PdfPages(pdf_path) as pdf:
            for fig, crop_box in figures:
                pdf.savefig(fig, facecolor="white", bbox_inches=crop_box)
    for fig, _crop_box in figures:
        plt.close(fig)
    return ReportPaths(png=png_paths[0], pdf=pdf_path, additional_pngs=tuple(png_paths[1:]))
