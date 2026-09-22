from uuid import uuid4
from fitness.domain.validation import finite_number
from fitness.services.plans import transaction


class NutritionService:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock

    def save_food(self, day, name, calories, grams=None, food_id=None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError('请输入食物名称')
        finite_number(calories)
        if grams is not None:
            finite_number(grams, positive=True)
        identity, now = food_id or str(uuid4()), self.clock.now_ms() // 1000
        with transaction(self.db):
            if food_id is not None:
                if not self.db.execute('SELECT 1 FROM nutrition_foods WHERE id=?', (identity,)).fetchone():
                    raise ValueError('饮食记录不存在')
                self.db.execute('UPDATE nutrition_foods SET name=?,local_date=?,calories=?,grams=?,updated_at=? WHERE id=?',
                                (name.strip(), day.isoformat(), calories, grams, now, identity))
            else:
                self.db.execute('INSERT INTO nutrition_foods VALUES (?,?,?,?,?,?,?)',
                                (identity, name.strip(), day.isoformat(), calories, grams, now, now))
        return identity

    def foods(self, day):
        return [dict(row) for row in self.db.execute('SELECT * FROM nutrition_foods WHERE local_date=? ORDER BY created_at,id', (day.isoformat(),))]

    def save_expenditure(self, day, calories):
        finite_number(calories)
        now = self.clock.now_ms() // 1000
        with transaction(self.db):
            self.db.execute('INSERT INTO nutrition_expenditures VALUES (?,?,?,?) '
                            'ON CONFLICT(local_date) DO UPDATE SET calories=excluded.calories,updated_at=excluded.updated_at',
                            (day.isoformat(), calories, now, now))

    def summary(self, day):
        intake = self.db.execute('SELECT COALESCE(SUM(calories),0) FROM nutrition_foods WHERE local_date=?', (day.isoformat(),)).fetchone()[0]
        row = self.db.execute('SELECT calories FROM nutrition_expenditures WHERE local_date=?', (day.isoformat(),)).fetchone()
        expenditure = row[0] if row else None
        return dict(intake=intake, expenditure=expenditure,
                    balance=intake-expenditure if expenditure is not None else None)
