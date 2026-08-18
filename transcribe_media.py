#!/usr/bin/env python3
"""Transcribe one audio or video file locally with MLX Whisper."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


DEFAULT_MODEL = "mlx-community/whisper-small-mlx"
OUTPUT_FORMATS = ("txt", "srt", "vtt", "tsv", "json", "all")


def output_name_for(source: Path) -> str:
    """Return the extension-free transcript name used by MLX Whisper."""
    # mlx_whisper treats dots in --output-name as extension separators.
    safe_stem = source.stem.replace(".", "-")
    return f"{safe_stem}_transcript"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcribe",
        description="Create a local transcript from an audio or video file.",
    )
    parser.add_argument("input", type=Path, help="Path to an audio or video file")
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Folder for the transcript (default: same folder as the input)",
    )
    parser.add_argument(
        "--format",
        choices=OUTPUT_FORMATS,
        default="txt",
        help="Transcript format (default: txt)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Spoken language code (default: en)",
    )
    parser.add_argument(
        "--auto-language",
        action="store_true",
        help="Let Whisper detect the spoken language",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("MLX_WHISPER_MODEL", DEFAULT_MODEL),
        help=f"Whisper model or local model path (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--whisper-bin",
        default=os.environ.get("MLX_WHISPER_BIN", "mlx_whisper"),
        help="mlx_whisper executable name or path (default: mlx_whisper)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed MLX Whisper arguments and segment output",
    )
    return parser.parse_args(argv)


def find_executable(value: str) -> str | None:
    """Resolve an executable from PATH or an explicit filesystem path."""
    discovered = shutil.which(value)
    if discovered:
        return discovered

    candidate = Path(value).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate.resolve())

    # Some existing `pip install --user` setups place scripts here on macOS,
    # but do not add the directory to PATH. Discover it without hard-coding a
    # username or Python version.
    if value == "mlx_whisper":
        pipx_candidate = Path.home() / ".local" / "bin" / "mlx_whisper"
        if pipx_candidate.is_file() and os.access(pipx_candidate, os.X_OK):
            return str(pipx_candidate.resolve())

        user_scripts = Path.home() / "Library" / "Python"
        for candidate in sorted(
            user_scripts.glob("*/bin/mlx_whisper"), reverse=True
        ):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.resolve())
    return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    source = args.input.expanduser().resolve()
    if not source.is_file():
        print(f"Input file not found: {source}", file=sys.stderr)
        return 2

    whisper_bin = find_executable(args.whisper_bin)
    if whisper_bin is None:
        print(
            "mlx_whisper was not found. Add it to PATH, set MLX_WHISPER_BIN, "
            "or pass --whisper-bin.",
            file=sys.stderr,
        )
        return 2

    out_dir = (args.out_dir or source.parent).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output_name = output_name_for(source)

    command = [
        whisper_bin,
        str(source),
        "--model",
        args.model,
        "--task",
        "transcribe",
        "--output-format",
        args.format,
        "--output-name",
        output_name,
        "--output-dir",
        str(out_dir),
        "--verbose",
        str(args.verbose),
    ]
    if not args.auto_language:
        command.extend(["--language", args.language])

    print(f"Transcribing: {source.name}", flush=True)
    try:
        subprocess.run(command, check=True)
    except KeyboardInterrupt:
        print("\nTranscription cancelled.", file=sys.stderr)
        return 130
    except subprocess.CalledProcessError as error:
        return error.returncode or 1

    if args.format == "all":
        print(f"Saved formats: {out_dir / output_name}.[txt|srt|vtt|tsv|json]")
    else:
        print(f"Saved: {out_dir / f'{output_name}.{args.format}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
