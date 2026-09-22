import json
from dataclasses import asdict
from datetime import datetime
from uuid import uuid4
from fitness.domain.models import Measurements
from fitness.domain.training import elapsed, measurement_dict, measurement_from, snapshot, snapshot_from
from fitness.domain.validation import validate_measurements
from fitness.storage.legacy import adapt_legacy_session
from fitness.services.plans import transaction


class TrainingService:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock

    def _load(self, identity):
        row = self.db.execute('SELECT * FROM training_sessions WHERE id=?', (identity,)).fetchone()
        if row is None:
            raise ValueError('训练不存在')
        state = json.loads(row['state'])
        meta = self.db.execute('SELECT * FROM py_session_meta WHERE session_id=?', (identity,)).fetchone()
        if meta:
            runtime, revision = json.loads(meta['runtime_json']), meta['revision']
        else:
            runtime = adapt_legacy_session(row, [], self.clock.now_ms())
            revision = 0
            self.db.execute('INSERT INTO py_session_meta VALUES (?,?,?)', (identity, revision, json.dumps(runtime, ensure_ascii=False)))
        return row, state, runtime, revision

    def _snapshot(self, row, state, runtime, revision):
        return snapshot(row['id'], state, runtime, revision, self.clock.now_ms())

    def get(self, session_id):
        with transaction(self.db):
            return self._snapshot(*self._load(session_id))

    def restore_active(self):
        row = self.db.execute('SELECT id FROM training_sessions WHERE active_slot=1').fetchone()
        return self.get(row['id']) if row else None

    def start(self, plan_id):
        with transaction(self.db):
            active = self.db.execute('SELECT id,plan_id FROM training_sessions WHERE active_slot=1').fetchone()
            if active:
                if active['plan_id'] == plan_id:
                    return self._snapshot(*self._load(active['id']))
                raise ValueError('请先结束当前训练')
            plan = self.db.execute('SELECT p.* FROM training_date_plans p LEFT JOIN py_plan_meta m ON p.id=m.plan_id WHERE p.id=? AND COALESCE(m.hidden,0)=0', (plan_id,)).fetchone()
            if plan is None or plan['status'] != 'pending':
                raise ValueError('计划无法开始')
            exercises = json.loads(plan['exercises'])
            if not exercises:
                raise ValueError('请先添加动作')
            identity, now = str(uuid4()), self.clock.now_ms()
            iso = datetime.fromtimestamp(now / 1000).isoformat()
            state = dict(name=plan['name'], exercises=exercises, status='running', startedAt=iso,
                         runningSince=iso, elapsedMs=0, exerciseIndex=0, setIndex=0, skipped=[])
            self.db.execute('INSERT INTO training_sessions VALUES (?,?,?,?,?,?,?)',
                            (identity, plan_id, 1, plan['local_date'], json.dumps(state, ensure_ascii=False), now // 1000, now // 1000))
            row, state, runtime, revision = self._load(identity)
            runtime['notice'] = None
            self.db.execute('UPDATE py_session_meta SET runtime_json=? WHERE session_id=?', (json.dumps(runtime, ensure_ascii=False), identity))
            self.db.execute("UPDATE training_date_plans SET status='active',updated_at=? WHERE id=?", (now // 1000, plan_id))
            return self._snapshot(row, state, runtime, revision)

    def _store(self, row, state, runtime, revision):
        revision += 1
        slot = self._slot(runtime) if runtime['current_slot_id'] else None
        state['exerciseIndex'] = slot['legacy_index'] if slot else len(state['exercises'])
        state['setIndex'] = runtime['set_index']
        now = self.clock.now_ms() // 1000
        self.db.execute('UPDATE training_sessions SET state=?,active_slot=?,updated_at=? WHERE id=?',
                        (json.dumps(state, ensure_ascii=False), None if state['status'] == 'ended' else 1, now, row['id']))
        self.db.execute('UPDATE py_session_meta SET revision=?,runtime_json=? WHERE session_id=?',
                        (revision, json.dumps(runtime, ensure_ascii=False), row['id']))
        return self._snapshot(row, state, runtime, revision)

    @staticmethod
    def _slot(runtime):
        return next(s for s in runtime['slots'] if s['id'] == runtime['current_slot_id'])

    @staticmethod
    def _collecting(state, runtime):
        if state['status'] == 'ended' or runtime['phase'] != 'collecting' or not runtime['current_slot_id']:
            raise ValueError('当前不能填写训练组')

    def save_draft(self, session_id, measurements):
        with transaction(self.db):
            row, state, runtime, revision = self._load(session_id)
            self._collecting(state, runtime)
            # Empty and partial values are durable drafts; completion validates them.
            runtime['draft'] = measurement_dict(measurements)
            return self._store(row, state, runtime, revision)

    def _command(self, session_id, expected_revision, command_id, operation):
        if not isinstance(command_id, str) or not command_id:
            raise ValueError('缺少操作标识')
        with transaction(self.db):
            previous = self.db.execute('SELECT result_json FROM py_commands WHERE session_id=? AND command_id=?', (session_id, command_id)).fetchone()
            if previous:
                return snapshot_from(json.loads(previous[0]))
            row, state, runtime, revision = self._load(session_id)
            if revision != expected_revision or state['status'] == 'ended':
                raise ValueError('训练状态已更新，请刷新后重试')
            operation(row, state, runtime)
            result = self._store(row, state, runtime, revision)
            self.db.execute('INSERT INTO py_commands VALUES (?,?,?)', (session_id, command_id, json.dumps(asdict(result), ensure_ascii=False)))
            return result

    def _stop_set_clock(self, runtime):
        started = runtime['set_started_ms']
        now = self.clock.now_ms()
        if started is not None and now < started:
            runtime['notice'] = '系统时间发生变化，本组计时请核对。'
            runtime['clock_warning'] = True
        runtime['set_elapsed_ms'] = elapsed(runtime['set_elapsed_ms'], started, now)
        runtime['set_started_ms'] = None

    def complete(self, session_id, expected_revision, command_id):
        def operation(row, state, runtime):
            self._collecting(state, runtime)
            if state['status'] != 'running':
                raise ValueError('请先恢复训练')
            slot = self._slot(runtime)
            exercise = slot['exercise']
            value = measurement_from(runtime['draft'])
            validate_measurements(exercise['kind'], value)
            value = (Measurements(duration_seconds=value.duration_seconds) if exercise['kind'] == 'timed'
                     else Measurements(weight=value.weight if exercise['kind'] == 'weighted' else None, reps=value.reps))
            runtime['draft'] = measurement_dict(value)
            self._stop_set_clock(runtime)
            now = self.clock.now_ms() // 1000
            cursor = self.db.execute('INSERT INTO gym_sets(name,reps,weight,unit,created,duration,cardio) VALUES (?,?,?,?,?,?,?)',
                                     (exercise['name'], value.reps or 0, value.weight or 0, 'km' if exercise['kind'] == 'timed' else 'kg', now,
                                      (value.duration_seconds or 0) / 60, int(exercise['kind'] == 'timed')))
            identity = str(uuid4())
            self.db.execute('INSERT INTO training_set_results VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (identity, row['id'], exercise['id'], slot['legacy_index'], runtime['set_index'],
                             json.dumps(runtime['draft']), cursor.lastrowid, row['local_date'], now, now))
            self.db.execute('INSERT INTO py_set_meta VALUES (?,?,?,?,?)',
                            (identity, slot['id'], runtime['set_elapsed_ms'], exercise['name'], exercise['kind']))
            runtime['phase'] = 'awaiting_choice'
        return self._command(session_id, expected_revision, command_id, operation)

    def _finish(self, row, state, runtime):
        self._stop_set_clock(runtime)
        self._pause_total(state)
        state['status'] = 'ended'
        runtime['phase'] = 'ended'
        runtime['current_slot_id'] = None
        self.db.execute("UPDATE training_date_plans SET status='completed',updated_at=? WHERE id=?", (self.clock.now_ms() // 1000, row['plan_id']))

    def _new_set(self, state, runtime, next_exercise=False, session_id=None):
        if next_exercise:
            index = runtime['order'].index(runtime['current_slot_id']) + 1 if runtime['current_slot_id'] else 0
            if index >= len(runtime['order']):
                raise ValueError('已是最后一个动作')
            runtime['current_slot_id'] = runtime['order'][index]
            slot = self._slot(runtime)
            previous = self.db.execute('SELECT MAX(set_index) FROM training_set_results WHERE session_id=? AND exercise_index=?',
                                       (session_id, slot['legacy_index'])).fetchone()[0]
            runtime['set_index'] = 0 if previous is None else previous + 1
        else:
            runtime['set_index'] += 1
        runtime.update(phase='collecting', draft=measurement_dict(Measurements()), set_elapsed_ms=0,
                       set_started_ms=self.clock.now_ms() if state['status'] == 'running' else None, notice=None)

    def choose(self, session_id, action, expected_revision, command_id):
        def operation(row, state, runtime):
            if runtime['phase'] not in ('awaiting_choice', 'awaiting_selection'):
                raise ValueError('当前无需选择下一步')
            if action == 'end':
                self._finish(row, state, runtime)
            elif action in ('add_set', 'next_exercise'):
                if action == 'add_set' and not runtime['current_slot_id']:
                    raise ValueError('请先选择动作')
                self._new_set(state, runtime, action == 'next_exercise', row['id'])
            else:
                raise ValueError('无效操作')
        return self._command(session_id, expected_revision, command_id, operation)

    def _pause_total(self, state):
        if state.get('runningSince'):
            started = int(datetime.fromisoformat(state['runningSince']).timestamp() * 1000)
            state['elapsedMs'] = elapsed(state['elapsedMs'], started, self.clock.now_ms())
        state['runningSince'] = None

    def pause(self, session_id):
        with transaction(self.db):
            row, state, runtime, revision = self._load(session_id)
            if state['status'] != 'running':
                return self._snapshot(row, state, runtime, revision)
            self._stop_set_clock(runtime)
            self._pause_total(state)
            state['status'] = 'paused'
            return self._store(row, state, runtime, revision)

    def resume(self, session_id):
        with transaction(self.db):
            row, state, runtime, revision = self._load(session_id)
            if state['status'] != 'paused':
                return self._snapshot(row, state, runtime, revision)
            state['status'] = 'running'
            state['runningSince'] = datetime.fromtimestamp(self.clock.now_ms() / 1000).isoformat()
            if runtime['phase'] == 'collecting' and runtime['current_slot_id']:
                runtime['set_started_ms'] = self.clock.now_ms()
            return self._store(row, state, runtime, revision)

    def inherit(self, session_id):
        with transaction(self.db):
            row, state, runtime, revision = self._load(session_id)
            self._collecting(state, runtime)
            slot = self._slot(runtime)
            previous = self.db.execute('SELECT measurements FROM training_set_results WHERE session_id=? AND exercise_index=? ORDER BY set_index DESC LIMIT 1',
                                       (session_id, slot['legacy_index'])).fetchone()
            if previous is None:
                raise ValueError('本动作还没有上一组数据')
            runtime['draft'] = json.loads(previous[0])
            return self._store(row, state, runtime, revision)

    def skip(self, session_id, expected_revision, command_id):
        def operation(row, state, runtime):
            self._collecting(state, runtime)
            slot = self._slot(runtime)
            if slot['legacy_index'] not in state['skipped']:
                state['skipped'].append(slot['legacy_index'])
            if runtime['current_slot_id'] == runtime['order'][-1]:
                self._finish(row, state, runtime)
            else:
                self._new_set(state, runtime, True, row['id'])
        return self._command(session_id, expected_revision, command_id, operation)

    def end(self, session_id, expected_revision, command_id):
        return self._command(session_id, expected_revision, command_id, self._finish)

    def begin_edit(self, session_id):
        return self.pause(session_id)

    def apply_edit(self, session_id, name, slots, order, expected_revision):
        from fitness.services.training_edit import apply_edit
        return apply_edit(self, session_id, name, slots, order, expected_revision)

    def session_name(self, session_id):
        row = self.db.execute('SELECT state FROM training_sessions WHERE id=?', (session_id,)).fetchone()
        if row is None:
            raise ValueError('训练不存在')
        return json.loads(row[0])['name']
