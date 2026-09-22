import argparse
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

PACKAGE='com.presley.flexify.localflow'


def validate_identity(package,version,signer,old_version,old_signer):
    if package!=PACKAGE:raise ValueError('Package does not match installed app')
    if version<=old_version:raise ValueError('Final versionCode must increase')
    if signer.lower()!=old_signer.lower():raise ValueError('Signing certificate mismatch')


def inspect(apk,tools):
    badging=subprocess.check_output([str(tools/'aapt.exe'),'dump','badging',str(apk)],text=True,encoding='utf-8')
    signature=subprocess.check_output([str(tools/'apksigner.bat'),'verify','--print-certs',str(apk)],text=True,encoding='utf-8')
    package=re.search(r"package: name='([^']+)' versionCode='(\d+)'",badging)
    signer=re.search(r'Signer #1 certificate SHA-256 digest: (\w+)',signature)
    minimum=re.search(r"sdkVersion:'(\d+)'",badging)
    if not package or not signer or not minimum:raise ValueError('Cannot read APK identity')
    return dict(package=package[1],version=int(package[2]),signer=signer[1],min_sdk=int(minimum[1]))


def verify_dependencies(apk):
    with zipfile.ZipFile(apk) as archive:
        with zipfile.ZipFile(io.BytesIO(archive.read('assets/sitepackages.zip'))) as packages:
            names=packages.namelist()
            for prefix in ('certifi/','flet/','flet_charts/'):
                if not any(name.startswith(prefix) for name in names):raise ValueError('Missing Python dependency: '+prefix)
        abis=sorted({name.split('/')[1] for name in archive.namelist() if name.startswith('lib/') and name.endswith('/libpython3.12.so')})
        # The embedded runtime may use another Python minor; check generic runtime too.
        if not abis:
            abis=sorted({name.split('/')[1] for name in archive.namelist() if name.startswith('lib/') and '/libpython' in name})
        if not abis:raise ValueError('Python native runtime missing')
    return abis


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('apk',type=Path);parser.add_argument('old_apk',type=Path)
    parser.add_argument('--build-tools',type=Path,required=True)
    args=parser.parse_args()
    old=inspect(args.old_apk,args.build_tools);current=inspect(args.apk,args.build_tools)
    validate_identity(current['package'],current['version'],current['signer'],old['version'],old['signer'])
    current.update(abis=verify_dependencies(args.apk),bytes=args.apk.stat().st_size,sha256=hashlib.sha256(args.apk.read_bytes()).hexdigest())
    print(json.dumps(current,indent=2))


if __name__=='__main__':main()
