"""Read-only projections. Saved result JSON, not legacy zero defaults, is authoritative."""
import json
from datetime import timedelta
from fitness.domain.models import Measurements
from fitness.services.history import HistoryService


def format_set(value: Measurements) -> str:
    if value.duration_seconds is not None:
        return f'{value.duration_seconds:g}秒'
    reps=f'{value.reps}次' if value.reps is not None else '—'
    weight=f'{value.weight:g}kg' if value.weight is not None else '—'
    return f'{reps} × {weight}'


class RecordsService:
    def __init__(self,db,clock):
        self.db,self.clock=db,clock
        self.history=HistoryService(db,clock)

    def day_sessions(self,day):
        output=[]
        # Result date matters for a session crossing midnight.
        sessions=self.db.execute('SELECT DISTINCT s.* FROM training_sessions s JOIN training_set_results r ON r.session_id=s.id WHERE r.local_date=? ORDER BY s.created_at,s.id',(day.isoformat(),)).fetchall()
        for session in sessions:
            groups={}
            for row in self.history.sets(session['id']):
                if row['local_date']!=day.isoformat(): continue
                key=row['slot_id']
                group=groups.setdefault(key,dict(slot_id=key,name=row['exercise_name'],sets=[]))
                m=row['measurements']
                group['sets'].append(dict(reps=m.get('reps'),weight=m.get('weight'),duration_seconds=m.get('durationSeconds'),kind=row['exercise_kind']))
            output.append(dict(session_id=session['id'],status=json.loads(session['state'])['status'],actions=list(groups.values())))
        return output

    def week_count(self,day):
        start=day-timedelta(days=day.weekday())
        end=start+timedelta(days=7)
        rows=self.db.execute('SELECT s.state FROM training_sessions s WHERE s.local_date>=? AND s.local_date<? AND EXISTS (SELECT 1 FROM training_set_results r WHERE r.session_id=s.id)',(start.isoformat(),end.isoformat()))
        return sum(json.loads(r[0])['status']=='ended' for r in rows)
