#!/usr/bin/env python3
"""Transcribe or translate one audio or video file with MLX Whisper."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import webbrowser
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Sequence


VERSION = "1.2.0"
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
        "--ui",
        action="store_true",
        help="Open the simple local interface in your browser",
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


def expected_output_path(
    source: Path, out_dir: Path, output_format: str, translate: bool
) -> Path:
    if output_format == "all":
        output_format = "txt"
    return out_dir / (
        f"{output_name_for(source, translated_to_english=translate)}.{output_format}"
    )


class LocalJob:
    """Manage the single transcription process owned by the local interface."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.state = "idle"
        self.log: list[str] = []
        self.output_path: Path | None = None

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "state": self.state,
                "log": "".join(self.log[-400:]),
                "output": str(self.output_path) if self.output_path else "",
            }

    def start(
        self,
        source: Path,
        out_dir: Path,
        output_format: str,
        language: str,
        translate: bool,
    ) -> tuple[bool, str]:
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                return False, "A transcription is already running."

        if not source.is_file():
            return False, "Choose a valid audio or video file."
        if output_format not in OUTPUT_FORMATS:
            return False, "Choose a valid output format."
        if language not in ("auto", "en", "tr"):
            return False, "Choose a valid language."
        if translate and language != "tr":
            return False, "Turkish-to-English translation requires Turkish input."

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

        with self.lock:
            self.state = "running"
            self.log = [f"Starting {source.name}…\n"]
            self.output_path = expected_output_path(
                source, out_dir, output_format, translate
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
        return_code = process.wait()
        with self.lock:
            if self.state == "cancelling":
                self.state = "cancelled"
                self.log.append("Cancelled.\n")
            elif return_code == 0:
                self.state = "success"
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
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Transcribe</title>
<style>
:root{color-scheme:light dark;--bg:#f3f4f6;--panel:#fff;--text:#17202a;--muted:#667085;--line:#d9dee7;--accent:#2563eb;--soft:#eff6ff;--danger:#b42318}
@media(prefers-color-scheme:dark){:root{--bg:#111318;--panel:#1b1e24;--text:#f3f4f6;--muted:#a8b0bd;--line:#343a46;--soft:#17264a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:760px;margin:48px auto;padding:0 20px}.brand{display:flex;gap:14px;align-items:center;margin-bottom:24px}.icon{width:48px;height:48px;border-radius:14px;background:linear-gradient(145deg,#4f8cff,#164bc1);display:grid;place-items:center;color:white;font-size:25px}.brand h1{font-size:28px;margin:0}.brand p{color:var(--muted);margin:4px 0 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px;box-shadow:0 12px 32px rgba(15,23,42,.06)}label{font-weight:650;display:block;margin:18px 0 8px}.row{display:grid;grid-template-columns:1fr auto;gap:10px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
input,select,button{font:inherit;border-radius:10px;border:1px solid var(--line);min-height:44px}input,select{width:100%;padding:10px 12px;background:var(--panel);color:var(--text)}input[readonly]{color:var(--muted)}button{padding:10px 16px;background:var(--panel);color:var(--text);cursor:pointer;font-weight:650}button:hover{border-color:var(--accent)}button.primary{background:var(--accent);border-color:var(--accent);color:white;width:100%;margin-top:22px}button:disabled{opacity:.55;cursor:not-allowed}.mode{display:grid;grid-template-columns:1fr 1fr;gap:10px}.mode button.active{background:var(--soft);border-color:var(--accent);color:var(--accent)}
.status{display:none;margin-top:18px;padding:16px;border-radius:12px;background:var(--bg)}.status.show{display:block}.status-line{display:flex;justify-content:space-between;align-items:center}.badge{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}pre{white-space:pre-wrap;word-break:break-word;max-height:220px;overflow:auto;color:var(--muted);font:12px ui-monospace,SFMono-Regular,Menlo,monospace;margin:12px 0 0}.actions{display:flex;gap:8px;margin-top:12px}.actions button{min-height:36px;padding:6px 12px}.privacy{text-align:center;color:var(--muted);font-size:13px;margin:16px}.error{color:var(--danger);margin-top:12px}.footer{display:flex;justify-content:center;margin-top:14px}.footer button{border:0;background:transparent;color:var(--muted);font-weight:500}
@media(max-width:600px){main{margin:24px auto}.grid,.mode{grid-template-columns:1fr}.card{padding:18px}}
</style>
</head>
<body><main>
<div class="brand"><div class="icon">⌁</div><div><h1>Transcribe</h1><p>Private transcription on your Apple silicon Mac</p></div></div>
<div class="card">
<label for="source">Audio or video</label><div class="row"><input id="source" readonly placeholder="Choose a recording or movie"><button onclick="pickFile()">Choose file</button></div>
<label>What should I do?</label><div class="mode"><button id="transcribeMode" class="active" aria-pressed="true" onclick="setMode(false)">Transcribe</button><button id="translateMode" aria-pressed="false" onclick="setMode(true)">Turkish → English</button></div>
<div class="grid"><div><label for="language">Spoken language</label><select id="language"><option value="auto">Detect automatically</option><option value="en">English</option><option value="tr">Turkish</option></select></div><div><label for="format">Output format</label><select id="format"><option value="txt">TXT — readable text</option><option value="srt">SRT — video subtitles</option><option value="vtt">VTT — web subtitles</option><option value="tsv">TSV — timing data</option><option value="json">JSON — structured data</option><option value="all">All formats</option></select></div></div>
<label for="outDir">Save location</label><div class="row"><input id="outDir" readonly placeholder="Beside the original file"><button onclick="pickFolder()">Choose folder</button></div>
<button class="primary" id="start" onclick="startJob()">Start transcription</button><div id="error" class="error" role="alert"></div>
<div id="status" class="status" aria-live="polite"><div class="status-line"><strong id="statusText">Preparing…</strong><span id="badge" class="badge">running</span></div><pre id="log"></pre><div class="actions"><button id="cancel" onclick="cancelJob()">Cancel</button><button id="reveal" onclick="reveal()" style="display:none">Show in Finder</button></div></div>
</div><p class="privacy">Your recording stays on this Mac. Internet is needed only for first-time model downloads.</p><div class="footer"><button onclick="quitUi()">Quit local interface</button></div>
</main>
<script>
const token=__TOKEN__;let translating=false,pollTimer=null;
const source=document.getElementById('source'),outDir=document.getElementById('outDir'),format=document.getElementById('format'),language=document.getElementById('language'),status=document.getElementById('status'),start=document.getElementById('start'),badge=document.getElementById('badge'),log=document.getElementById('log'),statusText=document.getElementById('statusText'),cancelEl=document.getElementById('cancel'),revealEl=document.getElementById('reveal');
async function api(path,body={}){const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Transcribe-Token':token},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Something went wrong.');return data}
function setMode(value){translating=value;const transcribeMode=document.getElementById('transcribeMode'),translateMode=document.getElementById('translateMode');transcribeMode.classList.toggle('active',!value);translateMode.classList.toggle('active',value);transcribeMode.setAttribute('aria-pressed',String(!value));translateMode.setAttribute('aria-pressed',String(value));const lang=document.getElementById('language'),format=document.getElementById('format');if(value){lang.value='tr';lang.disabled=true;if(format.value==='txt')format.value='srt'}else{lang.disabled=false}document.getElementById('start').textContent=value?'Translate to English':'Start transcription'}
async function pickFile(){try{const d=await api('choose-file');if(d.path){source.value=d.path;if(!outDir.value)outDir.placeholder='Beside '+d.parent}}catch(e){showError(e.message)}}
async function pickFolder(){try{const d=await api('choose-folder');if(d.path)outDir.value=d.path}catch(e){showError(e.message)}}
function showError(message){document.getElementById('error').textContent=message}
async function startJob(){showError('');if(!source.value)return showError('Choose an audio or video file first.');try{await api('start',{source:source.value,out_dir:outDir.value,format:format.value,language:language.value,translate:translating});status.classList.add('show');start.disabled=true;poll()}catch(e){showError(e.message)}}
async function poll(){try{const r=await fetch('/api/status',{headers:{'X-Transcribe-Token':token}}),d=await r.json();badge.textContent=d.state;log.textContent=d.log;log.scrollTop=log.scrollHeight;const done=['success','error','cancelled'].includes(d.state);statusText.textContent=d.state==='success'?'Finished successfully':d.state==='error'?'Could not finish':d.state==='cancelled'?'Cancelled':d.state==='cancelling'?'Cancelling…':'Working locally…';cancelEl.style.display=done?'none':'inline-block';revealEl.style.display=d.state==='success'?'inline-block':'none';start.disabled=!done;if(!done)pollTimer=setTimeout(poll,800)}catch(e){showError(e.message);start.disabled=false}}
async function cancelJob(){try{await api('cancel')}catch(e){showError(e.message)}}async function reveal(){try{await api('reveal')}catch(e){showError(e.message)}}async function quitUi(){try{await api('shutdown');document.body.innerHTML='<main><div class="card"><h2>Transcribe closed</h2><p>You can close this tab.</p></div></main>'}catch(e){showError(e.message)}}
</script></body></html>'''


def launch_ui(open_browser: bool = True) -> int:
    """Serve the dependency-free local interface until the user quits it."""
    token = secrets.token_urlsafe(24)
    job = LocalJob()
    page = UI_TEMPLATE.replace("__TOKEN__", json.dumps(token)).encode("utf-8")

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

        def do_GET(self) -> None:
            if self.path == "/":
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
            if self.path == "/api/status" and self._authorized():
                self._json(job.snapshot())
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if not self._authorized():
                self._json({"error": "Unauthorized"}, HTTPStatus.FORBIDDEN)
                return
            body = self._body()
            if self.path == "/api/choose-file":
                selected = choose_with_macos("Choose an audio or video file")
                self._json(
                    {
                        "path": str(selected) if selected else "",
                        "parent": str(selected.parent) if selected else "",
                    }
                )
                return
            if self.path == "/api/choose-folder":
                selected = choose_with_macos("Choose where to save the transcript", True)
                self._json({"path": str(selected) if selected else ""})
                return
            if self.path == "/api/start":
                source = Path(str(body.get("source", ""))).expanduser().resolve()
                out_value = str(body.get("out_dir", "")).strip()
                out_dir = (
                    Path(out_value).expanduser().resolve() if out_value else source.parent
                )
                started, message = job.start(
                    source,
                    out_dir,
                    str(body.get("format", "txt")),
                    str(body.get("language", "auto")),
                    bool(body.get("translate", False)),
                )
                self._json(
                    {"ok": started, "message": message},
                    HTTPStatus.OK if started else HTTPStatus.BAD_REQUEST,
                )
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
    print(f"Opening Transcribe: {url}")
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
    action = input("1) Transcribe  2) Turkish → English [1]: ").strip() or "1"
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
        arguments.extend(["--language", "tr", "--translate-to", "en"])
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
    print("1) Open the simple interface")
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
