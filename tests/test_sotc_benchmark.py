# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'sotc_benchmark', Path(__file__).resolve().parents[1] / 'tools' / 'sotc_benchmark.py')
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)


class FrameSummaryTests(unittest.TestCase):
    def summary(self, rows, start=0, end=100):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'frames.csv'
            path.write_text('elapsed_s,frame_ms\n' + rows)
            return BENCH.summarize(path, start, end)

    def test_long_stall_counts_in_mean_and_one_percent_low(self):
        rows = ''.join(f'{i / 100:.6f},10\n' for i in range(1, 100)) + '1.99,1000\n'
        result = self.summary(rows, end=1.99)
        self.assertEqual(result['frames'], 100)
        self.assertAlmostEqual(result['average_fps'], 100 / 1.99)
        self.assertEqual(result['one_percent_low_fps'], 1)
        self.assertEqual(result['over_100_ms'], 1)

    def test_warmup_boundary_frame_and_late_capture_are_excluded(self):
        result = self.summary('1.005,20\n1.025,20\n2.025,1000\n', start=1, end=2)
        self.assertEqual(result['frames'], 2)
        self.assertEqual(result['intervals'], 1)
        self.assertEqual(result['average_fps'], 2)
        self.assertEqual(result['interval_average_fps'], 50)

    def test_stall_crossing_window_end_counts_against_present_rate(self):
        result = self.summary('0.5,500\n3,2500\n', end=2)
        self.assertTrue(result['complete_window'])
        self.assertEqual(result['average_fps'], .5)

    def test_early_trace_end_has_no_verified_window_average(self):
        result = self.summary('0.5,500\n', end=2)
        self.assertFalse(result['complete_window'])
        self.assertIsNone(result['average_fps'])

    def test_no_measurement_is_not_reported_as_zero_fps(self):
        self.assertEqual(self.summary('0.5,10\n', start=1), {'frames': 0})


if __name__ == '__main__':
    unittest.main()
