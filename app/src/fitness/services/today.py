import json
from datetime import datetime, timedelta
from fitness.domain.training import elapsed
from fitness.services.weight import WeightService
from fitness.services.nutrition import NutritionService
from fitness.services.plans import PlanService


class TodayService:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock

    def summary(self, day):
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=7)
        days = self.db.execute('SELECT COUNT(DISTINCT local_date) FROM training_set_results WHERE local_date>=? AND local_date<?',
                               (start.isoformat(), end.isoformat())).fetchone()[0]
        sets = list(self.db.execute('SELECT r.id,r.session_id,r.exercise_index,m.slot_id FROM training_set_results r '
                                    'LEFT JOIN py_set_meta m ON m.set_id=r.id WHERE r.local_date=?', (day.isoformat(),)))
        actions = {r['slot_id'] or f"{r['session_id']}:{r['exercise_index']}" for r in sets}
        total = 0
        for row in self.db.execute('SELECT state FROM training_sessions WHERE local_date=?', (day.isoformat(),)):
            state = json.loads(row[0])
            started = int(datetime.fromisoformat(state['runningSince']).timestamp() * 1000) if state.get('runningSince') else None
            total += elapsed(state['elapsedMs'], started, self.clock.now_ms())
        weights = WeightService(self.db, self.clock)
        return dict(weight=weights.read(day), previous_weight=weights.previous(day),
                    plans=PlanService(self.db, self.clock).list_plans(day),
                    nutrition=NutritionService(self.db, self.clock).summary(day),
                    completed_sets=len(sets), completed_exercises=len(actions),
                    training_elapsed_ms=total, week_training_days=days)
