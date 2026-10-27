"""converter.py 的冒烟测试：不需要外部 MIDI 文件，用手工构造的 MIDI 走完整流程。

运行：python -m unittest discover -s tests -v
"""

import tempfile
import unittest
from pathlib import Path

import mido

import converter


def make_midi(notes, ticks_per_beat=480, tempo=500000, name="测试轨道"):
    """按 (pitch, start_tick, end_tick, channel) 生成单轨 MIDI，然后从磁盘读回。"""
    midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    # mido 只按 latin-1 写文本；真实中文 MIDI 里存的是 GBK 字节，这里模拟同样的情况。
    raw = name.encode("gbk").decode("latin1")
    track.append(mido.MetaMessage("track_name", name=raw, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

    events = []
    for pitch, start, end, channel in notes:
        events.append((start, 1, "note_on", pitch, channel))
        events.append((end, 0, "note_off", pitch, channel))
    events.sort(key=lambda e: (e[0], e[1]))

    now = 0
    for tick, _, kind, pitch, channel in events:
        track.append(mido.Message(kind, note=pitch, velocity=100 if kind == "note_on" else 0,
                                  channel=channel, time=tick - now))
        now = tick

    path = Path(tempfile.mkdtemp()) / "smoke.mid"
    midi.save(path)
    return path


class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.midi = make_midi([
            (60, 0, 480, 0),      # C4 白键
            (61, 480, 960, 0),    # C#4 黑键，就近向下应变成 60
            (72, 960, 1440, 0),   # C5
            (100, 1440, 1920, 0), # 超出音域，应折回
            (36, 1920, 2400, 0),  # 低于两排琴域，应升八度
        ])
        self.data = converter.load(str(self.midi))

    def test_load(self):
        self.assertEqual(len(self.data["tracks"]), 1)
        self.assertEqual(len(self.data["notes"]), 5)
        self.assertEqual(self.data["division"], 480)
        self.assertEqual(self.data["end"], 2400)
        self.assertEqual(self.data["tempos"], [(0, 500000)])

    def test_duration(self):
        # 2400 tick / 480 = 5 拍，每拍 0.5 秒 => 2.5 秒
        self.assertAlmostEqual(converter.duration(self.data), 2.5, places=6)
        self.assertAlmostEqual(converter.duration(self.data, speed=2), 1.25, places=6)

    def test_suggest_returns_in_range(self):
        shift = converter.suggest(converter.selected_notes(self.data, {0}, True))
        self.assertTrue(-6 <= shift <= 5)

    def test_convert_two_row(self):
        text, stats = converter.convert(self.data, {0}, low=60, shift=0,
                                        speed=1, no_drums=True, policy="nearest",
                                        title="冒烟测试")
        self.assertTrue(text.startswith("!v/2\n"))
        self.assertIn("!ti/冒烟测试", text)
        self.assertIn("!di/480", text)
        self.assertGreaterEqual(stats["output"], 1)
        self.assertEqual(stats["corrected"], 1)   # 只有 C#4 需要修正
        self.assertEqual(stats["skipped"], 0)
        converter.validate(text, 60)              # 自带校验必须通过

    def test_convert_skips_black_keys(self):
        text, stats = converter.convert(self.data, {0}, low=60, shift=0,
                                        speed=1, no_drums=True, policy="skip",
                                        title="跳过半音")
        self.assertEqual(stats["skipped"], 1)
        converter.validate(text, 60)

    def test_drum_track_filtered(self):
        drums = make_midi([(60, 0, 240, 9), (64, 0, 240, 0)])
        data = converter.load(str(drums))
        self.assertEqual(len(converter.selected_notes(data, {0}, True)), 1)
        self.assertEqual(len(converter.selected_notes(data, {0}, False)), 2)

    def test_empty_selection_rejected(self):
        empty = make_midi([(60, 0, 240, 0)])
        data = converter.load(str(empty))
        with self.assertRaises(ValueError):
            converter.convert(data, set(), low=60, shift=0, title="空")

    def test_octave_folding_stays_in_range(self):
        text, _ = converter.convert(self.data, {0}, low=48, shift=0, title="三排")
        stream = next(s[4:] for s in text.splitlines() if s.startswith("!tr/"))
        for token in stream.split("|"):
            if "n" in token:
                value = int(token.split("n")[1])
                self.assertTrue(48 <= value <= 83, token)
        converter.validate(text, 48)

    def test_unused_path_avoids_overwrite(self):
        folder = Path(tempfile.mkdtemp())
        first = converter.unused_path(folder, "曲谱")
        self.assertEqual(first.name, "曲谱.gs2")
        first.write_text("x", encoding="utf-8")
        second = converter.unused_path(folder, "曲谱")
        self.assertNotEqual(first, second)
        self.assertTrue(second.name.startswith("曲谱（"))

    def test_title_sanitized(self):
        _, _ = converter.convert(self.data, {0}, low=60, shift=0, title="a\nb")
        path = converter.unused_path(Path(tempfile.mkdtemp()), 'bad<>:"/\\|?*name')
        self.assertEqual(path.name, "bad_________name.gs2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
