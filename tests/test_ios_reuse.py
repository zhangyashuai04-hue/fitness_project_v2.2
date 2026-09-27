import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("ios_reuse", Path(__file__).parents[1] / "scripts/reuse-ios-build.py")
reuse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reuse)

def valid_run():
    return {"id": 123, "run_attempt": 2, "conclusion": "success", "head_repository": {"full_name": "owner/repo"}, "path": ".github/workflows/ios-simulator.yml", "event": "workflow_dispatch"}

@pytest.mark.parametrize("change", [
    {"path": ".github/workflows/unrelated.yml"},
    {"event": "pull_request"},
    {"conclusion": "failure"},
    {"head_repository": {"full_name": "fork/repo"}},
])
def test_rejects_untrusted_producer(change):
    run = valid_run(); run.update(change)
    with pytest.raises(ValueError):
        reuse.validate_run(run, "owner/repo")

def test_expected_artifact_matches_exact_run_attempt():
    run = valid_run()
    reuse.validate_run(run, "owner/repo")
    artifacts = [{"name": "ios-simulator-123-1", "expired": False}, {"name": "ios-simulator-123-2", "expired": False}]
    assert reuse.select_artifact(run, artifacts) is artifacts[1]

@pytest.mark.parametrize("artifact", [{"name": "ios-simulator-123-2", "expired": True}, {"name": "ios-simulator-other", "expired": False}])
def test_rejects_expired_or_wrong_artifact(artifact):
    with pytest.raises(ValueError):
        reuse.select_artifact(valid_run(), [artifact])
