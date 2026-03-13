from datetime import UTC, datetime


def parse_zoho_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    # Zoho API usually returns ISO 8601 values, but CSV exports can come as dd-mm-yyyy HH:MM.
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        pass

    for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def to_zoho_if_modified_since(value: datetime) -> str:
    utc_value = value.replace(tzinfo=UTC)
    return utc_value.isoformat(timespec="seconds")
