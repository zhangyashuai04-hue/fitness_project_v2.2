"""Fail a probe build if its embedded Python dependencies are missing."""
import io
import sys
import zipfile
from pathlib import Path

apk = Path(sys.argv[1])
with zipfile.ZipFile(apk) as archive:
    with zipfile.ZipFile(io.BytesIO(archive.read('assets/sitepackages.zip'))) as packages:
        names = packages.namelist()
        for required in ('certifi/', 'flet/'):
            if not any(name.startswith(required) for name in names):
                raise SystemExit(f'FAIL: {apk.name} has no {required} in sitepackages.zip')
        print(f'PASS: {apk.name}: {len(names)} Python dependency entries; required packages present.')
