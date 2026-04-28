import asyncio
import os
import sys
import json
import time
import shlex
import shutil
import hashlib
import urllib.request
import urllib.error
import runpy
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import asyncssh


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

ROOT = BASE_DIR / "system"
COMMADS = BASE_DIR / "commads"
LOGS = BASE_DIR / "logs"
DB_FILE = COMMADS / ".installed.json"
HOST_KEY_FILE = BASE_DIR / "minicmd_ssh_host_key"

ROOT.mkdir(exist_ok=True)
COMMADS.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)

SSH_HOST = os.environ.get("MINICMD_SSH_HOST", "0.0.0.0")
SSH_PORT = int(os.environ.get("MINICMD_SSH_PORT", "2222"))
SSH_USER = os.environ.get("MINICMD_SSH_USER", "admin")
SSH_PASSWORD = os.environ.get("MINICMD_SSH_PASSWORD", "minicmd123")
SUDO_PASSWORD = os.environ.get("MINICMD_SUDO_PASSWORD", "1234")
GITHUB_RAW_BASE = os.environ.get(
    "MINICMD_REPO_RAW",
    "https://raw.githubusercontent.com/animix-software/minicmd-repo/main/commads"
)

BUILTINS = {"help", "cls", "sudo", "cd", "pwd", "history", "exit"}

BUILTIN_HELP = {
    "help": "Muestra esta ayuda por paginas. Uso: help [pagina]",
    "cls": "Limpia la pantalla SSH.",
    "sudo": "Admin e instalador GitHub.",
    "cd": "Cambia de carpeta dentro de /system.",
    "pwd": "Muestra la ruta actual.",
    "history": "Muestra historial de comandos.",
    "exit": "Cierra la sesion SSH."
}


class MiniCMDState:
    def __init__(self):
        self.cwd = ""
        self.sudo = False
        self.history = []
        self.running = True


def now_date():
    return time.strftime("%Y-%m-%d")


def load_db():
    if not DB_FILE.exists():
        return {"installed": {}}
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"installed": {}}


def save_db(db):
    DB_FILE.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")


def log_event(text):
    with open(LOGS / "minicmd.log", "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


def valid_name(name):
    if not name or len(name) > 64:
        return False
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return all(c in allowed for c in name)


def download_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "MiniCMD-Installer"})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read(500_001)
        if len(data) > 500_000:
            raise RuntimeError("Archivo demasiado grande")
        return data.decode("utf-8")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repo_url(path):
    return f"{GITHUB_RAW_BASE}/{path}"


def extract_description_from_code(code):
    for line in code.splitlines():
        line = line.strip()
        if line.startswith("DESCRIPTION"):
            try:
                _, right = line.split("=", 1)
                return right.strip().strip('\"').strip("'")
            except Exception:
                return ""
    return ""


def get_prompt(state):
    if state.cwd:
        return "/system/" + state.cwd.replace("\\", "/")
    return "/system"


def safe_path_from_cwd(state, extra=""):
    cwd = state.cwd
    base = (ROOT / cwd).resolve()
    final = (base / extra).resolve()
    root_resolved = ROOT.resolve()
    try:
        final.relative_to(root_resolved)
    except ValueError:
        state.cwd = ""
        raise ValueError("Acceso denegado fuera de /system")
    return final


def get_repo_index():
    try:
        text = download_text(repo_url("index.json"))
        data = json.loads(text)
        commands = data.get("commands", [])
        clean = []
        for item in commands:
            if isinstance(item, str) and valid_name(item):
                clean.append({"name": item, "description": "", "entry": "main.py", "category": "legacy"})
            elif isinstance(item, dict):
                name = item.get("name", "")
                entry = item.get("entry", "main.py")
                if valid_name(name) and entry == "main.py":
                    clean.append({
                        "name": name,
                        "description": item.get("description", ""),
                        "entry": entry,
                        "category": item.get("category", "legacy")
                    })
        return clean
    except Exception:
        return []


def get_manifest(command_name):
    try:
        text = download_text(repo_url(f"{command_name}/manifest.json"))
        data = json.loads(text)
        if data.get("name") != command_name:
            return None
        return data
    except Exception:
        return None


def validate_command_code(code):
    if "DESCRIPTION" not in code:
        return False, "El comando debe tener DESCRIPTION."
    blocked = ["os.system", "subprocess.", "shutil.rmtree", "socket.", "requests.", "urllib.", "eval(", "exec(", "__import__"]
    for bad in blocked:
        if bad in code:
            return False, f"Codigo bloqueado: {bad}"
    return True, "OK"


