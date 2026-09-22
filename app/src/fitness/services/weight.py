from datetime import datetime, time, timedelta
from fitness.domain.validation import finite_number
from fitness.services.plans import transaction

# Conversion constants from the original daily_weight_repository.dart.
FACTORS = {'kg': 1, 'lb': 0.45359237, 'stone': 6.35029318}


def day_bounds(day):
    return (int(datetime.combine(day, time.min).timestamp()),
            int(datetime.combine(day + timedelta(days=1), time.min).timestamp()))


class WeightService:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock

    def _latest(self, day):
        start, end = day_bounds(day)
        for row in self.db.execute("SELECT * FROM gym_sets WHERE name='Weight' AND hidden=0 "
                                   'AND created>=? AND created<? ORDER BY created DESC,id DESC', (start, end)):
            try:
                finite_number(row['weight'], positive=True)
            except ValueError:
                continue
            if row['unit'] in FACTORS:
                return row
        return None

    def read(self, day):
        row = self._latest(day)
        return row['weight'] * FACTORS[row['unit']] if row else None

    def save(self, day, value_kg):
        finite_number(value_kg, positive=True)
        with transaction(self.db):
            row = self._latest(day)
            if row:
                self.db.execute("UPDATE gym_sets SET weight=?,unit='kg' WHERE id=?", (value_kg, row['id']))
            else:
                self.db.execute("INSERT INTO gym_sets(name,reps,weight,unit,created) VALUES ('Weight',1,?,'kg',?)",
                                (value_kg, day_bounds(day)[0]))

    def previous(self, day):
        for row in self.db.execute("SELECT * FROM gym_sets WHERE name='Weight' AND hidden=0 "
                                   'AND created<? ORDER BY created DESC,id DESC', (day_bounds(day)[0],)):
            try:
                finite_number(row['weight'], positive=True)
            except ValueError:
                continue
            if row['unit'] in FACTORS:
                return datetime.fromtimestamp(row['created']).date(), row['weight'] * FACTORS[row['unit']]
        return None
