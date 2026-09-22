import json
import pytest
from fitness.domain.models import Measurements
from fitness.services.training import TrainingService
from fitness.services.plans import PlanService
from fitness.domain.models import Exercise

@pytest.fixture
def training(db,clock):
    return TrainingService(db,clock)

@pytest.fixture
def new_plan(db,clock,training):
    active=training.restore_active()
    if active: training.end(active.id,active.revision,'fixture-end')
    s=PlanService(db,clock)
    template=s.save_template('测试',[Exercise('a','深蹲','weighted'),Exercise('b','划船','weighted')])
    return s.schedule(template,clock.today())

def complete(training,snap,identity='complete'):
    snap=training.save_draft(snap.id,Measurements(weight=40,reps=10))
    return training.complete(snap.id,snap.revision,identity)

def test_repeated_completion_and_no_automatic_inherit(training,new_plan,clock,db):
    snap=training.start(new_plan)
    assert snap.draft.weight is None
    snap=training.save_draft(snap.id,Measurements(weight=40,reps=10))
    clock.advance_ms(12000)
    saved=training.complete(snap.id,snap.revision,'first')
    assert training.complete(snap.id,snap.revision,'first')==saved
    assert saved.phase=='awaiting_choice'
    assert saved.set_elapsed_ms==12000
    assert db.execute('SELECT COUNT(*) FROM training_set_results WHERE session_id=?',(snap.id,)).fetchone()[0]==1
    next_=training.choose(saved.id,'add_set',saved.revision,'add')
    assert next_.draft.weight is None
    assert training.inherit(next_.id).draft==Measurements(weight=40,reps=10)

def test_unlimited_sets_and_next_action(training,new_plan,db):
    snap=training.start(new_plan)
    for i in range(101):
        saved=complete(training,snap,f'c{i}')
        snap=training.choose(saved.id,'add_set' if i<100 else 'next_exercise',saved.revision,f'n{i}')
    assert snap.set_index==0
    assert snap.current_slot_id==snap.order[1]
    with pytest.raises(ValueError): training.inherit(snap.id)
    assert db.execute('SELECT COUNT(*) FROM training_set_results WHERE session_id=?',(snap.id,)).fetchone()[0]==101
    saved=complete(training,snap,'last')
    with pytest.raises(ValueError): training.choose(saved.id,'next_exercise',saved.revision,'invalid-next')
    ended=training.choose(saved.id,'end',saved.revision,'end')
    assert ended.status=='ended'
    assert training.restore_active() is None

def test_stale_revision_and_invalid_input(training,new_plan):
    snap=training.start(new_plan)
    with pytest.raises(ValueError): training.complete(snap.id,snap.revision,'empty')
    current=training.save_draft(snap.id,Measurements(weight=0,reps=10))
    with pytest.raises(ValueError): training.complete(snap.id,snap.revision,'stale')
    assert training.complete(current.id,current.revision,'valid').phase=='awaiting_choice'

def test_transaction_failure_rolls_back_mirror(training,new_plan,db):
    snap=training.start(new_plan)
    snap=training.save_draft(snap.id,Measurements(weight=40,reps=10))
    before=db.execute('SELECT COUNT(*) FROM gym_sets').fetchone()[0]
    db.execute("CREATE TEMP TRIGGER fail_meta BEFORE INSERT ON py_set_meta BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(Exception,match='test failure'): training.complete(snap.id,snap.revision,'failed')
    assert db.execute('SELECT COUNT(*) FROM gym_sets').fetchone()[0]==before
    assert training.get(snap.id).revision==snap.revision
    assert training.get(snap.id).phase=='collecting'

def test_second_service_cannot_start_other_plan(training,new_plan,db,clock):
    training.start(new_plan)
    s=PlanService(db,clock)
    other=s.schedule(s.list_templates()[0]['id'],clock.today())
    with pytest.raises(ValueError): TrainingService(db,clock).start(other)

def test_timed_mirror_keeps_legacy_minutes(training,new_plan,db,clock):
    s=PlanService(db,clock)
    timed=s.schedule(s.save_template('计时',[Exercise('timed','平板','timed')]),clock.today())
    snap=training.start(timed)
    snap=training.save_draft(snap.id,Measurements(weight=99,reps=99,duration_seconds=90))
    training.complete(snap.id,snap.revision,'timed')
    row=db.execute('SELECT g.duration,g.unit,r.measurements FROM gym_sets g JOIN training_set_results r ON r.gym_set_id=g.id WHERE r.session_id=?',(snap.id,)).fetchone()
    assert row['duration']==1.5
    assert row['unit']=='km'
    assert json.loads(row['measurements'])==dict(weight=None,reps=None,durationSeconds=90)

def test_separate_connection_cannot_claim_second_active(training,new_plan,db,clock):
    from fitness.storage.database import open_database
    training.start(new_plan)
    s=PlanService(db,clock)
    other=s.schedule(s.list_templates()[0]['id'],clock.today())
    path=db.execute('PRAGMA database_list').fetchone()[2]
    second=open_database(path)
    try:
        with pytest.raises(ValueError): TrainingService(second,clock).start(other)
        assert second.execute('SELECT COUNT(*) FROM training_sessions WHERE active_slot=1').fetchone()[0]==1
    finally:
        second.close()
