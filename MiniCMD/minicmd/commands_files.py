from .fs import safe_path, cd as fs_cd
from .permissions import ensure_meta, set_meta, delete_meta, mode_to_rwx, require_perm, is_admin


def run_files(cmd, args, state, user_info, user_groups):
    if cmd == 'cd':
        return fs_cd(state, args[0] if args else '/system')
    if cmd == 'ls':
        return cmd_ls(state, args, user_info, user_groups)
    if cmd == 'mkdir':
        return cmd_mkdir(state, args, user_info, user_groups)
    if cmd == 'touch':
        return cmd_touch(state, args, user_info, user_groups)
    if cmd == 'cat':
        return cmd_cat(state, args, user_info, user_groups)
    if cmd == 'write':
        return cmd_write(state, args, user_info, user_groups, False)
    if cmd == 'append':
        return cmd_write(state, args, user_info, user_groups, True)
    if cmd == 'rm':
        return cmd_rm(state, args, user_info, user_groups)
    if cmd == 'rmdir':
        return cmd_rmdir(state, args, user_info, user_groups)
    if cmd == 'chmod':
        return cmd_chmod(state, args, user_info)
    if cmd == 'chown':
        return cmd_chown(state, args, user_info)
    return None


def cmd_ls(state, args, user_info, user_groups):
    long = False
    path_arg = '.'
    for a in args:
        if a == '-l':
            long = True
        else:
            path_arg = a
    target = safe_path(state, path_arg)
    require_perm(state, target, 'r', user_info, user_groups)
    if target.is_file():
        items = [target]
    else:
        require_perm(state, target, 'x', user_info, user_groups)
        items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    lines = []
    for item in items:
        meta = ensure_meta(item)
        if long:
            t = 'd' if item.is_dir() else '-'
            size = item.stat().st_size if item.is_file() else 0
            lines.append(f"{t}{mode_to_rwx(meta.get('mode'))} {meta.get('owner','admin'):<10} {meta.get('group','root'):<10} {size:>8} {item.name}")
        else:
            lines.append(item.name + ('/' if item.is_dir() else ''))
    return '\n'.join(lines) if lines else '(vacio)'


def cmd_mkdir(state, args, user_info, user_groups):
    if len(args) != 1:
        return 'Uso: mkdir <carpeta>'
    parent = safe_path(state)
    require_perm(state, parent, 'w', user_info, user_groups)
    require_perm(state, parent, 'x', user_info, user_groups)
    target = safe_path(state, args[0])
    target.mkdir(parents=False, exist_ok=False)
    group = (user_info(state.username) or {}).get('group', 'users')
    set_meta(target, {'owner': state.username, 'group': group, 'mode': '755'})
    return f'Carpeta creada: {args[0]}'


def cmd_touch(state, args, user_info, user_groups):
    if len(args) != 1:
        return 'Uso: touch <archivo>'
    parent = safe_path(state)
    require_perm(state, parent, 'w', user_info, user_groups)
    target = safe_path(state, args[0])
    target.touch(exist_ok=True)
    ensure_meta(target, state.username, (user_info(state.username) or {}).get('group', 'users'))
    return f'Archivo creado: {args[0]}'
