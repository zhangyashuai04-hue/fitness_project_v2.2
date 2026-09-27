import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("ios_reuse", Path(__file__).parents[1] / "scripts/reuse-ios-build.py")
reuse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reuse)

def valid_run():
    return {"status": "completed", "id": 123, "run_attempt": 2, "conclusion": "success", "head_repository": {"full_name": "owner/repo"}, "path": ".github/workflows/ios-simulator.yml", "event": "workflow_dispatch"}

@pytest.mark.parametrize("change", [
    {"path": ".github/workflows/unrelated.yml"},
    {"event": "pull_request"},
    {"conclusion": "cancelled"},
    {"head_repository": {"full_name": "fork/repo"}},
])
def test_rejects_untrusted_producer(change):
    run = valid_run(); run.update(change)
    with pytest.raises(ValueError):
        reuse.validate_run(run, "owner/repo", valid_jobs())

def test_expected_artifact_matches_exact_run_attempt():
    run = valid_run()
    reuse.validate_run(run, "owner/repo", valid_jobs())
    artifacts = [{"name": "ios-simulator-123-1", "expired": False}, {"name": "ios-simulator-123-2", "expired": False}]
    assert reuse.select_artifact(run, artifacts) is artifacts[1]

@pytest.mark.parametrize("artifact", [{"name": "ios-simulator-123-2", "expired": True}, {"name": "ios-simulator-other", "expired": False}])
def test_rejects_expired_or_wrong_artifact(artifact):
    with pytest.raises(ValueError):
        reuse.select_artifact(valid_run(), [artifact])


def valid_jobs():
    return [{"name": "build-and-launch", "steps": [{"name": name, "conclusion": "success"} for name in ["Build unsigned simulator app", "Archive simulator app", "Install and launch on simulator"]]}]


def test_reuse_build_when_only_interaction_test_failed():
    run = valid_run(); run["conclusion"] = "failure"
    jobs = valid_jobs(); jobs[0]["steps"].append({"name": "Native iOS interaction tests", "conclusion": "failure"})
    reuse.validate_run(run, "owner/repo", jobs)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_reuse_requires_successful_build_archive_and_launch(index):
    jobs = valid_jobs(); jobs[0]["steps"][index]["conclusion"] = "failure"
    with pytest.raises(ValueError):
        reuse.validate_run(valid_run(), "owner/repo", jobs)
