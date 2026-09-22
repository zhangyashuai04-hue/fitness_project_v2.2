"""Additive version migration. Existing records are never rewritten here."""
import json
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from .backup import backup_database
from .database import open_database

OLD_TABLES = {'gym_sets','plans','plan_exercises','settings','metadata','graph_preferences',
              'training_templates','training_date_plans','training_sessions','training_set_results',
              'nutrition_foods','nutrition_expenditures'}
DDL = (
 'CREATE TABLE py_migrations(version INTEGER PRIMARY KEY, applied_at_ms INTEGER NOT NULL)',
 'CREATE TABLE py_plan_meta(plan_id TEXT PRIMARY KEY, hidden INTEGER NOT NULL DEFAULT 0 CHECK(hidden IN (0,1)))',
 'CREATE TABLE py_session_meta(session_id TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0, runtime_json TEXT NOT NULL)',
 'CREATE TABLE py_set_meta(set_id TEXT PRIMARY KEY, slot_id TEXT NOT NULL, elapsed_ms INTEGER CHECK(elapsed_ms IS NULL OR elapsed_ms>=0), exercise_name TEXT NOT NULL, exercise_kind TEXT NOT NULL)',
 'CREATE TABLE py_commands(session_id TEXT NOT NULL, command_id TEXT NOT NULL, result_json TEXT NOT NULL, PRIMARY KEY(session_id,command_id))',
)
NEW_TABLES = {'py_migrations','py_plan_meta','py_session_meta','py_set_meta','py_commands'}

def validate_legacy_state(state):
    if not isinstance(state, dict) or not isinstance(state.get('name'),str):
        raise ValueError('Invalid training state')
    if state.get('status') not in {'running','paused','ended'}:
        raise ValueError('Invalid session status')
    exercises = state.get('exercises')
    if not isinstance(exercises,list): raise ValueError('Invalid exercise list')
    for exercise in exercises:
        if not isinstance(exercise,dict) or not isinstance(exercise.get('id'),str) or not isinstance(exercise.get('name'),str):
            raise ValueError('Invalid exercise')
        if exercise.get('kind') not in {'weighted','bodyweight','timed'}:
            raise ValueError('Unknown exercise kind')
    for key in ('elapsedMs','exerciseIndex','setIndex'):
        if type(state.get(key)) is not int or state[key]<0:
            raise ValueError('Invalid training index or timer')
    if state['exerciseIndex']>len(exercises): raise ValueError('Exercise index out of range')
    skipped = state.get('skipped')
    if not isinstance(skipped,list) or any(type(i) is not int or i<0 or i>=len(exercises) for i in skipped):
        raise ValueError('Invalid skipped indexes')
    try:
        datetime.fromisoformat(state['startedAt'])
        if state.get('runningSince') is not None: datetime.fromisoformat(state['runningSince'])
    except (ValueError,TypeError,KeyError) as exc:
        raise ValueError('Invalid session date') from exc

def _validate(db, version):
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
        raise ValueError('Database integrity check failed')
    tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    needed=OLD_TABLES | (NEW_TABLES if version==59 else set())
    if not needed<=tables: raise ValueError('Required database tables are missing')
    for row in db.execute('SELECT state FROM training_sessions'):
        try: state=json.loads(row[0])
        except (ValueError,TypeError) as exc: raise ValueError('Invalid saved training JSON') from exc
        validate_legacy_state(state)

def migrate_v58_to_v59(db: sqlite3.Connection, now_ms: int) -> None:
    if db.execute('PRAGMA user_version').fetchone()[0]!=58:
        raise ValueError('Expected schema v58')
    _validate(db,58)
    for sql in DDL: db.execute(sql)
    db.execute('INSERT INTO py_migrations VALUES(59,?)',(now_ms,))
    db.execute('PRAGMA user_version=59')

def initialize(path: Path, backup_dir: Path) -> None:
    path=Path(path).resolve()
    marker=path.parent/'.fitness-initialized'
    fresh=not path.exists()
    if fresh and marker.exists(): raise FileNotFoundError('Previously initialized database is missing')
    if fresh:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb'): pass
    db=None
    try:
        db=open_database(path)
        db.execute('BEGIN IMMEDIATE')
        version=db.execute('PRAGMA user_version').fetchone()[0]
        if fresh:
            # The bundled legacy DDL contains only schema statements, never sample rows.
            for statement in (Path(__file__).with_name('schema_v58.sql')).read_text(encoding='utf-8').split(';'):
                if statement.strip(): db.execute(statement)
            db.execute('PRAGMA user_version=58')
            version=58
        if version not in {58,59}: raise ValueError(f'Unsupported database version: {version}')
        _validate(db,version)
        if version==58:
            if not fresh:
                backup_database(path,Path(backup_dir)/f'v58-{uuid.uuid4().hex}.sqlite')
            migrate_v58_to_v59(db,time.time_ns()//1_000_000)
        db.commit()
    except BaseException:
        if db is not None: db.rollback()
        if fresh:
            if db is not None: db.close(); db=None
            path.unlink(missing_ok=True)
        raise
    finally:
        if db is not None: db.close()
    marker.write_text('59',encoding='ascii')
