# Transcribe

Transcribe audio and video locally on an Apple Silicon Mac with
[MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper).
The default result is a readable TXT transcript saved beside the source.
Timestamped subtitle output is available as SRT or VTT.
Supported non-English recordings can also be translated directly into English
TXT or English subtitles without installing another translation service.

The tool is useful for voice notes, meetings, interviews, and screen
recordings. It supports OPUS, OGG, M4A, MP3, WAV, MP4, and MOV input through
FFmpeg. Other FFmpeg-compatible formats may also work but are not part of the
tested interface.

## One-command setup

Paste this single command into Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Abdussalam-Mujeeb-ur-rahman/transcribe/main/install.sh)" && exec zsh -l
```

The installer automatically:

1. Confirms macOS 14 or newer and an Apple silicon `arm64` environment.
2. Checks for Homebrew, native Python 3.10+, FFmpeg, and `pipx`.
3. Installs Homebrew only when it is needed, then installs only missing tools.
4. Installs MLX Whisper with `pipx` when it is not already available.
5. Installs `transcribe` under your user account and configures your shell path.
6. Verifies the installed versions and runs `transcribe --help`.
7. Reloads your shell so the command is ready immediately.

Homebrew may request your macOS password or confirmation if it must be
installed. Dependency setup can take several minutes. You can
[review the installer](install.sh) before running it.

When setup finishes, start with:

```bash
transcribe
```

## Transcribe Lab or Terminal

Run `transcribe` without a file to choose how you want to continue:

```text
Welcome to Transcribe

