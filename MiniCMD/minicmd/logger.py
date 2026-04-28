from .config import SESSION_LOG_FILE, ERROR_LOG_FILE
import time


def log_event(text):
    with open(SESSION_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


def log_error(title, exc=None):
    with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {title}: {exc}\n")
