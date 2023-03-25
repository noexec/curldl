#!/bin/sh
set -e

script_dir=${0%/*}
script_name=${0##*/}
venv_dir="${script_dir}"/venv

python="python3"
package="curldl"


error()
{
    echo "$@" 1>&2
    exit 1
}


if [ $# = 0 ]; then
    error "${script_name} install-venv | upgrade-venv | <command> <args>..."
fi

if [ -e "${venv_dir}" ]; then
    . "${venv_dir}"/bin/activate
elif [ "$1" != "install-venv" ]; then
    error "virtualenv environment not found at ${venv_dir}"
fi


export PYTHONDONTWRITEBYTECODE=1

export PYTHONDEVMODE=1
# export PYTHONTRACEMALLOC=20

export PYTHONIOENCODING=utf-8
# export PYTHONWARNDEFAULTENCODING=1

# pytest-sugar 0.9.6 (adding it to pytest's filterwarnings is too late to disable the warning)
export PYTHONWARNINGS="ignore::DeprecationWarning:pytest_sugar,\
    ignore::DeprecationWarning:prompt_toolkit.application.application,\
    ignore::DeprecationWarning:pip._vendor.packaging.version,\
    ignore::DeprecationWarning:pip._vendor.packaging.specifiers"

if [ "$1" = "install-venv" ]; then
    echo "Installing virtualenv..."
    if [ -e "${venv_dir}" ] || [ -n "${VIRTUAL_ENV}" ]; then
        error "virtualenv is enabled or venv directory present"
    fi
    if ! ${python} -m ensurepip --version 1>/dev/null 2>&1; then
        error "ensurepip is not available, run: sudo apt install python3-venv"
    fi

    if ! curl-config --version 1>/dev/null 2>&1; then
        error "curl-config is not available, run: sudo apt install libcurl4-openssl-dev"
    fi

    python_version=$(${python} -V)
    upgrade_deps=
    if ${python} -c 'import sys; sys.exit(not sys.version_info >= (3, 9))'; then
        upgrade_deps=--upgrade-deps
    fi

    ${python} -m venv --prompt "venv/${python_version#* }" ${upgrade_deps} "${venv_dir}"
    . "${venv_dir}"/bin/activate

    pip install --use-pep517 --require-virtualenv "${script_dir}" "${script_dir}[test]" "${script_dir}[environment]"
    pip uninstall -y --require-virtualenv ${package}
    pip install -e "${script_dir}" --require-virtualenv
    exit
fi


if [ "$1" = "upgrade-venv" ]; then
    echo "Upgrading virtualenv..."
    exec pip-review --auto --require-virtualenv
fi


exec "$@"
