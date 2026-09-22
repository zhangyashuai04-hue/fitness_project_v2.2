import json
from datetime import date
import pytest
from fitness.services.plans import PlanService
from fitness.domain.models import Exercise

def test_hide_preserves_history_and_template(db,clock):
    service=PlanService(db,clock)
    row=db.execute('SELECT plan_id FROM training_sessions WHERE active_slot IS NULL LIMIT 1').fetchone()
    before=[tuple(x) for x in db.execute('SELECT * FROM training_sessions')]
    service.hide_plan(row[0]);service.hide_plan(row[0])
    assert [tuple(x) for x in db.execute('SELECT * FROM training_sessions')]==before
    assert row[0] not in [p['id'] for p in service.list_plans(date(2026,9,20))]
    assert len(service.list_templates())==3

def test_cannot_hide_active_plan(db,clock):
    row=db.execute('SELECT plan_id FROM training_sessions WHERE active_slot=1').fetchone()
    with pytest.raises(ValueError): PlanService(db,clock).hide_plan(row[0])

def test_schedule_copies_template_and_ignores_fixed_set_count(db,clock):
    s=PlanService(db,clock)
    template=s.save_template('测试',[Exercise('a','同名','weighted'),Exercise('b','同名','bodyweight')])
    plan=s.schedule(template,date(2026,10,1))
    s.save_template('改模板',[Exercise('c','另一动作','timed')],template)
    found=s.list_plans(date(2026,10,1))[0]
    assert found['id']==plan
    assert len(found['exercises'])==2
    assert found['exercises'][0]['id']=='a'
    s.skip_plan(plan);s.skip_plan(plan)
    assert s.list_plans(date(2026,10,1))[0]['status']=='skipped'

def test_invalid_template_and_active_edit_rejected(db,clock):
    s=PlanService(db,clock)
    with pytest.raises(ValueError):s.save_template(' ',[])
    with pytest.raises(ValueError):s.save_template('x',[Exercise('a','x','unknown')])
    plan=db.execute('SELECT plan_id FROM training_sessions WHERE active_slot=1').fetchone()[0]
    with pytest.raises(ValueError):s.edit_plan(plan,'x',[Exercise('a','x','weighted')])
