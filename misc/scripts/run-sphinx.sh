#!/bin/sh
set -e

script_dir=${0%/*}
[ "${script_dir}" != "$0" ] || script_dir=.

project_dir="${script_dir}/../.."
docs_root="docs"
build_docs_root="build/docs"
doctrees_root="build/tests/doctrees"

cd "${project_dir}"
sphinx-build -vW -d "${doctrees_root}" "${docs_root}" "${build_docs_root}" "$@"
