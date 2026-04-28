from .apt_manager import install_package, list_packages


def run_apt(cmd, args, state):
    if cmd == 'apt':
        if args and args[0] == 'list':
            return list_packages()
        return 'Uso: apt list'

    if cmd != 'sudo':
        return None

    if len(args) == 2 and args[0] == 'apt' and args[1] == 'list':
        return list_packages()

    if len(args) >= 3 and args[0] == 'apt' and args[1] == 'install':
        if not state.sudo:
            return 'Primero activa sudo: sudo 1234'
        lines = []
        for package_name in args[2:]:
            ok, msg = install_package(package_name)
            lines.append(msg)
        return '\n'.join(lines)

    return None
