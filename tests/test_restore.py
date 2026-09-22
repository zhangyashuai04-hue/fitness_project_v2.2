import sqlite3
from pathlib import Path
import pytest
from fitness.services.backup import BackupService
from fitness.storage.migrations import initialize
from fitness.storage.database import open_database

@pytest.fixture
def database_path(tmp_path):
    path=tmp_path/'current'/'flexify.sqlite'
    initialize(path,tmp_path/'backups')
    return path

def test_bad_restore_keeps_database(database_path,tmp_path):
    before=database_path.read_bytes()
    bad=tmp_path/'bad.sqlite';bad.write_bytes(b'bad')
    with pytest.raises(ValueError):BackupService(database_path,tmp_path/'backups').restore(bad)
    assert database_path.read_bytes()==before

def test_restore_legacy_and_export(database_path,legacy_db,tmp_path):
    s=BackupService(database_path,tmp_path/'backups')
    s.restore(legacy_db)
    db=open_database(database_path)
    assert db.execute('PRAGMA user_version').fetchone()[0]==59
    assert db.execute('SELECT COUNT(*) FROM training_sessions').fetchone()[0]==2
    db.close()
    target=tmp_path/'export.sqlite'
    s.export(target)
    assert target.exists()

def test_replace_failure_keeps_original(database_path,legacy_db,tmp_path,monkeypatch):
    before=database_path.read_bytes()
    def fail(*args):raise OSError('disk error')
    monkeypatch.setattr('fitness.services.backup.os.replace',fail)
    with pytest.raises(OSError):BackupService(database_path,tmp_path/'backups').restore(legacy_db)
    assert database_path.read_bytes()==before

def test_future_version_rejected(database_path,legacy_db,tmp_path):
    connection=sqlite3.connect(legacy_db)
    connection.execute('PRAGMA user_version=999');connection.close()
    before=database_path.read_bytes()
    with pytest.raises(ValueError):BackupService(database_path,tmp_path/'backups').restore(legacy_db)
    assert database_path.read_bytes()==before

def test_export_captures_wal(database_path,tmp_path):
    db=open_database(database_path)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('INSERT INTO nutrition_expenditures VALUES (?,?,?,?)',('2026-10-01',123,1,1))
    target=tmp_path/'wal-export.sqlite'
    BackupService(database_path,tmp_path/'backups').export(target)
    copy=open_database(target)
    assert copy.execute('SELECT calories FROM nutrition_expenditures').fetchone()[0]==123
    copy.close();db.close()
