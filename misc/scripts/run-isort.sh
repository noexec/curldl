#!/bin/sh
set -e

script_dir=${0%/*}
[ "${script_dir}" != "$0" ] || script_dir=.

project_dir="${script_dir}/../.."
code_roots="src tests docs"

cd "${project_dir}"
python3 -m isort ${code_roots} "$@"
