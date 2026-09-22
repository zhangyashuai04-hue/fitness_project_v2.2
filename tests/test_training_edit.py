import json
import pytest
from test_training import training,new_plan,complete
from fitness.domain.models import Exercise,Slot,Measurements

def test_editing_time_is_not_set_time(training,new_plan,clock,db):
    snap=training.start(new_plan)
    clock.advance_ms(5000)
    paused=training.begin_edit(snap.id)
    clock.advance_ms(30000)
    edited=training.apply_edit(snap.id,'改名',paused.slots,paused.order,paused.revision)
    assert edited.status=='paused'
    assert edited.set_elapsed_ms==5000
    assert db.execute('SELECT name FROM training_date_plans WHERE id=?',(new_plan,)).fetchone()[0]=='改名'

def test_history_and_template_survive_reorder(training,new_plan,db):
    snap=training.start(new_plan)
    saved=complete(training,snap)
    snap=training.choose(snap.id,'add_set',saved.revision,'add')
    before=[tuple(r) for r in db.execute('SELECT * FROM training_set_results')]
    template=db.execute('SELECT exercises FROM training_templates WHERE id=(SELECT template_id FROM training_date_plans WHERE id=?)',(new_plan,)).fetchone()[0]
    paused=training.begin_edit(snap.id)
    new=Slot('new',Exercise('c','新动作','weighted'),2)
    edited=training.apply_edit(snap.id,'重排',paused.slots+(new,),(paused.order[0],'new',paused.order[1]),paused.revision)
    assert edited.current_slot_id==paused.current_slot_id
    assert [tuple(r) for r in db.execute('SELECT * FROM training_set_results')]==before
    assert db.execute('SELECT exercises FROM training_templates WHERE id=(SELECT template_id FROM training_date_plans WHERE id=?)',(new_plan,)).fetchone()[0]==template

def test_kind_change_creates_new_slot(training,new_plan,db):
    snap=training.start(new_plan)
    saved=complete(training,snap)
    snap=training.choose(snap.id,'add_set',saved.revision,'add')
    paused=training.begin_edit(snap.id)
    old=paused.slots[0]
    replacement=Slot(old.id,Exercise(old.exercise.id,old.exercise.name,'timed'),old.legacy_index)
    edited=training.apply_edit(snap.id,'改类型',(replacement,paused.slots[1]),paused.order,paused.revision)
    assert edited.current_slot_id!=old.id
    assert edited.slots[-1].legacy_index==2
    assert db.execute('SELECT exercise_kind FROM py_set_meta WHERE slot_id=?',(old.id,)).fetchone()[0]=='weighted'
    assert edited.draft==Measurements()

def test_remove_current_discards_only_draft(training,new_plan):
    snap=training.start(new_plan)
    training.save_draft(snap.id,Measurements(weight=40,reps=10))
    paused=training.begin_edit(snap.id)
    edited=training.apply_edit(snap.id,'删除',(paused.slots[1],),(paused.order[1],),paused.revision)
    assert edited.current_slot_id is None
    assert edited.draft==Measurements()
    assert edited.phase=='awaiting_selection'
    next_=training.choose(edited.id,'next_exercise',edited.revision,'next')
    assert next_.current_slot_id==paused.order[1]

def test_remove_all_can_end_and_stale_edit_rejected(training,new_plan):
    snap=training.begin_edit(training.start(new_plan).id)
    edited=training.apply_edit(snap.id,'空计划',(),(),snap.revision)
    with pytest.raises(ValueError): training.apply_edit(snap.id,'旧修改',(),(),snap.revision)
    assert training.end(edited.id,edited.revision,'end').status=='ended'

def test_edit_cancel_preserves_draft_and_duplicate_slot_rejected(training,new_plan,clock):
    snap=training.start(new_plan)
    snap=training.save_draft(snap.id,Measurements(weight=12,reps=3))
    paused=training.begin_edit(snap.id)
    clock.advance_ms(60000)
    assert training.get(snap.id).draft==Measurements(weight=12,reps=3)
    with pytest.raises(ValueError): training.apply_edit(snap.id,'重复',(paused.slots[0],paused.slots[0]),(paused.order[0],paused.order[0]),paused.revision)
    assert training.resume(snap.id).draft==Measurements(weight=12,reps=3)

def test_legacy_completed_set_name_is_frozen_before_rename(db,clock,training):
    active=training.restore_active()
    old=db.execute('SELECT * FROM training_set_results WHERE session_id=? LIMIT 1',(active.id,)).fetchone()
    assert old is not None
    paused=training.begin_edit(active.id)
    slot=paused.slots[old['exercise_index']]
    changed=Slot(slot.id,Exercise(slot.exercise.id,'新名称',slot.exercise.kind),slot.legacy_index)
    slots=tuple(changed if s.id==slot.id else s for s in paused.slots)
    training.apply_edit(paused.id,'改名',slots,paused.order,paused.revision)
    meta=db.execute('SELECT exercise_name,elapsed_ms FROM py_set_meta WHERE set_id=?',(old['id'],)).fetchone()
    assert meta is not None
    assert meta['exercise_name']==slot.exercise.name
    assert meta['elapsed_ms'] is None

def test_change_kind_and_append_in_same_edit(training,new_plan):
    snap=training.begin_edit(training.start(new_plan).id)
    first=snap.slots[0]
    changed=Slot(first.id,Exercise(first.exercise.id,first.exercise.name,'timed'),first.legacy_index)
    added=Slot('new-action',Exercise('new','新动作','weighted'),len(snap.slots))
    edited=training.apply_edit(snap.id,'组合修改',(changed,snap.slots[1],added),(first.id,snap.order[1],added.id),snap.revision)
    assert len(edited.order)==3
    assert len({s.legacy_index for s in edited.slots})==4
