# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for adaptive_attacker GUI"""

import os
from pathlib import Path

block_cipher = None
project_root = Path(os.getcwd())

corpus_files = []
for f in sorted(project_root.iterdir()):
    if f.is_file() and f.suffix.lower() in ('.mkd', '.txt', '.json') and f.name not in (
        'requirements.txt', 'run.py', 'ATTACKER_README.md'
    ):
        corpus_files.append((str(f), 'corpus'))

datas = corpus_files

hiddenimports = [
    'Crypto.Cipher.AES',
    'Crypto.Protocol.KDF',
    'Crypto.Random',
    'fake_useragent',
    'numpy',
    'requests',
    'tkinter',
    'tkinter.ttk',
    'tkinter.scrolledtext',
    'tkinter.filedialog',
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
    ['gui.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests', 'matplotlib', 'PIL', 'PyQt5', 'PySide2'],
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
    name='adaptive_attacker_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
