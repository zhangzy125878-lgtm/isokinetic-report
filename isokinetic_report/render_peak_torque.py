from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, Wedge
from matplotlib.transforms import Bbox

from . import render as base
from .analysis import generate_recommendations
from .models import AnalysisResult, GaugeConfig, ReportPaths, TestRecord


def _fmt_torque(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:.0f}"


def _muscle_label(value: str) -> str:
    return value.removesuffix("肌群").removesuffix("肌")


def _torque_lines(record: Optional[TestRecord], side: str) -> tuple[str, str]:
    if record is None:
        return "峰力矩 —", "峰力矩 —"
    if side == "左侧":
        values = (record.left_a, record.left_b)
    else:
        values = (record.right_a, record.right_b)
    lines = []
    for muscle, value in zip((record.muscle_a, record.muscle_b), values):
        lines.append(f"{_muscle_label(muscle)} {_fmt_torque(value)} Nm" if muscle else "")
    return lines[0], lines[1]


def _report_joints(result: AnalysisResult) -> list[tuple[str, int]]:
    record_order: dict[str, int] = {}
    for record in result.records:
        record_order.setdefault(record.joint, len(record_order))
    ordered_joints = sorted(
        record_order,
        key=lambda joint: (
            result.standards.gauges[joint].display_order if joint in result.standards.gauges else float("inf"),
            record_order[joint],
        ),
    )
    return [(joint, index) for index, joint in enumerate(ordered_joints, start=1)]


def _page_result(result: AnalysisResult, joints: set[str]) -> AnalysisResult:
    page_records = [record for record in result.records if record.joint in joints]
    return replace(result, records=page_records, recommendations=generate_recommendations(page_records))


def draw_gauge(
    fig,
    rect: tuple[float, float, float, float],
    value: Optional[float],
    config: Optional[GaugeConfig],
    palette: dict[str, str],
    side: str,
    torque_lines: tuple[str, str],
) -> None:
    ax = fig.add_axes(rect, zorder=2)
    ax.set_aspect("equal")
    ax.axis("off")
    for (theta1, theta2), color_key in zip(base._visual_segment_angles(), base.VISUAL_BAND_KEYS):
        color = palette[color_key] if config is not None else "#E2E8F0"
        ax.add_patch(Wedge((0, 0), 1.0, theta1, theta2, width=0.28, facecolor=color, edgecolor="white", linewidth=0.8))
    if value is not None and config is not None:
        angle = math.radians(base._angle(value, config))
        ax.plot([0, 0.68 * math.cos(angle)], [0, 0.68 * math.sin(angle)], color=palette["主色"], linewidth=2.3, solid_capstyle="round")
        ax.add_patch(Circle((0, 0), 0.07, color=palette["主色"]))
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-0.86, 1.08)
    ax.text(0, 1.07, side, ha="center", va="bottom", fontsize=7.5, color="#172033")
    ax.text(0, -0.28, base._fmt(value), ha="center", va="center", fontsize=9, fontweight="bold", color=palette["主色"] if value is not None else palette["缺失"])
    ax.text(0, -0.53, torque_lines[0], ha="center", va="center", fontsize=5.8, color="#172033")
    if torque_lines[1]:
        ax.text(0, -0.73, torque_lines[1], ha="center", va="center", fontsize=5.8, color="#172033")


def _draw_speed_block(
    fig,
    x: float,
    y: float,
    width: float,
    height: float,
    record: Optional[TestRecord],
    config: Optional[GaugeConfig],
    palette: dict[str, str],
    levels,
) -> None:
    speed = record.speed if record else "—"
    label_w = width * 0.12
    gauge_w = width * 0.24
    asym_w = width * 0.25
    fig.text(x + label_w * 0.48, y + height * 0.55, speed, ha="center", va="center", fontsize=8, fontweight="bold", color=palette["主色"], bbox={"boxstyle": "round,pad=0.35", "facecolor": "#F1F6FF", "edgecolor": palette["边框色"], "linewidth": 0.6})
    left = record.left_ratio if record else None
    right = record.right_ratio if record else None
    draw_gauge(fig, (x + label_w, y + 0.002, gauge_w, height - 0.004), left, config, palette, "左侧", _torque_lines(record, "左侧"))
    draw_gauge(fig, (x + label_w + gauge_w + width * 0.02, y + 0.002, gauge_w, height - 0.004), right, config, palette, "右侧", _torque_lines(record, "右侧"))
    base._draw_asymmetry(fig, x + width - asym_w, y + height * 0.08, asym_w, height * 0.84, record, palette, levels)


