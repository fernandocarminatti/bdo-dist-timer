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
    'libopenblas',
    '_multiarray_umath',
    'libgfortran',
    
    'qt6pdf.dll',
    'qt6network.dll',
    'qt6webenginecore.dll',
    'qt6webenginewidgets.dll',
    
    'icudt73.dll',
    'd3dcompiler_47.dll',
    'opengl32sw.dll',
]

a = Analysis(
    ['client.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('zbuff01.wav', '.'),
        ('icon.ico', '.'),
        ('style.qss', '.')
    ],
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
    name='OlunSync',
    debug=False,
    bootloader_ignore_signals=False,
    runtime_tmpdir=None,
    console=False,
    icon='icon.ico'
)