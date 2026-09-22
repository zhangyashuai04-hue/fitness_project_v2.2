import os
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4
from fitness.storage.backup import backup_database
from fitness.storage.migrations import initialize
from fitness.storage.database import open_database


class BackupService:
    """Caller must close all application connections before restore."""
    def __init__(self, database_path, backup_dir):
        self.database_path, self.backup_dir = Path(database_path), Path(backup_dir)

    def export(self, target):
        backup_database(self.database_path, Path(target))

    def restore(self, source):
        source=Path(source)
        if source.resolve()==self.database_path.resolve():
            raise ValueError('请选择导出的备份文件')
        self.backup_dir.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='restore-',dir=self.backup_dir) as directory:
            candidate=Path(directory)/'flexify.sqlite'
            try:
                backup_database(source,candidate)
                initialize(candidate,Path(directory)/'backup')
            except (sqlite3.DatabaseError,ValueError,FileNotFoundError) as exc:
                raise ValueError('备份无效或版本不受支持，原数据未替换') from exc
            backup_database(self.database_path,self.backup_dir/f'before-restore-{uuid4().hex}.sqlite')
            db=open_database(self.database_path)
            try:
                result=db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                if result[0]:
                    raise ValueError('数据库仍在使用，请关闭训练后重试')
                db.execute('PRAGMA journal_mode=DELETE')
            finally:
                db.close()
            os.replace(candidate,self.database_path)
