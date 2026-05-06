# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['backend/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'markdown_reader.logic',
        'markdown_reader.plugins.docx_exporter',
        'markdown_reader.plugins.pdf_exporter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'docling',
        'docling_core',
        'pandas',
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
