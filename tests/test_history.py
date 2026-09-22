import json
from datetime import date
import pytest
from fitness.services.history import HistoryService
from fitness.domain.models import Exercise,Measurements

def test_edit_preserves_identity_and_mirror(db,clock):
    s=HistoryService(db,clock)
    row=db.execute('SELECT * FROM training_set_results LIMIT 1').fetchone()
    s.amend_set(row['id'],Measurements(weight=42.5,reps=8))
    result=db.execute('SELECT * FROM training_set_results WHERE id=?',(row['id'],)).fetchone()
    assert result['gym_set_id']==row['gym_set_id']
    assert json.loads(result['measurements'])['weight']==42.5
    assert db.execute('SELECT weight FROM gym_sets WHERE id=?',(row['gym_set_id'],)).fetchone()[0]==42.5

def test_backfill_and_explicit_elapsed_clear(db,clock):
    s=HistoryService(db,clock)
    active=db.execute('SELECT id FROM training_sessions WHERE active_slot=1').fetchone()[0]
    identity=s.add_historical_set(date(2026,10,1),Exercise('a','动作','weighted'),Measurements(weight=10,reps=5),elapsed_ms=12000)
    s.amend_set(identity,Measurements(weight=12,reps=5))
    assert db.execute('SELECT elapsed_ms FROM py_set_meta WHERE set_id=?',(identity,)).fetchone()[0]==12000
    s.amend_set(identity,Measurements(weight=12,reps=6),clear_elapsed=True)
    assert db.execute('SELECT elapsed_ms FROM py_set_meta WHERE set_id=?',(identity,)).fetchone()[0] is None
    assert db.execute('SELECT id FROM training_sessions WHERE active_slot=1').fetchone()[0]==active
    assert len(s.sessions(date(2026,10,1)))==1

def test_amend_failure_rolls_back(db,clock):
    s=HistoryService(db,clock)
    row=db.execute('SELECT * FROM training_set_results LIMIT 1').fetchone()
    db.execute("CREATE TEMP TRIGGER fail_mirror BEFORE UPDATE ON gym_sets BEGIN SELECT RAISE(ABORT,'mirror failure'); END")
    with pytest.raises(Exception,match='mirror failure'):s.amend_set(row['id'],Measurements(weight=45,reps=5))
    assert db.execute('SELECT measurements FROM training_set_results WHERE id=?',(row['id'],)).fetchone()[0]==row['measurements']
