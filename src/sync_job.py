import logging
from datetime import timedelta
from typing import Any

from src.config import Settings
from src.db import SqlServerStore
from src.time_utils import parse_zoho_datetime
from src.zoho_client import ZohoClient


def run_sync_job(trigger: str, force_full: bool = False) -> dict[str, Any]:
    settings = Settings.from_env()
    client = ZohoClient(settings)
    store = SqlServerStore(settings)
    if settings.auto_init_schema:
        store.ensure_schema()

    logging.info("Starting Zoho sync. Trigger=%s, force_full=%s", trigger, force_full)

    contacts_result = _sync_module(
        client=client,
        store=store,
        entity_name="contacts",
        module_api_name=settings.contacts_module,
        lookback_minutes=settings.sync_lookback_minutes,
        force_full=force_full,
    )
    deals_result = _sync_module(
        client=client,
        store=store,
        entity_name="deals",
        module_api_name=settings.deals_module,
        lookback_minutes=settings.sync_lookback_minutes,
        force_full=force_full,
    )
    users_rows = client.get_users()
    store.upsert_users(users_rows)

    result = {
        "status": "ok",
        "trigger": trigger,
        "force_full": force_full,
        "contacts": contacts_result,
        "deals": deals_result,
        "users": {"rows_upserted": len(users_rows)},
    }
    logging.info("Zoho sync completed: %s", result)
    return result


def _sync_module(
    *,
    client: ZohoClient,
    store: SqlServerStore,
    entity_name: str,
    module_api_name: str,
    lookback_minutes: int,
    force_full: bool,
) -> dict[str, Any]:
    last_modified = None if force_full else store.get_last_modified_time(entity_name)
    modified_since = None
    if last_modified is not None:
        modified_since = last_modified - timedelta(minutes=lookback_minutes)

    if modified_since is None:
        rows = client.get_records(module_api_name=module_api_name)
    else:
        rows = client.get_records(
            module_api_name=module_api_name,
            modified_since=modified_since,
        )

    if entity_name == "contacts":
        store.upsert_contacts(rows)
    elif entity_name == "deals":
        store.upsert_deals(rows)
    else:
        raise ValueError(f"Unsupported entity: {entity_name}")

    max_modified = _max_modified_time(rows)
    if max_modified is not None:
        store.upsert_last_modified_time(entity_name, max_modified)

    return {
        "module_api_name": module_api_name,
        "rows_upserted": len(rows),
        "incremental_from_utc": modified_since.isoformat() if modified_since else None,
        "last_modified_written_utc": max_modified.isoformat() if max_modified else None,
    }


def _max_modified_time(records: list[dict[str, Any]]):
    candidates = [
        parse_zoho_datetime(str(row.get("Modified_Time", "")).strip())
        for row in records
        if row.get("Modified_Time")
    ]
    values = [c for c in candidates if c is not None]
    return max(values) if values else None
