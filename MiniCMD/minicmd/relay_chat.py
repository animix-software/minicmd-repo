import base64
import json
import os
import time
import urllib.error
import urllib.request
import zlib

RELAY_URL = os.environ.get('MINICMD_RELAY_URL', 'https://dubbed.onrender.com').rstrip('/')
RELAY_KEY = os.environ.get('MINICMD_RELAY_KEY', '1234')
DEFAULT_CHANNEL = os.environ.get('MINICMD_CHAT_CHANNEL', 'minicmd-chat')


def _headers(content_type=None):
    headers = {
        'Authorization': f'Bearer {RELAY_KEY}',
        'User-Agent': 'MiniCMD-Chat'
    }
    if content_type:
        headers['Content-Type'] = content_type
    return headers


def _request(method, path, data=None):
    url = RELAY_URL + path
    body = None
    headers = _headers()
    if data is not None:
        if isinstance(data, str):
            body = data.encode('utf-8')
        else:
            body = data
        headers = _headers('application/json')
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=25) as res:
        raw = res.read().decode('utf-8', errors='replace')
        try:
            return json.loads(raw)
        except Exception:
            return {'ok': False, 'error': raw}


def _decode_packet(packet):
    data = packet.get('data', '')
    if not data:
        return None
    try:
        compressed = base64.b64decode(data)
        raw = zlib.decompress(compressed).decode('utf-8', errors='replace')
        return json.loads(raw)
    except Exception:
        return {'from': '?', 'text': '<mensaje invalido>', 'time': packet.get('time', 0)}


def send_message(channel, sender, text):
    channel = channel or DEFAULT_CHANNEL
    payload = {
        'from': sender,
        'text': text,
        'time': int(time.time()),
        'client': 'MiniCMD'
    }
    try:
        res = _request('POST', f'/push/{channel}', json.dumps(payload, ensure_ascii=False))
        if res.get('ok'):
            return True, f'Mensaje enviado a #{channel}'
        return False, 'Relay error: ' + str(res.get('error', res))
    except urllib.error.HTTPError as e:
        return False, f'Relay HTTP {e.code}'
    except Exception as e:
        return False, f'No se pudo enviar: {e}'


def read_messages(channel, peek=False):
    channel = channel or DEFAULT_CHANNEL
    endpoint = 'peek' if peek else 'pull'
    try:
        res = _request('GET', f'/{endpoint}/{channel}')
        if not res.get('ok'):
            return False, 'Relay error: ' + str(res.get('error', res))
        packets = res.get('packets', [])
        if not packets:
            return True, f'No hay mensajes en #{channel}'
        lines = [f'Mensajes de #{channel}:']
        for packet in packets:
            msg = _decode_packet(packet)
            if not msg:
                continue
            sender = msg.get('from', '?')
            text = msg.get('text', '')
            lines.append(f'[{sender}] {text}')
        return True, '\n'.join(lines)
    except urllib.error.HTTPError as e:
        return False, f'Relay HTTP {e.code}'
    except Exception as e:
        return False, f'No se pudo leer: {e}'


def clear_channel(channel):
    channel = channel or DEFAULT_CHANNEL
    try:
        res = _request('GET', f'/flush/{channel}')
        if res.get('ok'):
            return True, f'Canal limpiado #{channel} removed={res.get("removed", 0)}'
        return False, 'Relay error: ' + str(res.get('error', res))
    except Exception as e:
        return False, f'No se pudo limpiar: {e}'


def status():
    try:
        res = _request('GET', '/')
        if res.get('ok'):
            return True, f"Relay online: {res.get('name', 'relay')} channels={res.get('channels', '?')} packets={res.get('packets', '?')}"
        return False, 'Relay error: ' + str(res.get('error', res))
    except Exception as e:
        return False, f'Relay offline o inaccesible: {e}'
