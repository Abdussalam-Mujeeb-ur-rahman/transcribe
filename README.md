# Transcribe

Transcribe audio and video locally on an Apple Silicon Mac with
[MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper).
The default result is a timestamped TXT transcript saved beside the source.

The tool is useful for voice notes, meetings, interviews, and screen
recordings. It supports OPUS, OGG, M4A, MP3, WAV, MP4, and MOV input through
FFmpeg. Other FFmpeg-compatible formats may also work but are not part of the
tested interface.

## Privacy

Transcription runs on your Mac. Recordings are not sent to a hosted
transcription API by this project. The selected model is downloaded from
Hugging Face on first use and cached locally, so the first run can take longer
and requires internet access. Later transcription can run from the local model
cache.

## Requirements

- macOS on an Apple Silicon Mac (M1 or newer)
- Python 3.9 or newer
- FFmpeg
- MLX Whisper

Intel Macs, Windows, and Linux are not supported because MLX is optimized for
Apple silicon.

## Install from GitHub

Install FFmpeg with [Homebrew](https://brew.sh/):

```bash
brew install ffmpeg
```

Install MLX Whisper:

```bash
python3 -m pip install --user mlx-whisper
```

Clone this repository:

```bash
git clone git@github.com:Abdussalam-Mujeeb-ur-rahman/transcribe.git
cd transcribe
```

HTTPS also works:

```bash
git clone https://github.com/Abdussalam-Mujeeb-ur-rahman/transcribe.git
cd transcribe
```

Confirm the command-line interface:

```bash
python3 transcribe_media.py --help
```

## Use it directly

```bash
python3 transcribe_media.py "/path/to/recording.mp4"
```

English and timestamped TXT are the defaults. The result is saved beside the
recording:

```text
recording.mp4
recording_transcript.txt
```

Dots inside the original basename are changed to hyphens in the output name.
For example, `voice.note.09.38.opus` produces
`voice-note-09-38_transcript.txt`. The source file is never renamed.

## Install the short `transcribe` command

The included setup script creates a symlink in `~/bin`. It does not contain a
hard-coded username or repository path, and it refuses to replace an existing
command:

```bash
chmod +x transcribe_media.py install.sh
./install.sh
```

If `~/bin` is not already in your command search path, add it once:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Then use the short command from any directory:

```bash
transcribe "/path/to/audio-or-video.opus"
```

The symlink points to this checkout. If you move or delete the repository,
re-run `install.sh` from its new location.

## Drag a file from Finder

Type `transcribe`, add one space, drag the file from Finder into Terminal, and
press Return:

```text
transcribe /Users/you/Downloads/WhatsApp\ Audio\ 2026-08-18.opus
```

Terminal inserts backslashes to escape spaces. Do **not** put quotation marks
around a path that already contains those automatically inserted backslashes:

```text
Correct:   transcribe /Users/you/Downloads/WhatsApp\ Audio\ 2026-08-18.opus
Incorrect: transcribe "/Users/you/Downloads/WhatsApp\ Audio\ 2026-08-18.opus"
```

For a path typed manually, use quotation marks and no backslashes:

```bash
transcribe "/Users/you/Downloads/WhatsApp Audio 2026-08-18.opus"
```

Quoted paths and escaped paths are two different shell styles for protecting
spaces. Use either style, not both at once.

## Choose the output directory

By default, the transcript is written beside the input file. `--out-dir`
creates and uses another directory:

```bash
transcribe "/path/to/recording.mov" \
  --out-dir "$HOME/Documents/Transcripts"
```

## Output formats

```bash
transcribe "/path/to/recording.mp4" --format txt
transcribe "/path/to/recording.mp4" --format srt
transcribe "/path/to/recording.mp4" --format vtt
transcribe "/path/to/recording.mp4" --format tsv
transcribe "/path/to/recording.mp4" --format json
transcribe "/path/to/recording.mp4" --format all
```

| Format | Typical use |
| --- | --- |
| TXT | Readable, timestamped transcript; the default |
| SRT | Subtitles for video players and editors |
| VTT | Web subtitles and captions |
| TSV | Timing data in tab-separated rows |
| JSON | Structured segments and metadata |
| ALL | Generate all formats in one run |

## Language selection

English is the default. Set a Whisper language code when the recording uses
another language:

```bash
transcribe "/path/to/recording.m4a" --language fr
transcribe "/path/to/recording.m4a" --language yo
```

Let Whisper detect the spoken language by omitting the explicit language from
the underlying command:

```bash
transcribe "/path/to/recording.mov" --auto-language
```

If both options are supplied, `--auto-language` takes precedence.

## Model selection

The default model is `mlx-community/whisper-small-mlx`, a practical speed and
accuracy balance on Apple Silicon. Choose a different Hugging Face model or a
local model path with `--model`:

```bash
transcribe "/path/to/recording.mp4" \
  --model mlx-community/whisper-large-v3-turbo
```

Larger models generally need more memory and time. Each new remote model is
downloaded on its first use. Set a reusable default with:

```bash
export MLX_WHISPER_MODEL="mlx-community/whisper-small-mlx"
```

## Command-line options

```text
usage: transcribe [-h] [--out-dir OUT_DIR]
                  [--format {txt,srt,vtt,tsv,json,all}]
                  [--language LANGUAGE] [--auto-language]
                  [--model MODEL] [--whisper-bin WHISPER_BIN]
                  input

positional arguments:
  input                 Path to an audio or video file

options:
  -h, --help            Show help and exit
  --out-dir OUT_DIR     Folder for the transcript; defaults to input folder
  --format FORMAT       txt, srt, vtt, tsv, json, or all; defaults to txt
  --language LANGUAGE   Spoken language code; defaults to en
  --auto-language       Let Whisper detect the spoken language
  --model MODEL         Hugging Face model name or local model path
  --whisper-bin PATH    mlx_whisper executable name or explicit path
```

`MLX_WHISPER_BIN` can set a default executable name or path. A command-line
option overrides the environment variable. The tool searches `PATH` first and
also checks the standard `~/Library/Python/*/bin` location used by
`pip install --user` on macOS.

## Troubleshooting

### `command not found: transcribe`

Check the installation and path:

```bash
ls -l "$HOME/bin/transcribe"
echo "$PATH"
source ~/.zshrc
```

Run `./install.sh` again if the repository moved.

### `mlx_whisper was not found`

Install it, then find the installed executable:

```bash
python3 -m pip install --user mlx-whisper
command -v mlx_whisper
```

If it is outside your path, pass or export its location:

```bash
transcribe input.opus --whisper-bin "/path/to/mlx_whisper"
export MLX_WHISPER_BIN="/path/to/mlx_whisper"
```

### The media file cannot be decoded

Install or update FFmpeg and verify the source plays normally:

```bash
brew install ffmpeg
ffprobe "/path/to/recording.mp4"
```

### The first run is slow

The model is probably downloading. Download time depends on the model and
connection. Later runs reuse the cache; larger models still transcribe more
slowly.

### The transcript is inaccurate

Specify the language, try a larger model, and use the clearest recording
available. Names, specialist terms, accents, noise, low volume, music, and
overlapping speakers can reduce accuracy.

Whisper output is probabilistic and can omit, mishear, or invent words. Review
important transcripts against the original recording. This tool does not
identify speakers and should not be treated as a certified or legal
transcription service.

## Development and validation

The tests use Python's standard library and do not run a model:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile transcribe_media.py tests/test_transcribe_media.py
```

Recordings, generated transcripts, caches, secrets, and local environments are
excluded by `.gitignore`.

## Future direction

An npm wrapper may eventually make command discovery familiar to JavaScript
users, but it would still depend on Python, MLX Whisper, and FFmpeg. The first
release intentionally stays Python-only.

## License

[MIT](LICENSE)
