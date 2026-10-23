import importlib.util
import plistlib
from pathlib import Path
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/package-ios-device.py"


def load_module():
    assert SCRIPT.exists(), "Device package validator is not implemented"
    spec = importlib.util.spec_from_file_location("ios_device", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_app(tmp_path, platform="iPhoneOS", executable="Runner"):
    app = tmp_path / "Runner.xcarchive/Products/Applications/Runner.app"
    app.mkdir(parents=True)
    (app / "Info.plist").write_bytes(plistlib.dumps({
        "CFBundleSupportedPlatforms": [platform], "CFBundleExecutable": executable,
        "CFBundleIdentifier": "io.github.zhangyashuai04hue.fitness",
        "CFBundleShortVersionString": "2.2.0", "CFBundleVersion": "1"}))
    (app / "Runner").write_bytes(b"test executable")
    return app


def test_accepts_single_device_archive(tmp_path):
    app = make_app(tmp_path)
    found, info = load_module().validate_app(tmp_path)
    assert found == app
    assert info["CFBundleIdentifier"] == "io.github.zhangyashuai04hue.fitness"


def test_rejects_simulator_archive_even_when_named_like_device(tmp_path):
    make_app(tmp_path, "iPhoneSimulator")
    with pytest.raises(ValueError, match="iPhoneOS"):
        load_module().validate_app(tmp_path)


@pytest.mark.parametrize("executable", ["Missing", "../outside", "/outside"])
def test_rejects_missing_or_unsafe_executable(tmp_path, executable):
    make_app(tmp_path, executable=executable)
    with pytest.raises(ValueError, match="executable"):
        load_module().validate_app(tmp_path)


def test_rejects_missing_or_ambiguous_archive(tmp_path):
    module = load_module()
    with pytest.raises(ValueError, match="one"):
        module.validate_app(tmp_path)
    make_app(tmp_path)
    extra = tmp_path / "Other.xcarchive/Products/Applications/Other.app"
    extra.mkdir(parents=True)
    with pytest.raises(ValueError, match="one"):
        module.validate_app(tmp_path)
