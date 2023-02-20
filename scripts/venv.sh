#!/bin/sh
set -e

script_dir=${0%/*}
venv_dir="${script_dir}"/../venv

if ! [ -e "${venv_dir}" ]; then
    echo "venv environment not found at ${venv_dir}" 1>&2
    exit 1
fi

if [ $# = 0 ]; then
    echo "$0 <command> <args>..." 1>&2
    exit 1
fi

. "${venv_dir}"/bin/activate
export PYTHONDONTWRITEBYTECODE=1

exec "$@"
