"""
PyInstaller hook for mysql.connector
This ensures all plugins and native libraries are included
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect all submodules
hiddenimports = collect_submodules('mysql.connector')

# Collect data files (plugins, etc.)
datas = collect_data_files('mysql.connector')

# Collect dynamic libraries (DLLs, .so files)
binaries = collect_dynamic_libs('mysql.connector')

# Explicitly add plugin modules
hiddenimports += [
    'mysql.connector.plugins',
    'mysql.connector.plugins.mysql_native_password',
    'mysql.connector.plugins.caching_sha2_password',
]