def draw_joint_panel(
    fig,
    rect: tuple[float, float, float, float],
    joint: str,
    display_order: int,
    result: AnalysisResult,
    horizontal: bool = False,
) -> None:
    x, y, width, height = rect
    palette = result.standards.palette
    config = result.standards.gauges.get(joint)
    base._box(fig, x, y, width, height, palette["边框色"], radius=0.012, lw=0.75)
    fig.text(x + 0.012, y + height - 0.018, f"{display_order}. {joint}", ha="left", va="center", fontsize=11, fontweight="bold", color=palette["主色"])
    badge = f"目标区间  {config.target_low:.2f}–{config.target_high:.2f}" if config else "峰力矩数据"
    fig.text(x + width * 0.55, y + height - 0.018, badge, ha="center", va="center", fontsize=7.5, color=palette["主色"], bbox={"boxstyle": "round,pad=0.25", "facecolor": "#F1F6FF", "edgecolor": palette["边框色"], "linewidth": 0.5})
    priority = result.joint_priorities.get(joint)
    if priority:
        matching_rule = next((rule for rule in result.standards.priority_rules if rule.enabled and rule.output_label == priority and rule.label_color), None)
        color = matching_rule.label_color if matching_rule else palette.get(priority, palette["关注"])
        fig.text(x + width - 0.014, y + height - 0.018, priority, ha="right", va="center", fontsize=8.5, fontweight="bold", color="white", bbox={"boxstyle": "round,pad=0.35", "facecolor": color, "edgecolor": color})
    header_h = 0.036
    if horizontal:
        block_width = (width - 0.026) / 2
        for index, speed in enumerate(["慢速", "快速"]):
            record = base._record_for(result.records, joint, speed)
            _draw_speed_block(fig, x + 0.008 + index * (block_width + 0.010), y + 0.008, block_width, height - header_h - 0.012, record, config, palette, result.standards.asymmetry_levels)
    else:
        block_height = (height - header_h - 0.018) / 2
        for index, speed in enumerate(["慢速", "快速"]):
            block_y = y + height - header_h - (index + 1) * block_height - index * 0.004
            record = base._record_for(result.records, joint, speed)
            _draw_speed_block(fig, x + 0.006, block_y, width - 0.012, block_height, record, config, palette, result.standards.asymmetry_levels)
            if index == 0:
                fig.add_artist(plt.Line2D([x + 0.012, x + width - 0.012], [block_y - 0.002, block_y - 0.002], transform=fig.transFigure, color="#D8E2F2", linewidth=0.6, linestyle="--"))


def generate_report(result: AnalysisResult, output_dir: Path, include_pdf: bool = True) -> ReportPaths:
    if not result.standards.complete:
        raise ValueError("Sheet 3 配置不完整，不能生成正式判读报告")
    base._configure_chinese_font()
    joints = _report_joints(result)
    if not joints:
        raise ValueError("没有可绘制的关节配置")
    if len(joints) > 10:
        raise ValueError(f"当前版本最多支持 10 个关节，实际读取到 {len(joints)} 个")
    pages = [joints[index:index + 5] for index in range(0, len(joints), 5)]
    output_dir.mkdir(parents=True, exist_ok=True)
    date_part = base._safe_filename_part(result.athlete.test_date.replace("-", ""))
    filename_base = f"{base._safe_filename_part(result.athlete.name)}_等速肌力综合报告_{date_part}_峰力矩版"
    if result.standards.preview:
        filename_base += "_预览版"
    if len(pages) == 1:
        for stale_png in output_dir.glob(f"{filename_base}_第*页.png"):
            stale_png.unlink()
    else:
        stale_png = output_dir / f"{filename_base}.png"
        if stale_png.exists():
            stale_png.unlink()
    pdf_path = output_dir / f"{filename_base}.pdf" if include_pdf else None
    png_paths: list[Path] = []
    figures: list[tuple[object, Optional[Bbox]]] = []
    page_height = 12
    for page_index, page_joints in enumerate(pages, start=1):
        fig = plt.figure(figsize=(8, page_height), dpi=200, facecolor="white")
        base._draw_header(fig, result, page_index, len(pages))
        panel_rects, weakness_y, crop_bottom, weakness_font_size = base._page_layout(len(page_joints))
        for index, (joint, display_order) in enumerate(page_joints):
            draw_joint_panel(fig, panel_rects[index], joint, display_order, result, horizontal=panel_rects[index][2] > 0.8)
        page_result = _page_result(result, {joint for joint, _display_order in page_joints})
        base._draw_weaknesses(fig, page_result, weakness_y, weakness_font_size)
        suffix = f"_第{page_index}页" if len(pages) > 1 else ""
        png_path = output_dir / f"{filename_base}{suffix}.png"
        crop_box = Bbox.from_bounds(0, page_height * crop_bottom, 8, page_height * (1 - crop_bottom)) if crop_bottom else None
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
