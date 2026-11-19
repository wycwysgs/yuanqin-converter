"""Short local synthesized score previews, independent of game keyboard input."""
from array import array
import io
import math
from pathlib import Path
import tempfile
import threading
import wave
import winsound
from score import NOTE_KEYS

KEY_NOTES = {key: note for note, key in NOTE_KEYS.items()}


def render_preview(score, speed=1.0, limit=20.0, cancelled=lambda: False):
    if not math.isfinite(speed) or not .25 <= speed <= 4:
        raise ValueError('试听速度应为0.25–4。')
    if not score.chords:
        raise ValueError('曲谱没有可试听的音符。')
    rate, tail = 22050, .42
    origin = score.chords[0][0]
    length = max(.1, min(limit, (score.seconds - origin) / speed))
    samples = array('f', [0.]) * (int((length + tail) * rate) + 1)
    count = 0
    tones = {}
    for when, keys in score.chords:
        if cancelled(): return None
        offset = (when - origin) / speed
        if offset >= length: break
        start = max(0, round(offset * rate))
        for key in keys:
            count += 1
            if count > 30000:
                raise ValueError('试听片段音符过密，请先简化伴奏。')
            pitch = KEY_NOTES[key]
            if key not in tones:
                step = 2 * math.pi * 440 * 2 ** ((pitch - 69) / 12) / rate
                tones[key] = array('f', (min(1., i / (rate * .005)) * math.exp(-i / (rate * .11))
                    * (math.sin(step * i) + .15 * math.sin(2 * step * i)) for i in range(int(tail * rate))))
            for i, value in enumerate(tones[key]):
                if start + i >= len(samples): break
                samples[start + i] += value
    if cancelled(): return None
    peak = max(1., max(abs(v) for v in samples))
    pcm = array('h', (round(max(-1., min(1., v / peak * .72)) * 32767) for v in samples))
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate)
        output.writeframes(pcm.tobytes())
    return buffer.getvalue()


class Audition:
    def __init__(self, emit):
        self.emit = emit
        self.lock = threading.Lock()
        self.generation = 0
        self.thread = None
        self.cancelled = threading.Event()

    def stop(self):
        with self.lock:
            self.generation += 1
            self.cancelled.set()
            winsound.PlaySound(None, 0)

    def start(self, score, speed=1.):
        self.stop()
        token = self.generation
        cancelled = self.cancelled = threading.Event()
        def worker():
            path = None
            try:
                data = render_preview(score, speed, cancelled=cancelled.is_set)
                if data is None: return
                with tempfile.NamedTemporaryFile(suffix='.wav', prefix='yuanqin-preview-', delete=False) as f:
                    path = Path(f.name)
                    f.write(data)
                with self.lock:
                    if cancelled.is_set() or token != self.generation: return
                    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                self.emit(dict(kind='audition', generation=token, message='正在试听前20秒（合成音色）；可随时停止试听。'))
                with wave.open(io.BytesIO(data), 'rb') as audio:
                    seconds = audio.getnframes()/audio.getframerate()
                if not cancelled.wait(seconds) and token == self.generation:
                    self.emit(dict(kind='audition', generation=token, message='试听结束。'))
            except Exception as exc:
                if token == self.generation:
                    self.emit(dict(kind='audition', generation=token, message='试听失败：' + str(exc)))
            finally:
                with self.lock:
                    if token == self.generation: winsound.PlaySound(None, 0)
                if path is not None:
                    try: path.unlink(missing_ok=True)
                    except OSError: pass
        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()
