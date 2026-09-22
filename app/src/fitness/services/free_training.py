"""Free-training commands layered on the existing transactional store."""
import json
from dataclasses import replace
from datetime import datetime
from uuid import uuid4
from fitness.domain.models import Measurements
from fitness.domain.free_training import should_save, validate_partial, validate_next_set
from fitness.domain.training import measurement_dict, measurement_from
from fitness.services.plans import transaction


class FreeTrainingMixin:
    def start_free(self):
        with transaction(self.db):
            active=self.db.execute('SELECT id FROM training_sessions WHERE active_slot=1').fetchone()
            if active:
                return self._snapshot(*self._load(active['id']))
            identity, now=str(uuid4()),self.clock.now_ms()
            iso=datetime.fromtimestamp(now/1000).isoformat()
            state=dict(name='自由训练',exercises=[],status='running',startedAt=iso,runningSince=iso,
                       elapsedMs=0,exerciseIndex=0,setIndex=0,skipped=[])
            runtime=dict(version=2,free=True,slots=[],order=[],current_slot_id=None,set_index=0,
                         phase='collecting',draft=measurement_dict(Measurements()),set_elapsed_ms=0,
                         set_started_ms=now,notice=None)
            self._append_free_action(state,runtime)
            # plan_id is unique but has no FK: private identity needs no visible plan/template.
            self.db.execute('INSERT INTO training_sessions VALUES (?,?,?,?,?,?,?)',
                            (identity,'free:'+identity,1,self.clock.today().isoformat(),json.dumps(state,ensure_ascii=False),now//1000,now//1000))
            self.db.execute('INSERT INTO py_session_meta VALUES (?,?,?)',(identity,0,json.dumps(runtime,ensure_ascii=False)))
            return self._snapshot(*self._load(identity))

    def _append_free_action(self,state,runtime):
        exercise=dict(id=str(uuid4()),name='',kind='weighted')
        slot=dict(id=str(uuid4()),exercise=exercise,legacy_index=len(state['exercises']))
        state['exercises'].append(exercise)
        runtime['slots'].append(slot)
        runtime['order'].append(slot['id'])
        runtime.update(current_slot_id=slot['id'],set_index=0,phase='collecting',
                       draft=measurement_dict(Measurements()),set_elapsed_ms=0,
                       set_started_ms=self.clock.now_ms() if state['status']=='running' else None)

    def _free_snapshot(self,result,row,state,runtime):
        if not runtime.get('free'):
            return result
        slot=self._slot(runtime) if runtime['current_slot_id'] else None
        previous=slot and self.db.execute('SELECT 1 FROM training_set_results WHERE session_id=? AND exercise_index=? LIMIT 1',
                                          (row['id'],slot['legacy_index'])).fetchone()
        return replace(result,action_name=slot['exercise']['name'] if slot else '',can_inherit=bool(previous))

    def rename_current(self,session_id,name):
        with transaction(self.db):
            row,state,runtime,revision=self._load(session_id)
            self._collecting(state,runtime)
            slot=self._slot(runtime)
            name=name.strip()
            has_sets=self.db.execute('SELECT 1 FROM training_set_results WHERE session_id=? AND exercise_index=? LIMIT 1',(session_id,slot['legacy_index'])).fetchone()
            if not name and has_sets:
                raise ValueError('已有训练组的动作名称不能为空')
            slot['exercise']['name']=name
            state['exercises'][slot['legacy_index']]['name']=name
            args=(name,session_id,slot['legacy_index'])
            self.db.execute('UPDATE py_set_meta SET exercise_name=? WHERE set_id IN (SELECT id FROM training_set_results WHERE session_id=? AND exercise_index=?)',args)
            # Legacy plan_exercises references non-unique gym_sets.name. Preserve that
            # mirror name; authoritative session + py_set_meta names are updated above.
            return self._store(row,state,runtime,revision)

    def _save_free_set(self,row,state,runtime,value):
        slot=self._slot(runtime); exercise=slot['exercise']
        self._stop_set_clock(runtime)
        now=self.clock.now_ms()//1000
        cursor=self.db.execute('INSERT INTO gym_sets(name,reps,weight,unit,created,duration,cardio) VALUES (?,?,?,?,?,?,?)',
                               (exercise['name'],value.reps or 0,value.weight or 0,'kg',now,0,0))
        identity=str(uuid4())
        self.db.execute('INSERT INTO training_set_results VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (identity,row['id'],exercise['id'],slot['legacy_index'],runtime['set_index'],json.dumps(measurement_dict(value)),cursor.lastrowid,self.clock.today().isoformat(),now,now))
        self.db.execute('INSERT INTO py_set_meta VALUES (?,?,?,?,?)',
                        (identity,slot['id'],runtime['set_elapsed_ms'],exercise['name'],'weighted'))

    def advance(self,session_id,action,expected_revision,command_id):
        if action not in ('next_set','next_action','end'):
            raise ValueError('无效操作')
        def operation(row,state,runtime):
            self._collecting(state,runtime)
            value=measurement_from(runtime['draft'])
            validate_partial(value)
            if action=='next_set':
                validate_next_set(value)
            if should_save(value):
                if not self._slot(runtime)['exercise']['name'].strip():
                    raise ValueError('请输入动作名称')
                self._save_free_set(row,state,runtime,value)
            if action=='end':
                self._finish(row,state,runtime)
            elif action=='next_action':
                self._append_free_action(state,runtime)
            else:
                self._new_set(state,runtime,session_id=row['id'])
        return self._command(session_id,expected_revision,command_id,operation)
