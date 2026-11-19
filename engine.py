"""Playback scheduling; no UI dependencies and injectable keyboard for offline tests."""
from dataclasses import dataclass
import threading
import time


@dataclass(frozen=True)
class Settings:
    speed: float = 1.0
    countdown: float = 3.0
    gap: float = 2.0
    tap: float = 0.02


class Player:
    def __init__(self, keyboard, foreground, modifiers, emit, check_target=lambda target: None):
        self.keyboard, self.foreground, self.modifiers, self.emit = keyboard, foreground, modifiers, emit
        self.check_target = check_target
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.paused = threading.Event()
        self.state = 'idle'
        self.thread = None

    def start(self, scores, settings):
        if self.thread and self.thread.is_alive(): return False
        if not scores: raise ValueError('请先选择曲谱。')
        self.stopped.clear(); self.paused.clear()
        self.state = 'countdown'
        self.thread = threading.Thread(target=self.run, args=(tuple(scores), settings), daemon=True)
        self.thread.start()
        return True

    def toggle_pause(self):
        with self.lock:
            if self.state == 'playing':
                self.paused.set(); self.state = 'paused'
                self.emit(dict(kind='state', state='paused', message='已暂停，按开始/暂停快捷键继续。'))
            elif self.state == 'paused':
                if not self.foreground() or self.modifiers():
                    self.emit(dict(kind='notice', message='请切回原神，松开 Ctrl / Alt / Shift 后再继续。'))
                    return
                self.paused.clear(); self.state = 'playing'
                self.emit(dict(kind='state', state='playing', message='继续演奏'))

    def stop(self):
        self.stopped.set()

    def run(self, scores, settings):
        try:
            end = time.perf_counter() + settings.countdown
            previous = None
            while not self.stopped.is_set():
                remaining = end - time.perf_counter()
                if remaining <= 0: break
                value = int(remaining) + 1
                if value != previous:
                    self.emit(dict(kind='state', state='countdown', message=f'{value} 秒后开始：请切回原神的乐器演奏界面'))
                    previous = value
                self.stopped.wait(min(0.03, remaining))
            if self.stopped.is_set(): return
            target = self.foreground()
            if not target:
                raise ValueError('当前前台窗口不是原神。请打开乐器演奏界面，切回游戏后按开始快捷键。')
            issue = self.check_target(target)
            if issue: raise ValueError(issue)
            if self.modifiers(): raise ValueError('请松开 Ctrl / Alt / Shift 等修饰键后重新开始。')
            for index, score in enumerate(scores):
                if self.stopped.is_set(): return
                self.emit(dict(kind='song', index=index, title=score.title, seconds=score.seconds / settings.speed))
                self.state = 'playing'
                self.emit(dict(kind='state', state='playing', message='正在演奏：' + score.title))
                self.play_score(score, target, settings)
                if self.stopped.is_set(): return
                if index + 1 < len(scores):
                    # Silence between songs is subject to the same focus and pause checks.
                    from types import SimpleNamespace
                    self.play_score(SimpleNamespace(chords=(), seconds=settings.gap * settings.speed), target, settings, progress=False)
            self.emit(dict(kind='finished', message='演奏完成'))
        except Exception as exc:
            self.emit(dict(kind='error', message=str(exc)))
        finally:
            try: self.keyboard.release()
            except Exception as exc: self.emit(dict(kind='error', message='松开琴键失败：' + str(exc)))
            self.state = 'idle'
            self.emit(dict(kind='idle'))

    def play_score(self, score, target, settings, progress=True):
        index, position, last_notice = 0, 0.0, -1.0
        previous = time.perf_counter()
        releases = {}
        total = score.seconds / settings.speed
        while not self.stopped.is_set():
            now = time.perf_counter()
            elapsed = now - previous
            previous = now
            with self.lock:
                if self.foreground() != target or self.modifiers():
                    if not self.paused.is_set():
                        self.paused.set(); self.state = 'paused'
                        self.emit(dict(kind='state', state='paused', message='已自动暂停：切回原神并松开修饰键后，按开始/暂停快捷键继续。'))
                is_paused = self.paused.is_set()
            if is_paused:
                self.keyboard.release(); releases.clear()
                self.stopped.wait(0.01)
                continue
            position += elapsed
            expired = tuple(key for key, due in releases.items() if now >= due)
            if expired:
                self.keyboard.send(expired, up=True)
                for key in expired: releases.pop(key, None)
            while index < len(score.chords) and score.chords[index][0] / settings.speed <= position:
                if self.stopped.is_set() or self.paused.is_set(): break
                if self.foreground() != target or self.modifiers(): break
                when, keys = score.chords[index]
                # After a long system stall do not send a rapid burst of old notes.
                if position - when / settings.speed > 0.25:
                    self.paused.set(); self.state = 'paused'
                    position = when / settings.speed
                    self.keyboard.release(); releases.clear()
                    self.emit(dict(kind='state', state='paused', message='系统延迟过大，已暂停。按开始/暂停快捷键继续。'))
                    break
                repeat = tuple(key for key in keys if key in releases)
                if repeat: self.keyboard.send(repeat, up=True)
                self.keyboard.send(keys)
                for key in keys: releases[key] = now + settings.tap
                index += 1
            if progress and position - last_notice >= 0.1:
                self.emit(dict(kind='progress', seconds=min(position, total), total=total))
                last_notice = position
            if index >= len(score.chords) and position >= total and not releases: break
            self.stopped.wait(0.003)
