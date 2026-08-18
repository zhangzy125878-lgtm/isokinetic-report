"""一键运行峰力矩显示版；原版 run_report.py 保持不变。"""

from __future__ import annotations

import sys
from pathlib import Path

from run_report import DEFAULT_INPUT_DIR, build_parser, find_input_excel


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_dir = Path(__file__).resolve().parent
    input_excel = args.input or find_input_excel(project_dir)
    if input_excel is None:
        print(f"错误：没有找到 Excel。请把 xlsx 放入 {DEFAULT_INPUT_DIR}，或把文件路径作为参数传入。", file=sys.stderr)
        return 2
    input_excel = input_excel.expanduser().resolve()
    output_dir = (args.output_dir or (project_dir / "output_peak_torque")).expanduser().resolve()
    print(f"输入文件：{input_excel}")
    print(f"峰力矩版输出目录：{output_dir}")
    try:
        from isokinetic_report.cli_peak_torque import main as report_main
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
