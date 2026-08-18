from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class InstallerTests(unittest.TestCase):
    def test_installs_command_when_dependencies_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            home = root / "home"
            fake_bin = root / "fake-bin"
            home.mkdir()
            fake_bin.mkdir()

            write_executable(
                fake_bin / "python3",
                """#!/bin/bash
if [[ "$1" == "-c" ]]; then
    exit 0
fi
exec /usr/bin/python3 "$@"
""",
            )
            write_executable(
                fake_bin / "ffmpeg",
                "#!/bin/sh\necho 'ffmpeg test version'\n",
            )
            write_executable(fake_bin / "brew", "#!/bin/sh\nexit 0\n")
            write_executable(fake_bin / "pipx", "#!/bin/sh\nexit 0\n")
            write_executable(fake_bin / "mlx_whisper", "#!/bin/sh\nexit 0\n")

            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": str(home),
                    "PATH": f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
                    "TRANSCRIBE_SOURCE_FILE": str(
                        PROJECT_ROOT / "transcribe_media.py"
                    ),
                }
            )

            result = subprocess.run(
                ["/bin/bash", str(PROJECT_ROOT / "install.sh")],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            command = home / ".local/bin/transcribe"
            target = home / ".local/share/transcribe/transcribe_media.py"
            self.assertTrue(command.is_symlink())
            self.assertEqual(command.resolve(), target.resolve())
            self.assertIn("Installation complete.", result.stdout)
            self.assertIn("transcribe --help", result.stdout)

            for shell_file in (home / ".zprofile", home / ".zshrc"):
                contents = shell_file.read_text(encoding="utf-8")
                self.assertEqual(
                    contents.count('export PATH="$HOME/.local/bin:$PATH"'), 1
                )

            subprocess.run(
                ["/bin/bash", str(PROJECT_ROOT / "install.sh")],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertTrue(command.is_symlink())

    def test_installs_only_missing_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            home = root / "home"
            fake_bin = root / "fake-bin"
            brew_log = root / "brew.log"
            home.mkdir()
            fake_bin.mkdir()

            write_executable(
                fake_bin / "brew",
                """#!/usr/bin/python3
import os
import stat
import sys
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] == "shellenv":
    raise SystemExit(0)

if len(sys.argv) > 1 and sys.argv[1] == "install":
    Path(os.environ["BREW_LOG"]).write_text(" ".join(sys.argv[2:]))
    target = Path(__file__).parent
    scripts = {
        "python3": '''#!/bin/bash
if [[ "$1" == "-c" ]]; then exit 0; fi
exec /usr/bin/python3 "$@"
''',
        "ffmpeg": "#!/bin/sh\\necho 'ffmpeg test version'\\n",
        "pipx": '''#!/bin/bash
if [[ "$1" == "--version" ]]; then echo "test"; exit 0; fi
if [[ "$1" == "install" ]]; then
    mkdir -p "$HOME/.local/bin"
    printf '#!/bin/sh\\nexit 0\\n' > "$HOME/.local/bin/mlx_whisper"
    chmod +x "$HOME/.local/bin/mlx_whisper"
fi
exit 0
''',
    }
    for name, content in scripts.items():
        path = target / name
        path.write_text(content)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    raise SystemExit(0)

raise SystemExit(0)
""",
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "BREW_LOG": str(brew_log),
                    "HOME": str(home),
                    "PATH": f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
                    "TRANSCRIBE_SOURCE_FILE": str(
                        PROJECT_ROOT / "transcribe_media.py"
                    ),
                }
            )

            result = subprocess.run(
                ["/bin/bash", str(PROJECT_ROOT / "install.sh")],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )

            installed = brew_log.read_text(encoding="utf-8").split()
            self.assertEqual(installed, ["python", "ffmpeg", "pipx"])
            self.assertTrue((home / ".local/bin/mlx_whisper").is_file())
            self.assertTrue((home / ".local/bin/transcribe").is_symlink())
            self.assertIn("Installing missing dependencies", result.stdout)
            self.assertIn("Installing MLX Whisper", result.stdout)


if __name__ == "__main__":
    unittest.main()
