#!/usr/bin/env python3
"""Transcribe or translate one audio or video file with MLX Whisper."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Sequence


VERSION = "1.1.0"
DEFAULT_MODEL = "mlx-community/whisper-small-mlx"
OUTPUT_FORMATS = ("txt", "srt", "vtt", "tsv", "json", "all")
RAW_SCRIPT_URL = (
    "https://raw.githubusercontent.com/Abdussalam-Mujeeb-ur-rahman/"
    "transcribe/main/transcribe_media.py"
)


def output_name_for(source: Path, translated_to_english: bool = False) -> str:
    """Return the extension-free transcript name used by MLX Whisper."""
    # mlx_whisper treats dots in --output-name as extension separators.
    safe_stem = source.stem.replace(".", "-")
    suffix = "_english_translation" if translated_to_english else "_transcript"
    return f"{safe_stem}{suffix}"


def install_dir() -> Path:
    """Return the user-level directory used by the public installer."""
    configured = os.environ.get("TRANSCRIBE_INSTALL_DIR")
    return Path(configured).expanduser() if configured else (
        Path.home() / ".local" / "share" / "transcribe"
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcribe",
        description="Create a local transcript or Turkish-to-English translation.",
    )
    parser.add_argument(
        "input", nargs="?", type=Path, help="Path to an audio or video file"
    )
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
        "--translate-to",
        choices=("en",),
        help="Translate Turkish speech into English (use: --language tr)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update only the transcribe command; keep dependencies and models",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {VERSION}"
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


def update_command() -> int:
    """Download, validate, and atomically install the latest command script."""
    target_dir = install_dir()
    target = target_dir / "transcribe_media.py"
    update_url = os.environ.get("TRANSCRIBE_UPDATE_URL", RAW_SCRIPT_URL)
    target_dir.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    print("Checking for the latest transcribe command...", flush=True)
    try:
        with tempfile.NamedTemporaryFile(
            prefix="transcribe-update-",
            suffix=".py",
            dir=target_dir,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            with urllib.request.urlopen(update_url, timeout=30) as response:
                shutil.copyfileobj(response, temporary)
        source_code = temporary_path.read_text(encoding="utf-8")
        if not source_code.startswith("#!/usr/bin/env python3") or (
            "def main(" not in source_code or "VERSION =" not in source_code
        ):
            raise ValueError("the downloaded file is not a transcribe release")
        compile(source_code, str(temporary_path), "exec")
        temporary_path.chmod(0o755)
        os.replace(temporary_path, target)
    except (
        OSError,
        SyntaxError,
        UnicodeError,
        ValueError,
        urllib.error.URLError,
    ) as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        print(f"Update failed: {error}", file=sys.stderr)
        return 1

    print(f"Updated transcribe at {target}")
    print("MLX Whisper, FFmpeg, Python, pipx, and downloaded models were untouched.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.update:
        return update_command()
    if args.input is None:
        print("An input file is required. Try: transcribe --help", file=sys.stderr)
        return 2

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
    if args.translate_to and args.auto_language:
        print(
            "For Turkish translation, use --language tr instead of --auto-language.",
            file=sys.stderr,
        )
        return 2
    if args.translate_to and args.language != "tr":
        print(
            "Turkish-to-English translation requires --language tr.",
            file=sys.stderr,
        )
        return 2

    output_name = output_name_for(
        source, translated_to_english=bool(args.translate_to)
    )

    command = [
        whisper_bin,
        str(source),
        "--model",
        args.model,
        "--task",
        "translate" if args.translate_to else "transcribe",
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

    action = (
        "Transcribing and translating to English"
        if args.translate_to
        else "Transcribing"
    )
    print(f"{action}: {source.name}", flush=True)
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
