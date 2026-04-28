from pathlib import Path
from .config import ROOT, PERMS_FILE
from .storage import load_json, save_json


def rel_key(path):
    path = Path(path).resolve()
    if path == ROOT.resolve():
        return '.'
    return str(path.relative_to(ROOT.resolve())).replace('\\', '/')


def default_meta(path, owner='admin', group='root'):
    return {'owner': owner, 'group': group, 'mode': '755' if Path(path).is_dir() else '644'}


def load_perms():
    data = load_json(PERMS_FILE, {'items': {}})
    data.setdefault('items', {})
    return data


def save_perms(data):
    save_json(PERMS_FILE, data)


def ensure_meta(path, owner='admin', group='root'):
    data = load_perms()
    key = rel_key(path)
    if key not in data['items']:
        data['items'][key] = default_meta(path, owner, group)
        save_perms(data)
    return data['items'][key]


def set_meta(path, meta):
    data = load_perms()
    data.setdefault('items', {})[rel_key(path)] = meta
    save_perms(data)


def delete_meta(path):
    data = load_perms()
    key = rel_key(path)
    for k in list(data.get('items', {})):
        if k == key or k.startswith(key + '/'):
            data['items'].pop(k, None)
    save_perms(data)


def mode_to_rwx(mode):
    out = ''
    for d in str(mode).zfill(3)[-3:]:
        n = int(d)
        out += 'r' if n & 4 else '-'
        out += 'w' if n & 2 else '-'
        out += 'x' if n & 1 else '-'
    return out


def is_admin(state, user_info_func):
    info = user_info_func(state.username) or {}
    return state.sudo or bool(info.get('admin'))


def has_perm(state, path, perm, user_info_func, user_groups_func):
    if is_admin(state, user_info_func):
        return True
    path = Path(path).resolve()
    meta = ensure_meta(path)
    mode = str(meta.get('mode', '755' if path.is_dir() else '644')).zfill(3)[-3:]
    if state.username == meta.get('owner'):
        digit = int(mode[0])
    elif meta.get('group') in user_groups_func(state.username):
        digit = int(mode[1])
    else:
        digit = int(mode[2])
    return bool(digit & {'r': 4, 'w': 2, 'x': 1}[perm])


def require_perm(state, path, perm, user_info_func, user_groups_func):
    if not has_perm(state, path, perm, user_info_func, user_groups_func):
        raise PermissionError(f"permiso '{perm}' denegado en {rel_key(path)}")
