# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('D:\\projet\\Official\\qdrant-manager\\qdrant_distributed\\interface\\image', 'qdrant_distributed/interface/image')]
binaries = [('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\plugin\\authentication_kerberos_client.dll', 'mysql/vendor/plugin'), ('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\plugin\\authentication_ldap_sasl_client.dll', 'mysql/vendor/plugin'), ('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\plugin\\authentication_oci_client.dll', 'mysql/vendor/plugin'), ('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\plugin\\authentication_openid_connect_client.dll', 'mysql/vendor/plugin'), ('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\plugin\\authentication_webauthn_client.dll', 'mysql/vendor/plugin'), ('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\plugin\\mysql_native_password.dll', 'mysql/vendor/plugin'), ('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\libcrypto-3-x64.dll', 'mysql/vendor'), ('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\libsasl.dll', 'mysql/vendor'), ('C:\\Users\\orlando\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\mysql\\vendor\\libssl-3-x64.dll', 'mysql/vendor')]
hiddenimports = ['tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.messagebox', 'tkinter.filedialog', 'dotenv', 'qdrant_client', 'qdrant_client.async_qdrant_client', 'mysql', 'mysql.connector', 'mysql.connector.cursor', 'mysql.connector.pooling', 'mysql.connector.plugins', 'mysql.connector.plugins.mysql_native_password', 'mysql.connector.plugins.caching_sha2_password', 'pymongo', 'numpy', 'numpy.core', 'numpy.core._multiarray_umath']
hiddenimports += collect_submodules('mysql.connector')
tmp_ret = collect_all('mysql.connector')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:\\projet\\Official\\qdrant-manager\\qdrant_distributed\\interface\\launcher.py'],
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
    icon=['D:\\projet\\Official\\qdrant-manager\\qdrant_distributed\\interface\\image\\qdrant-icon-seeklogo.png'],
)
