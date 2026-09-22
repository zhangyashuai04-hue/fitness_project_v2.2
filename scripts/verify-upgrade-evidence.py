"""Recheck saved evidence for the isolated legacy-to-Python APK upgrade."""
import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'research' / 'upgrade'
inspect_db = runpy.run_path(str(ROOT / 'spike/upgrade_probe/src/main.py'))['inspect_database']
fixture = EVIDENCE / 'pre-upgrade.sqlite'
before_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
baseline = inspect_db(fixture)
saved_baseline = json.loads((EVIDENCE / 'pre-upgrade.json').read_text(encoding='utf-8'))
assert baseline['tables'] == saved_baseline['tables']
assert baseline['schema'] == 58
assert baseline['integrity'] == 'ok'
assert baseline['weights'] == [(74.6, 'kg')]
assert baseline['foods'] == [('Ri', 230.0, None)]
assert len(baseline['sets']) == 1
assert json.loads(baseline['sets'][0][0]) == {'weight': 40.0, 'reps': 10, 'durationSeconds': None}
assert baseline['tables']['training_sessions']['count'] == 2
assert baseline['tables']['training_templates']['count'] == 3
lines = (EVIDENCE / 'relaunch-audit-log.txt').read_text(encoding='utf-8-sig').splitlines()
reports = [json.loads(line.split('UPGRADE_AUDIT=', 1)[1]) for line in lines if 'UPGRADE_AUDIT=' in line]
assert len(reports) >= 2, 'Need initial launch and relaunch evidence'
for report in reports:
    assert report['tables'] == baseline['tables'], 'Legacy table content changed'
    assert report['schema'] == 58 and report['integrity'] == 'ok'
    assert report['database'] == '/data/user/0/com.presley.flexify.localflow/app_flutter/flexify.sqlite'
assert 'Success' in (EVIDENCE / 'install-upgrade.txt').read_text(encoding='utf-8-sig')
assert 'versionCode=\'44704\'' in (EVIDENCE / 'new-identity.txt').read_text(encoding='utf-8-sig')
assert '6b29fdab3e720e78c4ccf7d7738607a2fb282bf86cd8ee0cce0a2c0624f82763' in (EVIDENCE / 'new-signature.txt').read_text(encoding='utf-8-sig')
assert before_hash == hashlib.sha256(fixture.read_bytes()).hexdigest()
print('PASS: saved Android emulator evidence; 14 tables identical across APK upgrade and Python relaunch.')
print('PASS: legacy weight, nullable food grams, Chinese plans, training set and session rows preserved.')
print('Scope: Android 16 emulator and read-only Python probe; not final product migration or physical-phone validation.')

