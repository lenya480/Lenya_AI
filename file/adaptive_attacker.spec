# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for adaptive_attacker"""

import os
from pathlib import Path

block_cipher = None

# Parent directory (L1B3RT4S-main) = corpus root
project_root = Path(os.getcwd())

# Collect corpus data files (*.mkd, *.txt, *.json) from project root
corpus_files = []
for f in sorted(project_root.iterdir()):
    if f.is_file() and f.suffix.lower() in ('.mkd', '.txt', '.json') and f.name not in (
        'requirements.txt', 'run.py', 'ATTACKER_README.md'
    ):
        corpus_files.append((str(f), 'corpus'))

datas = corpus_files

# Hidden imports
hiddenimports = [
    'Crypto.Cipher.AES',
    'Crypto.Protocol.KDF',
    'Crypto.Random',
    'fake_useragent',
    'numpy',
    'requests',
    'adaptive_attacker',
    'adaptive_attacker.cli',
    'adaptive_attacker.corpus',
    'adaptive_attacker.crypto',
    'adaptive_attacker.distributed',
    'adaptive_attacker.glitch',
    'adaptive_attacker.manager',
    'adaptive_attacker.obfuscation',
    'adaptive_attacker.payload',
]

a = Analysis(
    ['run.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='adaptive_attacker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
