#!/bin/sh
set -e

script_dir=${0%/*}
venv_dir="${script_dir}"/../venv
src_dir="${script_dir}"/../src

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
export PYTHONPATH="${src_dir}"

export PYTHONDEVMODE=1

export PYTHONIOENCODING=utf-8
# export PYTHONWARNDEFAULTENCODING=1

# pytest-sugar 0.9.6 (adding it to pytest's filterwarnings is too late to disable the warning)
export PYTHONWARNINGS="ignore::DeprecationWarning:pytest_sugar,\
    ignore::DeprecationWarning:prompt_toolkit.application.application"

# export PYTHONTRACEMALLOC=20

exec "$@"
