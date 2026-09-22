from datetime import timedelta
from fitness.domain.models import Measurements

def api():
    from fitness.services import records
    return records

def finish(service, reps=8, weight=None):
    s=service.start_free()
    service.rename_current(s.id,'深蹲')
    s=service.save_draft(s.id,Measurements(reps=reps,weight=weight))
    return service.advance(s.id,'end',s.revision,s.id)

def test_missing_values_and_timed():
    f=api().format_set
    assert f(Measurements(reps=8))=='8次 × —'
    assert f(Measurements(reps=8,weight=0))=='8次 × 0kg'
    assert f(Measurements(weight=45))=='— × 45kg'
    assert f(Measurements(duration_seconds=120))=='120秒'

def test_week_counts_sessions_not_days(free_service,clock):
    finish(free_service);finish(free_service)
    finish(free_service,None,None)
    free_service.start_free()
    records=api().RecordsService(free_service.db,clock)
    assert records.week_count(clock.today())==2
    assert records.week_count(clock.today()+timedelta(days=7))==0
    assert records.week_count(clock.today()-timedelta(days=7))==0

def test_same_named_actions_separate_read_only(free_service,clock):
    s=free_service.start_free()
    for i in range(2):
        free_service.rename_current(s.id,'深蹲')
        s=free_service.save_draft(s.id,Measurements(reps=8))
        s=free_service.advance(s.id,'next_action' if i==0 else 'end',s.revision,str(i))
    changes=free_service.db.total_changes
    rows=api().RecordsService(free_service.db,clock).day_sessions(clock.today())
    assert len(rows)==1 and len(rows[0]['actions'])==2
    assert rows[0]['actions'][0]['sets'][0]['weight'] is None
    assert free_service.db.total_changes==changes
