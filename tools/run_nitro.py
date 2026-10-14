#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Launch this fork with local paths and independent saves, without the global launcher."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    config = ROOT / '.local' / 'nitro.json'
    if not config.is_file():
        raise SystemExit('Create .local/nitro.json as described in docs/sotc/NITRO-V15.md')
    settings = json.loads(config.read_text(encoding='utf-8-sig'))
    user = ROOT / '.local' / 'play-user'
    user.mkdir(parents=True, exist_ok=True)
    if not (user / 'savedata').exists() and settings.get('save_template'):
        shutil.copytree(settings['save_template'], user / 'savedata')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SOTC_', 'BB_'))}
    env.update({
        'SOTC_GAME_DIR': settings['game'], 'SOTC_UPDATE_DIR': settings['update'],
        'SOTC_SYS_MODULES': settings['sys_modules'], 'SOTC_USER_DIR': str(user),
        'BB_GPU_USER_DIR': str(user), 'SOTC_MODES': 'fps60', 'SOTC_NEO': '0',
        'SOTC_OUTPUT_RES': '1920x1080', 'BB_FSR1': '0', 'BB_RCAS': '0',
        'BB_FULLSCREEN': '0', 'BB_PRESENT_MODE': 'Mailbox',
        'SOTC_STREAM_MEMORY': settings.get('stream_memory', 'device'),
        'SOTC_BUFFER_DIAG': '1', 'SOTC_FPS': '1', 'BB_VBLANK_HZ': '120',
        'BB_CONFIG': str(ROOT / '.local' / 'nitro.ini'),
    })
    log_path = user / 'last_run.log'
    print('Iniciando o fork experimental em 1080p nativo; 60 fps ainda nao garantidos.', flush=True)
    print(f'Saves desta copia: {user / "savedata"}', flush=True)
    print(f'Log: {log_path}', flush=True)
    with log_path.open('wb') as log:
        result = subprocess.call([sys.executable, str(ROOT / 'sotc.py')], cwd=ROOT, env=env,
                                 stdout=log, stderr=subprocess.STDOUT)
    if result:
        print(f'O jogo encerrou com erro 0x{result & 0xffffffff:08X}. Consulte {log_path}.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
