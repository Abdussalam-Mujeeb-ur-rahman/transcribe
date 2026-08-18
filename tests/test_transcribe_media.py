from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import transcribe_media


class TranscribeMediaTests(unittest.TestCase):
    def test_missing_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "missing.opus"
            with mock.patch("sys.stderr") as stderr:
                result = transcribe_media.main([str(missing)])

        self.assertEqual(result, 2)
        self.assertIn("Input file not found", str(stderr.write.call_args_list))

    def test_output_filename_generation(self) -> None:
        name = transcribe_media.output_name_for(Path("meeting.mp4"))
        self.assertEqual(name, "meeting_transcript")

    def test_dots_in_filename_are_normalized_safely(self) -> None:
        name = transcribe_media.output_name_for(Path("voice.note.09.38.19.opus"))
        self.assertEqual(name, "voice-note-09-38-19_transcript")

    def test_help_uses_short_command_name(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "transcribe_media.py"), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("usage: transcribe", result.stdout)
        self.assertNotIn("usage: transcribe_media.py", result.stdout)

    def test_verbose_flag_is_opt_in(self) -> None:
        default_args = transcribe_media.parse_args(["sample.wav"])
        verbose_args = transcribe_media.parse_args(["sample.wav", "--verbose"])

        self.assertFalse(default_args.verbose)
        self.assertTrue(verbose_args.verbose)

    def test_custom_output_directory_is_created_and_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "sample.audio.wav"
            source.touch()
            executable = root / "mlx_whisper"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)
            output = root / "nested" / "transcripts"

            with mock.patch("transcribe_media.subprocess.run") as run:
                result = transcribe_media.main(
                    [
                        str(source),
                        "--out-dir",
                        str(output),
                        "--whisper-bin",
                        str(executable),
                    ]
                )

            self.assertEqual(result, 0)
            self.assertTrue(output.is_dir())
            command = run.call_args.args[0]
            actual_output = Path(command[command.index("--output-dir") + 1])
            self.assertEqual(actual_output, output.resolve())
            self.assertEqual(
                command[command.index("--output-name") + 1],
                "sample-audio_transcript",
            )
            self.assertEqual(command[command.index("--verbose") + 1], "False")


if __name__ == "__main__":
    unittest.main()
