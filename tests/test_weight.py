from datetime import date, datetime
import pytest
from fitness.services.weight import WeightService
from fitness.domain.validation import validate_measurements
from fitness.domain.models import Measurements


def test_daily_weight_updates_and_previous(db, clock):
    s = WeightService(db, clock)
    s.save(date(2026, 10, 1), 75)
    s.save(date(2026, 10, 1), 76)
    s.save(date(2026, 10, 2), 77)
    assert s.read(date(2026, 10, 1)) == 76
    assert s.previous(date(2026, 10, 2)) == (date(2026, 10, 1), 76)
    assert db.execute("SELECT COUNT(*) FROM gym_sets WHERE name='Weight' AND weight=76").fetchone()[0] == 1


def test_legacy_units_and_midnight(db, clock):
    def insert(day, value, unit, hidden=0):
        db.execute("INSERT INTO gym_sets(name,reps,weight,unit,created,hidden) VALUES ('Weight',1,?,?,?,?)",
                   (value, unit, int(datetime.fromisoformat(day).timestamp()), hidden))
    insert('2026-10-01T23:59:59', 150, 'lb')
    insert('2026-10-02T00:00:00', 12, 'stone')
    insert('2026-10-02T12:00:00', 100, 'kg', 1)
    s = WeightService(db, clock)
    assert s.read(date(2026,10,1)) == pytest.approx(150 * .45359237)
    assert s.read(date(2026,10,2)) == pytest.approx(12 * 6.35029318)
    s.save(date(2026,10,2), 78)
    assert db.execute("SELECT weight FROM gym_sets WHERE unit='lb'").fetchone()[0] == 150


@pytest.mark.parametrize('value', [0,-1,float('nan'),float('inf'),True,None])
def test_invalid_weight(db, clock, value):
    with pytest.raises(ValueError): WeightService(db,clock).save(clock.today(),value)


@pytest.mark.parametrize('kind,m', [('weighted',Measurements(reps=2)),('bodyweight',Measurements(reps=True)),('bodyweight',Measurements(reps=1.5)),('timed',Measurements(duration_seconds=0)),('weighted',Measurements(weight=float('inf'),reps=1))])
def test_invalid_set_measurement(kind,m):
    with pytest.raises(ValueError): validate_measurements(kind,m)


def test_zero_load_is_valid():
    validate_measurements('weighted',Measurements(weight=0,reps=1))
