#!/usr/bin/env python3
"""Transcribe or translate one audio or video file with MLX Whisper."""

from __future__ import annotations

import argparse
import array
import json
import mimetypes
import os
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Sequence


VERSION = "2.0.0"
DEFAULT_MODEL = "mlx-community/whisper-small-mlx"
OUTPUT_FORMATS = ("txt", "srt", "vtt", "tsv", "json", "all")
SUPPORTED_LANGUAGES = {
    "af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "as": "Assamese",
    "az": "Azerbaijani", "ba": "Bashkir", "be": "Belarusian", "bg": "Bulgarian",
    "bn": "Bengali", "bo": "Tibetan", "br": "Breton", "bs": "Bosnian",
    "ca": "Catalan", "cs": "Czech", "cy": "Welsh", "da": "Danish",
    "de": "German", "el": "Greek", "en": "English", "es": "Spanish",
    "et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish",
    "fo": "Faroese", "fr": "French", "gl": "Galician", "gu": "Gujarati",
    "ha": "Hausa", "haw": "Hawaiian", "he": "Hebrew", "hi": "Hindi",
    "hr": "Croatian", "ht": "Haitian Creole", "hu": "Hungarian",
    "hy": "Armenian", "id": "Indonesian", "is": "Icelandic", "it": "Italian",
    "ja": "Japanese", "jw": "Javanese", "ka": "Georgian", "kk": "Kazakh",
    "km": "Khmer", "kn": "Kannada", "ko": "Korean", "la": "Latin",
    "lb": "Luxembourgish", "ln": "Lingala", "lo": "Lao", "lt": "Lithuanian",
    "lv": "Latvian", "mg": "Malagasy", "mi": "Maori", "mk": "Macedonian",
    "ml": "Malayalam", "mn": "Mongolian", "mr": "Marathi", "ms": "Malay",
    "mt": "Maltese", "my": "Myanmar", "ne": "Nepali", "nl": "Dutch",
    "nn": "Nynorsk", "no": "Norwegian", "oc": "Occitan", "pa": "Punjabi",
    "pl": "Polish", "ps": "Pashto", "pt": "Portuguese", "ro": "Romanian",
    "ru": "Russian", "sa": "Sanskrit", "sd": "Sindhi", "si": "Sinhala",
    "sk": "Slovak", "sl": "Slovenian", "sn": "Shona", "so": "Somali",
    "sq": "Albanian", "sr": "Serbian", "su": "Sundanese", "sv": "Swedish",
    "sw": "Swahili", "ta": "Tamil", "te": "Telugu", "tg": "Tajik",
    "th": "Thai", "tk": "Turkmen", "tl": "Tagalog", "tr": "Turkish",
    "tt": "Tatar", "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek",
    "vi": "Vietnamese", "yi": "Yiddish", "yo": "Yoruba", "yue": "Cantonese",
    "zh": "Chinese",
}
FEATURED_LANGUAGE_CODES = (
    "en",
    "zh",
    "es",
    "ko",
    "pt",
    "fr",
    "ar",
    "hi",
    "ja",
    "de",
    "ru",
    "tr",
    "yo",
    "ha",
    "sw",
)
RAW_SCRIPT_URL = (
    "https://raw.githubusercontent.com/Abdussalam-Mujeeb-ur-rahman/"
    "transcribe/main/transcribe_media.py"
)


def output_name_for(
    source: Path,
    translated_to_english: bool = False,
    start_at: float | None = None,
    end_at: float | None = None,
) -> str:
    """Return the extension-free transcript name used by MLX Whisper."""
    # mlx_whisper treats dots in --output-name as extension separators.
    safe_stem = source.stem.replace(".", "-")
    clip = ""
    if start_at is not None and end_at is not None:
        start_slug = f"{start_at:.3f}".rstrip("0").rstrip(".").replace(".", "p")
        end_slug = f"{end_at:.3f}".rstrip("0").rstrip(".").replace(".", "p")
        clip = f"_clip-{start_slug}-to-{end_slug}"
    suffix = "_english_translation" if translated_to_english else "_transcript"
    return f"{safe_stem}{clip}{suffix}"


def install_dir() -> Path:
    """Return the user-level directory used by the public installer."""
    configured = os.environ.get("TRANSCRIBE_INSTALL_DIR")
    return Path(configured).expanduser() if configured else (
        Path.home() / ".local" / "share" / "transcribe"
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcribe",
        description="Create a local transcript or translate supported speech to English.",
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
        "--start-at",
        type=float,
        help="Start time in seconds for a selected media range",
    )
    parser.add_argument(
        "--end-at",
        type=float,
        help="End time in seconds for a selected media range",
    )
    parser.add_argument(
        "--translate-to",
        choices=("en",),
        help="Translate supported non-English speech into English",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update only the transcribe command; keep dependencies and models",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Open the Transcribe Lab interface in your browser",
    )
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Start an interactive guided Terminal session",
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


def choose_with_macos(prompt: str, folder: bool = False) -> Path | None:
    """Open a native macOS picker and return the selected POSIX path."""
    selection = "choose folder" if folder else "choose file"
    script = f'POSIX path of ({selection} with prompt "{prompt}")'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return Path(value) if value else None