def install_command(command_name, update=False):
    command_name = command_name.lower()
    if not valid_name(command_name):
        return False, "Nombre de comando no permitido."
    if command_name in BUILTINS:
        return False, "No puedes instalar encima de un comando interno."
    try:
        manifest = get_manifest(command_name)
        entry = "main.py"
        legacy = False
        if manifest:
            entry = manifest.get("entry", "main.py")
            if entry != "main.py":
                return False, "Solo se permite entry: main.py"
            description = manifest.get("description", "")
            version = manifest.get("version", "1.0.0")
            author = manifest.get("author", "")
            category = manifest.get("category", "normal")
            expected = manifest.get("sha256", "")
        else:
            legacy = True
            description = ""
            version = now_date()
            author = "desconocido"
            category = "legacy"
            expected = ""
        code = download_text(repo_url(f"{command_name}/{entry}"))
        ok, msg = validate_command_code(code)
        if not ok:
            return False, f"Instalacion cancelada: {msg}"
        if legacy:
            description = extract_description_from_code(code)
            if not description:
                return False, "Comando legacy cancelado: no tiene DESCRIPTION interno."
        checksum = sha256_text(code)
        if expected and expected != checksum:
            return False, "Checksum incorrecto. Archivo no confiable."
        command_folder = COMMADS / command_name
        command_folder.mkdir(exist_ok=True)
        final_manifest = {
            "name": command_name,
            "version": version,
            "author": author,
            "description": description,
            "entry": "main.py",
            "sha256": checksum,
            "category": category,
            "legacy": legacy,
            "updated_date": now_date()
        }
        (command_folder / "manifest.json").write_text(json.dumps(final_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        (command_folder / "main.py").write_text(code, encoding="utf-8")
        db = load_db()
        now = int(time.time())
        old = db["installed"].get(command_name, {})
        db["installed"][command_name] = {
            "name": command_name,
            "source": repo_url(f"{command_name}/{entry}"),
            "sha256": checksum,
            "installed_at": old.get("installed_at", now),
            "updated_at": now,
            "updated_date": now_date(),
            "description": description,
            "version": version,
            "author": author,
            "entry": "main.py",
            "category": category,
            "legacy": legacy
        }
        save_db(db)
        log_event(f"{'updated' if update else 'installed'} {command_name}")
        if legacy:
            return True, f"Comando {'actualizado' if update else 'instalado'} legacy: {command_name}"
        return True, f"Comando {'actualizado' if update else 'instalado'}: {command_name}"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, f"No existe en GitHub: {command_name}/main.py"
        return False, f"HTTP Error {e.code}"
    except Exception as e:
        return False, f"No se pudo instalar {command_name}: {e}"


def remove_command(command_name):
    command_name = command_name.lower()
    if not valid_name(command_name):
        return False, "Nombre no permitido."
    if command_name in BUILTINS:
        return False, "No puedes eliminar comandos internos."
    path = COMMADS / command_name
    if not path.exists():
        return False, "Ese comando no esta instalado."
    shutil.rmtree(path)
    db = load_db()
    db["installed"].pop(command_name, None)
    save_db(db)
    log_event(f"removed {command_name}")
    return True, f"Comando eliminado: {command_name}"


def get_external_help():
    commands = {}
    db = load_db().get("installed", {})
    for folder in COMMADS.iterdir():
        if not folder.is_dir():
            continue
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            name = data.get("name", folder.name)
            description = data.get("description", "")
            version = data.get("version", "")
            category = data.get("category", "normal")
            legacy = data.get("legacy", False)
            if legacy:
                version = db.get(name, {}).get("updated_date", data.get("updated_date", now_date()))
            if description:
                commands[name] = {"description": description, "version": version, "category": category, "legacy": legacy}
        except Exception:
            pass
    return commands


def run_external_command(state, cmd, args):
    command_folder = COMMADS / cmd
    script_path = command_folder / "main.py"
    if not script_path.exists():
        return None
    old_argv = sys.argv[:]
    old_cwd = os.getcwd()
    env_backup = {
        "MINICMD_ROOT": os.environ.get("MINICMD_ROOT"),
        "MINICMD_CWD": os.environ.get("MINICMD_CWD"),
        "MINICMD_SUDO": os.environ.get("MINICMD_SUDO")
    }
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        current_dir = safe_path_from_cwd(state)
        os.environ["MINICMD_ROOT"] = str(ROOT.resolve())
        os.environ["MINICMD_CWD"] = str(current_dir)
        os.environ["MINICMD_SUDO"] = "1" if state.sudo else "0"
        sys.argv = [str(script_path)] + args
        os.chdir(str(current_dir))
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                runpy.run_path(str(script_path), run_name="__main__")
            except SystemExit:
                pass
        output = stdout.getvalue().strip()
        error = stderr.getvalue().strip()
        if error:
            output += ("\n" if output else "") + error
        return output
    except Exception as e:
        return f"Error ejecutando comando: {e}"
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def execute_command(state, raw):
    raw = raw.strip()
    if not raw:
        return ""
    state.history.append(raw)
    state.history = state.history[-100:]
    try:
        parts = shlex.split(raw)
    except Exception:
        return "Error: comillas invalidas."
    if not parts:
        return ""
    cmd = parts[0].lower()
    args = parts[1:]
    try:
        if cmd == "help":
            page = 1
            per_page = 12
            if args:
                try:
                    page = max(1, int(args[0]))
                except Exception:
                    return "Uso: help [pagina]\nEjemplo: help 2"
            lines = ["Comandos internos:"]
            for name, desc in BUILTIN_HELP.items():
                lines.append(f"  {name:<12} {desc}")
            external = get_external_help()
            if external:
                lines.append("")
                lines.append("Comandos externos instalados:")
                for name, data in sorted(external.items()):
                    desc = data["description"]
                    version = data["version"]
                    category = data["category"]
                    legacy = data["legacy"]
                    if legacy:
                        lines.append(f"  {name:<12} [legacy] v{version} - {desc}")
                    else:
                        lines.append(f"  {name:<12} [{category}] v{version} - {desc}")
            lines += [
                "",
                "Sudo:",
                "  sudo 1234",
                "  sudo logout",
                "  sudo status",
                "  sudo install <comando>",
                "  sudo install all",
                "  sudo update <comando>",
                "  sudo update all",
                "  sudo remove <comando>",
                "  sudo list",
                "  sudo search <texto>",
                "  sudo info <comando>"
            ]
            total = len(lines)
            pages = max(1, (total + per_page - 1) // per_page)
            if page > pages:
                page = pages
            start = (page - 1) * per_page
            end = start + per_page
            return "\n".join(lines[start:end]) + f"\nPagina {page}/{pages} | Usa: help <pagina>"
        if cmd == "cls":
            return "\033[2J\033[H"
        if cmd == "pwd":
            return get_prompt(state).replace("/", "\\")
        if cmd == "history":
            return "\n".join([f"{i + 1}: {x}" for i, x in enumerate(state.history)])
        if cmd == "exit":
            state.running = False
            return "Cerrando sesion MiniCMD..."
        if cmd == "cd":
            if len(args) != 1:
                return "Uso: cd <carpeta>"
            target = args[0]
            if target in ["\\", "/", "C:\\system", "c:\\system", "/system"]:
                state.cwd = ""
                return ""
            if target == "..":
                parent = os.path.dirname(state.cwd).replace("\\", "/")
                state.cwd = "" if parent == "." else parent
                return ""
            if not valid_name(target):
                return "Nombre de carpeta no permitido."
            new_path = safe_path_from_cwd(state, target)
            if not new_path.is_dir():
                return "La carpeta no existe."
            relative = os.path.relpath(new_path, ROOT)
            state.cwd = "" if relative == "." else relative.replace("\\", "/")
            return ""
        if cmd == "sudo":
            if len(args) == 1 and args[0] == SUDO_PASSWORD:
                state.sudo = True
                return "Sudo activado."
            if not args:
                return "Uso: sudo 1234 | sudo install <comando>"
            if args[0] == "logout":
                state.sudo = False
                return "Sudo desactivado."
            if args[0] == "status":
                return "Sudo activo." if state.sudo else "Sudo inactivo."
            if not state.sudo:
                return "Primero activa sudo: sudo 1234"
            action = args[0]
            if action == "install":
                if len(args) != 2:
                    return "Uso: sudo install <comando|all>"
                target = args[1].lower()
                if target == "all":
                    repo_commands = get_repo_index()
                    if not repo_commands:
                        return "No se encontro index.json o esta vacio."
                    return "\n".join([install_command(item["name"])[1] for item in repo_commands])
                return install_command(target)[1]
            if action == "update":
                if len(args) != 2:
                    return "Uso: sudo update <comando|all>"
                target = args[1].lower()
                if target == "all":
                    installed = list(load_db().get("installed", {}).keys())
                    if not installed:
                        return "No hay comandos instalados."
                    return "\n".join([install_command(name, update=True)[1] for name in installed])
                return install_command(target, update=True)[1]
            if action == "remove":
                if len(args) != 2:
                    return "Uso: sudo remove <comando>"
                return remove_command(args[1])[1]
            if action == "list":
                repo_commands = get_repo_index()
                if not repo_commands:
                    return "No hay comandos en index.json."
                installed = load_db().get("installed", {})
                lines = ["Comandos disponibles en GitHub:"]
                for item in repo_commands:
                    name = item["name"]
                    desc = item.get("description", "")
                    category = item.get("category", "legacy")
                    mark = "[instalado]" if name in installed else "[repo]"
                    lines.append(f"  {mark:<12} {name:<12} [{category}] {desc}")
                return "\n".join(lines)
            if action == "search":
                if len(args) < 2:
                    return "Uso: sudo search <texto>"
                query = " ".join(args[1:]).lower()
                found = []
                for item in get_repo_index():
                    name = item.get("name", "")
                    desc = item.get("description", "")
                    category = item.get("category", "")
                    if query in name.lower() or query in desc.lower() or query in category.lower():
                        found.append(f"  {name:<12} [{category}] {desc}")
                return "Resultados:\n" + "\n".join(found) if found else "Sin resultados."
            if action == "info":
                if len(args) != 2:
                    return "Uso: sudo info <comando>"
                name = args[1].lower()
                if not valid_name(name):
                    return "Nombre no permitido."
                manifest = get_manifest(name)
                installed = load_db().get("installed", {})
                lines = [f"Comando: {name}"]
                if manifest:
                    lines.append(f"Descripcion: {manifest.get('description', '')}")
                    lines.append(f"Version: {manifest.get('version', 'N/A')}")
                    lines.append(f"Autor: {manifest.get('author', 'N/A')}")
                    lines.append(f"Entry: {manifest.get('entry', 'main.py')}")
                    lines.append(f"Categoria: {manifest.get('category', 'normal')}")
                else:
                    lines += ["Manifest remoto: no disponible", "Si existe main.py, se instalara como legacy.", "Version: fecha de update", "Categoria: legacy"]
                if name in installed:
                    local = installed[name]
                    lines.append("Estado: instalado")
                    lines.append(f"Local version: {local.get('version', '')}")
                    lines.append(f"Local categoria: {local.get('category', '')}")
                    lines.append(f"Fecha update: {local.get('updated_date', '')}")
                    lines.append(f"SHA256: {local.get('sha256', '')}")
                else:
                    lines.append("Estado: no instalado")
                return "\n".join(lines)
            return "Accion sudo no reconocida."
        output = run_external_command(state, cmd, args)
        if output is not None:
            return output
        return f"Comando no encontrado: {cmd}"
    except Exception as e:
        return f"Error: {e}"


class MiniCMDSSHServer(asyncssh.SSHServer):
    def connection_made(self, conn):
        peer = conn.get_extra_info("peername")
        log_event(f"ssh connection from {peer}")

    def begin_auth(self, username):
        return True

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        ok = username == SSH_USER and password == SSH_PASSWORD
        log_event(f"auth {'ok' if ok else 'fail'} user={username}")
        return ok


class MiniCMDSSHSession(asyncssh.SSHServerSession):
    def __init__(self):
        self.chan = None
        self.state = MiniCMDState()
        self.buffer = ""

    def connection_made(self, chan):
        self.chan = chan

    def shell_requested(self):
        return True

    def session_started(self):
        self.write("MiniCMD SSH v1.0\n")
        self.write("Sistema seguro: /system\n")
        self.write("Escribe 'help' para ver comandos.\n\n")
        self.write_prompt()

    def data_received(self, data, datatype):
        for ch in data:
            if ch in ("\r", "\n"):
                self.write("\n")
                line = self.buffer
                self.buffer = ""
                output = execute_command(self.state, line)
                if output:
                    self.write(output)
                    if not output.endswith("\n"):
                        self.write("\n")
                if not self.state.running:
                    self.chan.exit(0)
                    return
                self.write_prompt()
            elif ch == "\x7f":
                if self.buffer:
                    self.buffer = self.buffer[:-1]
                    self.write("\b \b")
            elif ch == "\x03":
                self.buffer = ""
                self.write("^C\n")
                self.write_prompt()
            else:
                self.buffer += ch
                self.write(ch)

    def eof_received(self):
        return False

    def write_prompt(self):
        self.write(get_prompt(self.state) + "> ")

    def write(self, text):
        if self.chan:
            self.chan.write(text)


def ensure_host_key():
    if not HOST_KEY_FILE.exists():
        key = asyncssh.generate_private_key("ssh-rsa")
        HOST_KEY_FILE.write_text(key.export_private_key().decode("utf-8"), encoding="utf-8")
    return str(HOST_KEY_FILE)


async def start_server():
    key_file = ensure_host_key()
    print("MiniCMD SSH iniciado")
    print(f"Host: {SSH_HOST}")
    print(f"Puerto: {SSH_PORT}")
    print(f"Usuario: {SSH_USER}")
    print(f"Conectar local: ssh {SSH_USER}@127.0.0.1 -p {SSH_PORT}")
    await asyncssh.create_server(
        MiniCMDSSHServer,
        SSH_HOST,
        SSH_PORT,
        server_host_keys=[key_file],
        session_factory=MiniCMDSSHSession,
    )
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except (KeyboardInterrupt, SystemExit):
        print("\nMiniCMD SSH detenido.")
