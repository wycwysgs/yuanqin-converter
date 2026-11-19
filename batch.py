"""Batch conversion without GUI dependencies; each input fails independently."""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import csv
import math
from uuid import uuid4
from converter import load, arrange_notes, suggest, convert, unused_path, validate
from song_name import clean_title


@dataclass
class Job:
    path: Path
    title: str = ''
    tracks: set | None = None
    shift: int = 0
    data: dict | None = None


@dataclass(frozen=True)
class Options:
    auto_shift: bool = True
    speed: float = 1.0
    no_drums: bool = True
    policy: str = 'nearest'
    arrangement: str = 'full'

    def check(self):
        if not math.isfinite(self.speed) or not 0.25 <= self.speed <= 4:
            raise ValueError('速度倍率应为 0.25–4。')
        if self.policy not in ('nearest', 'up', 'skip'):
            raise ValueError('半音处理选项无效。')
        if self.arrangement not in ('full', 'simple', 'melody'):
            raise ValueError('伴奏模式无效。')


def run_batch(jobs, folder, options, notify=lambda event: None):
    options.check()
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError('输出目录不存在，请选择现有文件夹。')
    rows, succeeded, failed = [], 0, 0
    for index, job in enumerate(jobs):
        notify(dict(kind='start', index=index, name=job.path.name))
        try:
            data = job.data if job.data is not None else load(job.path)
            tracks = job.tracks if job.tracks is not None else {t[0] for t in data['tracks'] if t[2]}
            shift = suggest(arrange_notes(data, tracks, options.no_drums, options.arrangement), data) if options.auto_shift else job.shift
            if not -24 <= shift <= 24:
                raise ValueError('移调应为 -24 至 24 半音。')
            title = clean_title(job.title.strip() or job.path.stem)
            text, stats = convert(data, tracks, 48, shift, options.speed,
                                  options.no_drums, options.policy, title, options.arrangement)
            path = unused_path(folder, title)
            with path.open('x', encoding='utf-8', newline='\n') as f:
                f.write(text)
            validate(path.read_text(encoding='utf-8'), 48)
            paths = [str(path)]
            row = dict(源文件=str(job.path), 结果='成功', 输出=str(path),
                       移调=shift, 时长秒=round(stats['seconds'], 3), 音符=stats['output'],
                       半音修正=stats['corrected'], 八度折回=stats['octave'],
                       伴奏模式=options.arrangement, 简化音符=stats['reduced'],
                       白键适配前=round(stats['white_before']*100, 1), 白键适配后=round(stats['white_after']*100, 1),
                       提醒='；'.join(dict.fromkeys(data['warnings'])))
            rows.append(row)
            song_rows = [row]
            succeeded += 1
            notify(dict(kind='success', index=index, name=job.path.name, paths=paths, rows=song_rows))
        except Exception as exc:
            failed += 1
            error = str(exc) or type(exc).__name__
            rows.append(dict(源文件=str(job.path), 结果='失败', 提醒=error))
            notify(dict(kind='failure', index=index, name=job.path.name, error=error))
        notify(dict(kind='progress', done=index + 1, total=len(jobs)))
    report, report_error = None, None
    try:
        name = '原琴转换记录_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid4().hex + '.csv'
        report = folder / name
        with report.open('x', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['源文件', '结果', '输出', '移调',
                '时长秒', '音符', '半音修正', '八度折回', '伴奏模式', '简化音符', '白键适配前', '白键适配后', '提醒'])
            writer.writeheader()
            writer.writerows(rows)
    except Exception as exc:
        report_error = str(exc)
        report = None
    return dict(succeeded=succeeded, failed=failed, outputs=sum(r['结果']=='成功' for r in rows),
                rows=rows, report=str(report) if report else None, report_error=report_error)
