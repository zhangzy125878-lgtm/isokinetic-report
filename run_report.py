"""一键运行等速肌力综合报告生成器。

直接执行 ``python run_report.py`` 即可。脚本会优先寻找
``D:\博士\江苏体科所\等速测试新报告_用于测试`` 中的 Excel，
其次寻找项目目录和当前用户 Downloads 目录中的 Codex 输入模板。
也可以把任意同结构 xlsx 路径作为第一个参数传入。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


TEMPLATE_NAME = "等速肌力报告_Codex输入模板_周建伟.xlsx"
FULL_TEMPLATE_NAME = "等速肌力报告_Codex输入模板_按当前脚本完整版.xlsx"
DEFAULT_INPUT_DIR = Path(r"D:\博士\江苏体科所\等速测试新报告_用于测试")


def _excel_candidates(project_dir: Path, preferred_dir: Path = DEFAULT_INPUT_DIR) -> list[Path]:
    candidates: list[Path] = []
    exact_locations = [
        preferred_dir / FULL_TEMPLATE_NAME,
        preferred_dir / TEMPLATE_NAME,
        project_dir / FULL_TEMPLATE_NAME,
        project_dir / TEMPLATE_NAME,
        Path.home() / "Downloads" / FULL_TEMPLATE_NAME,
        Path.home() / "Downloads" / TEMPLATE_NAME,
    ]
    for path in exact_locations:
        if path.is_file():
            candidates.append(path)
    for directory in [preferred_dir, project_dir, Path.home() / "Downloads"]:
        if not directory.is_dir():
            continue
        matches = sorted(directory.glob("*等速肌力*.xlsx"), key=lambda path: ("完整版" not in path.name, path.name))
        for path in matches:
            if path.name.startswith("~$") or path in candidates:
                continue
            candidates.append(path)
    return candidates


def find_input_excel(project_dir: Path) -> Path | None:
    candidates = _excel_candidates(project_dir)
    if candidates:
        return candidates[0]
    try:
        from tkinter import Tk, filedialog

        root = Tk()
        root.withdraw()
        selected = filedialog.askopenfilename(
            title="请选择等速肌力 Excel 输入文件",
            filetypes=[("Excel 工作簿", "*.xlsx")],
        )
        root.destroy()
        return Path(selected) if selected else None
    except Exception:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="一键生成等速肌力综合报告")
    parser.add_argument("input", nargs="?", type=Path, help="可选：输入 Excel 路径")
    parser.add_argument("--output-dir", type=Path, help="可选：报告输出目录")
    parser.add_argument("--validate-only", action="store_true", help="只检查 Excel，不生成报告")
    parser.add_argument("--no-pdf", action="store_true", help="只生成 PNG")
    parser.add_argument("--no-pause", action="store_true", help="运行结束后不等待回车")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_dir = Path(__file__).resolve().parent
    input_excel = args.input or find_input_excel(project_dir)
    if input_excel is None:
        print(f"错误：没有找到 Excel。请把 xlsx 放入 {DEFAULT_INPUT_DIR}，或把文件路径作为参数传入。", file=sys.stderr)
        return 2
    input_excel = input_excel.expanduser().resolve()
    output_dir = (args.output_dir or (project_dir / "output")).expanduser().resolve()

    print(f"输入文件：{input_excel}")
    print(f"输出目录：{output_dir}")
    try:
        from isokinetic_report.cli import main as report_main
    except ModuleNotFoundError as exc:
        print(f"错误：缺少 Python 依赖 {exc.name}。", file=sys.stderr)
        print(f'请先运行：python -m pip install -r "{project_dir / "requirements.txt"}"', file=sys.stderr)
        return 2

    command = [str(input_excel), "--output-dir", str(output_dir)]
    if args.validate_only:
        command.append("--validate-only")
    if args.no_pdf:
        command.append("--no-pdf")
    return report_main(command)


def main() -> int:
    launched_without_arguments = len(sys.argv) == 1
    args = build_parser().parse_args()
    forwarded: list[str] = []
    if args.input:
        forwarded.append(str(args.input))
    if args.output_dir:
        forwarded.extend(["--output-dir", str(args.output_dir)])
    if args.validate_only:
        forwarded.append("--validate-only")
    if args.no_pdf:
        forwarded.append("--no-pdf")
    if args.no_pause:
        forwarded.append("--no-pause")
    exit_code = run(forwarded)
    if launched_without_arguments and not args.no_pause and sys.stdin.isatty():
        try:
            input("\n运行结束，按回车键退出……")
        except EOFError:
            pass
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
