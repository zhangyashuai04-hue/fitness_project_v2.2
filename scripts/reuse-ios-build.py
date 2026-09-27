"""Reuse a successful simulator artifact only when app sources match exactly."""
import hashlib
import io
import json
import os
import subprocess
import tarfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    run_id = os.environ["REUSE_RUN"]
    if not run_id.isdecimal():
        raise ValueError("Run ID must be numeric")
    base = "https://api.github.com/repos/" + repo
    headers = {"Authorization": "Bearer " + os.environ["GH_TOKEN"], "User-Agent": "fitness-ios-test"}
    def get(path):
        with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=60) as response:
            return json.load(response)
    run = get("/actions/runs/" + run_id)
    if run["conclusion"] != "success" or run["head_repository"]["full_name"] != repo:
        raise ValueError("Only successful builds from this repository may be reused")
    sha = run["head_sha"]
    subprocess.run(["git", "diff", "--exit-code", sha, "HEAD", "--", "app", "requirements-build.lock.txt"], check=True)
    artifacts = get("/actions/runs/" + run_id + "/artifacts")["artifacts"]
    choices = [a for a in artifacts if a["name"].startswith("ios-simulator-") and not a["expired"]]
    if len(choices) != 1:
        raise ValueError("Expected one unexpired simulator artifact")
    artifact = choices[0]
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    try:
        urllib.request.build_opener(NoRedirect).open(urllib.request.Request(artifact["archive_download_url"], headers=headers), timeout=60)
        raise RuntimeError("Expected artifact storage redirect")
    except urllib.error.HTTPError as exc:
        if exc.code != 302: raise
        location = exc.headers["Location"]
    # No GitHub Authorization header is forwarded to storage.
    with urllib.request.urlopen(location, timeout=120) as response:
        content = response.read()
    if "sha256:" + hashlib.sha256(content).hexdigest() != artifact["digest"]:
        raise ValueError("Artifact checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        tar_bytes = archive.read("fitness-ios-simulator.tar.gz")
    destination = Path("app/build"); destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as archive:
        archive.extractall(destination, filter="data")
    Path("evidence/reused-build.json").write_text(json.dumps({"run_id": run_id, "source_sha": sha, "artifact_id": artifact["id"], "app_sources_unchanged": True}, indent=2))
    print("Reused verified build from", run_id, "with unchanged app sources")


if __name__ == "__main__": main()
