from datetime import date
from fitness.services.today import TodayService
from fitness.services.history import HistoryService
from fitness.domain.models import Exercise,Measurements

def test_week_days_come_from_sets_not_plans(db,clock):
    history=HistoryService(db,clock)
    for day in [date(2026,10,4),date(2026,10,5),date(2026,10,5),date(2026,10,6)]:
        history.add_historical_set(day,Exercise('a','动作','weighted'),Measurements(weight=10,reps=5))
    summary=TodayService(db,clock).summary(date(2026,10,6))
    assert summary['week_training_days']==2
    assert summary['completed_sets']==1
    assert summary['completed_exercises']==1
    assert summary['training_elapsed_ms']==0
    assert summary['weight'] is None
