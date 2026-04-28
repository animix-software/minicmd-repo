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


def cmd_cat(state, args, user_info, user_groups):
    if len(args) != 1:
        return 'Uso: cat <archivo>'
    target = safe_path(state, args[0])
    if not target.is_file():
        return 'No es archivo.'
    require_perm(state, target, 'r', user_info, user_groups)
    return target.read_text(encoding='utf-8', errors='replace')


def cmd_write(state, args, user_info, user_groups, append=False):
    if len(args) < 2:
        return 'Uso: append <archivo> <texto>' if append else 'Uso: write <archivo> <texto>'
    target = safe_path(state, args[0])
    parent = target.parent
    if target.exists():
        require_perm(state, target, 'w', user_info, user_groups)
    else:
        require_perm(state, parent, 'w', user_info, user_groups)
        require_perm(state, parent, 'x', user_info, user_groups)
    text = ' '.join(args[1:])
    if append:
        with target.open('a', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        target.write_text(text, encoding='utf-8')
    ensure_meta(target, state.username, (user_info(state.username) or {}).get('group', 'users'))
    return 'OK'


def cmd_rm(state, args, user_info, user_groups):
    if len(args) != 1:
        return 'Uso: rm <archivo>'
    target = safe_path(state, args[0])
    if not target.is_file():
        return 'No es archivo.'
    require_perm(state, target.parent, 'w', user_info, user_groups)
    target.unlink()
    delete_meta(target)
    return f'Archivo eliminado: {args[0]}'


def cmd_rmdir(state, args, user_info, user_groups):
    if len(args) != 1:
        return 'Uso: rmdir <carpeta>'
    target = safe_path(state, args[0])
    if not target.is_dir():
        return 'No es carpeta.'
    require_perm(state, target.parent, 'w', user_info, user_groups)
    target.rmdir()
    delete_meta(target)
    return f'Carpeta eliminada: {args[0]}'


def cmd_chmod(state, args, user_info):
    if len(args) != 2 or not args[0].isdigit() or len(args[0]) != 3:
        return 'Uso: chmod 755 <ruta>'
    target = safe_path(state, args[1])
    meta = ensure_meta(target)
    if not (is_admin(state, user_info) or meta.get('owner') == state.username):
        return 'Solo el dueño o admin puede usar chmod.'
    meta['mode'] = args[0]
    set_meta(target, meta)
    return f'Modo actualizado: {args[1]} -> {args[0]}'


def cmd_chown(state, args, user_info):
    if len(args) != 2:
        return 'Uso: chown user[:group] <ruta>'
    if not is_admin(state, user_info):
        return 'Solo admin/sudo puede usar chown.'
    target = safe_path(state, args[1])
    meta = ensure_meta(target)
    owner_group = args[0].split(':', 1)
    new_owner = owner_group[0]
    if new_owner and user_info(new_owner) is None:
        return 'Usuario no existe.'
    if new_owner:
        meta['owner'] = new_owner
    if len(owner_group) == 2 and owner_group[1]:
        meta['group'] = owner_group[1]
    set_meta(target, meta)
    return f'Dueño actualizado: {args[1]}'
