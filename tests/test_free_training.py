import json
import sqlite3
import pytest
from fitness.domain.models import Measurements

def sets(service):
    return [json.loads(r[0]) for r in service.db.execute('SELECT measurements FROM training_set_results ORDER BY created_at,rowid')]

def named(service):
    s=service.start_free()
    return service.rename_current(s.id,'深蹲')

@pytest.mark.parametrize('action',['end','next_action'])
@pytest.mark.parametrize('value,count',[ (Measurements(),0),(Measurements(reps=8),1),(Measurements(weight=0),1),(Measurements(reps=8,weight=40),1)])
def test_leave_saves_any_present_value(free_service,action,value,count):
    s=named(free_service)
    s=free_service.save_draft(s.id,value)
    result=free_service.advance(s.id,action,s.revision,'leave')
    assert len(sets(free_service))==count
    if count:
        assert sets(free_service)[0]['weight']==value.weight
        assert sets(free_service)[0]['reps']==value.reps
    if action=='next_action':
        assert result.action_name=='' and result.draft==Measurements() and result.set_index==0


def test_twenty_sets_inherit_and_idempotency(free_service):
    s=named(free_service)
    assert not s.can_inherit
    for i in range(20):
        s=free_service.save_draft(s.id,Measurements(reps=10,weight=0))
        before=s
        s=free_service.advance(s.id,'next_set',s.revision,str(i))
        assert free_service.advance(before.id,'next_set',before.revision,str(i))==s
    assert len(sets(free_service))==20 and s.set_index==20
    assert free_service.inherit(s.id).draft==Measurements(reps=10,weight=0)
    s=free_service.get(s.id)
    s=free_service.advance(s.id,'next_action',s.revision,'next')
    assert not s.can_inherit
    assert free_service.inherit(s.id).draft==Measurements()


def test_rename_only_current_action(free_service):
    s=named(free_service)
    s=free_service.save_draft(s.id,Measurements(reps=10,weight=20))
    s=free_service.advance(s.id,'next_set',s.revision,'one')
    s=free_service.rename_current(s.id,'杠铃深蹲')
    assert free_service.db.execute('SELECT exercise_name FROM py_set_meta').fetchone()[0]=='杠铃深蹲'
    s=free_service.advance(s.id,'next_action',s.revision,'next')
    free_service.rename_current(s.id,'另一个动作')
    assert free_service.db.execute('SELECT exercise_name FROM py_set_meta').fetchone()[0]=='杠铃深蹲'
    assert free_service.db.execute('SELECT name FROM gym_sets').fetchone()[0]=='深蹲'


def test_incomplete_next_set_and_missing_name_rejected(free_service):
    s=free_service.start_free()
    s=free_service.save_draft(s.id,Measurements(reps=10))
    for action in ('next_set','end'):
        with pytest.raises(ValueError): free_service.advance(s.id,action,s.revision,action)
    assert sets(free_service)==[]


def test_failed_write_does_not_advance(free_service):
    s=named(free_service)
    s=free_service.save_draft(s.id,Measurements(reps=10,weight=20))
    free_service.db.execute("CREATE TRIGGER fail_group BEFORE INSERT ON py_set_meta BEGIN SELECT RAISE(ABORT,'disk failure'); END")
    with pytest.raises(sqlite3.IntegrityError): free_service.advance(s.id,'next_set',s.revision,'one')
    assert free_service.get(s.id)==s and sets(free_service)==[]
    assert free_service.db.execute('SELECT COUNT(*) FROM gym_sets').fetchone()[0]==0


def test_start_returns_existing(free_service):
    first=free_service.start_free()
    assert free_service.start_free().id==first.id
