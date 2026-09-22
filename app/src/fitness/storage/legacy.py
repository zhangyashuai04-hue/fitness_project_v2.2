import json
from fitness.storage.migrations import validate_legacy_state


def adapt_legacy_session(row, result_rows, now_ms: int) -> dict:
    state = json.loads(row['state'])
    validate_legacy_state(state)
    slots = [dict(id=f"{row['id']}:{index}", exercise=exercise,
                  legacy_index=index)
             for index, exercise in enumerate(state['exercises'])]
    order = [slot['id'] for slot in slots]
    index = state['exerciseIndex']
    current = order[index] if index < len(order) and state['status'] != 'ended' else None
    if current is None and state['status'] != 'ended':
        order = []
    return dict(version=1, slots=slots, order=order,
                phase='ended' if state['status'] == 'ended' else ('collecting' if current else 'awaiting_selection'),
                current_slot_id=current, set_index=state['setIndex'],
                draft=dict(weight=None, reps=None, durationSeconds=None),
                set_elapsed_ms=0,
                set_started_ms=now_ms if state['status'] == 'running' and current else None,
                clock_warning=False,
                notice='旧版没有记录本组持续时间，本组将重新计时。' if current else None)
