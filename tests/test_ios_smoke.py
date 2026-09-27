import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("ios_smoke", Path(__file__).parents[1]/"scripts"/"ios-simulator-smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_simulator_selection_ignores_unavailable_and_non_iphone():
    payload = {"devices": {
        "com.apple.CoreSimulator.SimRuntime.iOS-26-5": [
            {"name": "iPhone 16", "udid": "phone", "isAvailable": True},
            {"name": "iPhone 17", "udid": "missing", "isAvailable": False},
            {"name": "iPad Pro", "udid": "tablet", "isAvailable": True}],
        "com.apple.CoreSimulator.SimRuntime.tvOS-27-0": [
            {"name": "iPhone fake", "udid": "wrong", "isAvailable": True}],
        "com.apple.CoreSimulator.SimRuntime.iOS-18-0": [
            {"name": "iPhone 16", "udid": "old", "isAvailable": True}]}}
    assert smoke.choose_device(payload) == "phone"


def test_no_iphone_cannot_report_launch_verified():
    with pytest.raises(RuntimeError, match="NOT verified"):
        smoke.choose_device({"devices": {}})


def test_missing_or_ambiguous_bundle_is_rejected(tmp_path):
    with pytest.raises(RuntimeError): smoke.find_app(tmp_path)
    app = tmp_path / "Runner.app"
    app.mkdir(); (app / "Info.plist").write_bytes(b"test")
    assert smoke.find_app(tmp_path) == app
    other = tmp_path / "Other.app"
    other.mkdir(); (other / "Info.plist").write_bytes(b"test")
    with pytest.raises(RuntimeError): smoke.find_app(tmp_path)
