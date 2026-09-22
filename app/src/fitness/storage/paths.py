"""Locate legacy storage without implicitly replacing missing user data."""
from pathlib import Path

def resolve_database(storage: Path, android: bool) -> Path:
    storage = Path(storage).resolve()
    if android:
        if storage.name != 'data' or storage.parent.name != 'files':
            raise ValueError('Unexpected Android application storage layout')
        path = storage.parent.parent / 'app_flutter' / 'flexify.sqlite'
    else:
        path = storage / 'flexify.sqlite'
    if (path.parent / '.fitness-initialized').exists() and not path.is_file():
        raise FileNotFoundError('Previously initialized database is missing')
    return path
