import sqlite3
import pytest
from fitness.storage import migrations

def test_v60_repeat(legacy_db,tmp_path):
    migrations.initialize(legacy_db,tmp_path/'backups')
    migrations.initialize(legacy_db,tmp_path/'backups')
    with sqlite3.connect(legacy_db) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 60
        assert db.execute('SELECT version FROM py_migrations ORDER BY version').fetchall() == [(59,),(60,)]
    assert len(list((tmp_path/'backups').glob('*.sqlite'))) == 1

def test_v60_failure_rolls_back(legacy_db,tmp_path,monkeypatch):
    def fail(db, now):
        db.execute('PRAGMA user_version=60')
        raise sqlite3.OperationalError('disk full')
    monkeypatch.setattr(migrations,'migrate_v59_to_v60',fail,raising=False)
    with pytest.raises(sqlite3.OperationalError):
        migrations.initialize(legacy_db,tmp_path/'backups')
    with sqlite3.connect(legacy_db) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 58
