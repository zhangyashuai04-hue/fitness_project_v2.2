import json
from uuid import uuid4
from fitness.domain.models import Measurements
from fitness.domain.training import measurement_dict
from fitness.services.plans import transaction, exercise_json


def apply_edit(service, session_id, name, slots, order, expected_revision):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('请输入计划名称')
    ids = [s.id for s in slots]
    if len(set(ids)) != len(ids) or len(set(order)) != len(order) or set(ids) != set(order):
        raise ValueError('动作顺序或标识重复')
    if slots:
        exercise_json(name, [s.exercise for s in slots])
    with transaction(service.db):
        row, state, runtime, revision = service._load(session_id)
        if revision != expected_revision or state['status'] != 'paused':
            raise ValueError('请先暂停训练并刷新')
        # Freeze old history before changing the session's exercise definitions.
        from fitness.services.history import HistoryService
        history = HistoryService(service.db, service.clock)
        for result in service.db.execute('SELECT * FROM training_set_results WHERE session_id=?', (session_id,)).fetchall():
            meta = history._details(result)
            service.db.execute('INSERT OR IGNORE INTO py_set_meta VALUES (?,?,?,?,?)',
                               (result['id'], meta['slot_id'], meta['elapsed_ms'], meta['exercise_name'], meta['exercise_kind']))
        stored = {s['id']: s for s in runtime['slots']}
        mapping = {}
        current_changed = False
        for supplied in slots:
            if not isinstance(supplied.id, str) or not supplied.id:
                raise ValueError('动作标识为空')
            old = stored.get(supplied.id)
            exercise = dict(id=supplied.exercise.id, name=supplied.exercise.name.strip(), kind=supplied.exercise.kind, targetSets=1)
            changed = old and (old['exercise']['kind'] != exercise['kind'] or old['exercise']['id'] != exercise['id'])
            if old and supplied.legacy_index != old['legacy_index']:
                raise ValueError('旧动作位置不可改写')
            if changed:
                # Preserve both legacy JSON and completed-set identity when changing type.
                identity = str(uuid4())
                index = len(runtime['slots'])
                replacement = dict(id=identity, exercise=exercise, legacy_index=index)
                runtime['slots'].append(replacement)
                state['exercises'].append(exercise)
                mapping[supplied.id] = identity
                if supplied.id == runtime['current_slot_id']:
                    current_changed = True
            elif old:
                old['exercise'] = exercise
                state['exercises'][old['legacy_index']] = exercise
                mapping[supplied.id] = supplied.id
            else:
                runtime['slots'].append(dict(id=supplied.id, exercise=exercise, legacy_index=len(runtime['slots'])))
                state['exercises'].append(exercise)
                mapping[supplied.id] = supplied.id
        runtime['order'] = [mapping[identity] for identity in order]
        current = runtime['current_slot_id']
        if current not in mapping:
            runtime.update(current_slot_id=None, phase='awaiting_selection', draft=measurement_dict(Measurements()),
                           set_elapsed_ms=0, set_started_ms=None, set_index=0)
        elif current_changed:
            runtime.update(current_slot_id=mapping[current], phase='collecting', draft=measurement_dict(Measurements()),
                           set_elapsed_ms=0, set_started_ms=None, set_index=0)
        state['name'] = name.strip()
        planned = {s['id']: s['exercise'] for s in runtime['slots']}
        service.db.execute('UPDATE training_date_plans SET name=?,exercises=?,updated_at=? WHERE id=?',
                           (name.strip(), json.dumps([planned[i] for i in runtime['order']], ensure_ascii=False),
                            service.clock.now_ms() // 1000, row['plan_id']))
        return service._store(row, state, runtime, revision)
