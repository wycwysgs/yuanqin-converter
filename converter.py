from collections import defaultdict, deque
from pathlib import Path
import re
import mido

WHITE = {0, 2, 4, 5, 7, 9, 11}

def load(path):
    midi = mido.MidiFile(path)
    if midi.type == 2 or midi.ticks_per_beat <= 0:
        raise ValueError('不支持异步 MIDI Type 2 或 SMPTE 时间格式。请先导出为普通 Type 0/1 MIDI。')
    notes, tempos, tracks, warnings = [], [], [], []
    total = 0
    for index, track in enumerate(midi.tracks):
        tick, count = 0, 0
        active = defaultdict(deque)
        name = next((m.name for m in track if m.type == 'track_name'), '未命名')
        try:
            name = name.encode('latin1').decode('gbk')
        except (UnicodeError, LookupError):
            pass
        for msg in track:
            tick += msg.time
            if msg.type == 'set_tempo':
                if msg.tempo <= 0:
                    raise ValueError('MIDI 含无效速度。')
                tempos.append((tick, index, msg.tempo))
            elif msg.type == 'note_on' and msg.velocity > 0:
                active[msg.channel, msg.note].append(tick)
                count += 1
            elif msg.type in ('note_off', 'note_on'):
                key = (msg.channel, msg.note)
                if active[key]:
                    start = active[key].popleft()
                    notes.append((start, max(start + 1, tick), msg.note, msg.channel, index))
        for (channel, pitch), starts in active.items():
            for start in starts:
                notes.append((start, max(start + 1, tick), pitch, channel, index))
                warnings.append(f'轨道 {index} 的未闭合音符已在轨道末尾结束。')
        total = max(total, tick)
        tracks.append((index, name, count))
    total = max([total] + [n[1] for n in notes])
    tempo_map = {0: 500000}
    for tick, _, tempo in sorted(tempos):
        tempo_map[tick] = tempo
    return dict(notes=notes, tempos=sorted(tempo_map.items()), tracks=tracks,
                division=midi.ticks_per_beat, end=total, warnings=warnings)

def duration(data, speed=1):
    last, tempo, seconds = 0, 500000, 0
    for tick, new in data['tempos']:
        seconds += (tick-last)*tempo/data['division']/1e6
        last, tempo = tick, new
    return (seconds+(data['end']-last)*tempo/data['division']/1e6)/speed

def selected_notes(data, tracks, no_drums):
    return [n for n in data['notes'] if n[4] in tracks and (not no_drums or n[3] != 9)]

def suggest(notes):
    if not notes:
        raise ValueError('所选轨道没有可转换的音符。')
    return min(range(-6, 6), key=lambda s: (sum((n[2]+s)%12 not in WHITE for n in notes), abs(s), s))

def convert(data, tracks, low=48, shift=0, speed=1, no_drums=True, policy='nearest', title='曲谱'):
    if not 0.25 <= speed <= 4:
        raise ValueError('速度倍率应为 0.25–4。')
    source = selected_notes(data, tracks, no_drums)
    if not source:
        raise ValueError('所选轨道没有可转换的音符。')
    mapped = defaultdict(dict)
    stats = dict(source=len(source), octave=0, corrected=0, skipped=0, merged=0, clipped=0)
    for start, end, pitch, _, _ in source:
        p = pitch + shift
        if p%12 not in WHITE:
            if policy == 'skip':
                stats['skipped'] += 1
                continue
            p += 1 if policy == 'up' else -1
            stats['corrected'] += 1
        before = p
        while p < low:
            p += 12
        while p > 83:
            p -= 12
        stats['octave'] += p != before
        if start in mapped[p]:
            stats['merged'] += 1
        mapped[p][start] = max(mapped[p].get(start, 0), end)
    if not mapped:
        raise ValueError('半音处理后没有可播放音符，请调整移调或半音选项。')
    events = [(t, 0, 's', max(1, round(v/speed))) for t, v in data['tempos']]
    for pitch, intervals in mapped.items():
        seq = sorted(intervals.items())
        for i, (start, end) in enumerate(seq):
            if i+1 < len(seq) and end > seq[i+1][0]:
                end = seq[i+1][0]
                stats['clipped'] += 1
            events.extend([(start, 2, 'n', pitch), (end, 1, 'u', pitch)])
    events.append((data['end'], 3, 's', max(1, round(data['tempos'][-1][1]/speed))))
    tokens, previous = [], 0
    for tick, _, kind, value in sorted(events):
        tokens.append(f'{tick-previous}{kind}{value}')
        previous = tick
    title = title.replace('\n', ' ').replace('\r', ' ').strip() or '曲谱'
    text = '\n'.join(['!v/2', '!gi/0', '!ti/'+title, '!ar/原琴转换器',
                      '!di/'+str(data['division']),
                      f'移调{shift:+d}半音；速度{speed:g}倍；超出音域按八度折回。',
                      '!tr/'+'|'.join(tokens), ''])
    validate(text, low)
    stats['output'] = sum(len(v) for v in mapped.values())
    stats['seconds'] = duration(data, speed)
    return text, stats

def validate(text, low):
    if text.splitlines()[0] != '!v/2':
        raise ValueError('曲谱文件头错误。')
    active = set()
    for token in next(s[4:] for s in text.splitlines() if s.startswith('!tr/')).split('|'):
        m = re.fullmatch(r'(\d+)([nus])(\d+)', token)
        if not m:
            raise ValueError('曲谱事件格式错误。')
        _, kind, value = m.groups()
        value = int(value)
        if kind == 'n':
            if value in active or not low <= value <= 83 or value%12 not in WHITE:
                raise ValueError('琴键映射或音符配对错误。')
            active.add(value)
        elif kind == 'u':
            if value not in active:
                raise ValueError('音符松开事件未配对。')
            active.remove(value)
    if active:
        raise ValueError('存在未松开的琴键。')

def unused_path(folder, filename):
    folder = Path(folder)
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename).rstrip(' .') or '曲谱'
    # Prefix reserved Windows device names.
    if base.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *[f'COM{i}' for i in range(1,10)], *[f'LPT{i}' for i in range(1,10)]}:
        base = '_'+base
    candidate = folder/(base+'.gs2')
    i = 2
    while candidate.exists():
        candidate = folder/f'{base}（{i}）.gs2'
        i += 1
    return candidate
