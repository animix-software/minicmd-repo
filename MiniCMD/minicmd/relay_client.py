import base64
import json
import os
import time
import urllib.error
import urllib.request
import zlib

RELAY_URL = os.environ.get('MINICMD_RELAY_URL', 'https://dubbed.onrender.com').rstrip('/')
RELAY_KEY = os.environ.get('MINICMD_RELAY_KEY', os.environ.get('RELAY_KEY', '1234'))
TIMEOUT = int(os.environ.get('MINICMD_RELAY_TIMEOUT', '20'))


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
            return False, json.loads(text)
        except Exception:
            return False, {'ok': False, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return False, {'ok': False, 'error': str(e)}


def _decode_packet(packet):
    data = packet.get('data', '')
    try:
        raw = base64.b64decode(data.encode('utf-8'))
        decoded = zlib.decompress(raw).decode('utf-8', errors='replace')
        return decoded
    except Exception:
        return data


def push(channel, text):
    payload = text.encode('utf-8')
    ok, data = _request('POST', f'/push/{channel}', payload)
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Error enviando mensaje')
    return True, f'Mensaje enviado a {channel}'


def pull(channel):
    ok, data = _request('GET', f'/pull/{channel}')
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Error leyendo mensajes')
    messages = []
    for packet in data.get('packets', []):
        messages.append(_decode_packet(packet))
    return True, messages


def peek(channel):
    ok, data = _request('GET', f'/peek/{channel}')
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Error leyendo mensajes')
    messages = []
    for packet in data.get('packets', []):
        messages.append(_decode_packet(packet))
    return True, messages


def flush(channel):
    ok, data = _request('GET', f'/flush/{channel}')
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Error limpiando canal')
    return True, f'Canal limpiado: {channel} ({data.get("removed", 0)} mensajes)'


def status():
    ok, data = _request('GET', '/')
    if not ok or not data.get('ok'):
        return False, data.get('error', 'Relay no disponible')
    return True, data


def make_chat_message(username, text):
    return json.dumps({
        'user': username,
        'text': text,
        'time': int(time.time())
    }, ensure_ascii=False)


def format_chat_message(raw):
    try:
        data = json.loads(raw)
        user = data.get('user', '?')
        text = data.get('text', '')
        return f'{user}: {text}'
    except Exception:
        return raw
