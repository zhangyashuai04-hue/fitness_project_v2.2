from fitness.domain.models import Exercise, Slot, Measurements, Snapshot


def measurement_dict(value):
    return dict(weight=value.weight, reps=value.reps, durationSeconds=value.duration_seconds)


def measurement_from(value):
    return Measurements(value.get('weight'), value.get('reps'), value.get('durationSeconds'))


def elapsed(accumulated, started, now):
    return accumulated + (max(0, now - started) if started is not None else 0)


def snapshot(identity, state, runtime, revision, now):
    warning = runtime.get('notice')
    started = runtime['set_started_ms']
    if started is not None and now < started:
        warning = '系统时间发生变化，本组计时请核对。'
    return Snapshot(identity, state['status'], runtime['phase'], revision,
                    tuple(Slot(slot['id'], Exercise(slot['exercise']['id'], slot['exercise']['name'], slot['exercise']['kind']), slot['legacy_index']) for slot in runtime['slots']),
                    tuple(runtime['order']), runtime['current_slot_id'], runtime['set_index'],
                    measurement_from(runtime['draft']),
                    elapsed(runtime['set_elapsed_ms'], started, now), warning)


def snapshot_from(value):
    value = dict(value)
    value['slots'] = tuple(Slot(s['id'], Exercise(**s['exercise']), s['legacy_index']) for s in value['slots'])
    value['order'] = tuple(value['order'])
    value['draft'] = Measurements(**value['draft'])
    return Snapshot(**value)
