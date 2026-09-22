import sqlite3
from pathlib import Path
import pytest
from fitness.storage.migrations import initialize
from fitness.storage.database import open_database
from fitness.services.backup import BackupService
from fitness.services.training import TrainingService
from fitness.services.records import RecordsService

@pytest.mark.parametrize('version',[58,59])
def test_all_legacy_tables_unchanged_and_restore(version,tmp_path,clock):
    source=Path('tests/fixtures')/('legacy_v58.sql' if version==58 else 'python_v59.sql')
    path=tmp_path/'source.sqlite'
    with sqlite3.connect(path) as db:
        db.executescript(source.read_text(encoding='utf-8'))
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'py_%'")]
        before={t:db.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}
    db.close()
    initialize(path,tmp_path/'backups')
    with sqlite3.connect(path) as db:
        assert {t:db.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}==before
        assert db.execute('PRAGMA user_version').fetchone()[0]==60
    db.close()
    target=tmp_path/'current'/'flexify.sqlite';initialize(target,tmp_path/'backups')
    BackupService(target,tmp_path/'backups').restore(path)
    db=open_database(target)
    training=TrainingService(db,clock)
    active=training.restore_free()
    if active:training.advance(active.id,'end',active.revision,'finish-old')
    assert training.start_free().status=='running'
    db.close()


def test_standalone_dart_rows_visible(db,clock):
    now=clock.now_ms()//1000
    db.execute("INSERT INTO gym_sets(name,reps,weight,unit,created,duration,cardio) VALUES ('独立旧动作',8,100,'lb',?,0,0)",(now,))
    groups=RecordsService(db,clock).day_sessions(clock.today())
    actions=[a for s in groups for a in s['actions']]
    assert any(a['name']=='独立旧动作' and abs(a['sets'][0]['weight']-45.359237)<0.001 for a in actions)
