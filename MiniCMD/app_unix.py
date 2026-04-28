# MiniCMD/app_unix.py
# Launcher seguro: aplica la capa Unix a app.py en memoria sin romper el archivo principal.
# Ejecuta con: python app_unix.py

from pathlib import Path

APP_PATH = Path(__file__).resolve().parent / "app.py"
source = APP_PATH.read_text(encoding="utf-8")

source = source.replace(
    "import asyncssh\n",
    "import asyncssh\nfrom minicmd.unix_layer import UNIX_BUILTINS, UNIX_HELP, unix_prompt, execute_unix_command\n",
    1,
)

source = source.replace(
    'BUILTINS = {"help", "cls", "sudo", "cd", "pwd", "history", "exit", "ls", "mkdir", "touch", "cat", "write", "append", "rm", "rmdir", "chmod", "chown", "whoami", "id", "useradd", "groupadd", "passwd", "groups", "users"}',
    'BUILTINS = {"help", "cls", "sudo", "cd", "pwd", "history", "exit", "ls", "mkdir", "touch", "cat", "write", "append", "rm", "rmdir", "chmod", "chown", "whoami", "id", "useradd", "groupadd", "passwd", "groups", "users"} | UNIX_BUILTINS',
    1,
)

source = source.replace(
    '    "exit": "Cierra la sesion SSH."\n}\n\n\nclass MiniCMDState:',
    '    "exit": "Cierra la sesion SSH."\n}\nBUILTIN_HELP.update(UNIX_HELP)\n\n\nclass MiniCMDState:',
    1,
)

source = source.replace(
    'def get_prompt(state):\n    if state.cwd:\n        return "/system/" + state.cwd.replace("\\\\", "/")\n    return "/system"\n',
    'def get_prompt(state):\n    return unix_prompt(state, is_admin)\n',
    1,
)

source = source.replace(
    '        if cmd == "pwd":\n            return get_prompt(state).replace("/", "\\\\")\n',
    '        if cmd == "pwd":\n            if state.cwd:\n                return "/system/" + state.cwd.replace("\\\\", "/")\n            return "/system"\n',
    1,
)

source = source.replace(
    '        if cmd == "ls":\n            return ls_command(state, args)\n        if cmd == "cd":',
    '        if cmd == "ls":\n            return ls_command(state, args)\n        if cmd in UNIX_BUILTINS:\n            return execute_unix_command(\n                state, cmd, args,\n                safe_path_from_cwd=safe_path_from_cwd,\n                require_perm=require_perm,\n                ensure_meta=ensure_meta,\n                set_meta=set_meta,\n                delete_meta=delete_meta,\n                user_info=user_info,\n            )\n        if cmd == "cd":',
    1,
)

namespace = {
    "__name__": "__main__",
    "__file__": str(APP_PATH),
    "__package__": None,
}

exec(compile(source, str(APP_PATH), "exec"), namespace)