1) Open Transcribe Lab
2) Continue with guided Terminal mode
3) Show command help
```

**Transcribe Lab** is the local visual workspace. Add one or several media
files, confirm the real duration, size, format, sample rate and channel count,
preview the selected recording, and inspect its generated waveform. Click the
waveform to seek, or enable **Transcribe selection** and drag across it to run
only a specific range. Choose transcription or translation to English, the
spoken language, output format and folder, then follow percentage, elapsed
time, estimated remaining time, processing speed and the live process stream.

The interface also shows the exact equivalent `transcribe` command. Its dark
theme is designed for a code-focused workspace; use the sun button for the
lighter long-session theme. The browser does not upload or copy recordings.
It talks only to a temporary localhost server, while FFmpeg and MLX Whisper
process the original paths on your Mac. **LOCAL / PRIVATE — ENFORCED** cannot
be turned off because this project has no cloud transcription mode.

Open either experience directly with:

```bash
transcribe --ui
transcribe --guided
```

Keep the launching Terminal window open while Transcribe Lab is running.
Use **Quit local interface** on the page when finished. Existing file-based
commands continue to work exactly as before.

Browser playback depends on the media codecs supported by the browser. If a
file cannot play in the preview control, its waveform and transcription may
still work because those use FFmpeg rather than the browser decoder.

## Fast updates

After version 1.1.0 is installed, get future project updates with:

```bash
transcribe --update
```

This downloads and validates only the latest small `transcribe` script. It
does **not** reinstall Homebrew, Python, FFmpeg, `pipx`, MLX Whisper, or any
downloaded model, so an update should be much faster than first-time setup.
Your existing model cache and transcripts remain untouched.

If you installed an older version that says `unrecognized arguments: --update`,
run the one-command setup once more. The installer checks what is already on
the Mac and skips Homebrew, Python, FFmpeg, `pipx`, and MLX Whisper when they
are present; it replaces only the project command. After that one-time upgrade,
use `transcribe --update` for future releases.

## Demo

Run `transcribe --help`, then transcribe a file directly from Terminal:

![Transcribe command-line help and a completed local transcription](docs/images/transcribe-terminal-demo.png)

Open the generated TXT file to read the transcript:

![Generated transcript opened as a text file](docs/images/transcript-output-demo.png)

Drag a voice note from Finder into Terminal, transcribe it, and open the saved
TXT result:

![Finder drag-and-drop transcription workflow with the generated transcript](docs/images/finder-drag-and-drop-demo.png)

## Privacy

Transcription and translation to English run on your Mac. Recordings
are not sent to a hosted transcription API by this project. The selected model
is downloaded from Hugging Face on first use and cached locally, so the first
run can take longer and requires internet access. Later transcription can run
from the local model cache.

## Requirements

- macOS 14 or newer on an Apple Silicon Mac (M1 or newer)
- An internet connection for setup and the first model download
- Enough free space for dependencies and roughly 500 MB for the default model

The installer handles Python, [Homebrew](https://brew.sh/), FFmpeg, `pipx`, and
MLX Whisper. Intel Macs are not supported. If Terminal is running through
Rosetta, the installer stops and explains how to continue natively.

## Start transcribing

```bash
transcribe "/path/to/recording.mp4"
```

English and plain TXT are the defaults. The result is saved beside the
recording:

```text
recording.mp4
recording_transcript.txt
```

Dots inside the original basename are changed to hyphens in the output name.
For example, `voice.note.09.38.opus` produces
`voice-note-09-38_transcript.txt`. The source file is never renamed.

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

## Transcribe only part of a recording

Select a range visually in Transcribe Lab, or provide start and end times in
seconds from Terminal:

```bash
transcribe "/path/to/interview.wav" --start-at 222 --end-at 491 --format srt
```

This creates a separately named result such as
`interview_clip-222-to-491_transcript.srt`; the source media is unchanged.
Both values are required, the start must be zero or greater, and the end must
be later than the start.

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
| TXT | Readable plain transcript; the default |
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

### Supported languages

All languages below can be selected for transcription. Every non-English
language can also be used with `--translate-to en`. Accuracy varies by language,
accent, recording quality, background sound, and model size.

| Language | Code | Language | Code | Language | Code |
| --- | --- | --- | --- | --- | --- |
| Afrikaans | `af` | Albanian | `sq` | Amharic | `am` |
| Arabic | `ar` | Armenian | `hy` | Assamese | `as` |
| Azerbaijani | `az` | Bashkir | `ba` | Basque | `eu` |
| Belarusian | `be` | Bengali | `bn` | Bosnian | `bs` |
| Breton | `br` | Bulgarian | `bg` | Cantonese | `yue` |
| Catalan | `ca` | Chinese | `zh` | Croatian | `hr` |
| Czech | `cs` | Danish | `da` | Dutch | `nl` |
| English | `en` | Estonian | `et` | Faroese | `fo` |
| Finnish | `fi` | French | `fr` | Galician | `gl` |
| Georgian | `ka` | German | `de` | Greek | `el` |
| Gujarati | `gu` | Haitian Creole | `ht` | Hausa | `ha` |
| Hawaiian | `haw` | Hebrew | `he` | Hindi | `hi` |
| Hungarian | `hu` | Icelandic | `is` | Indonesian | `id` |
| Italian | `it` | Japanese | `ja` | Javanese | `jw` |
| Kannada | `kn` | Kazakh | `kk` | Khmer | `km` |
| Korean | `ko` | Lao | `lo` | Latin | `la` |
| Latvian | `lv` | Lingala | `ln` | Lithuanian | `lt` |
| Luxembourgish | `lb` | Macedonian | `mk` | Malagasy | `mg` |
| Malay | `ms` | Malayalam | `ml` | Maltese | `mt` |
| Maori | `mi` | Marathi | `mr` | Mongolian | `mn` |
| Myanmar | `my` | Nepali | `ne` | Norwegian | `no` |
| Nynorsk | `nn` | Occitan | `oc` | Pashto | `ps` |
| Persian | `fa` | Polish | `pl` | Portuguese | `pt` |
| Punjabi | `pa` | Romanian | `ro` | Russian | `ru` |
| Sanskrit | `sa` | Serbian | `sr` | Shona | `sn` |
| Sindhi | `sd` | Sinhala | `si` | Slovak | `sk` |
| Slovenian | `sl` | Somali | `so` | Spanish | `es` |
| Sundanese | `su` | Swahili | `sw` | Swedish | `sv` |
| Tagalog | `tl` | Tajik | `tg` | Tamil | `ta` |
| Tatar | `tt` | Telugu | `te` | Thai | `th` |
| Tibetan | `bo` | Turkish | `tr` | Turkmen | `tk` |
| Ukrainian | `uk` | Urdu | `ur` | Uzbek | `uz` |
| Vietnamese | `vi` | Welsh | `cy` | Yiddish | `yi` |
| Yoruba | `yo` |  |  |  |  |

## Translate speech to English

Whisper can translate supported non-English speech into English. The interface
includes Chinese, Spanish, Korean, Portuguese, French, Arabic, Hindi, Japanese,
German, Russian, Turkish, Yoruba, Hausa, Swahili, and many more languages.

Set the source language and add `--translate-to en`. For a movie, choose SRT to
keep subtitle timestamps:

```bash
transcribe "/path/to/spanish-movie.mp4" \
  --language es \
  --translate-to en \
  --format srt
