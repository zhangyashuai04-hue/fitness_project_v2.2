import json
from contextlib import contextmanager
from uuid import uuid4


@contextmanager
def transaction(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


def exercise_json(name, exercises):
    if not isinstance(name, str) or not name.strip() or not exercises:
        raise ValueError('请输入计划名称并添加动作')
    output = []
    for exercise in exercises:
        if (not isinstance(exercise.id, str) or not exercise.id.strip()
                or not isinstance(exercise.name, str) or not exercise.name.strip()
                or exercise.kind not in ('weighted', 'bodyweight', 'timed')):
            raise ValueError('动作名称、标识或类型无效')
        output.append(dict(id=exercise.id, name=exercise.name.strip(),
                           kind=exercise.kind, targetSets=1))
    return json.dumps(output, ensure_ascii=False)


class PlanService:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock

    def save_template(self, name, exercises, template_id=None):
        payload = exercise_json(name, exercises)
        now = self.clock.now_ms() // 1000
        identity = template_id or str(uuid4())
        with transaction(self.db):
            if template_id is not None:
                if self.db.execute('SELECT 1 FROM training_templates WHERE id=?', (identity,)).fetchone() is None:
                    raise ValueError('模板不存在')
                self.db.execute('UPDATE training_templates SET name=?,exercises=?,updated_at=? WHERE id=?',
                                (name.strip(), payload, now, identity))
            else:
                self.db.execute('INSERT INTO training_templates VALUES (?,?,?,?,?,?)',
                                (identity, name.strip(), payload, self.clock.today().isoformat(), now, now))
        return identity

    @staticmethod
    def _decode(row):
        result = dict(row)
        result['exercises'] = json.loads(result['exercises'])
        return result

    def list_templates(self):
        return [self._decode(row) for row in self.db.execute('SELECT * FROM training_templates ORDER BY created_at,id')]

    def schedule(self, template_id, day):
        identity, now = str(uuid4()), self.clock.now_ms() // 1000
        with transaction(self.db):
            row = self.db.execute('SELECT * FROM training_templates WHERE id=?', (template_id,)).fetchone()
            if row is None:
                raise ValueError('模板不存在')
            self.db.execute('INSERT INTO training_date_plans VALUES (?,?,?,?,?,?,?,?)',
                            (identity, template_id, row['name'], row['exercises'], day.isoformat(), 'pending', now, now))
        return identity

    def list_plans(self, day):
        return [self._decode(row) for row in self.db.execute(
            'SELECT p.* FROM training_date_plans p LEFT JOIN py_plan_meta m ON m.plan_id=p.id '
            'WHERE p.local_date=? AND COALESCE(m.hidden,0)=0 ORDER BY p.created_at,p.id', (day.isoformat(),))]

    def _plan(self, plan_id):
        row = self.db.execute('SELECT * FROM training_date_plans WHERE id=?', (plan_id,)).fetchone()
        if row is None:
            raise ValueError('计划不存在')
        return row

    def edit_plan(self, plan_id, name, exercises):
        payload = exercise_json(name, exercises)
        with transaction(self.db):
            row = self._plan(plan_id)
            if row['status'] != 'pending' or self.db.execute('SELECT 1 FROM training_sessions WHERE plan_id=?', (plan_id,)).fetchone():
                raise ValueError('已开始的计划请在训练页面修改')
            self.db.execute('UPDATE training_date_plans SET name=?,exercises=?,updated_at=? WHERE id=?',
                            (name.strip(), payload, self.clock.now_ms() // 1000, plan_id))

    def hide_plan(self, plan_id):
        with transaction(self.db):
            self._plan(plan_id)
            if self.db.execute('SELECT 1 FROM training_sessions WHERE plan_id=? AND active_slot=1', (plan_id,)).fetchone():
                raise ValueError('请先结束正在进行的训练')
            self.db.execute('INSERT INTO py_plan_meta(plan_id,hidden) VALUES (?,1) '
                            'ON CONFLICT(plan_id) DO UPDATE SET hidden=1', (plan_id,))

    def skip_plan(self, plan_id):
        with transaction(self.db):
            row = self._plan(plan_id)
            if row['status'] == 'skipped':
                return
            if row['status'] != 'pending':
                raise ValueError('只能跳过尚未开始的计划')
            self.db.execute('UPDATE training_date_plans SET status=?,updated_at=? WHERE id=?',
                            ('skipped', self.clock.now_ms() // 1000, plan_id))
