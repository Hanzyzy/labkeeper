"""LabKeeper — Date/time & config helpers (avoid repeated None-checks everywhere)"""
from datetime import datetime


def utcnow():
    """Non-deprecated replacement for ``datetime.utcnow``.

    We keep naive datetimes internally because the existing DB rows are naive;
    mixing aware/naive would cause comparison errors in SQLAlchemy + SQLite.
    """
    return datetime.now()


def get_config():
    """Get the Config singleton, always returning an object.

    Used to avoid ``AttributeError`` when ``Config.get_solo()`` is None
    (e.g. before seed has run).
    """
    from models import Config

    cfg = Config.get_solo()
    if cfg is None:
        class _F:
            loan_duration_hours = 2
            school_name = "SMK Telkom"
            base_url = "http://localhost:5000"
        return _F()
    return cfg
