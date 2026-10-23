"""Package a device xcarchive for later signing; this does not install or sign it."""
import argparse
import hashlib
import json
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def validate_app(root):
    apps = list(Path(root).glob("*.xcarchive/Products/Applications/*.app"))
    if len(apps) != 1:
        raise ValueError("Expected exactly one app in a device xcarchive")
    app = apps[0]
    info = plistlib.loads((app / "Info.plist").read_bytes())
    if info.get("CFBundleSupportedPlatforms") != ["iPhoneOS"]:
        raise ValueError("Expected iPhoneOS, not an iOS Simulator app")
    name = info.get("CFBundleExecutable", "")
    if not name or Path(name).name != name or not (app / name).is_file():
        raise ValueError("Missing or unsafe app executable")
    return app, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    app, info = validate_app(args.archive_dir)
    executable = app / info["CFBundleExecutable"]
    architecture = subprocess.check_output(["xcrun", "lipo", "-archs", str(executable)], text=True).strip()
    build = subprocess.check_output(["xcrun", "vtool", "-show-build", str(executable)], text=True)
    if architecture != "arm64" or not re.search(r"platform\s+IOS\s*$", build, re.MULTILINE):
        raise ValueError("Expected arm64 iOS device executable")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    # Apple's ditto preserves bundle permissions and symlinks inside the ZIP.
    with tempfile.TemporaryDirectory() as temp:
        payload = Path(temp) / "Payload"
        payload.mkdir()
        shutil.copytree(app, payload / app.name, symlinks=True)
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(payload), str(args.output.resolve())], check=True)
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip() is not None:
            raise ValueError("IPA ZIP integrity failed")
        archive.getinfo(f"Payload/{app.name}/Info.plist")
    result = {"bundle_id": info["CFBundleIdentifier"], "version": info["CFBundleShortVersionString"],
              "build": info["CFBundleVersion"], "minimum_ios": info.get("MinimumOSVersion"),
              "architecture": architecture, "platform": "iPhoneOS", "requires_signing": True,
              "physical_device_tested": False, "bytes": args.output.stat().st_size,
              "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}
    args.output.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".build.txt").write_text(build, encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
