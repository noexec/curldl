#!/bin/sh
set -e

script_dir=${0%/*}
[ "${script_dir}" != "$0" ] || script_dir=.

project_dir="${script_dir}/../.."
code_roots="src tests"

cd "${project_dir}"
bandit -c pyproject.toml -r ${code_roots} "$@"
