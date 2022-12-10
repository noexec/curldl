#!/bin/sh
set -e

script_dir=${0%/*}
venv_dir="${script_dir}"/../venv

if ! [ -e "${venv_dir}" ]; then
    echo "venv environment not found at ${venv_dir}"
    exit 1
fi

. "${venv_dir}"/bin/activate
export PYTHONDONTWRITEBYTECODE=1

exec "${venv_dir}"/bin/python "$@"
