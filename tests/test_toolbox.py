"""Portable regression coverage for the integrated conversion/playback format."""
import tempfile
import unittest
from pathlib import Path

import mido
from batch import Job, Options, run_batch
from converter import load, arrange_notes, suggest, white_rate
from preferences import read_preferences, write_preferences
from score import load_score, adapt_score, Score


class ToolboxTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.midi = self.folder / 'sample.mid'
        midi = mido.MidiFile()
        track = mido.MidiTrack()
        midi.tracks.append(track)
        for note in (48, 60, 64, 67, 72):
            track.append(mido.Message('note_on', note=note, velocity=80, time=0))
        for index, note in enumerate((48, 60, 64, 67, 72)):
            track.append(mido.Message('note_off', note=note, time=480 if index == 0 else 0))
        midi.save(self.midi)

    def test_batch_failure_continues_and_modes_parse(self):
        bad = self.folder / 'bad.mid'
        bad.write_bytes(b'invalid')
        for mode, count in [('full', 5), ('simple', 3), ('melody', 1)]:
            with self.subTest(mode=mode):
                result = run_batch([Job(bad), Job(self.midi)], self.folder, Options(arrangement=mode))
                self.assertEqual((result['succeeded'], result['failed'], result['outputs']), (1, 1, 1))
                score = load_score(result['rows'][1]['输出'])
                self.assertEqual(score.notes, count)
                self.assertTrue(Path(result['report']).is_file())

    def test_two_row_folding_preserves_source_and_deduplicates(self):
        raw = Score(Path('test.gs2'), '测试', ((0.0, ('Z', 'A', 'Q')), (1.0, ('M',))), 2, 4)
        folded = adapt_score(raw, False)
        self.assertEqual(folded.chords, ((0.0, ('A', 'Q')), (1.0, ('J',))))
        self.assertEqual(raw.chords[0][1], ('Z', 'A', 'Q'))
        self.assertEqual(folded.seconds, raw.seconds)

    def test_duration_weighted_transpose(self):
        data = load(self.midi)
        # Long C with a very short C-sharp: recommendation must favor the sustained note.
        notes = [(0, 4800, 60, 0, 0), (0, 1, 61, 0, 0)]
        shift = suggest(notes, data)
        self.assertGreater(white_rate(notes, shift, data), .99)
        self.assertEqual(len(arrange_notes(data, {0}, arrangement='melody')), 1)

    def test_preferences_roundtrip_and_corruption_fallback(self):
        path = self.folder / 'settings.json'
        settings = {'schema': 1, 'player': {'three_rows': False, 'speed': '1.25'}}
        write_preferences(path, settings)
        self.assertEqual(read_preferences(path), settings)
        path.write_text('{broken', encoding='utf-8')
        self.assertEqual(read_preferences(path), {})


if __name__ == '__main__':
    unittest.main()
