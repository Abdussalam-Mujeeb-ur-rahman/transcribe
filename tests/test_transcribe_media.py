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

    def test_translation_output_filename_generation(self) -> None:
        name = transcribe_media.output_name_for(
            Path("turkish.movie.mp4"), translated_to_english=True
        )
        self.assertEqual(name, "turkish-movie_english_translation")

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

    def test_interface_flags_do_not_require_an_input_file(self) -> None:
        ui_args = transcribe_media.parse_args(["--ui"])
        guided_args = transcribe_media.parse_args(["--guided"])

        self.assertTrue(ui_args.ui)
        self.assertTrue(guided_args.guided)
        self.assertIsNone(ui_args.input)

    def test_all_formats_reveals_the_text_result(self) -> None:
        result = transcribe_media.expected_output_path(
            Path("voice.opus"), Path("/tmp/results"), "all", False
        )
        self.assertEqual(result, Path("/tmp/results/voice_transcript.txt"))

    def test_native_file_picker_returns_selected_path(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["osascript"], returncode=0, stdout="/tmp/movie.mp4\n"
        )
        with mock.patch("transcribe_media.subprocess.run", return_value=completed):
            result = transcribe_media.choose_with_macos("Choose a file")

        self.assertEqual(result, Path("/tmp/movie.mp4"))

    def test_interface_cancel_stops_the_complete_process_group(self) -> None:
        job = transcribe_media.LocalJob()
        process = mock.Mock()
        process.poll.return_value = None
        process.pid = 9876
        job.process = process

        with mock.patch("transcribe_media.os.killpg") as kill_group:
            cancelled = job.cancel()

        self.assertTrue(cancelled)
        self.assertEqual(job.state, "cancelling")
        kill_group.assert_called_once_with(9876, transcribe_media.signal.SIGTERM)

    def test_no_argument_menu_can_open_guided_mode(self) -> None:
        with mock.patch("builtins.input", return_value="2"), mock.patch(
            "transcribe_media.guided_terminal", return_value=17
        ) as guided:
            result = transcribe_media.launch_menu()

        self.assertEqual(result, 17)
        guided.assert_called_once_with()

    def test_turkish_to_english_uses_whisper_translate_task(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "movie.mp4"
            source.touch()
            executable = root / "mlx_whisper"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)

            with mock.patch("transcribe_media.subprocess.run") as run:
                result = transcribe_media.main(
                    [
                        str(source),
                        "--language",
                        "tr",
                        "--translate-to",
                        "en",
                        "--format",
                        "srt",
                        "--whisper-bin",
                        str(executable),
                    ]
                )

            self.assertEqual(result, 0)
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--task") + 1], "translate")
            self.assertEqual(command[command.index("--language") + 1], "tr")
            self.assertEqual(
                command[command.index("--output-name") + 1],
                "movie_english_translation",
            )

    def test_translation_requires_turkish_source(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "movie.mp4"
            source.touch()
            with mock.patch("transcribe_media.find_executable", return_value="mlx"):
                result = transcribe_media.main(
                    [str(source), "--translate-to", "en"]
                )
        self.assertEqual(result, 2)

    def test_update_replaces_only_installed_script(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            latest = root / "latest.py"
            latest.write_text(
                "#!/usr/bin/env python3\nVERSION = 'test'\ndef main(): pass\n",
                encoding="utf-8",
            )
            install = root / "installed"

            with mock.patch.dict(
                "os.environ",
                {
                    "TRANSCRIBE_INSTALL_DIR": str(install),
                    "TRANSCRIBE_UPDATE_URL": latest.as_uri(),
                },
                clear=False,
            ):
                result = transcribe_media.main(["--update"])

            target = install / "transcribe_media.py"
            self.assertEqual(result, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), latest.read_text())
            self.assertTrue(target.stat().st_mode & 0o100)

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
