import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('verify_release',Path(__file__).parents[1]/'scripts'/'verify-release.py')
release=importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

@pytest.mark.parametrize('package,version,signer',[('wrong',50000,'old'),('com.presley.flexify.localflow',40703,'old'),('com.presley.flexify.localflow',50000,'new')])
def test_bad_identity_rejected(package,version,signer):
    with pytest.raises(ValueError):release.validate_identity(package,version,signer,40703,'old')

def test_correct_identity_passes():
    release.validate_identity('com.presley.flexify.localflow',50000,'old',40703,'old')

def test_missing_python_dependency_rejected(tmp_path):
    import io,zipfile
    packages=io.BytesIO()
    with zipfile.ZipFile(packages,'w') as archive:archive.writestr('flet/__init__.py','')
    apk=tmp_path/'bad.apk'
    with zipfile.ZipFile(apk,'w') as archive:
        archive.writestr('assets/sitepackages.zip',packages.getvalue())
        archive.writestr('lib/arm64-v8a/libpython3.12.so',b'')
    with pytest.raises(ValueError,match='certifi'):release.verify_dependencies(apk)
