from .config import SUDO_PASSWORD
from .fs import prompt_path

HELP = {
    'help': 'Muestra ayuda.',
    'cls': 'Limpia pantalla.',
    'pwd': 'Muestra ruta actual.',
    'whoami': 'Muestra usuario actual.',
    'id': 'Muestra usuario, grupos y sudo.',
    'history': 'Muestra historial.',
    'sudo': 'Uso: sudo 1234 | sudo logout | sudo status',
    'exit': 'Cierra sesion.',
}


def run_system(cmd, args, state, user_info, user_groups):
    if cmd == 'help':
        return '\n'.join(f'{k:<10} {v}' for k, v in HELP.items())
    if cmd == 'cls':
        return '\033[2J\033[H'
    if cmd == 'pwd':
        return prompt_path(state)
    if cmd == 'whoami':
        return state.username
    if cmd == 'id':
        info = user_info(state.username) or {}
        return f"uid={state.username} gid={info.get('group','users')} groups={','.join(sorted(user_groups(state.username)))} sudo={'yes' if state.sudo else 'no'} admin={'yes' if info.get('admin') else 'no'}"
    if cmd == 'history':
        return '\n'.join(f'{i + 1}: {x}' for i, x in enumerate(state.history))
    if cmd == 'exit':
        state.running = False
        return 'Cerrando sesion MiniCMD...'
    if cmd == 'sudo':
        if len(args) == 1 and args[0] == SUDO_PASSWORD:
            state.sudo = True
            return 'Sudo activado.'
        if args and args[0] == 'logout':
            state.sudo = False
            return 'Sudo desactivado.'
        if args and args[0] == 'status':
            return 'Sudo activo.' if state.sudo else 'Sudo inactivo.'
        return 'Uso: sudo 1234 | sudo logout | sudo status'
    return None
