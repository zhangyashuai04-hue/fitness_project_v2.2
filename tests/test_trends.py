from datetime import date
import pytest
from fitness.services.trends import TrendService
from fitness.services.history import HistoryService
from fitness.services.weight import WeightService
from fitness.domain.models import Exercise,Measurements


def test_metrics_and_identity(db,clock):
    h=HistoryService(db,clock)
    day=date(2026,10,1)
    h.add_historical_set(day,Exercise('a','原名','weighted'),Measurements(weight=40,reps=10))
    h.add_historical_set(day,Exercise('a','改名','weighted'),Measurements(weight=50,reps=5),elapsed_ms=0)
    h.add_historical_set(day,Exercise('b','改名','weighted'),Measurements(weight=20,reps=1))
    for metric,expected in [('weight_max',50),('reps_total',15),('volume_total',650)]:
        cards=TrendService(db).series(day,day,metric)
        a=next(c for c in cards if c['key']=='exercise:a:weighted')
        assert a['points'][0]['value']==expected
        assert len(cards)==2
    a=next(c for c in TrendService(db).series(day,day,'elapsed_total') if c['key']=='exercise:a:weighted')
    assert a['points'][0]['value']==0
    assert a['points'][0]['missing_elapsed']==1


def test_mirrors_not_double_counted_and_missing_days_not_zero(db,clock):
    day=date(2026,10,1)
    h=HistoryService(db,clock)
    identity=h.add_historical_set(day,Exercise('a','动作','weighted'),Measurements(weight=10,reps=3))
    cards=TrendService(db).series(day,date(2026,10,3),'reps_total')
    assert sum(p['value'] for c in cards for p in c['points'])==3
    assert len(cards[0]['points'])==1
    h.amend_set(identity,Measurements(weight=12,reps=4))
    assert TrendService(db).series(day,day,'reps_total')[0]['points'][0]['value']==4


def test_weight_series_and_null_elapsed(db,clock):
    day=date(2026,10,1)
    WeightService(db,clock).save(day,75)
    HistoryService(db,clock).add_historical_set(day,Exercise('a','动作','timed'),Measurements(duration_seconds=60))
    cards=TrendService(db).series(day,day,'elapsed_total')
    assert next(c for c in cards if c['key']=='body_weight')['points'][0]['value']==75
    assert next(c for c in cards if c['kind']=='timed')['points'][0]['value'] is None
    assert next(c for c in TrendService(db).series(day,day) if c['kind']=='timed')['points'][0]['value']==60
