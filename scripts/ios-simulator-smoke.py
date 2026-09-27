"""Install a simulator build and collect launch evidence. No signing or user data."""
import json
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path


def choose_device(payload):
    candidates = []
    for runtime, devices in payload.get("devices", {}).items():
        if ".iOS-" not in runtime:
            continue
        version = tuple(int(n) for n in runtime.split(".iOS-", 1)[1].split("-") if n.isdigit())
        for device in devices:
            if device.get("isAvailable") and device.get("name", "").startswith("iPhone"):
                candidates.append((version, device["name"], device["udid"]))
    if not candidates:
        raise RuntimeError("No available iPhone simulator; build may be valid, launch is NOT verified")
    return max(candidates)[2]


def find_app(directory):
    apps = sorted(p for p in Path(directory).rglob("*.app") if (p / "Info.plist").is_file())
    if len(apps) != 1:
        raise RuntimeError(f"Expected exactly one simulator app, got {len(apps)}")
    return apps[0]


def run(*args, timeout=120, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check, timeout=timeout)


def main(build_dir, evidence_dir):
    evidence = Path(evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    app = find_app(build_dir).resolve()
    with (app / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    bundle = info["CFBundleIdentifier"]
    if bundle != "com.example.fitness.iosprobe":
        raise RuntimeError("Unexpected bundle: refuse to operate on a non-probe app")
    payload = json.loads(run("xcrun", "simctl", "list", "devices", "available", "--json").stdout)
    device = choose_device(payload)
    print(f"Selected simulator {device}; app {app}; bundle {bundle}", flush=True)
    succeeded = False
    try:
        # A selected simulator can already be booted. bootstatus is authoritative.
        run("xcrun", "simctl", "boot", device, check=False)
        run("xcrun", "simctl", "bootstatus", device, "-b", timeout=300)
        run("xcrun", "simctl", "install", device, str(app), timeout=180)
        launch = run("xcrun", "simctl", "launch", device, bundle)
        (evidence / "launch.txt").write_text(launch.stdout + launch.stderr, encoding="utf-8")
        match = re.search(r":\s*(\d+)\s*$", launch.stdout)
        if not match:
            raise RuntimeError("simctl launch did not return an app PID")
        pid = match.group(1)
        time.sleep(20)
        run("xcrun", "simctl", "io", device, "screenshot", str(evidence / "launch.png"))
        live = run("xcrun", "simctl", "spawn", device, "launchctl", "list")
        (evidence / "processes.txt").write_text(live.stdout, encoding="utf-8")
        if not any(line.split() and line.split()[0] == pid for line in live.stdout.splitlines()):
            raise RuntimeError("App process exited after launch; inspect screenshot and simulator log")
        (evidence / "result.json").write_text(json.dumps({"bundle": bundle, "device": device,
            "alive_after_seconds": 20, "visual_review_required": True,
            "note": "Process liveness is not proof that Python startup or UI is correct"}, indent=2), encoding="utf-8")
        succeeded = True
        print("Process survived 20 seconds. Review launch.png for the records page; interactions and physical iPhone are not verified.")
    finally:
        try:
            log = run("xcrun", "simctl", "spawn", device, "log", "show", "--last", "3m", "--style", "compact", "--predicate", 'process == "Runner"', check=False)
            (evidence / "simulator.log").write_text(log.stdout + log.stderr, encoding="utf-8")
        finally:
            if not succeeded or os.environ.get("KEEP_SIMULATOR_BOOTED") != "1":
                run("xcrun", "simctl", "shutdown", device, check=False)


if __name__ == "__main__":
    main(*sys.argv[1:])
