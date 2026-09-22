from contextlib import closing
from pathlib import Path
import sqlite3
import pytest

@pytest.fixture
def legacy_db(tmp_path):
    path = tmp_path / 'flexify.sqlite'
    with sqlite3.connect(path) as db:
        db.executescript((Path(__file__).parent / 'fixtures/legacy_v58.sql').read_text(encoding='utf-8'))
    return path

@pytest.fixture
def db(legacy_db,tmp_path):
    from fitness.storage.migrations import initialize
    from fitness.storage.database import open_database
    initialize(legacy_db,tmp_path/'backups')
    connection=open_database(legacy_db)
    yield connection
    connection.close()

class FakeClock:
    def __init__(self): self.value=1789948800000
    def now_ms(self): return self.value
    def today(self):
        from datetime import datetime
        return datetime.fromtimestamp(self.value/1000).date()
    def advance_ms(self,value): self.value+=value
    def set_ms(self,value): self.value=value

@pytest.fixture
def clock(): return FakeClock()
