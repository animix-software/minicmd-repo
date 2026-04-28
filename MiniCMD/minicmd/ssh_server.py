import asyncio
import asyncssh
from .config import *
from .logger import log_event, log_error
from .executor import run
from .auth import auth


def _peer_ip(conn):
    try:
        peer = conn.get_extra_info("peername")
        if isinstance(peer, (list, tuple)) and peer:
            return peer[0]
    except Exception:
        pass
    return None


def _allow_no_password(conn):
    if not SSH_NO_PASSWORD:
        return False
    ip = _peer_ip(conn)
    if SSH_NO_PASSWORD_SCOPE == "unsafe":
        return True
    return ip in ("127.0.0.1", "::1", None)


class Server(asyncssh.SSHServer):

    def connection_made(self, conn):
        self.conn = conn
        log_event(f"conexion nueva from {_peer_ip(conn)}")

    def begin_auth(self, username):
        if _allow_no_password(self.conn):
            return False
        return True

    def password_auth_supported(self):
        if _allow_no_password(self.conn):
            return False
        return True

    def validate_password(self, username, password):
        if _allow_no_password(self.conn):
            self.conn._minicmd_username = username or SSH_USER
            return True

        ok = auth(username, password)
        if ok:
            self.conn._minicmd_username = username
        return ok


class Session(asyncssh.SSHServerSession):

    def __init__(self):
        self.buffer = ""

    def connection_made(self, chan):
        self.chan = chan
        conn = chan.get_extra_info("connection")
        self.user = getattr(conn, "_minicmd_username", SSH_USER)

    def shell_requested(self):
        return True

    def session_started(self):
        self.chan.write("MiniCMD SSH passwordless mode\n")
        self.prompt()

    def data_received(self, data, datatype):
        try:
            for c in data:
                if c == "\n":
                    self.chan.write("\n")
                    out = run(self.buffer.strip())
                    self.chan.write(out + "\n")
                    self.buffer = ""
                    self.prompt()
                else:
                    self.buffer += c
                    self.chan.write(c)
        except Exception as e:
            log_error("SSH crash", e)
            self.chan.write("\nError interno\n")
            self.prompt()

    def prompt(self):
        self.chan.write(f"{self.user}@mini$ ")


async def _run():
    await asyncssh.create_server(Server, SSH_HOST, SSH_PORT, session_factory=Session)
    await asyncio.Future()


def start():
    print("MiniCMD SSH iniciado")
    print(f"No-password: {SSH_NO_PASSWORD} scope={SSH_NO_PASSWORD_SCOPE}")
    asyncio.run(_run())
