import json
import sqlite3
import pytest
from fitness.storage.paths import resolve_database
from fitness.storage.database import open_database

def test_android_uses_existing_legacy_path(tmp_path):
    storage = tmp_path / 'files/data'
    storage.mkdir(parents=True)
    legacy = tmp_path / 'app_flutter/flexify.sqlite'
    legacy.parent.mkdir()
    legacy.touch()
    assert resolve_database(storage, android=True) == legacy

@pytest.mark.parametrize('suffix', ['data', 'files', 'wrong/data'])
def test_bad_android_layout_rejected(tmp_path, suffix):
    with pytest.raises(ValueError):
        resolve_database(tmp_path / suffix, android=True)

def test_missing_initialized_database_not_recreated(tmp_path):
    (tmp_path / '.fitness-initialized').touch()
    with pytest.raises(FileNotFoundError):
        resolve_database(tmp_path, android=False)
    assert not (tmp_path / 'flexify.sqlite').exists()

def test_connect_never_creates_empty_database(tmp_path):
    missing = tmp_path / 'missing.sqlite'
    with pytest.raises(sqlite3.OperationalError):
        open_database(missing)
    assert not missing.exists()

def test_real_legacy_values_and_connection_settings(legacy_db):
    db = open_database(legacy_db)
    try:
        assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert db.execute('PRAGMA busy_timeout').fetchone()[0] == 5000
        assert db.execute("SELECT weight FROM gym_sets WHERE name='Weight'").fetchone()['weight'] == 74.6
        assert db.execute('SELECT grams FROM nutrition_foods').fetchone()['grams'] is None
        row=db.execute('SELECT measurements FROM training_set_results').fetchone()
        assert json.loads(row['measurements'])['reps'] == 10
    finally:
        db.close()
