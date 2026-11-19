"""Read GS2 v2 files into an absolute-time sequence of chords."""
from dataclasses import dataclass, replace
from pathlib import Path
import re
from song_name import clean_title

NOTE_KEYS = dict(zip(
    [72, 74, 76, 77, 79, 81, 83, 60, 62, 64, 65, 67, 69, 71, 48, 50, 52, 53, 55, 57, 59],
    'QWERTYUASDFGHJZXCVBNM'))


@dataclass(frozen=True)
class Score:
    path: Path
    title: str
    chords: tuple
    seconds: float
    notes: int
    skipped: int = 0


def adapt_score(score, three_rows=True):
    """Fold the low octave up for two rows, without modifying the cached score."""
    low_keys = dict(zip('ZXCVBNM', 'ASDFGHJ'))
    chords = score.chords if three_rows else tuple(
        (when, tuple(dict.fromkeys(low_keys.get(key, key) for key in keys)))
        for when, keys in score.chords)
    return replace(score, title=clean_title(score.title), chords=chords,
                   notes=sum(len(keys) for _, keys in chords))


def load_score(path):
    path = Path(path)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('曲谱超过32 MB，请先拆分。')
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('gb18030')
    headers, tracks = {}, []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('!tr/'):
            tracks.append(line[4:])
        elif re.match(r'^![a-z]{1,2}/', line):
            name, value = line[1:].split('/', 1)
            headers[name] = value.strip()
    if headers.get('v') != '2':
        raise ValueError('仅支持 GS2 v2 曲谱，请先用原琴转换器生成 .gs2。')
    division = int(headers.get('di', '480'))
    if division <= 0:
        raise ValueError('曲谱的四分音符 tick 数无效。')
    if not tracks:
        raise ValueError('曲谱没有事件轨道。')
    events = []
    for track_index, track in enumerate(tracks):
        tick = 0
        for index, token in enumerate(track.split('|')):
            token = token.strip()
            if not token: continue
            match = re.fullmatch(r'(\d+)([nus])(\d+)', token)
            if not match:
                raise ValueError(f'轨道{track_index + 1}第{index + 1}个事件格式错误：{token[:40]}')
            delta, kind, value = match.groups()
            tick += int(delta)
            value = int(value)
            if kind == 's' and not 1 <= value <= 0xFFFFFF:
                raise ValueError('曲谱含无效的速度事件。')
            if kind in ('n', 'u') and value > 127:
                raise ValueError(f'曲谱包含无效的 MIDI 音高：{value}')
            events.append((tick, track_index, index, kind, value))
    tempo, previous_tick, seconds, skipped = 500000, 0, 0.0, 0
    by_tick = {}
    for tick, _, _, kind, value in sorted(events):
        seconds += (tick - previous_tick) * tempo / division / 1e6
        previous_tick = tick
        if kind == 's': tempo = value
        elif kind == 'n':
            if value not in NOTE_KEYS:
                skipped += 1
                continue
            if tick not in by_tick: by_tick[tick] = (seconds, [])
            keys = by_tick[tick][1]
            if NOTE_KEYS[value] not in keys: keys.append(NOTE_KEYS[value])
    if not by_tick:
        raise ValueError('曲谱没有可演奏的音符。')
    chords = tuple((when, tuple(keys)) for when, keys in by_tick.values())
    if seconds > 24 * 3600:
        raise ValueError('曲谱时长超过24小时，请检查时间数据。')
    return Score(path, headers.get('ti') or path.stem, chords, seconds,
                 sum(len(keys) for _, keys in chords), skipped)
