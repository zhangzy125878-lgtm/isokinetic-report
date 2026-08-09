from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis import analyze, build_preview_result
from .excel_io import WorkbookStructureError, load_workbook_data
from .render import generate_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 Excel 生成一页式等速肌力综合报告")
    parser.add_argument("input", type=Path, help="输入 Excel 文件")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="输出目录，默认 output")
    parser.add_argument("--validate-only", action="store_true", help="只检查数据和 Sheet 3 配置，不生成报告")
    parser.add_argument("--no-pdf", action="store_true", help="只输出 PNG")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        athlete, records, standards, comments = load_workbook_data(args.input)
        result = analyze(athlete, records, standards, comments)
    except (FileNotFoundError, WorkbookStructureError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    print(f"已读取：{athlete.name}，本次记录 {len(result.records)} 条")
    for warning in result.warnings:
        print(f"警告：{warning}", file=sys.stderr)
    if standards.issues:
        print("Sheet 3 配置尚未完成：", file=sys.stderr)
        for issue in standards.issues:
            print(f"- {issue}", file=sys.stderr)
        print("未使用默认判定阈值。", file=sys.stderr)
        if args.validate_only:
            return 2
        try:
            preview_result = build_preview_result(result)
            paths = generate_report(preview_result, args.output_dir, include_pdf=not args.no_pdf)
        except ValueError as exc:
            print(f"错误：无法生成预览版：{exc}", file=sys.stderr)
            return 2
        print("已生成不含状态判定的预览版报告：")
        print(f"PNG：{paths.png.resolve()}")
        if paths.pdf:
            print(f"PDF：{paths.pdf.resolve()}")
        return 0
    if args.validate_only:
        print("校验通过：数据和 Sheet 3 配置完整。")
        return 0
    paths = generate_report(result, args.output_dir, include_pdf=not args.no_pdf)
    print(f"PNG：{paths.png.resolve()}")
    if paths.pdf:
        print(f"PDF：{paths.pdf.resolve()}")
    return 0
