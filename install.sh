#!/bin/bash
set -Eeuo pipefail

readonly RAW_BASE_URL="https://raw.githubusercontent.com/Abdussalam-Mujeeb-ur-rahman/transcribe/main"
readonly SCRIPT_URL="${RAW_BASE_URL}/transcribe_media.py"
readonly INSTALL_DIR="${TRANSCRIBE_INSTALL_DIR:-${HOME}/.local/share/transcribe}"
readonly BIN_DIR="${TRANSCRIBE_BIN_DIR:-${HOME}/.local/bin}"
readonly TARGET_SCRIPT="${INSTALL_DIR}/transcribe_media.py"
readonly COMMAND_PATH="${BIN_DIR}/transcribe"
TEMPORARY_FILE=""

cleanup() {
    if [[ -n "$TEMPORARY_FILE" && -f "$TEMPORARY_FILE" ]]; then
        rm -f "$TEMPORARY_FILE"
    fi
}

trap cleanup EXIT

info() {
    printf '\n==> %s\n' "$1"
}

fail() {
    printf '\nError: %s\n' "$1" >&2
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

append_line_once() {
    local line="$1"
    local file="$2"

    mkdir -p "$(dirname "$file")"
    touch "$file"
    if ! grep -Fqx "$line" "$file"; then
        printf '\n%s\n' "$line" >> "$file"
    fi
}

refresh_homebrew() {
    local brew_path=""

    if command_exists brew; then
        brew_path="$(command -v brew)"
    elif [[ -x /opt/homebrew/bin/brew ]]; then
        brew_path="/opt/homebrew/bin/brew"
    elif [[ -x /usr/local/bin/brew ]]; then
        brew_path="/usr/local/bin/brew"
    fi

    if [[ -n "$brew_path" ]]; then
        eval "$("$brew_path" shellenv)"
    fi
    hash -r
}

check_platform() {
    [[ "$(uname -s)" == "Darwin" ]] || fail "This installer supports macOS only."
    [[ "$(uname -m)" == "arm64" ]] || fail \
        "Apple silicon is required. If this is an M-series Mac, disable Rosetta for Terminal."

    local macos_version
    local macos_major
    macos_version="$(sw_vers -productVersion)"
    macos_major="${macos_version%%.*}"
    [[ "$macos_major" =~ ^[0-9]+$ ]] || fail "Could not determine the macOS version."
    (( macos_major >= 14 )) || fail "macOS 14 or newer is required."

    printf 'macOS %s on Apple silicon: OK\n' "$macos_version"
}

python_is_compatible() {
    command_exists python3 && python3 -c '
import platform
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) and platform.machine() == "arm64" else 1)
' >/dev/null 2>&1
}

install_homebrew() {
    if command_exists brew; then
        return
    fi

    info "Installing Homebrew"
    command_exists curl || fail "curl is required to install Homebrew."
    printf 'Homebrew may request your macOS password or confirmation.\n'
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    refresh_homebrew
    command_exists brew || fail "Homebrew installation did not make brew available."
    append_line_once 'eval "$(/opt/homebrew/bin/brew shellenv)"' "${HOME}/.zprofile"
}

install_system_dependencies() {
    local missing=""

    python_is_compatible || missing="${missing} python"
    command_exists ffmpeg || missing="${missing} ffmpeg"
    command_exists pipx || missing="${missing} pipx"

    if [[ -z "$missing" ]]; then
        printf 'Python, FFmpeg, and pipx: already available\n'
        return
    fi

    install_homebrew
    refresh_homebrew

    info "Installing missing dependencies:${missing}"
    # Values in $missing are fixed formula names selected above.
    brew install $missing
    refresh_homebrew

    python_is_compatible || fail "Native Python 3.10 or newer is unavailable after installation."
    command_exists ffmpeg || fail "FFmpeg is unavailable after installation."
    command_exists pipx || fail "pipx is unavailable after installation."
}

