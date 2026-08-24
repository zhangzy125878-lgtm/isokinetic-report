"""一键或批量运行峰力矩显示版；原版 run_report.py 保持不变。"""

from __future__ import annotations

import sys
from pathlib import Path

from run_report import DEFAULT_INPUT_DIR, build_parser, find_input_excel


def _directory_excels(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".xlsx" and not path.name.startswith("~$")
        ),
        key=lambda path: path.name.casefold(),
    )


def _input_excels(requested_input: Path | None, project_dir: Path) -> list[Path]:
    if requested_input is not None:
        requested_input = requested_input.expanduser().resolve()
        return _directory_excels(requested_input) if requested_input.is_dir() else [requested_input]
    preferred = _directory_excels(DEFAULT_INPUT_DIR)
    if preferred:
        return preferred
    fallback = find_input_excel(project_dir)
    return [fallback.expanduser().resolve()] if fallback else []


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_dir = Path(__file__).resolve().parent
    input_excels = _input_excels(args.input, project_dir)
    if not input_excels:
        location = args.input if args.input else DEFAULT_INPUT_DIR
        print(f"错误：{location} 中没有找到 Excel。", file=sys.stderr)
        return 2
    output_dir = (args.output_dir or (project_dir / "output_peak_torque")).expanduser().resolve()
    print(f"发现 {len(input_excels)} 个 Excel 输入文件。")
    print(f"峰力矩版输出目录：{output_dir}")
    try:
        from isokinetic_report.cli_peak_torque import main as report_main
    except ModuleNotFoundError as exc:
        print(f"错误：缺少 Python 依赖 {exc.name}。", file=sys.stderr)
        print(f'请先运行：python -m pip install -r "{project_dir / "requirements.txt"}"', file=sys.stderr)
        return 2
    failures: list[Path] = []
    for index, input_excel in enumerate(input_excels, start=1):
        print(f"\n[{index}/{len(input_excels)}] 输入文件：{input_excel}")
        command = [str(input_excel), "--output-dir", str(output_dir)]
        if args.validate_only:
            command.append("--validate-only")
        if args.no_pdf:
            command.append("--no-pdf")
        if report_main(command) != 0:
            failures.append(input_excel)
    if failures:
        print(f"\n批量处理完成：成功 {len(input_excels) - len(failures)} 个，失败 {len(failures)} 个。", file=sys.stderr)
        for path in failures:
            print(f"- {path}", file=sys.stderr)
        return 2
    print(f"\n批量处理完成：成功生成 {len(input_excels)} 份报告。")
    return 0


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
