from .users_store import load_users


def run_users(cmd, args, state):
    if cmd == 'users':
        users = load_users()
        lines = []
        for name, info in users.get('users', {}).items():
            admin = 'yes' if info.get('admin') else 'no'
            lines.append(f"{name:<12} group={info.get('group','users'):<10} admin={admin}")
        return '\n'.join(lines)
    if cmd == 'groups':
        users = load_users()
        lines = []
        for group, members in users.get('groups', {}).items():
            lines.append(f"{group}: {', '.join(members)}")
        return '\n'.join(lines)
    return None