configure_user_path() {
    local path_line='export PATH="$HOME/.local/bin:$PATH"'

    mkdir -p "$BIN_DIR"
    pipx ensurepath >/dev/null 2>&1 || true
    append_line_once "$path_line" "${HOME}/.zprofile"
    append_line_once "$path_line" "${HOME}/.zshrc"
    export PATH="${BIN_DIR}:${PATH}"
}

find_mlx_whisper() {
    local candidate=""

    if command_exists mlx_whisper; then
        candidate="$(command -v mlx_whisper)"
        if "$candidate" --help >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    fi

    if [[ -x "${HOME}/.local/bin/mlx_whisper" ]]; then
        candidate="${HOME}/.local/bin/mlx_whisper"
        if "$candidate" --help >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    fi

    return 1
}

install_mlx_whisper() {
    local mlx_path=""

    configure_user_path
    if mlx_path="$(find_mlx_whisper)"; then
        printf 'MLX Whisper: already available at %s\n' "$mlx_path"
        return
    fi

    info "Installing MLX Whisper"
    printf 'This dependency installation can take several minutes.\n'
    pipx install --force --python "$(command -v python3)" mlx-whisper

    configure_user_path
    mlx_path="$(find_mlx_whisper)" || fail "MLX Whisper is unavailable after installation."
    printf 'MLX Whisper installed at %s\n' "$mlx_path"
}

download_transcribe() {
    local source_file=""

    info "Installing the transcribe command"
    mkdir -p "$INSTALL_DIR" "$BIN_DIR"

    if [[ -n "${TRANSCRIBE_SOURCE_FILE:-}" ]]; then
        source_file="$TRANSCRIBE_SOURCE_FILE"
        [[ -f "$source_file" ]] || fail "TRANSCRIBE_SOURCE_FILE does not exist."
    else
        command_exists curl || fail "curl is required to download transcribe."
        TEMPORARY_FILE="$(mktemp "${TMPDIR:-/tmp}/transcribe-media.XXXXXX")"
        curl -fsSL "$SCRIPT_URL" -o "$TEMPORARY_FILE"
        source_file="$TEMPORARY_FILE"
    fi

    python3 -m py_compile "$source_file"
    install -m 0755 "$source_file" "$TARGET_SCRIPT"

    if [[ -e "$COMMAND_PATH" || -L "$COMMAND_PATH" ]]; then
        if [[ -L "$COMMAND_PATH" && "$(readlink "$COMMAND_PATH")" == "$TARGET_SCRIPT" ]]; then
            return
        fi

        local backup_path
        backup_path="${COMMAND_PATH}.backup.$(date +%Y%m%d%H%M%S).$$"
        mv "$COMMAND_PATH" "$backup_path"
        printf 'Preserved the previous command as %s\n' "$backup_path"
    fi

    ln -s "$TARGET_SCRIPT" "$COMMAND_PATH"
}

verify_installation() {
    local mlx_path
    mlx_path="$(find_mlx_whisper)" || fail "MLX Whisper verification failed."

    info "Verifying installation"
    if command_exists brew; then
        brew --version | sed -n '1p'
    fi
    python3 -c 'import platform; print(f"Python {platform.python_version()} ({platform.machine()})")'
    ffmpeg -version | sed -n '1p'
    printf 'pipx %s\n' "$(pipx --version)"
    "$mlx_path" --help >/dev/null
    "$COMMAND_PATH" --help >/dev/null

    printf '\nInstallation complete.\n'
    printf 'Command: %s\n' "$COMMAND_PATH"
    printf 'Try: transcribe --help\n'
    printf 'Then: type transcribe, add a space, and drag an audio or video file into Terminal.\n\n'
    "$COMMAND_PATH" --help | sed -n '1,12p'
}

main() {
    info "Checking this Mac"
    check_platform
    refresh_homebrew
    install_system_dependencies
    configure_user_path
    install_mlx_whisper
    download_transcribe
    verify_installation
}

main "$@"
