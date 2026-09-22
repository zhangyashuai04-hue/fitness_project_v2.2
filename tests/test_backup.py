from contextlib import closing
import sqlite3
import pytest
from fitness.storage.backup import backup_database

def test_backup_includes_committed_wal_rows(legacy_db,tmp_path):
    writer=sqlite3.connect(legacy_db)
    writer.execute('PRAGMA journal_mode=WAL')
    writer.execute("INSERT INTO nutrition_foods VALUES('wal','WAL food','2026-09-21',123,NULL,1,1)")
    writer.commit()
    target=tmp_path/'snapshot.sqlite'
    backup_database(legacy_db,target)
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT calories FROM nutrition_foods WHERE id='wal'").fetchone()[0]==123
    writer.close()

def test_backup_does_not_overwrite(legacy_db,tmp_path):
    target=tmp_path/'existing.sqlite';target.write_bytes(b'keep me')
    with pytest.raises(FileExistsError): backup_database(legacy_db,target)
    assert target.read_bytes()==b'keep me'
