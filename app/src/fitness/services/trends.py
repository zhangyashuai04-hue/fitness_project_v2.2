import json
import math
from datetime import datetime
from fitness.services.weight import FACTORS, day_bounds

METRICS = {'weight_max': 'kg', 'reps_total': '次', 'volume_total': 'kg·次',
           'elapsed_total': '秒', 'duration_total': '秒'}
DEFAULTS = {'weighted': 'weight_max', 'bodyweight': 'reps_total', 'timed': 'duration_total'}
ALLOWED = {'weighted': {'weight_max', 'reps_total', 'volume_total', 'elapsed_total'},
           'bodyweight': {'reps_total', 'elapsed_total'}, 'timed': {'duration_total', 'elapsed_total'}}


def valid(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


class TrendService:
    def __init__(self, db):
        self.db = db

    def series(self, start, end, metric=None):
        if end < start or (metric is not None and metric not in METRICS):
            raise ValueError('趋势日期或指标无效')
        records = []
        for row in self.db.execute('SELECT r.*,s.state,m.elapsed_ms,m.exercise_name,m.exercise_kind '
                                    'FROM training_set_results r JOIN training_sessions s ON s.id=r.session_id '
                                    'LEFT JOIN py_set_meta m ON m.set_id=r.id WHERE r.local_date>=? AND r.local_date<=? '
                                    'ORDER BY r.local_date,r.created_at,r.id', (start.isoformat(), end.isoformat())):
            exercise = json.loads(row['state'])['exercises'][row['exercise_index']]
            kind = row['exercise_kind'] or exercise['kind']
            records.append(dict(key=f"exercise:{row['exercise_id']}:{kind}", name=row['exercise_name'] or exercise['name'],
                                kind=kind, day=row['local_date'], identity=row['id'], values=json.loads(row['measurements']), elapsed=row['elapsed_ms']))
        begin, _ = day_bounds(start)
        _, finish = day_bounds(end)
        weights = {}
        for row in self.db.execute('SELECT g.* FROM gym_sets g WHERE g.hidden=0 AND g.created>=? AND g.created<? '
                                    'AND NOT EXISTS (SELECT 1 FROM training_set_results r WHERE r.gym_set_id=g.id) ORDER BY g.created,g.id', (begin, finish)):
            day = datetime.fromtimestamp(row['created']).date().isoformat()
            if row['name'] == 'Weight':
                if row['unit'] in FACTORS and valid(row['weight']) and row['weight'] > 0:
                    weights[day] = dict(day=day, value=row['weight'] * FACTORS[row['unit']], set_ids=[f"gym:{row['id']}"], missing_elapsed=0)
                continue
            kind = 'timed' if row['cardio'] else 'weighted'
            weight = row['weight'] * FACTORS.get(row['unit'], 1)
            records.append(dict(key=f"legacy:{row['name']}:{kind}", name=f"{row['name']}（旧记录）", kind=kind, day=day,
                                identity=f"gym:{row['id']}", values=dict(weight=weight,reps=row['reps'],durationSeconds=row['duration'] * 60), elapsed=None))
        cards = {}
        for record in records:
            kind = record['kind']
            selected = metric or DEFAULTS[kind]
            if selected not in ALLOWED[kind]:
                continue
            card = cards.setdefault(record['key'], dict(key=record['key'],name=record['name'],kind=kind,unit=METRICS[selected],metric=selected,points={}))
            card['name'] = record['name']
            point = card['points'].setdefault(record['day'], dict(day=record['day'],value=None,set_ids=[],missing_elapsed=0))
            point['set_ids'].append(record['identity'])
            point['missing_elapsed'] += int(record['elapsed'] is None)
            values = record['values']
            if selected == 'elapsed_total':
                value = record['elapsed'] / 1000 if record['elapsed'] is not None else None
            elif selected == 'weight_max':
                value = values.get('weight')
            elif selected == 'reps_total':
                value = values.get('reps')
            elif selected == 'duration_total':
                value = values.get('durationSeconds')
            else:
                weight, reps = values.get('weight'), values.get('reps')
                value = weight * reps if valid(weight) and valid(reps) else None
            if valid(value):
                point['value'] = (value if point['value'] is None else max(point['value'],value)) if selected == 'weight_max' else (point['value'] or 0) + value
        result = []
        if weights:
            result.append(dict(key='body_weight',name='体重',kind='body_weight',unit='kg',metric='weight_max',points=[weights[d] for d in sorted(weights)]))
        for key in sorted(cards):
            card = cards[key]
            card['points'] = [card['points'][d] for d in sorted(card['points'])]
            result.append(card)
        return result
