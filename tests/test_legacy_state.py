import json
from fitness.storage.legacy import adapt_legacy_session

def test_duplicate_exercise_has_stable_distinct_slots(db):
    row=dict(db.execute('SELECT * FROM training_sessions WHERE active_slot=1').fetchone())
    state=json.loads(row['state']);state['exercises'][1]=dict(state['exercises'][0]);row['state']=json.dumps(state)
    first=adapt_legacy_session(row,[],1000)
    second=adapt_legacy_session(row,[],2000)
    assert first['order']==second['order']
    assert first['order'][0]!=first['order'][1]
    assert first['draft']=={'weight':None,'reps':None,'durationSeconds':None}
    assert first['set_started_ms'] is None
    assert first['notice']

def test_ended_index_at_end_is_valid(db):
    row=dict(db.execute('SELECT * FROM training_sessions LIMIT 1').fetchone())
    state=json.loads(row['state']);state['status']='ended';state['exerciseIndex']=len(state['exercises']);row['state']=json.dumps(state)
    result=adapt_legacy_session(row,[],1000)
    assert result['current_slot_id'] is None

def test_running_old_group_does_not_invent_elapsed(db):
    row=dict(db.execute('SELECT * FROM training_sessions WHERE active_slot=1').fetchone())
    state=json.loads(row['state']);state['status']='running';row['state']=json.dumps(state)
    result=adapt_legacy_session(row,[],1000)
    assert result['set_elapsed_ms']==0
    assert result['set_started_ms']==1000

def test_old_active_at_end_can_finish_without_restarting_actions(db):
    row=dict(db.execute('SELECT * FROM training_sessions WHERE active_slot=1').fetchone())
    state=json.loads(row['state']);state['exerciseIndex']=len(state['exercises']);row['state']=json.dumps(state)
    result=adapt_legacy_session(row,[],1000)
    assert result['phase']=='awaiting_selection'
    assert result['order']==[]
