# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('/home/johfanang/qdrant-shared/qdrant_distributed/interface/image', 'qdrant_distributed/interface/image')]
binaries = []
hiddenimports = ['tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.messagebox', 'tkinter.filedialog', 'dotenv', 'qdrant_client', 'qdrant_client.async_qdrant_client', 'mysql', 'mysql.connector', 'mysql.connector.cursor', 'mysql.connector.pooling', 'mysql.connector.plugins', 'mysql.connector.plugins.mysql_native_password', 'mysql.connector.plugins.caching_sha2_password', 'pymongo', 'numpy', 'numpy.core', 'numpy.core._multiarray_umath']
hiddenimports += collect_submodules('mysql.connector')
tmp_ret = collect_all('mysql.connector')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['/home/johfanang/qdrant-shared/qdrant_distributed/interface/launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas', 'scipy', 'IPython', 'jupyter', 'pytest'],
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
    name='QdrantManager',
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
    icon=['/home/johfanang/qdrant-shared/qdrant_distributed/interface/image/qdrant-icon-seeklogo.png'],
)
