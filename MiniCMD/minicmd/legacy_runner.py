import io
import os
import runpy
import sys
from contextlib import redirect_stdout, redirect_stderr

from .config import COMMADS, ROOT
from .fs import safe_path


def run_legacy(state, cmd, args):
    script = COMMADS / cmd / 'main.py'
    if not script.exists():
        return None
    old_argv = sys.argv[:]
    old_cwd = os.getcwd()
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        current_dir = safe_path(state)
        os.environ['MINICMD_ROOT'] = str(ROOT.resolve())
        os.environ['MINICMD_CWD'] = str(current_dir)
        os.environ['MINICMD_SUDO'] = '1' if state.sudo else '0'
        os.environ['MINICMD_USER'] = state.username
        sys.argv = [str(script)] + args
        os.chdir(str(current_dir))
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                runpy.run_path(str(script), run_name='__main__')
            except SystemExit:
                pass
        out = stdout.getvalue().strip()
        err = stderr.getvalue().strip()
        return out + (('\n' if out else '') + err if err else '')
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
