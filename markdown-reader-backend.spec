# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


a = Analysis(
    ['backend/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'backend.ai_logic',
        'backend.citation_logic',
        'backend.converters',
        'backend.docx_exporter',
        'backend.pdf_exporter',
        'backend.routers.citations',
        'bibtexparser',
        *collect_submodules('markitdown'),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'docling',
        'docling_core',
        'scipy',
        'sklearn',
        'torch',
        'torchaudio',
        'torchvision',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='markdown-reader-backend',
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
