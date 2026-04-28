import json
import time
import urllib.request
import urllib.error
from .config import COMMADS, DB_FILE, GITHUB_RAW_BASE
from .storage import load_json, save_json


def valid_name(name):
    allowed = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
    return bool(name and len(name) <= 64 and all(c in allowed for c in name))


def raw_url(path):
    return f'{GITHUB_RAW_BASE}/{path}'


def download_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'MiniCMD-Apt'})
    with urllib.request.urlopen(req, timeout=20) as res:
        data = res.read(500_001)
        if len(data) > 500_000:
            raise RuntimeError('Archivo remoto demasiado grande')
        return data.decode('utf-8')


def get_index():
    try:
        text = download_text(raw_url('index.json'))
        data = json.loads(text)
        return data.get('commands', [])
    except Exception:
        return []


def extract_description(code):
    for line in code.splitlines():
        line = line.strip()
        if line.startswith('DESCRIPTION'):
            try:
                return line.split('=', 1)[1].strip().strip('"').strip("'")
            except Exception:
                return ''
    return ''


def classify_package(index_item=None, code=''):
    # Regla MiniCMD:
    # legacy = optimizado / liviano
    # heavy = no optimizado / mas pesado
    if isinstance(index_item, dict):
        if index_item.get('heavy') is True:
            return 'heavy', False
        if index_item.get('optimized') is False:
            return 'heavy', False
        if str(index_item.get('type', '')).lower() in ['heavy', 'pesado', 'full']:
            return 'heavy', False
    marker = code.lower()
    if 'minicmd_package_type = "heavy"' in marker or "minicmd_package_type = 'heavy'" in marker:
        return 'heavy', False
    return 'legacy', True


def find_index_item(name):
    for item in get_index():
        if isinstance(item, str) and item.lower() == name:
            return item
        if isinstance(item, dict) and str(item.get('name', '')).lower() == name:
            return item
    return None


def install_package(name):
    name = name.lower().strip()
    if not valid_name(name):
        return False, 'Nombre de paquete invalido.'
    try:
        code = download_text(raw_url(f'{name}/main.py'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, f'Paquete no encontrado: {name}'
        return False, f'HTTP error {e.code}'
    except Exception as e:
        return False, f'Error descargando paquete: {e}'

    index_item = find_index_item(name)
    package_type, optimized = classify_package(index_item, code)

    folder = COMMADS / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'main.py').write_text(code, encoding='utf-8')

    desc = extract_description(code) or 'Comando MiniCMD instalado por apt.'
    manifest = {
        'name': name,
        'version': time.strftime('%Y-%m-%d'),
        'description': desc,
        'entry': 'main.py',
        'category': package_type,
        'package_type': package_type,
        'optimized': optimized,
        'legacy': optimized,
        'updated_date': time.strftime('%Y-%m-%d')
    }
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

    db = load_json(DB_FILE, {'installed': {}})
    db.setdefault('installed', {})[name] = {
        'name': name,
        'source': raw_url(f'{name}/main.py'),
        'installed_at': int(time.time()),
        'updated_at': int(time.time()),
        'description': desc,
        'version': manifest['version'],
        'entry': 'main.py',
        'category': package_type,
        'package_type': package_type,
        'optimized': optimized,
        'legacy': optimized
    }
    save_json(DB_FILE, db)
    label = 'optimizado legacy' if optimized else 'pesado no optimizado'
    return True, f'Paquete instalado: {name} [{label}]'


def list_packages():
    items = get_index()
    if not items:
        return 'No se pudo leer index.json o esta vacio.'
    lines = ['Paquetes disponibles:']
    for item in items:
        if isinstance(item, str):
            lines.append(f'  {item:<12} [legacy/optimizado]')
        elif isinstance(item, dict):
            name = item.get('name', '?')
            package_type, optimized = classify_package(item, '')
            label = 'legacy/optimizado' if optimized else 'heavy/pesado'
            lines.append(f"  {name:<12} [{label}] {item.get('description','')}")
    return '\n'.join(lines)
