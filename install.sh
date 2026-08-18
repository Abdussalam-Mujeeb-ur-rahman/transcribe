#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bin_dir=${HOME}/bin
command_path=${bin_dir}/transcribe
target=${project_dir}/transcribe_media.py

mkdir -p "$bin_dir"

if [ -e "$command_path" ] || [ -L "$command_path" ]; then
    if [ "$(readlink "$command_path" 2>/dev/null || true)" = "$target" ]; then
        echo "Already installed: $command_path"
        exit 0
    fi
    echo "Not replacing existing file: $command_path" >&2
    echo "Move or remove it, then run ./install.sh again." >&2
    exit 1
fi

ln -s "$target" "$command_path"
echo "Installed: $command_path -> $target"
echo "Make sure $bin_dir is in your PATH."
