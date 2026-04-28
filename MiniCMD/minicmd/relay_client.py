import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

RELAY_URL = os.environ.get('MINICMD_RELAY_URL', 'https://dubbed.onrender.com').rstrip('/')
RELAY_KEY = os.environ.get('MINICMD_RELAY_KEY', os.environ.get('RELAY_KEY', '1234'))
TIMEOUT = int(os.environ.get('MINICMD_RELAY_TIMEOUT', '20'))


def normalize_channel(channel):
    channel = str(channel or 'chat').strip().lower()
    safe = []
    for c in channel:
        if c.isalnum() or c in ['-', '_', '.']:
            safe.append(c)
    value = ''.join(safe)
    return value or 'chat'


def _headers(extra=None):
    headers = {
        'Authorization': f'Bearer {RELAY_KEY}',
        'User-Agent': 'MiniCMD-Relay-Chat',
    }
    if extra:
        headers.update(extra)
    return headers


def _request(method, path, data=None):
    url = f'{RELAY_URL}{path}'
    body = None if data is None else data
    req = urllib.request.Request(url, data=body, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            text = res.read().decode('utf-8', errors='replace')
            return True, json.loads(text)
    except urllib.error.HTTPError as e:
        try:
            text = e.read().decode('utf-8', errors='replace')
            data = json.loads(text)
            err = data.get('error', f'HTTP {e.code}')
            if e.code == 401:
                err += ' | Revisa MINICMD_RELAY_KEY'
            return False, {'ok': False, 'error': err}
        except Exception:
            msg = f'HTTP {e.code}'
            if e.code == 401:
                msg += ' | Revisa MINICMD_RELAY_KEY'
            return False, {'ok': False, 'error': msg}
    except Exception as e:
        return False, {'ok': False, 'error': f'No se pudo conectar al relay {RELAY_URL}: {e}'}


def _decode_packet(packet):
    data = packet.get('data', '') if isinstance(packet, dict) else str(packet)
    try:
        raw = base64.b64decode(data.encode('utf-8'))
        decoded = zlib.decompress(raw).decode('utf-8', errors='replace')
        return decoded
    except Exception:
        return data


def push(channel, text):
    channel = normalize_channel(channel)
    payload = str(text).encode('utf-8')
    ok, data = _request('POST', f'/push/{urllib.parse.quote(channel)}', payload)
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Error enviando mensaje')
    return True, f'Mensaje enviado a {channel}'


def pull(channel):
    channel = normalize_channel(channel)
    ok, data = _request('GET', f'/pull/{urllib.parse.quote(channel)}')
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Error leyendo mensajes')
    messages = []
    for packet in data.get('packets', []):
        messages.append(_decode_packet(packet))
    return True, messages


def peek(channel):
    channel = normalize_channel(channel)
    ok, data = _request('GET', f'/peek/{urllib.parse.quote(channel)}')
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Error leyendo mensajes')
    messages = []
    for packet in data.get('packets', []):
        messages.append(_decode_packet(packet))
    return True, messages


def flush(channel):
    channel = normalize_channel(channel)
    ok, data = _request('GET', f'/flush/{urllib.parse.quote(channel)}')
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Error limpiando canal')
    return True, f'Canal limpiado: {channel} ({data.get("removed", 0)} mensajes)'


def status():
    ok, data = _request('GET', '/')
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Relay no disponible')
    return True, data


def make_chat_message(username, text, channel='chat'):
    return json.dumps({
        'type': 'minicmd-chat',
        'channel': normalize_channel(channel),
        'user': username,
        'text': str(text),
        'time': int(time.time())
    }, ensure_ascii=False)


def format_chat_message(raw):
    try:
        data = json.loads(raw)
        user = data.get('user', '?')
        text = data.get('text', '')
        channel = data.get('channel', 'chat')
        return f'[{channel}] {user}: {text}'
    except Exception:
        return raw