```

The English subtitle is saved beside the movie:

```text
spanish-movie.mp4
spanish-movie_english_translation.srt
```

The same command works with other supported language codes:

```bash
transcribe "/path/to/chinese-audio.m4a" --language zh --translate-to en --format txt
transcribe "/path/to/korean-video.mov" --language ko --translate-to en --format srt
transcribe "/path/to/portuguese-audio.mp3" --language pt --translate-to en --format txt
transcribe "/path/to/turkish-movie.mp4" --language tr --translate-to en --format srt
```

Let Whisper detect the source language when you do not know it:

```bash
transcribe "/path/to/recording.m4a" --auto-language --translate-to en --format txt
```

For an English plain-text translation of French speech:

```bash
transcribe "/path/to/french-audio.m4a" \
  --language fr \
  --translate-to en \
  --format txt
```

Translation is one-way: supported speech becomes English text or English
subtitles. It does not translate English speech into other languages or create
dubbed audio. The original recording is never modified. Music,
background noise, overlapping dialogue, and unclear speech can reduce subtitle
accuracy, so review important results against the movie.

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

For translation, keep the multilingual default model or another multilingual
Whisper model. Do not use a `.en`-only model. Whisper's `turbo` model is aimed
at transcription and is not recommended for translation.

## Command-line options

```text
usage: transcribe [-h] [--out-dir OUT_DIR]
                  [--format {txt,srt,vtt,tsv,json,all}]
                  [--language LANGUAGE] [--auto-language]
                  [--start-at START_AT] [--end-at END_AT]
                  [--translate-to {en}] [--update] [--ui] [--guided]
                  [--version]
                  [--model MODEL] [--whisper-bin WHISPER_BIN] [--verbose]
                  [input]

positional arguments:
  input                 Path to an audio or video file

options:
  -h, --help            Show help and exit
  --out-dir OUT_DIR     Folder for the transcript; defaults to input folder
  --format FORMAT       txt, srt, vtt, tsv, json, or all; defaults to txt
  --language LANGUAGE   Spoken language code; defaults to en
  --auto-language       Let Whisper detect the spoken language
  --start-at SECONDS    Start time for a selected media range
  --end-at SECONDS      End time for a selected media range
  --translate-to en     Translate supported non-English speech into English
  --update              Update the command without reinstalling dependencies
  --ui                  Open the Transcribe Lab interface in your browser
  --guided              Start an interactive guided Terminal session
  --version             Show the installed transcribe version
  --model MODEL         Hugging Face model name or local model path
  --whisper-bin PATH    mlx_whisper executable name or explicit path
  --verbose             Show detailed MLX Whisper arguments and segments
```

Normal runs show transcription progress without dumping MLX Whisper's internal
argument dictionary or every segment to Terminal. Add `--verbose` when that
detailed diagnostic output is useful.

`MLX_WHISPER_BIN` can set a default executable name or path. A command-line
option overrides the environment variable. The tool searches `PATH` first and
also recognizes the standard `~/Library/Python/*/bin` location used by older
`pip install --user` setups on macOS.

## Troubleshooting

### `command not found: transcribe`

Open a new Terminal window first. If the command is still unavailable, rerun
the one-command setup; it safely skips tools that are already installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Abdussalam-Mujeeb-ur-rahman/transcribe/main/install.sh)" && exec zsh -l
```

### `mlx_whisper was not found`

Rerun the one-command setup. It checks `pipx` and MLX Whisper independently,
then repairs only the missing part:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Abdussalam-Mujeeb-ur-rahman/transcribe/main/install.sh)" && exec zsh -l
```

### The media file cannot be decoded

Install or update FFmpeg and verify the source plays normally:

```bash
brew install ffmpeg
ffprobe "/path/to/recording.mp4"
```

### The first run is slow

The default model is probably downloading. Allow roughly 500 MB of free space;
download time depends on your connection. Later runs reuse the cache, although
larger models still take longer to download and transcribe.

The one-command setup itself can also take 20–30 minutes or longer on a slow
connection because Homebrew, Python tools, MLX Whisper, and the first model may
need to be downloaded. This is a first-time cost. Later use reuses those files,
and `transcribe --update` does not download them again.

### The transcript is inaccurate

Specify the language, try a larger model, and use the clearest recording
available. Names, specialist terms, accents, noise, low volume, music, and
overlapping speakers can reduce accuracy.

Whisper output is probabilistic and can omit, mishear, or invent words. Review
important transcripts against the original recording. This tool does not
identify speakers and should not be treated as a certified or legal
transcription service.

## Development and validation

The automated tests use Python's standard library and do not run a model:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile transcribe_media.py tests/*.py
```

Recordings, generated transcripts, caches, secrets, and local environments are
excluded by `.gitignore`.

## Future direction

An npm wrapper may eventually make command discovery familiar to JavaScript
users, but it would still depend on Python, MLX Whisper, and FFmpeg. The first
release intentionally stays Python-only.

## License

[MIT](LICENSE)
