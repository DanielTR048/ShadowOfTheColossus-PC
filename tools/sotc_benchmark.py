#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Isolated Windows benchmark. Requires psutil; prepares nothing in the game folder.

Use sotc.py --prepare-only first with the same game, update, modules and fps60 mode.
Each run creates a new directory under .local/bench, copies saves/cache if supplied,
and records host flip intervals plus CPU/RAM and NVIDIA telemetry. It never starts
the installed launcher or changes its settings. Screenshots stall rendering: take
them outside the measurement interval. Timings are not physical display scanout.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime

import psutil

ROOT = Path(__file__).resolve().parent.parent


def summarize(path, start, end):
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    presents = sum(start < float(r['elapsed_s']) <= end for r in rows)
    complete = bool(rows) and float(rows[-1]['elapsed_s']) >= end
    values = [float(r['frame_ms']) for r in rows
              if start <= float(r['elapsed_s']) - float(r['frame_ms']) / 1000
              and float(r['elapsed_s']) <= end and float(r['frame_ms']) > 0]
    if not values:
        return {'frames': 0}
    ordered = sorted(values)
    worst = ordered[-max(1, math.ceil(len(ordered) * .01)):]
    return {
        'frames': presents, 'intervals': len(values),
        'window_seconds': end - start, 'complete_window': complete,
        # Count presents over the WHOLE window, including a stall across its end.
        # If recording ends early, do not invent observation time or claim an average.
        'average_fps': presents / (end - start) if complete else None,
        'measured_seconds': sum(values) / 1000,
        'interval_average_fps': 1000 * len(values) / sum(values),
        'one_percent_low_fps': 1000 * len(worst) / sum(worst),
        'p50_ms': ordered[math.ceil(len(ordered) * .50) - 1],
        'p95_ms': ordered[math.ceil(len(ordered) * .95) - 1],
        'p99_ms': ordered[math.ceil(len(ordered) * .99) - 1],
        'max_ms': max(values),
        'over_16_67_ms_percent': 100 * sum(v > 1000 / 60 for v in values) / len(values),
        'over_50_ms': sum(v > 50 for v in values),
        'over_100_ms': sum(v > 100 for v in values),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game', type=Path, required=True)
    p.add_argument('--update', type=Path)
    p.add_argument('--save-template', type=Path, help='savedata directory to COPY')
    p.add_argument('--cache-template', type=Path, help='user directory; copy shader/cache only')
    p.add_argument('--stream-memory', choices=('device', 'host', 'cached'), required=True)
    p.add_argument('--seconds', type=float, default=240)
    p.add_argument('--warmup', type=float, default=90)
    p.add_argument('--measure-end', type=float)
    p.add_argument('--label', required=True)
    p.add_argument('--event', action='append', default=[], help='seconds:pad tokens:hold seconds')
    p.add_argument('--capture', action='append', type=float, default=[])
    p.add_argument('--env', action='append', default=[], help='additional diagnostic NAME=value')
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', a.label):
        p.error('label must use letters, digits, underscores or hyphens')
    if not (a.game / 'eboot.bin').is_file():
        p.error('game must contain eboot.bin')
    if a.seconds <= 0 or not 0 <= a.warmup < a.seconds:
        p.error('require seconds > warmup >= 0')
    end = a.measure_end if a.measure_end is not None else a.seconds - 5
    if not a.warmup < end <= a.seconds:
        p.error('measurement end must be after warmup and at most seconds')
    events = []
    for item in a.event:
        at, tokens, hold = item.split(':')
        events.extend([(float(at), 'pad', tokens.replace(',', ' ')),
                       (float(at) + float(hold), 'pad', '')])
    events.extend((t, 'capture', '') for t in a.capture)
    events.sort(key=lambda event: event[0])
    run = ROOT / '.local' / 'bench' / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + a.label)
    run.mkdir(parents=True, exist_ok=False)
    user = run / 'user'
    user.mkdir()
    if a.save_template:
        shutil.copytree(a.save_template.resolve(), user / 'savedata')
    if a.cache_template:
        for name in ('shader', 'cache'):
            source = a.cache_template.resolve() / name
            if source.is_dir():
                shutil.copytree(source, user / name)
    pad = run / 'pad.txt'
    pad.write_text('')
    # Avoid inheriting an installed launcher's paths or experimental settings.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('BB_', 'SOTC_'))}
    env.update(dict(item.split('=', 1) for item in a.env))
    env.update({
        'SOTC_STREAM_MEMORY': a.stream_memory, 'SOTC_BUFFER_DIAG': '1',
        'SOTC_FPS': '1', 'SOTC_CMD_STATS': '1', 'BB_VBLANK_HZ': '120',
        'SOTC_NEO': '0', 'SOTC_OUTPUT_RES': '1920x1080', 'BB_FSR1': '0',
        'BB_RCAS': '0', 'BB_FULLSCREEN': '0', 'BB_PRESENT_MODE': 'Mailbox',
        'SOTC_MOUSE': '0', 'BB_GPU_USER_DIR': str(user), 'BB_CONFIG': str(run / 'empty.ini'),
        'BB_PAD_FILE': str(pad), 'SOTC_FRAME_CSV': str(run / 'frames.csv'),
        'BB_FRAME_DUMP_TRIGGER': str(run / 'capture.trigger'),
    })
    (run / 'empty.ini').write_text('# Isolated benchmark; no launcher settings.\n')
    if a.update:
        env['SOTC_UPDATE_DIR'] = str(a.update.resolve())
    msys = Path(os.environ.get('MSYS2_ROOT', r'C:\msys64')) / 'clang64' / 'bin'
    env['PATH'] = str(msys) + os.pathsep + env['PATH']
    out = ROOT / 'out'
    exe = out / 'bb-probe.exe'
    command = [str(exe), str(out / 'boot-linked.bin'), '--content-profile', str(out / 'content.bin'),
               '--sotc-cpu', str(out / 'sotc-cpu.bin'), '--patches', str(out / 'patches.bin'),
               *(['--sotc-cmdline', str(out / 'cmdline.bin')] if (out / 'cmdline.bin').is_file() else []),
               '--app0', str(a.game.resolve()),
               '--user', str(user)]
    metadata = {'label': a.label, 'stream_memory': a.stream_memory,
                'seconds': a.seconds, 'warmup': a.warmup, 'measure_end': end,
                'events': events, 'executable_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
                'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'prepared_settings_sha256': {
                    name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                    for name in ('patches.bin', 'cmdline.bin') if (out / name).is_file()},
                'settings': {k: v for k, v in env.items() if k.startswith(('BB_', 'SOTC_'))}}
    (run / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    print(f'RUN_DIR={run}', flush=True)
    gpu = None
    timed_out = False
    process = None
    with (run / 'run.log').open('wb') as log, (run / 'nvidia.csv').open('wb') as gpu_log, \
            (run / 'process.csv').open('w', newline='') as proc_log:
        writer = csv.writer(proc_log)
        writer.writerow(['elapsed_s', 'process_cpu_percent_one_core', 'working_set_bytes'])
        try:
            try:
                gpu = subprocess.Popen(['nvidia-smi', '--query-gpu=timestamp,name,utilization.gpu,memory.used,temperature.gpu,power.draw,clocks.sm,clocks.mem',
                                        '--format=csv', '-lms', '1000'], stdout=gpu_log,
                                       stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            except FileNotFoundError:
                pass
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            observed = psutil.Process(process.pid)
            observed.cpu_percent()
            begin = time.monotonic()
            next_sample = 0
            while process.poll() is None:
                elapsed = time.monotonic() - begin
                if elapsed >= a.seconds:
                    timed_out = True
                    break
                while events and events[0][0] <= elapsed:
                    _, kind, value = events.pop(0)
                    if kind == 'pad':
                        pad.write_text(value)
                    else:
                        (run / 'capture.trigger').touch()
                if elapsed >= next_sample:
                    try:
                        writer.writerow([round(elapsed, 3), observed.cpu_percent(), observed.memory_info().rss])
                        proc_log.flush()
                    except psutil.NoSuchProcess:
                        break
                    next_sample = elapsed + 1
                time.sleep(.05)
        finally:
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
            if gpu:
                gpu.terminate()
                gpu.wait(timeout=15)
    result = {'exit_code': process.returncode if process else None,
              'stopped_at_time_limit': timed_out,
              'timing_basis': 'host presentation calls; not GPU timestamps or display scanout',
              'nvidia_scope': 'whole GPU, not just this process'}
    frames = run / 'frames.csv'
    if frames.is_file():
        result.update(summarize(frames, a.warmup, end))
    (run / 'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)
    return 0 if timed_out else 1


if __name__ == '__main__':
    raise SystemExit(main())
