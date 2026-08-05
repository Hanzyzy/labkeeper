from datetime import datetime, timezone, timedelta

# WIB (Waktu Indonesia Barat / Asia/Jakarta) timezone (UTC+7)
WIB = timezone(timedelta(hours=7))


def utcnow():
    """Returns naive datetime in Asia/Jakarta timezone (WIB, UTC+7).

    We keep naive datetimes internally for SQLite compatibility while ensuring
    timestamps match Jakarta, Indonesia time.
    """
    return datetime.now(WIB).replace(tzinfo=None)


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