def choose_files_with_macos(prompt: str) -> list[Path]:
    """Open a native multi-file picker and return selected POSIX paths."""
    script = f'''
set chosenFiles to choose file with prompt "{prompt}" with multiple selections allowed
set outputText to ""
repeat with chosenFile in chosenFiles
    set outputText to outputText & POSIX path of chosenFile & linefeed
end repeat
return outputText
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def inspect_media(source: Path) -> dict[str, object]:
    """Read real duration, size, format, sample rate, and channels with FFprobe."""
    ffprobe = find_executable("ffprobe")
    if ffprobe is None:
        raise RuntimeError("FFprobe was not found. Rerun the installer to repair FFmpeg.")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,format_name:stream=codec_type,sample_rate,channels",
            "-of",
            "json",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    media_format = payload.get("format", {})
    audio_stream = next(
        (
            stream
            for stream in payload.get("streams", [])
            if stream.get("codec_type") == "audio"
        ),
        {},
    )
    return {
        "name": source.name,
        "path": str(source),
        "duration": float(media_format.get("duration") or 0),
        "size": int(media_format.get("size") or source.stat().st_size),
        "format": str(media_format.get("format_name") or source.suffix.lstrip(".")),
        "sample_rate": int(audio_stream.get("sample_rate") or 0),
        "channels": int(audio_stream.get("channels") or 0),
    }


def waveform_peaks(source: Path, bin_count: int = 900) -> list[float]:
    """Decode a low-rate mono stream and reduce it to normalized waveform peaks."""
    ffmpeg = find_executable("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("FFmpeg was not found. Rerun the installer to repair it.")
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "200",
            "-f",
            "s16le",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    samples = array.array("h")
    samples.frombytes(result.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return [0.0] * bin_count
    bucket_size = max(1, len(samples) // bin_count)
    raw_peaks: list[int] = []
    for index in range(bin_count):
        start = index * bucket_size
        end = len(samples) if index == bin_count - 1 else min(
            len(samples), start + bucket_size
        )
        raw_peaks.append(max((abs(value) for value in samples[start:end]), default=0))
    ceiling = max(raw_peaks, default=0)
    if not ceiling:
        return [0.0] * bin_count
    return [round(min(1.0, peak / ceiling), 4) for peak in raw_peaks]


def expected_output_path(
    source: Path,
    out_dir: Path,
    output_format: str,
    translate: bool,
    start_at: float | None = None,
    end_at: float | None = None,
) -> Path:
    if output_format == "all":
        output_format = "txt"
    return out_dir / (
        f"{output_name_for(source, translated_to_english=translate, start_at=start_at, end_at=end_at)}.{output_format}"
    )


class LocalJob:
    """Manage the single transcription process owned by the local interface."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.state = "idle"
        self.log: list[str] = []
        self.output_path: Path | None = None
        self.started_at: float | None = None
        self.progress = 0.0
        self.media_duration = 0.0
        self.selected_frame_total = 0

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            elapsed = max(0.0, time.monotonic() - self.started_at) if self.started_at else 0.0
            speed = (
                (self.media_duration * self.progress / elapsed)
                if elapsed > 0 and self.progress > 0
                else 0.0
            )
            remaining = (
                elapsed * (1 - self.progress) / self.progress
                if self.state == "running" and self.progress > 0
                else 0.0
            )
            return {
                "state": self.state,
                "log": "".join(self.log[-400:]),
                "output": str(self.output_path) if self.output_path else "",
                "progress": round(self.progress * 100),
                "elapsed": round(elapsed),
                "remaining": round(remaining),
                "speed": round(speed, 2),
            }

    def start(
        self,
        source: Path,
        out_dir: Path,
        output_format: str,
        language: str,
        translate: bool,
        media_duration: float = 0.0,
        start_at: float | None = None,
        end_at: float | None = None,
    ) -> tuple[bool, str]:
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                return False, "A transcription is already running."

        if not source.is_file():
            return False, "Choose a valid audio or video file."
        if output_format not in OUTPUT_FORMATS:
            return False, "Choose a valid output format."
        if language != "auto" and language not in SUPPORTED_LANGUAGES:
            return False, "Choose a valid language."
        if translate and language == "en":
            return False, "Choose a non-English source language or automatic detection."
        if start_at is not None or end_at is not None:
            if start_at is None or end_at is None or start_at < 0 or end_at <= start_at:
                return False, "Choose a valid start and end time."
            if media_duration and end_at > media_duration + 0.5:
                return False, "The selected range exceeds the media duration."

        out_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            str(source),
            "--out-dir",
            str(out_dir),
            "--format",
            output_format,
        ]
        if language == "auto":
            command.append("--auto-language")
        else:
            command.extend(["--language", language])
        if translate:
            command.extend(["--translate-to", "en"])
        if start_at is not None and end_at is not None:
            command.extend(["--start-at", str(start_at), "--end-at", str(end_at)])

        with self.lock:
            self.state = "running"
            self.log = [f"Starting {source.name}…\n"]
            self.started_at = time.monotonic()
            self.progress = 0.0
            self.media_duration = (
                end_at - start_at
                if start_at is not None and end_at is not None
                else media_duration
            )
            self.selected_frame_total = (
                max(1, round(self.media_duration * 100))
                if start_at is not None and end_at is not None
                else 0
            )
            self.output_path = expected_output_path(
                source, out_dir, output_format, translate, start_at, end_at
            )
            try:
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                )
            except OSError as error:
                self.state = "error"
                self.log.append(f"Could not start: {error}\n")
                self.process = None
                return False, str(error)

        threading.Thread(target=self._collect, daemon=True).start()
        return True, "Started"

    def _collect(self) -> None:
        process = self.process
        if process is None:
            return
        if process.stdout is not None:
            for line in process.stdout:
                with self.lock:
                    self.log.append(line)
                    frame_progress = re.search(r"(\d+)/(\d+).*frames/s", line)
                    if frame_progress and int(frame_progress.group(2)):
                        denominator = (
                            self.selected_frame_total
                            or int(frame_progress.group(2))
                        )
                        self.progress = min(
                            0.99,
                            int(frame_progress.group(1)) / denominator,
                        )
        return_code = process.wait()
        with self.lock:
            if self.state == "cancelling":
                self.state = "cancelled"
                self.log.append("Cancelled.\n")
            elif return_code == 0:
                self.state = "success"
                self.progress = 1.0
            else:
                self.state = "error"
                self.log.append(f"Exited with status {return_code}.\n")

    def cancel(self) -> bool:
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                return False
            self.state = "cancelling"
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return False
            return True


UI_TEMPLATE = r'''<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Local Apple silicon transcription workspace">
<title>Transcribe Lab</title>
<style>
:root{color-scheme:dark;--bg:#0d0d0c;--panel:#131412;--panel2:#191a17;--line:#34352f;--text:#f1f0e8;--muted:#989990;--amber:#f0ae3c;--amber-soft:#3a2b12;--lime:#b9f54a;--danger:#ff6961;--shadow:rgba(0,0,0,.4)}
:root[data-theme="light"]{color-scheme:light;--bg:#f2f0e9;--panel:#fffdf7;--panel2:#ebe8df;--line:#cbc7ba;--text:#1e211b;--muted:#66695f;--amber:#a65f00;--amber-soft:#fff0cd;--lime:#4e7900;--danger:#b42318;--shadow:rgba(54,45,24,.12)}
:root[data-theme="light"] .run{color:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px ui-monospace,SFMono-Regular,Menlo,Monaco,monospace;min-height:100vh}button,input,select{font:inherit}button,select,input[type="number"]{border:1px solid var(--line);background:var(--panel2);color:var(--text);border-radius:6px}button{cursor:pointer;padding:9px 12px;font-weight:700}button:hover,button:focus-visible,select:focus-visible,input:focus-visible{border-color:var(--amber);outline:2px solid color-mix(in srgb,var(--amber) 35%,transparent);outline-offset:1px}button:disabled{opacity:.5;cursor:not-allowed}.shell{max-width:1500px;margin:auto;padding:18px}.topbar{height:54px;border:1px solid var(--line);border-radius:10px 10px 0 0;background:var(--panel);display:flex;align-items:center;justify-content:space-between;padding:0 18px;box-shadow:0 16px 40px var(--shadow)}.brand{font-size:17px;font-weight:800;letter-spacing:.08em}.brand b{color:var(--amber)}.tagline{color:var(--muted);font-size:11px;margin-left:14px}.local{color:var(--lime);font-size:11px;letter-spacing:.08em}.theme{margin-left:14px;background:transparent}.workspace{display:grid;grid-template-columns:240px minmax(420px,1fr) 340px;grid-template-areas:"library viewer settings" "process process settings";gap:10px;border:1px solid var(--line);border-top:0;padding:10px;background:#080907;border-radius:0 0 10px 10px;min-height:720px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:7px;min-width:0}.panel-title{padding:13px 14px;border-bottom:1px solid var(--line);font-size:12px;font-weight:800;letter-spacing:.08em}.library{grid-area:library;display:flex;flex-direction:column}.add-media{margin:12px;border:1px dashed var(--line);background:transparent;color:var(--muted);min-height:94px}.add-media strong{display:block;color:var(--text);font-size:18px;margin-bottom:7px}.file-list{display:grid;gap:5px;padding:0 8px 10px;overflow:auto}.file{display:grid;grid-template-columns:1fr;gap:5px;text-align:left;background:transparent;padding:10px;border-color:transparent}.file.active{border-color:var(--amber);background:var(--amber-soft)}.file-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.file-meta{font-size:10px;color:var(--muted)}.library-empty{padding:16px;color:var(--muted);font-size:11px;line-height:1.6}.privacy-stamp{margin:auto 12px 14px;padding-top:12px;border-top:1px solid var(--line);color:var(--lime);font-size:10px;line-height:1.5}.viewer{grid-area:viewer;padding:12px;display:flex;flex-direction:column;gap:10px}.media-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px;border:1px solid var(--line);border-radius:6px;background:var(--panel2)}.media-name{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.media-detail{font-size:10px;color:var(--muted);margin-top:5px}.ready{color:var(--lime);border:1px solid var(--lime);padding:3px 7px;border-radius:99px;font-size:9px}.wave-shell{position:relative;min-height:270px;border:1px solid var(--line);border-radius:6px;background:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:100% 25%,10% 100%;overflow:hidden}.wave-shell.empty{display:grid;place-items:center;color:var(--muted)}canvas{display:block;width:100%;height:270px;touch-action:none;cursor:crosshair}.wave-hint{position:absolute;left:12px;bottom:10px;color:var(--muted);font-size:10px;pointer-events:none}.selection{display:grid;grid-template-columns:auto 1fr 1fr;align-items:end;gap:9px;padding:9px;border:1px solid var(--line);border-radius:6px}.selection label{font-size:10px;color:var(--muted)}.selection input[type="number"]{width:100%;padding:7px;margin-top:4px}.selection-toggle{display:flex;gap:7px;align-items:center;padding-bottom:7px;color:var(--lime)!important}.player{width:100%;height:38px}.settings{grid-area:settings;padding-bottom:12px}.settings-body{padding:12px}.field{margin-bottom:13px}.field label{display:block;font-size:10px;color:var(--muted);margin-bottom:6px;letter-spacing:.08em}.field select,.field input[type="text"]{width:100%;min-height:38px;padding:8px}.path-row{display:grid;grid-template-columns:1fr auto;gap:5px}.path-row input{border:1px solid var(--line);background:var(--panel2);color:var(--muted);border-radius:6px;padding:8px;min-width:0}.enforced{display:flex;gap:8px;align-items:center;color:var(--lime);font-size:11px;margin:16px 0}.run{width:100%;background:var(--lime);border-color:var(--lime);color:#172000;min-height:48px;letter-spacing:.06em}.command{margin-top:14px;border:1px solid var(--line);border-radius:6px}.command summary{cursor:pointer;padding:9px;color:var(--muted);font-size:10px}.command pre{margin:0;padding:10px;border-top:1px solid var(--line);white-space:pre-wrap;word-break:break-word;color:var(--amber);font-size:10px;line-height:1.6}.error{color:var(--danger);font-size:11px;line-height:1.5;margin-top:9px}.process{grid-area:process;min-height:220px}.process-grid{display:grid;grid-template-columns:1fr 300px;gap:14px;padding:12px}.log{margin:0;max-height:180px;overflow:auto;white-space:pre-wrap;word-break:break-word;color:var(--muted);font-size:11px;line-height:1.55}.telemetry{border-left:1px solid var(--line);padding-left:14px}.progress-head{display:flex;justify-content:space-between;font-size:11px;margin-bottom:8px}.progress-track{height:8px;background:var(--panel2);border:1px solid var(--line);border-radius:99px;overflow:hidden}.progress-bar{height:100%;width:0;background:var(--lime);transition:width .2s}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:12px}.metric{padding:7px;background:var(--panel2);border-radius:5px;text-align:center}.metric b{display:block;color:var(--text);font-size:11px}.metric span{font-size:8px;color:var(--muted)}.job-actions{display:flex;gap:6px;margin-top:12px}.job-actions button{flex:1}.reveal{display:none;color:var(--lime)}.footer{text-align:center;color:var(--muted);font-size:9px;letter-spacing:.09em;padding:12px}.footer button{border:0;background:transparent;color:var(--muted);font-size:9px;letter-spacing:.09em;font-weight:500}.mobile-library{display:none}
@media(max-width:1050px){.workspace{grid-template-columns:210px 1fr;grid-template-areas:"library viewer" "settings settings" "process process"}.settings-body{display:grid;grid-template-columns:repeat(2,1fr);gap:0 12px}.run,.command,.enforced,.error{grid-column:1/-1}}
@media(max-width:700px){.shell{padding:0}.topbar{border-radius:0;border-left:0;border-right:0}.tagline{display:none}.workspace{display:flex;flex-direction:column;border:0;border-radius:0;padding:8px;min-height:calc(100vh - 54px)}.library{order:1;min-height:auto}.viewer{order:2}.settings{order:3}.process{order:4}.file-list{max-height:150px}.privacy-stamp{display:none}.wave-shell,canvas{height:180px;min-height:180px}.settings-body{display:block}.process-grid{grid-template-columns:1fr}.telemetry{border-left:0;border-top:1px solid var(--line);padding:12px 0 0}.selection{grid-template-columns:1fr 1fr}.selection-toggle{grid-column:1/-1}.local{font-size:9px}.theme{padding:7px}.metrics{grid-template-columns:repeat(3,1fr)}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
</style>
</head>
<body><div class="shell">
<header class="topbar"><div><span class="brand">TRANSCRIBE <b>LAB</b></span><span class="tagline">// MEDIA IN. TEXT OUT. LOCALLY.</span></div><div><span class="local">● LOCAL / PRIVATE</span><button class="theme" id="themeButton" aria-label="Toggle light theme">☼</button></div></header>
<main class="workspace">
<aside class="panel library"><div class="panel-title">INPUT / MEDIA</div><button class="add-media" id="addMedia"><strong>＋</strong>ADD AUDIO OR VIDEO</button><div class="file-list" id="fileList"><div class="library-empty">No media loaded.<br>Select one or several files to begin.</div></div><div class="privacy-stamp">● LOCALHOST SECURED<br>FILES STAY ON THIS MAC</div></aside>
<section class="panel viewer"><div class="media-head"><div><div class="media-name" id="mediaName">NO MEDIA SELECTED</div><div class="media-detail" id="mediaDetail">Choose a file to inspect its technical metadata.</div></div><span class="ready" id="readyBadge">WAITING</span></div><div class="wave-shell empty" id="waveShell"><canvas id="waveform" aria-label="Media waveform and selection timeline"></canvas><span id="waveEmpty">WAVEFORM / TIMELINE</span><span class="wave-hint" id="waveHint"></span></div><div class="selection"><label class="selection-toggle"><input type="checkbox" id="useSelection"> TRANSCRIBE SELECTION</label><label>START (SECONDS)<input type="number" id="startAt" min="0" step="0.1" value="0" disabled></label><label>END (SECONDS)<input type="number" id="endAt" min="0" step="0.1" value="0" disabled></label></div><audio class="player" id="player" aria-label="Selected media preview" controls preload="metadata"></audio></section>
<aside class="panel settings"><div class="panel-title">COMPILE SETTINGS</div><div class="settings-body"><div class="field"><label for="mode">MODE</label><select id="mode"><option value="transcribe">Transcribe speech → text</option><option value="translate">Translate speech → English</option></select></div><div class="field"><label for="language">LANGUAGE</label><select id="language"><option value="auto">Detect automatically</option>__LANGUAGE_OPTIONS__</select></div><div class="field"><label for="format">FORMAT</label><select id="format"><option value="txt">TXT — readable text</option><option value="srt">SRT — subtitles</option><option value="vtt">VTT — web captions</option><option value="tsv">TSV — timing data</option><option value="json">JSON — structured data</option><option value="all">ALL — every format</option></select></div><div class="field"><label for="outDir">OUTPUT</label><div class="path-row"><input id="outDir" readonly placeholder="Beside source file"><button id="chooseFolder" aria-label="Choose output folder">…</button></div></div><label class="enforced"><input type="checkbox" checked disabled> LOCAL / PRIVATE — ENFORCED</label><button class="run" id="runButton">▶ COMPILE TRANSCRIPT</button><div class="error" id="error" role="alert"></div><details class="command" open><summary>COMMAND PREVIEW</summary><pre id="commandPreview">$ transcribe [choose media]</pre></details></div></aside>
<section class="panel process" aria-live="polite"><div class="panel-title">PROCESS STREAM</div><div class="process-grid"><pre class="log" id="log">[ready] localhost transcription engine awaiting media...</pre><div class="telemetry"><div class="progress-head"><span id="jobState">IDLE</span><b id="progressLabel">0%</b></div><div class="progress-track"><div class="progress-bar" id="progressBar"></div></div><div class="metrics"><div class="metric"><b id="elapsed">00:00</b><span>ELAPSED</span></div><div class="metric"><b id="remaining">--:--</b><span>REMAINING</span></div><div class="metric"><b id="speed">—</b><span>SPEED</span></div></div><div class="job-actions"><button id="cancelButton" disabled>■ CANCEL</button><button class="reveal" id="revealButton">▣ REVEAL</button></div></div></div></section>
</main><div class="footer">A LOCAL TRANSCRIPTION ENVIRONMENT FOR PEOPLE WHO LIKE TO TINKER. <button id="quitButton">[ QUIT LOCAL INTERFACE ]</button></div></div>
<script>
const token=__TOKEN__;let files=[],current=null,peaks=[],dragging=false,dragStart=0,pollTimer=null;
const $=id=>document.getElementById(id),fileList=$('fileList'),wave=$('waveform'),waveShell=$('waveShell'),player=$('player'),mode=$('mode'),language=$('language'),format=$('format'),outDir=$('outDir'),useSelection=$('useSelection'),startAt=$('startAt'),endAt=$('endAt'),runButton=$('runButton'),cancelButton=$('cancelButton'),revealButton=$('revealButton'),log=$('log');
async function api(path,body={}){const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Transcribe-Token':token},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Operation failed.');return data}
function esc(value){return String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}
function clock(value,short=false){value=Math.max(0,Math.round(Number(value)||0));const h=Math.floor(value/3600),m=Math.floor(value%3600/60),s=value%60;return h||!short?[h,m,s].map(v=>String(v).padStart(2,'0')).join(':'):[m,s].map(v=>String(v).padStart(2,'0')).join(':')}
function bytes(value){const units=['B','KB','MB','GB'];let size=Number(value)||0,index=0;while(size>=1024&&index<3){size/=1024;index++}return (index?size.toFixed(size>=100?0:1):size)+' '+units[index]}
function metadata(file){const rate=file.sample_rate?Math.round(file.sample_rate/1000)+'kHz':'audio';const channels=file.channels===1?'mono':file.channels===2?'stereo':file.channels?file.channels+'ch':'—';return `${String(file.format).split(',')[0].toUpperCase()} · ${rate} · ${channels} · ${clock(file.duration)} · ${bytes(file.size)}`}
function shellQuote(value){return `'${String(value).replace(/'/g,"'\\''")}'`}
function renderFiles(){if(!files.length){fileList.innerHTML='<div class="library-empty">No media loaded.<br>Select one or several files to begin.</div>';return}fileList.innerHTML=files.map(file=>`<button class="file ${current&&current.id===file.id?'active':''}" data-id="${file.id}"><span class="file-name">${esc(file.name)}</span><span class="file-meta">${esc(clock(file.duration,true))} · ${esc(bytes(file.size))}</span></button>`).join('');fileList.querySelectorAll('.file').forEach(button=>button.onclick=()=>selectFile(button.dataset.id))}
async function addMedia(){showError('');$('addMedia').disabled=true;$('addMedia').innerHTML='<strong>⌁</strong>INSPECTING MEDIA…';try{const data=await api('choose-files');for(const file of data.files){if(!files.some(item=>item.id===file.id))files.push(file)}renderFiles();if(data.files.length)await selectFile(data.files[0].id)}catch(error){showError(error.message)}finally{$('addMedia').disabled=false;$('addMedia').innerHTML='<strong>＋</strong>ADD AUDIO OR VIDEO'}}
async function selectFile(id){current=files.find(file=>file.id===id);if(!current)return;renderFiles();$('mediaName').textContent=current.name;$('mediaDetail').textContent=metadata(current);$('readyBadge').textContent='READY';outDir.placeholder='Beside '+current.name;startAt.value='0';endAt.value=String(current.duration.toFixed(1));startAt.max=endAt.max=String(current.duration);useSelection.checked=false;toggleSelection();player.src=`/media/${encodeURIComponent(current.id)}?token=${encodeURIComponent(token)}`;waveShell.classList.remove('empty');$('waveEmpty').style.display='none';$('waveHint').textContent='CLICK TO SEEK · DRAG TO SELECT';peaks=[];drawWave();updateCommand();try{const data=await api('waveform',{id:current.id});peaks=data.peaks;drawWave()}catch(error){showError(error.message)}}
function drawWave(){const rect=wave.getBoundingClientRect(),ratio=window.devicePixelRatio||1;wave.width=Math.max(1,Math.round(rect.width*ratio));wave.height=Math.max(1,Math.round(rect.height*ratio));const ctx=wave.getContext('2d');ctx.scale(ratio,ratio);ctx.clearRect(0,0,rect.width,rect.height);const style=getComputedStyle(document.documentElement),amber=style.getPropertyValue('--amber'),muted=style.getPropertyValue('--muted');if(!peaks.length){ctx.fillStyle=muted;ctx.font='11px ui-monospace';ctx.fillText(current?'ANALYZING WAVEFORM…':'',16,28);return}if(useSelection.checked){const left=Number(startAt.value)/current.duration*rect.width,right=Number(endAt.value)/current.duration*rect.width;ctx.fillStyle=style.getPropertyValue('--amber-soft');ctx.fillRect(left,0,Math.max(2,right-left),rect.height)}ctx.strokeStyle=amber;ctx.lineWidth=Math.max(1,rect.width/peaks.length*.62);const middle=rect.height/2,step=rect.width/peaks.length;ctx.beginPath();peaks.forEach((peak,index)=>{const height=Math.max(1,peak*(rect.height*.82));const x=index*step;ctx.moveTo(x,middle-height/2);ctx.lineTo(x,middle+height/2)});ctx.stroke();if(current&&player.currentTime){const x=player.currentTime/current.duration*rect.width;ctx.strokeStyle=style.getPropertyValue('--lime');ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,rect.height);ctx.stroke()}}
function pointTime(event){const rect=wave.getBoundingClientRect();return Math.max(0,Math.min(current.duration,(event.clientX-rect.left)/rect.width*current.duration))}
function toggleSelection(){startAt.disabled=endAt.disabled=!useSelection.checked;updateCommand();drawWave()}
function updateCommand(){if(!current){$('commandPreview').textContent='$ transcribe [choose media]';return}const parts=['transcribe',shellQuote(current.path)];if(mode.value==='translate')parts.push('--translate-to en');parts.push(language.value==='auto'?'--auto-language':'--language '+language.value,'--format '+format.value);if(outDir.value)parts.push('--out-dir '+shellQuote(outDir.value));if(useSelection.checked)parts.push('--start-at '+Number(startAt.value).toFixed(1),'--end-at '+Number(endAt.value).toFixed(1));$('commandPreview').textContent='$ '+parts.join(' \\\n  ')}
function updateMode(){const english=language.querySelector('option[value="en"]');english.disabled=mode.value==='translate';if(english.disabled&&language.value==='en')language.value='auto';if(mode.value==='translate'&&format.value==='txt')format.value='srt';runButton.textContent=mode.value==='translate'?'▶ COMPILE ENGLISH TRANSLATION':'▶ COMPILE TRANSCRIPT';updateCommand()}
function showError(message){$('error').textContent=message}
async function pickFolder(){try{const data=await api('choose-folder');if(data.path)outDir.value=data.path;updateCommand()}catch(error){showError(error.message)}}
async function startJob(){showError('');if(!current)return showError('Add and select a media file first.');try{await api('start',{id:current.id,out_dir:outDir.value,format:format.value,language:language.value,translate:mode.value==='translate',duration:current.duration,start_at:useSelection.checked?Number(startAt.value):null,end_at:useSelection.checked?Number(endAt.value):null});runButton.disabled=true;cancelButton.disabled=false;revealButton.style.display='none';poll()}catch(error){showError(error.message)}}
async function poll(){try{const response=await fetch('/api/status',{headers:{'X-Transcribe-Token':token}}),data=await response.json();log.textContent=data.log||'[working]';log.scrollTop=log.scrollHeight;$('jobState').textContent=data.state.toUpperCase();$('progressLabel').textContent=data.progress+'%';$('progressBar').style.width=data.progress+'%';$('elapsed').textContent=clock(data.elapsed,true);$('remaining').textContent=data.remaining?clock(data.remaining,true):'--:--';$('speed').textContent=data.speed?data.speed.toFixed(2)+'×':'—';const done=['success','error','cancelled'].includes(data.state);runButton.disabled=!done;cancelButton.disabled=done;revealButton.style.display=data.state==='success'?'block':'none';if(!done)pollTimer=setTimeout(poll,700)}catch(error){showError(error.message);runButton.disabled=false}}
async function cancelJob(){try{await api('cancel')}catch(error){showError(error.message)}}async function reveal(){try{await api('reveal')}catch(error){showError(error.message)}}async function quitUi(){try{await api('shutdown');document.body.innerHTML='<div style="padding:48px;font-family:ui-monospace;background:#0d0d0c;color:#f1f0e8;min-height:100vh"><h1>TRANSCRIBE LAB / CLOSED</h1><p>You can close this tab.</p></div>'}catch(error){showError(error.message)}}
$('addMedia').onclick=addMedia;$('chooseFolder').onclick=pickFolder;runButton.onclick=startJob;cancelButton.onclick=cancelJob;revealButton.onclick=reveal;$('quitButton').onclick=quitUi;mode.onchange=updateMode;language.onchange=format.onchange=updateCommand;outDir.onchange=updateCommand;useSelection.onchange=toggleSelection;startAt.oninput=endAt.oninput=()=>{if(Number(endAt.value)<=Number(startAt.value))endAt.value=String(Math.min(current.duration,Number(startAt.value)+1));updateCommand();drawWave()};wave.onpointerdown=event=>{if(!current)return;dragging=useSelection.checked;dragStart=pointTime(event);if(dragging){startAt.value=endAt.value=String(dragStart.toFixed(1));wave.setPointerCapture(event.pointerId)}else{player.currentTime=dragStart;drawWave()}};wave.onpointermove=event=>{if(!dragging)return;const now=pointTime(event);startAt.value=String(Math.min(dragStart,now).toFixed(1));endAt.value=String(Math.max(dragStart,now).toFixed(1));updateCommand();drawWave()};wave.onpointerup=()=>{dragging=false;if(Number(endAt.value)-Number(startAt.value)<.5)endAt.value=String(Math.min(current.duration,Number(startAt.value)+1).toFixed(1));updateCommand();drawWave()};player.ontimeupdate=drawWave;window.onresize=drawWave;$('themeButton').onclick=()=>{const root=document.documentElement;root.dataset.theme=root.dataset.theme==='dark'?'light':'dark';$('themeButton').textContent=root.dataset.theme==='dark'?'☼':'☾';drawWave()};updateMode();
</script></body></html>'''


def launch_ui(open_browser: bool = True) -> int:
    """Serve the dependency-free local interface until the user quits it."""
    token = secrets.token_urlsafe(24)
    job = LocalJob()
    media_registry: dict[str, Path] = {}
    featured_options = "".join(
        f'<option value="{code}">{SUPPORTED_LANGUAGES[code]}</option>'
        for code in FEATURED_LANGUAGE_CODES
    )
    other_options = "".join(
        f'<option value="{code}">{name}</option>'
        for code, name in sorted(SUPPORTED_LANGUAGES.items(), key=lambda item: item[1])
        if code not in FEATURED_LANGUAGE_CODES
    )
    language_options = (
        f'<optgroup label="Popular languages">{featured_options}</optgroup>'
        f'<optgroup label="All other supported languages">{other_options}</optgroup>'
    )
    page = (
        UI_TEMPLATE.replace("__TOKEN__", json.dumps(token))
        .replace("__LANGUAGE_OPTIONS__", language_options)
        .encode("utf-8")
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _authorized(self) -> bool:
            return self.headers.get("X-Transcribe-Token") == token

        def _json(self, payload: dict[str, object], status: int = 200) -> None:
            content = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def _body(self) -> dict[str, object]:
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 65536)
                return json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return {}

        def _serve_media(self, media_id: str) -> None:
            source = media_registry.get(media_id)
            if source is None or not source.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            total = source.stat().st_size
            start, end = 0, total - 1
            range_header = self.headers.get("Range", "")
            if range_header:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
                if not match:
                    self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    return
                if not match.group(1) and not match.group(2):
                    self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    return
                if not match.group(1):
                    suffix_length = min(total, int(match.group(2)))
                    start = total - suffix_length
                else:
                    start = int(match.group(1))
                if match.group(1) and match.group(2):
                    end = min(end, int(match.group(2)))
                if start > end or start >= total:
                    self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    return
            length = end - start + 1
            self.send_response(
                HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK
            )
            self.send_header(
                "Content-Type",
                mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            )
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            if range_header:
                self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
            self.end_headers()
            try:
                with source.open("rb") as media:
                    media.seek(start)
                    remaining = length
                    while remaining:
                        chunk = media.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/media/"):
                query_token = parse_qs(parsed.query).get("token", [""])[0]
                if query_token != token:
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                self._serve_media(parsed.path.removeprefix("/media/"))
                return
            if parsed.path == "/":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'unsafe-inline'; "
                    "style-src 'unsafe-inline'; connect-src 'self'; "
                    "img-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                )
                self.end_headers()
                self.wfile.write(page)
                return
            if parsed.path == "/api/status" and self._authorized():
                self._json(job.snapshot())
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if not self._authorized():
                self._json({"error": "Unauthorized"}, HTTPStatus.FORBIDDEN)
                return
            body = self._body()
            if self.path == "/api/choose-files":
                selected = choose_files_with_macos("Choose audio or video files")
                inspected = []
                try:
                    for source in selected:
                        source = source.expanduser().resolve()
                        if not source.is_file():
                            continue
                        existing_id = next(
                            (
                                media_id
                                for media_id, registered in media_registry.items()
                                if registered == source
                            ),
                            None,
                        )
                        media_id = existing_id or secrets.token_urlsafe(9)
                        media_registry[media_id] = source
                        details = inspect_media(source)
                        details["id"] = media_id
                        inspected.append(details)
                except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
                    self._json({"error": f"Could not inspect media: {error}"}, 400)
                    return
                self._json({"files": inspected})
                return
            if self.path == "/api/choose-folder":
                selected = choose_with_macos("Choose where to save the transcript", True)
                self._json({"path": str(selected) if selected else ""})
                return
            if self.path == "/api/start":
                source = media_registry.get(str(body.get("id", "")))
                if source is None:
                    self._json({"error": "Select a registered media file."}, 400)
                    return
                out_value = str(body.get("out_dir", "")).strip()
                out_dir = (
                    Path(out_value).expanduser().resolve() if out_value else source.parent
                )
                try:
                    duration = float(body.get("duration") or 0)
                    start_at = (
                        float(body["start_at"])
                        if body.get("start_at") is not None
                        else None
                    )
                    end_at = (
                        float(body["end_at"])
                        if body.get("end_at") is not None
                        else None
                    )
                except (TypeError, ValueError):
                    self._json({"error": "Choose a valid media range."}, 400)
                    return
                started, message = job.start(
                    source,
                    out_dir,
                    str(body.get("format", "txt")),
                    str(body.get("language", "auto")),
                    bool(body.get("translate", False)),
                    duration,
                    start_at,
                    end_at,
                )
                self._json(
                    {"ok": started, "message": message},
                    HTTPStatus.OK if started else HTTPStatus.BAD_REQUEST,
                )
                return
            if self.path == "/api/waveform":
                source = media_registry.get(str(body.get("id", "")))
                if source is None:
                    self._json({"error": "Select a registered media file."}, 400)
                    return
                try:
                    peaks = waveform_peaks(source)
                except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
                    self._json({"error": f"Could not create waveform: {error}"}, 400)
                    return
                self._json({"peaks": peaks})
                return
            if self.path == "/api/cancel":
                self._json({"cancelled": job.cancel()})
                return
            if self.path == "/api/reveal":
                output = job.snapshot().get("output", "")
                if output and Path(str(output)).exists():
                    subprocess.run(["open", "-R", str(output)], check=False)
                    self._json({"ok": True})
                else:
                    self._json({"error": "The result is not available."}, 404)
                return
            if self.path == "/api/shutdown":
                if job.snapshot()["state"] in ("running", "cancelling"):
                    self._json({"error": "Cancel the current job before quitting."}, 409)
                    return
                self._json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Opening Transcribe Lab: {url}")
    print("Keep this Terminal window open while using the interface.")
    print("Press Control-C here if you need to close it.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        job.cancel()
        print("\nClosing Transcribe.")
    finally:
        server.server_close()
    return 0


def _read_path(prompt: str) -> Path | None:
    raw = input(prompt).strip()
    if not raw:
        return None
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = [raw]
    return Path(parts[0]).expanduser() if len(parts) == 1 else Path(raw).expanduser()


def guided_terminal() -> int:
    """Collect the common options through simple Terminal questions."""
    print("\nGuided transcription\n")
    source = _read_path("File path (you can drag the file here): ")
    if source is None:
        print("No file selected.", file=sys.stderr)
        return 2
    action = input("1) Transcribe  2) Translate to English [1]: ").strip() or "1"
    translate = action == "2"
    if action not in ("1", "2"):
        print("Please choose 1 or 2.", file=sys.stderr)
        return 2
    default_format = "srt" if translate else "txt"
    output_format = input(f"Output format [default: {default_format}]: ").strip()
    output_format = output_format.lower() or default_format
    if output_format not in OUTPUT_FORMATS:
        print("Choose txt, srt, vtt, tsv, json, or all.", file=sys.stderr)
        return 2
    arguments = [str(source), "--format", output_format]
    if translate:
        language = input("Source language code, or auto [auto]: ").strip() or "auto"
        arguments.extend(
            ["--auto-language"] if language == "auto" else ["--language", language]
        )
        arguments.extend(["--translate-to", "en"])
    else:
        language = input("Spoken language code, or auto [auto]: ").strip() or "auto"
        arguments.extend(
            ["--auto-language"] if language == "auto" else ["--language", language]
        )
    out_dir = _read_path("Save folder [beside original]: ")
    if out_dir:
        arguments.extend(["--out-dir", str(out_dir)])
    print()
    return main(arguments)


def launch_menu() -> int:
    print("\nWelcome to Transcribe\n")
    print("1) Open Transcribe Lab")
    print("2) Continue with guided Terminal mode")
    print("3) Show command help")
    try:
        choice = input("\nChoose [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        print()
        return 130
    if choice == "1":
        return launch_ui()
    if choice == "2":
        return guided_terminal()
    if choice == "3":
        try:
            parse_args(["--help"])
        except SystemExit as error:
            return int(error.code or 0)
    print("Please choose 1, 2, or 3.", file=sys.stderr)
    return 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.update:
        return update_command()
    if args.ui:
        return launch_ui()
    if args.guided:
        return guided_terminal()
    if args.input is None:
        if sys.stdin.isatty():
            return launch_menu()
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
    if args.translate_to and not args.auto_language and args.language == "en":
        print(
            "Choose a non-English --language or use --auto-language for translation.",
            file=sys.stderr,
        )
        return 2
    if args.start_at is not None or args.end_at is not None:
        if (
            args.start_at is None
            or args.end_at is None
            or args.start_at < 0
            or args.end_at <= args.start_at
        ):
            print(
                "--start-at and --end-at must define a valid increasing range.",
                file=sys.stderr,
            )
            return 2

    output_name = output_name_for(
        source,
        translated_to_english=bool(args.translate_to),
        start_at=args.start_at,
        end_at=args.end_at,
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
    if args.start_at is not None and args.end_at is not None:
        command.extend(
            ["--clip-timestamps", f"{args.start_at:g},{args.end_at:g}"]
        )

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
