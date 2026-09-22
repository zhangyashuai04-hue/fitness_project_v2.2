import json
from datetime import datetime, time
from uuid import uuid4
from fitness.domain.models import Measurements
from fitness.domain.training import measurement_dict
from fitness.domain.validation import validate_measurements
from fitness.services.plans import transaction, exercise_json


def check_elapsed(value):
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError('本组时长必须是非负整数毫秒')


def normalized(kind, value):
    validate_measurements(kind, value)
    return (Measurements(duration_seconds=value.duration_seconds) if kind == 'timed'
            else Measurements(weight=value.weight if kind == 'weighted' else None, reps=value.reps))


class HistoryService:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock

    def sessions(self, day=None):
        query = 'SELECT * FROM training_sessions'
        parameters = ()
        if day is not None:
            query += ' WHERE local_date=?'
            parameters = (day.isoformat(),)
        output = []
        for row in self.db.execute(query + ' ORDER BY local_date DESC,created_at DESC,id', parameters):
            item = dict(row)
            item['state'] = json.loads(item['state'])
            output.append(item)
        return output

    def _details(self, row):
        meta = self.db.execute('SELECT * FROM py_set_meta WHERE set_id=?', (row['id'],)).fetchone()
        if meta:
            return dict(meta)
        session = self.db.execute('SELECT state FROM training_sessions WHERE id=?', (row['session_id'],)).fetchone()
        exercise = json.loads(session[0])['exercises'][row['exercise_index']]
        return dict(set_id=row['id'], slot_id=f"{row['session_id']}:{row['exercise_index']}",
                    elapsed_ms=None, exercise_name=exercise['name'], exercise_kind=exercise['kind'])

    def sets(self, session_id):
        output = []
        for row in self.db.execute('SELECT * FROM training_set_results WHERE session_id=? ORDER BY exercise_index,set_index', (session_id,)):
            item = dict(row)
            item.update(self._details(row))
            item['measurements'] = json.loads(item['measurements'])
            output.append(item)
        return output

    def amend_set(self, set_id, measurements, elapsed_ms=None, clear_elapsed=False):
        check_elapsed(elapsed_ms)
        if clear_elapsed and elapsed_ms is not None:
            raise ValueError('不能同时设置和清除时长')
        with transaction(self.db):
            row = self.db.execute('SELECT * FROM training_set_results WHERE id=?', (set_id,)).fetchone()
            if row is None:
                raise ValueError('训练组不存在')
            meta = self._details(row)
            value = normalized(meta['exercise_kind'], measurements)
            duration = None if clear_elapsed else (elapsed_ms if elapsed_ms is not None else meta['elapsed_ms'])
            self.db.execute('UPDATE training_set_results SET measurements=?,updated_at=? WHERE id=?',
                            (json.dumps(measurement_dict(value)), self.clock.now_ms() // 1000, set_id))
            cursor = self.db.execute('UPDATE gym_sets SET reps=?,weight=?,duration=?,unit=?,cardio=? WHERE id=?',
                                    (value.reps or 0, value.weight or 0, (value.duration_seconds or 0) / 60,
                                     'km' if meta['exercise_kind'] == 'timed' else 'kg', int(meta['exercise_kind'] == 'timed'), row['gym_set_id']))
            if cursor.rowcount != 1:
                raise ValueError('旧训练镜像缺失，修改已取消')
            self.db.execute('INSERT INTO py_set_meta VALUES (?,?,?,?,?) ON CONFLICT(set_id) DO UPDATE SET elapsed_ms=excluded.elapsed_ms',
                            (set_id, meta['slot_id'], duration, meta['exercise_name'], meta['exercise_kind']))

    def add_historical_set(self, day, exercise, measurements, elapsed_ms=None):
        exercise_json('补录', [exercise])
        check_elapsed(elapsed_ms)
        value = normalized(exercise.kind, measurements)
        session, plan, identity = str(uuid4()), str(uuid4()), str(uuid4())
        now = self.clock.now_ms() // 1000
        iso = datetime.combine(day, time.min).isoformat()
        created = int(datetime.fromisoformat(iso).timestamp())
        exercises = json.loads(exercise_json(exercise.name, [exercise]))
        state = dict(name=exercise.name, exercises=exercises, status='ended', startedAt=iso, runningSince=None,
                     elapsedMs=0, exerciseIndex=1, setIndex=0, skipped=[])
        with transaction(self.db):
            self.db.execute('INSERT INTO training_date_plans VALUES (?,?,?,?,?,?,?,?)',
                            (plan, '', exercise.name, json.dumps(exercises, ensure_ascii=False), day.isoformat(), 'completed', now, now))
            self.db.execute('INSERT INTO training_sessions VALUES (?,?,?,?,?,?,?)',
                            (session, plan, None, day.isoformat(), json.dumps(state, ensure_ascii=False), now, now))
            cursor = self.db.execute('INSERT INTO gym_sets(name,reps,weight,unit,created,duration,cardio) VALUES (?,?,?,?,?,?,?)',
                                     (exercise.name, value.reps or 0, value.weight or 0, 'km' if exercise.kind == 'timed' else 'kg',
                                      created, (value.duration_seconds or 0) / 60, int(exercise.kind == 'timed')))
            self.db.execute('INSERT INTO training_set_results VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (identity, session, exercise.id, 0, 0, json.dumps(measurement_dict(value)), cursor.lastrowid, day.isoformat(), now, now))
            self.db.execute('INSERT INTO py_set_meta VALUES (?,?,?,?,?)', (identity, f'{session}:0', elapsed_ms, exercise.name, exercise.kind))
        return identity
