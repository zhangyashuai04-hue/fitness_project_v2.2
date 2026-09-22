import json
from datetime import datetime
import pytest
from fitness.domain.models import Measurements
from fitness.services.training import TrainingService

@pytest.mark.parametrize('paused',[False,True])
def test_confirmation_cancel_preserves_status_and_time(free_service,clock,paused):
    s=free_service.start_free()
    clock.advance_ms(2000)
    if paused: free_service.pause(s.id)
    before=free_service.begin_confirmation(s.id,'end')
    clock.advance_ms(5000)
    after=free_service.cancel_confirmation(s.id)
    assert after.set_elapsed_ms==before.set_elapsed_ms==2000
    assert after.action_elapsed_ms==2000
    assert after.status==('paused' if paused else 'running')


def test_recovery_cancels_unsubmitted_confirmation(free_service,clock):
    s=free_service.start_free()
    free_service.save_draft(s.id,Measurements(reps=8))
    clock.advance_ms(1000)
    free_service.begin_confirmation(s.id,'next_action')
    clock.advance_ms(7000)
    recovered=TrainingService(free_service.db,clock).restore_free()
    assert recovered.draft.reps==8 and recovered.status=='running'
    assert recovered.set_elapsed_ms==1000
    assert free_service.db.execute('SELECT COUNT(*) FROM training_set_results').fetchone()[0]==0


def test_background_pause_and_next_action_clocks(free_service,clock):
    s=free_service.start_free()
    clock.advance_ms(3000)
    assert TrainingService(free_service.db,clock).restore_free().daily_elapsed_ms==3000
    free_service.pause(s.id)
    clock.advance_ms(9000)
    assert TrainingService(free_service.db,clock).restore_free().set_elapsed_ms==3000
    free_service.resume(s.id)
    clock.advance_ms(2000)
    s=free_service.get(s.id)
    s=free_service.advance(s.id,'next_action',s.revision,'next')
    assert s.action_elapsed_ms==s.set_elapsed_ms==0
    assert s.daily_elapsed_ms==5000


def test_midnight_and_no_write_on_refresh(free_service,clock):
    clock.set_ms(int(datetime(2026,9,22,23,59,59).timestamp()*1000))
    s=free_service.start_free()
    changes=free_service.db.total_changes
    clock.advance_ms(3000)
    s=free_service.get(s.id)
    assert s.daily_elapsed_ms==2000 and s.set_elapsed_ms==3000
    assert free_service.db.total_changes==changes
    clock.advance_ms(-5000)
    s=free_service.get(s.id)
    assert s.set_elapsed_ms==0 and s.daily_elapsed_ms>=0 and s.notice


def test_legacy_saved_choice_not_saved_again(free_service,clock):
    s=free_service.start_free()
    free_service.rename_current(s.id,'旧动作')
    s=free_service.save_draft(s.id,Measurements(reps=10,weight=20))
    s=free_service.complete(s.id,s.revision,'legacy-complete')
    row=free_service.db.execute('SELECT runtime_json FROM py_session_meta WHERE session_id=?',(s.id,)).fetchone()
    runtime=json.loads(row[0]);runtime.pop('free');runtime['version']=1
    free_service.db.execute('UPDATE py_session_meta SET runtime_json=? WHERE session_id=?',(json.dumps(runtime),s.id))
    s=free_service.restore_free()
    assert s.draft==Measurements() and s.set_index==1
    free_service.advance(s.id,'end',s.revision,'end')
    assert free_service.db.execute('SELECT COUNT(*) FROM training_set_results').fetchone()[0]==1

@pytest.mark.parametrize('action',['end','next_action'])
@pytest.mark.parametrize('paused',[False,True])
def test_confirm_transition_keeps_pause_and_excludes_wait(free_service,clock,action,paused):
    s=free_service.start_free()
    free_service.rename_current(s.id,'深蹲')
    free_service.save_draft(s.id,Measurements(weight=0))
    clock.advance_ms(3000)
    if paused: free_service.pause(s.id)
    s=free_service.begin_confirmation(s.id,action)
    clock.advance_ms(9000)
    s=free_service.advance(s.id,action,s.revision,'confirm')
    assert s.daily_elapsed_ms==3000
    assert s.status==('ended' if action=='end' else ('paused' if paused else 'running'))
    assert free_service.db.execute('SELECT elapsed_ms FROM py_set_meta').fetchone()[0]==3000

def test_legacy_timed_moves_to_new_action(free_service):
    s=free_service.start_free()
    row=free_service.db.execute('SELECT state FROM training_sessions WHERE id=?',(s.id,)).fetchone()
    state=json.loads(row[0]); state['exercises'][0]['kind']='timed';state['exercises'][0]['name']='跑步'
    row=free_service.db.execute('SELECT runtime_json FROM py_session_meta WHERE session_id=?',(s.id,)).fetchone()
    runtime=json.loads(row[0]);runtime.pop('free');runtime['slots'][0]['exercise']=state['exercises'][0]
    free_service.db.execute('UPDATE training_sessions SET state=? WHERE id=?',(json.dumps(state),s.id))
    free_service.db.execute('UPDATE py_session_meta SET runtime_json=? WHERE session_id=?',(json.dumps(runtime),s.id))
    restored=free_service.restore_free()
    assert restored.action_name=='' and restored.draft==Measurements()
    assert len(restored.slots)==2 and restored.slots[0].exercise.kind=='timed'
