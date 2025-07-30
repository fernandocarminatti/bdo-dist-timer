# client.spec
# -*- mode: python ; coding: utf-8 -*-
import os

py_excludes = [
    'numpy',
    'scipy',
    'pandas',
    'matplotlib',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtNetwork',
    'PyQt6.QtMultimedia',
    'PyQt6.QtSql',
    'PyQt6.QtTest',
    'tkinter',
]

file_excludes = [
    'libscipy_openblas64',
    '_multiarray_umath',
    'libgfortran',
    'libqt6pdf.so.6',
    'libqt6network.so.6',
    'libicudata.so.73',
    'libgtk-3.so.0',
]

a = Analysis(
    ['client.py'],
    pathex=[],
    binaries=[],
    datas=[('zbuff01.wav', '.')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=py_excludes,
    noarchive=False
)
a.binaries = [
    item for item in a.binaries
    if not any(os.path.basename(item[0]).lower().startswith(ex) for ex in file_excludes)
]
a.datas = [
    item for item in a.datas
    if not any(os.path.basename(item[0]).lower().startswith(ex) for ex in file_excludes)
]
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_dir=None,
    runtime_tmpdir=None,
    console=False,
    icon=None
)