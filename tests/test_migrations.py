from contextlib import closing
import json
import sqlite3
import pytest
from fitness.storage import migrations

def rows(path, table):
    with closing(sqlite3.connect(path)) as db:
        return db.execute(f'SELECT * FROM "{table}"').fetchall()

def version(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute('PRAGMA user_version').fetchone()[0]

def test_migrate_and_repeat_keep_all_original_rows(legacy_db, tmp_path):
    with sqlite3.connect(legacy_db) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    before = {t:rows(legacy_db,t) for t in tables}
    migrations.initialize(legacy_db,tmp_path/'backups')
    migrations.initialize(legacy_db,tmp_path/'backups')
    assert version(legacy_db)==59
    assert {t:rows(legacy_db,t) for t in tables}==before
    assert len(rows(legacy_db,'py_migrations'))==1
    assert len(list((tmp_path/'backups').glob('*.sqlite')))==1

def test_backup_failure_leaves_old_database(legacy_db,tmp_path,monkeypatch):
    before=legacy_db.read_bytes()
    def fail(*args): raise OSError('disk full')
    monkeypatch.setattr(migrations,'backup_database',fail)
    with pytest.raises(OSError): migrations.initialize(legacy_db,tmp_path/'backups')
    assert legacy_db.read_bytes()==before

def test_mid_migration_rolls_back_ddl(legacy_db,tmp_path,monkeypatch):
    original=migrations.migrate_v58_to_v59
    def fail(db,now_ms):
        original(db,now_ms)
        raise RuntimeError('injected after migration')
    monkeypatch.setattr(migrations,'migrate_v58_to_v59',fail)
    with pytest.raises(RuntimeError): migrations.initialize(legacy_db,tmp_path/'backups')
    assert version(legacy_db)==58
    with sqlite3.connect(legacy_db) as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='py_migrations'").fetchall()

@pytest.mark.parametrize('problem',['future','missing_table','bad_json','bad_index','corrupt'])
def test_invalid_legacy_rejected_without_replacement(legacy_db,tmp_path,problem):
    if problem=='corrupt': legacy_db.write_bytes(b'not a database')
    else:
        with sqlite3.connect(legacy_db) as db:
            if problem=='future': db.execute('PRAGMA user_version=60')
            elif problem=='missing_table': db.execute('DROP TABLE nutrition_foods')
            elif problem=='bad_json': db.execute("UPDATE training_sessions SET state='{}'")
            else:
                row=db.execute('SELECT id,state FROM training_sessions LIMIT 1').fetchone()
                state=json.loads(row[1]);state['exerciseIndex']=999
                db.execute('UPDATE training_sessions SET state=? WHERE id=?',(json.dumps(state),row[0]))
    before=legacy_db.read_bytes()
    with pytest.raises((ValueError,sqlite3.DatabaseError)):
        migrations.initialize(legacy_db,tmp_path/'backups')
    assert legacy_db.read_bytes()==before

def test_fresh_install_and_missing_initialized_guard(tmp_path):
    path=tmp_path/'new'/'flexify.sqlite'
    migrations.initialize(path,tmp_path/'backups')
    assert version(path)==59
    assert not list((tmp_path/'backups').glob('*.sqlite'))
    path.unlink()
    with pytest.raises(FileNotFoundError): migrations.initialize(path,tmp_path/'backups')
    assert not path.exists()
