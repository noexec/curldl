#!/bin/sh
set -e

script_dir=${0%/*}
[ "${script_dir}" != "$0" ] || script_dir=.
script_name=${0##*/}
venv_dir="${script_dir}/venv"

python="python3"                # non-venv and venv interpreter name
pip="pip --require-virtualenv"  # used only in venv
package="curldl"


error()
{
    echo "$@" 1>&2
    exit 1
}

activate_venv()
{
    if [ -d "${venv_dir}"/bin ]; then
        . "${venv_dir}"/bin/activate
    else
        . "${venv_dir}"/Scripts/activate
    fi
}


if [ $# = 0 ]; then
    error "${script_name} install-venv | upgrade-venv | downgrade-venv | <command> <args>..."
fi

if [ -e "${venv_dir}" ]; then
    activate_venv
elif [ "$1" != "install-venv" ]; then
    error "virtualenv environment not found at ${venv_dir}"
fi


export PYTHONDONTWRITEBYTECODE=1

export PYTHONDEVMODE=1
# export PYTHONTRACEMALLOC=20

export PYTHONIOENCODING=utf-8
# export PYTHONWARNDEFAULTENCODING=1

if [ "$1" = "install-venv" ]; then
    echo "Installing virtualenv..."
    if [ -e "${venv_dir}" ] || [ -n "${VIRTUAL_ENV}" ]; then
        error "virtualenv is enabled or venv directory present"
    fi
    if ! ${python} -m ensurepip --version 1>/dev/null 2>&1; then
        error "ensurepip is not available, run: sudo apt install python3-venv"
    fi

    python_platform=$(${python} -c 'import sys; print(sys.platform)')
    if [ "${python_platform}" != "win32" ] && ! curl-config --version 1>/dev/null 2>&1; then
        # NOTE: curl-config is not required if PyPI has native PycURL builds
        error "curl-config is not available, run: sudo apt install libcurl4-openssl-dev"
    fi

    python_version=$(${python} -c 'import sys; print(sys.version.split()[0])')
    ${python} -m venv --symlinks --prompt "venv/${python_version}" "${venv_dir}"
    activate_venv

    # venv --upgrade-deps is available from Python 3.9.0
    ${python} -m pip --require-virtualenv install -U pip setuptools

    ${pip} install --use-pep517 "${script_dir}[test,dev,doc]"
    ${pip} uninstall -y ${package}
    ${pip} install -e "${script_dir}"
    ${pip} check
    exit
fi


if [ "$1" = "downgrade-venv" ]; then
    ${pip} install --use-pep517 --force-reinstall "${script_dir}[minimal]"
    ${pip} uninstall -y ${package}
    ${pip} install -e "${script_dir}"
    ${pip} check
    exit
fi


if [ "$1" = "upgrade-venv" ]; then
    echo "Upgrading virtualenv..."
    pip-review --require-virtualenv --auto
    ${pip} check
    exit
fi


exec "$@"
