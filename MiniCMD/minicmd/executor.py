import shlex

from .commands_system import run_system, HELP as SYSTEM_HELP
from .commands_apt import run_apt
from .commands_chat import run_chat
from .commands_files import run_files
from .commands_users import run_users
from .legacy_runner import run_legacy
from .state import MiniCMDState
from .users_store import user_info, user_groups
from .command_detector import normalize_command, detect_command, suggestion

_DEFAULT_STATE = MiniCMDState()


def run(command, state=None):
    if state is None:
        state = _DEFAULT_STATE
    return execute(command, state)


def execute(command, state):
    command = (command or '').strip()
    if not command:
        return ''

    state.history.append(command)
    state.history = state.history[-100:]

    try:
        parts = shlex.split(command)
    except Exception:
        return 'Error: comillas invalidas.'

    if not parts:
        return ''

    cmd = parts[0].lower()
    args = parts[1:]

    cmd, args, original = normalize_command(cmd, args)
    cmd_type = detect_command(cmd)

    if cmd == 'help':
        base = run_system(cmd, args, state, user_info, user_groups)
        return base

    try:
        for handler in (
            lambda: run_chat(cmd, args, state),
            lambda: run_apt(cmd, args, state),
            lambda: run_system(cmd, args, state, user_info, user_groups),
            lambda: run_users(cmd, args, state),
            lambda: run_files(cmd, args, state, user_info, user_groups),
        ):
            result = handler()
            if result is not None:
                return result

        legacy = run_legacy(state, cmd, args)
        if legacy is not None:
            return legacy

        if cmd_type == 'available':
            return f'Comando disponible para instalar: sudo apt install {cmd}'

        return suggestion(original)

    except PermissionError as e:
        return f'Permiso denegado: {e}'
    except Exception as e:
        return f'Error: {e}'
