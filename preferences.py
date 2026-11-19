"""Small, atomic preferences file; malformed settings never prevent startup."""
import json
import logging
import math
import os
from pathlib import Path
import tempfile

PLAYER_DEFAULTS = dict(speed='1.0', countdown='3', gap='2', continuous=False,
                       three_rows=True, play_key='F8', stop_key='F9')


def player_preferences(data):
    data = data if isinstance(data, dict) else {}
    result = PLAYER_DEFAULTS.copy()
    for name, low, high in [('speed', .25, 4), ('countdown', 1, 15), ('gap', 0, 30)]:
        try:
            value = float(data[name])
            if math.isfinite(value) and low <= value <= high: result[name] = str(value)
        except (KeyError, ValueError, TypeError): pass
    for name in ('continuous', 'three_rows'):
        if isinstance(data.get(name), bool): result[name] = data[name]
    keys = tuple(f'F{i}' for i in range(6, 12))
    play, stop = data.get('play_key'), data.get('stop_key')
    if play in keys and stop in keys and play != stop:
        result.update(play_key=play, stop_key=stop)
    return result


def path_list(value):
    return list(dict.fromkeys(v for v in value if isinstance(v, str) and v and '\0' not in v and len(v) < 32768))[:10000] if isinstance(value, list) else []


def read_preferences(path):
    try:
        path = Path(path)
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('设置文件过大')
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        logging.getLogger('yuanqin').warning('读取设置失败，使用默认值：%s', exc)
        return {}


def write_preferences(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
