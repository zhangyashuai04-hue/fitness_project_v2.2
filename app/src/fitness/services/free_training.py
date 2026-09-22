"""Free-training commands layered on the existing transactional store."""
import json
from dataclasses import replace
from datetime import datetime
from uuid import uuid4
from fitness.domain.models import Measurements
from fitness.domain.free_training import should_save, validate_partial, validate_next_set, parse_measurements
from fitness.domain.training import measurement_dict, measurement_from, elapsed
from fitness.domain.training_time import daily_duration
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
                         set_started_ms=now,notice=None,intervals=[],active_started_ms=now,
                         action_elapsed_ms=0,action_started_ms=now)
            self._append_free_action(state,runtime)
            # plan_id is unique but has no FK: private identity needs no visible plan/template.
            self.db.execute('INSERT INTO training_sessions VALUES (?,?,?,?,?,?,?)',
                            (identity,'free:'+identity,1,self.clock.today().isoformat(),json.dumps(state,ensure_ascii=False),now//1000,now//1000))
            self.db.execute('INSERT INTO py_session_meta VALUES (?,?,?)',(identity,0,json.dumps(runtime,ensure_ascii=False)))
            return self._snapshot(*self._load(identity))

    def _append_free_action(self,state,runtime):
        runtime.pop('input_text',None)
        runtime.pop('input_error',None)
        exercise=dict(id=str(uuid4()),name='',kind='weighted')
        slot=dict(id=str(uuid4()),exercise=exercise,legacy_index=len(state['exercises']))
        state['exercises'].append(exercise)
        runtime['slots'].append(slot)
        runtime['order'].append(slot['id'])
        runtime.update(action_elapsed_ms=0,action_started_ms=self.clock.now_ms() if state['status']=='running' else None,
                       current_slot_id=slot['id'],set_index=0,phase='collecting',
                       draft=measurement_dict(Measurements()),set_elapsed_ms=0,
                       set_started_ms=self.clock.now_ms() if state['status']=='running' else None)

    def _free_snapshot(self,result,row,state,runtime):
        if not runtime.get('free'):
            return result
        slot=self._slot(runtime) if runtime['current_slot_id'] else None
        previous=slot and self.db.execute('SELECT 1 FROM training_set_results WHERE session_id=? AND exercise_index=? LIMIT 1',
                                          (row['id'],slot['legacy_index'])).fetchone()
        raw=runtime.get('input_text',{})
        return replace(result,input_name=raw.get('name'),input_reps=raw.get('reps'),input_weight=raw.get('weight'),input_error=runtime.get('input_error'),
                       notice='系统时间发生变化，计时已冻结至校时追平。' if self.clock.backward else result.notice,action_name=slot['exercise']['name'] if slot else '',can_inherit=bool(previous),
                       action_elapsed_ms=elapsed(runtime.get('action_elapsed_ms',0),runtime.get('action_started_ms'),self.clock.now_ms()),
                       daily_elapsed_ms=self.daily_training_ms())

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
            if runtime.get('input_error'):
                raise ValueError(runtime['input_error'])
            value=measurement_from(runtime['draft'])
            validate_partial(value)
            if action=='next_set':
                validate_next_set(value)
            if should_save(value):
                if not runtime.get('input_text',{}).get('name',self._slot(runtime)['exercise']['name']).strip():
                    raise ValueError('请输入动作名称')
                self._save_free_set(row,state,runtime,value)
            confirmation=runtime.pop('confirmation',None)
            if confirmation and action != confirmation['action']:
                raise ValueError('确认操作不匹配')
            if confirmation and confirmation['status']=='running' and action!='end':
                state['status']='running'
                state['runningSince']=datetime.fromtimestamp(self.clock.now_ms()/1000).isoformat()
                self._resume_free_clock(runtime)
            if action=='end':
                self._finish(row,state,runtime)
            elif action=='next_action':
                self._append_free_action(state,runtime)
            else:
                self._new_set(state,runtime,session_id=row['id'])
        return self._command(session_id,expected_revision,command_id,operation)

    def daily_training_ms(self):
        total=0
        now=self.clock.now_ms()
        for row in self.db.execute('SELECT runtime_json FROM py_session_meta'):
            runtime=json.loads(row[0])
            intervals=list(runtime.get('intervals',[]))
            started=runtime.get('active_started_ms')
            if started is not None:
                intervals.append((started,max(started,now)))
            total+=daily_duration(intervals,self.clock.today())
        return total

    def _stop_free_clock(self,runtime):
        if not runtime.get('free'): return
        now=self.clock.now_ms()
        started=runtime.get('active_started_ms')
        if started is not None:
            runtime.setdefault('intervals',[]).append([started,max(started,now)])
        runtime['active_started_ms']=None
        runtime['action_elapsed_ms']=elapsed(runtime.get('action_elapsed_ms',0),runtime.get('action_started_ms'),now)
        runtime['action_started_ms']=None

    def _resume_free_clock(self,runtime):
        if not runtime.get('free'): return
        runtime['active_started_ms']=self.clock.now_ms()
        runtime['action_started_ms']=self.clock.now_ms()

    def begin_confirmation(self,session_id,action):
        if action not in ('end','next_action'):
            raise ValueError('无效操作')
        with transaction(self.db):
            row,state,runtime,revision=self._load(session_id)
            self._collecting(state,runtime)
            if runtime.get('confirmation'):
                return self._snapshot(row,state,runtime,revision)
            runtime['confirmation']=dict(action=action,status=state['status'])
            self._stop_set_clock(runtime)
            self._stop_free_clock(runtime)
            self._pause_total(state)
            state['status']='paused'
            return self._store(row,state,runtime,revision)

    def cancel_confirmation(self,session_id):
        with transaction(self.db):
            row,state,runtime,revision=self._load(session_id)
            confirmation=runtime.pop('confirmation',None)
            if not confirmation:
                return self._snapshot(row,state,runtime,revision)
            if confirmation['status']=='running':
                state['status']='running'
                state['runningSince']=datetime.fromtimestamp(self.clock.now_ms()/1000).isoformat()
                runtime['set_started_ms']=self.clock.now_ms()
                self._resume_free_clock(runtime)
            return self._store(row,state,runtime,revision)

    def restore_free(self):
        row=self.db.execute('SELECT id FROM training_sessions WHERE active_slot=1').fetchone()
        if not row: return None
        identity=row['id']
        with transaction(self.db):
            row,state,runtime,revision=self._load(identity)
            if not runtime.get('free'):
                now=self.clock.now_ms()
                runtime.update(free=True,version=2,intervals=[],action_elapsed_ms=runtime['set_elapsed_ms'],
                               action_started_ms=runtime['set_started_ms'],
                               active_started_ms=int(datetime.fromisoformat(state['runningSince']).timestamp()*1000) if state.get('runningSince') else None)
                slot=self._slot(runtime) if runtime['current_slot_id'] else None
                if slot and slot['exercise']['kind']!='timed':
                    previous=self.db.execute('SELECT MAX(set_index) FROM training_set_results WHERE session_id=? AND exercise_index=?',(identity,slot['legacy_index'])).fetchone()[0]
                    if runtime['phase']=='awaiting_choice' or (previous is not None and runtime['set_index']<=previous):
                        runtime.update(phase='collecting',set_index=previous+1 if previous is not None else runtime['set_index']+1,
                                       draft=measurement_dict(Measurements()),set_elapsed_ms=0,set_started_ms=now if state['status']=='running' else None)
                    slot['exercise']['kind']='weighted'
                    state['exercises'][slot['legacy_index']]['kind']='weighted'
                    runtime['order']=[slot['id']]
                else:
                    # Freeze old result labels/kinds before appending a new free action.
                    self._append_free_action(state,runtime)
                    runtime['notice']='旧计时动作已保留，新动作请填写名称、次数和重量。'
                self._store(row,state,runtime,revision)
        # An unsubmitted confirmation never completes a destructive transition on restart.
        return self.cancel_confirmation(identity)

    def save_input_text(self,session_id,name,reps,weight):
        with transaction(self.db):
            row,state,runtime,revision=self._load(session_id)
            self._collecting(state,runtime)
            runtime['input_text']=dict(name=name,reps=reps,weight=weight)
            runtime['input_error']=None
            try:
                runtime['draft']=measurement_dict(parse_measurements(reps,weight))
            except ValueError as exc:
                runtime['input_error']=str(exc)
            slot=self._slot(runtime)
            if name.strip():
                slot['exercise']['name']=name.strip()
                state['exercises'][slot['legacy_index']]['name']=name.strip()
                self.db.execute('UPDATE py_set_meta SET exercise_name=? WHERE set_id IN (SELECT id FROM training_set_results WHERE session_id=? AND exercise_index=?)',(name.strip(),session_id,slot['legacy_index']))
            return self._store(row,state,runtime,revision)

    def command_result(self,session_id,command_id):
        from fitness.domain.training import snapshot_from
        row=self.db.execute('SELECT result_json FROM py_commands WHERE session_id=? AND command_id=?',(session_id,command_id)).fetchone()
        return snapshot_from(json.loads(row[0])) if row else None
