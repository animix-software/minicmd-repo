def run(command):
    command = command.strip()
    if not command:
        return ""
    if command == "help":
        return "help, whoami, echo, exit"
    if command == "whoami":
        return "admin"
    if command.startswith("echo "):
        return command[5:]
    return f"Comando no encontrado: {command}"
