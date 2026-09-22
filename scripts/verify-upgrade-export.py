import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('before',type=Path)
parser.add_argument('after',type=Path)
args=parser.parse_args()
with closing(sqlite3.connect(args.before)) as before, closing(sqlite3.connect(args.after)) as after:
    assert after.execute('PRAGMA user_version').fetchone()[0]==59
    assert after.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    tables=[r[0] for r in before.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    report={}
    for table in tables:
        escaped=table.replace('"','""')
        original=sorted(repr(row) for row in before.execute(f'SELECT * FROM "{escaped}"'))
        current=sorted(repr(row) for row in after.execute(f'SELECT * FROM "{escaped}"'))
        assert original==current, f'Legacy content changed: {table}'
        report[table]=len(current)
    print(json.dumps(dict(integrity='ok',schema=59,unchanged_legacy_tables=report),indent=2))
