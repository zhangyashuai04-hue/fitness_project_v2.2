"""Consistent snapshots, including committed rows still in the WAL."""
import sqlite3
from pathlib import Path

def backup_database(source: Path, target: Path) -> None:
    source, target = Path(source).resolve(), Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb'):
        pass
    try:
        src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
        try:
            dst = sqlite3.connect(target)
            try:
                src.backup(dst)
                if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed')
            finally:
                dst.close()
        finally:
            src.close()
    except BaseException:
        target.unlink(missing_ok=True)
        raise
