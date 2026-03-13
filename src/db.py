import json
import re
import struct
from datetime import UTC, datetime
from typing import Any

import pyodbc
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

from src.config import Settings

_VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SqlServerStore:
    def __init__(self, settings: Settings) -> None:
        if not _VALID_IDENTIFIER.match(settings.schema_name):
            raise ValueError(
                f"Invalid schema name '{settings.schema_name}'. Use letters, digits, underscore only."
            )
        self._settings = settings
        self._schema = settings.schema_name

    def _base_conn_str(self) -> str:
        return (
            f"Driver={{{self._settings.sql_odbc_driver}}};"
            f"Server=tcp:{self._settings.sql_server},{self._settings.sql_port};"
            f"Database={self._settings.sql_database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )

    def _connect(self) -> pyodbc.Connection:
        conn_str = self._base_conn_str()
        if self._settings.sql_auth_mode == "managed_identity":
            import logging

            if self._settings.sql_managed_identity_client_id:
                credential = ManagedIdentityCredential(
                    client_id=self._settings.sql_managed_identity_client_id
                )
            else:
                credential = ManagedIdentityCredential()
            token = credential.get_token("https://database.windows.net/.default")
            logging.info(
                "Acquired SQL token, expires_on=%s, token_length=%d",
                token.expires_on,
                len(token.token),
            )
            token_bytes = token.token.encode("utf-16-le")
            token_struct = struct.pack(
                f"<I{len(token_bytes)}s", len(token_bytes), token_bytes
            )
            return pyodbc.connect(
                conn_str, attrs_before={1256: token_struct}, autocommit=False
            )

        conn_str += (
            f"UID={self._settings.sql_username};PWD={self._settings.sql_password};"
        )
        return pyodbc.connect(conn_str, autocommit=False)

    def ensure_schema(self) -> None:
        ddl = f"""
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = '{self._schema}')
BEGIN
    EXEC('CREATE SCHEMA [{self._schema}]')
END

IF OBJECT_ID('{self._schema}.contacts_raw', 'U') IS NULL
BEGIN
    CREATE TABLE [{self._schema}].[contacts_raw](
        [record_id] NVARCHAR(100) NOT NULL PRIMARY KEY,
        [owner_id] NVARCHAR(100) NULL,
        [owner_name] NVARCHAR(255) NULL,
        [created_time_utc] DATETIME2 NULL,
        [modified_time_utc] DATETIME2 NULL,
        [payload_json] NVARCHAR(MAX) NOT NULL,
        [last_synced_at_utc] DATETIME2 NOT NULL CONSTRAINT DF_contacts_last_synced DEFAULT SYSUTCDATETIME()
    )
    CREATE INDEX IX_contacts_modified_time_utc ON [{self._schema}].[contacts_raw]([modified_time_utc])
END

IF OBJECT_ID('{self._schema}.deals_raw', 'U') IS NULL
BEGIN
    CREATE TABLE [{self._schema}].[deals_raw](
        [record_id] NVARCHAR(100) NOT NULL PRIMARY KEY,
        [owner_id] NVARCHAR(100) NULL,
        [owner_name] NVARCHAR(255) NULL,
        [created_time_utc] DATETIME2 NULL,
        [modified_time_utc] DATETIME2 NULL,
        [payload_json] NVARCHAR(MAX) NOT NULL,
        [last_synced_at_utc] DATETIME2 NOT NULL CONSTRAINT DF_deals_last_synced DEFAULT SYSUTCDATETIME()
    )
    CREATE INDEX IX_deals_modified_time_utc ON [{self._schema}].[deals_raw]([modified_time_utc])
END

IF OBJECT_ID('{self._schema}.users_raw', 'U') IS NULL
BEGIN
    CREATE TABLE [{self._schema}].[users_raw](
        [record_id] NVARCHAR(100) NOT NULL PRIMARY KEY,
        [full_name] NVARCHAR(255) NULL,
        [email] NVARCHAR(320) NULL,
        [status] NVARCHAR(100) NULL,
        [payload_json] NVARCHAR(MAX) NOT NULL,
        [last_synced_at_utc] DATETIME2 NOT NULL CONSTRAINT DF_users_last_synced DEFAULT SYSUTCDATETIME()
    )
END

IF OBJECT_ID('{self._schema}.sync_state', 'U') IS NULL
BEGIN
    CREATE TABLE [{self._schema}].[sync_state](
        [entity_name] NVARCHAR(50) NOT NULL PRIMARY KEY,
        [last_modified_time_utc] DATETIME2 NULL,
        [updated_at_utc] DATETIME2 NOT NULL CONSTRAINT DF_sync_state_updated DEFAULT SYSUTCDATETIME()
    )
END

EXEC('
CREATE OR ALTER VIEW [{self._schema}].[vw_owner_mapping]
AS
SELECT
    o.owner_id AS zoho_owner_id,
    COALESCE(u.full_name, o.owner_name) AS owner_name,
    u.email
FROM (
    SELECT owner_id, owner_name FROM [{self._schema}].[contacts_raw] WHERE owner_id IS NOT NULL
    UNION
    SELECT owner_id, owner_name FROM [{self._schema}].[deals_raw] WHERE owner_id IS NOT NULL
) o
LEFT JOIN [{self._schema}].[users_raw] u
    ON u.record_id = o.owner_id
')
"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def get_last_modified_time(self, entity_name: str) -> datetime | None:
        sql = (
            f"SELECT [last_modified_time_utc] FROM [{self._schema}].[sync_state] "
            "WHERE [entity_name] = ?"
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (entity_name,))
                row = cur.fetchone()
                return row[0] if row else None

    def upsert_last_modified_time(
        self, entity_name: str, last_modified_time_utc: datetime | None
    ) -> None:
        sql = f"""
MERGE [{self._schema}].[sync_state] AS target
USING (SELECT ? AS entity_name, ? AS last_modified_time_utc) AS source
ON target.entity_name = source.entity_name
WHEN MATCHED THEN
    UPDATE SET
        target.last_modified_time_utc = source.last_modified_time_utc,
        target.updated_at_utc = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (entity_name, last_modified_time_utc, updated_at_utc)
    VALUES (source.entity_name, source.last_modified_time_utc, SYSUTCDATETIME());
"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (entity_name, last_modified_time_utc))
            conn.commit()

    def upsert_contacts(self, records: list[dict[str, Any]]) -> None:
        self._upsert_crm_records(table_name="contacts_raw", records=records)

    def upsert_deals(self, records: list[dict[str, Any]]) -> None:
        self._upsert_crm_records(table_name="deals_raw", records=records)

    def _upsert_crm_records(self, table_name: str, records: list[dict[str, Any]]) -> None:
        sql = f"""
MERGE [{self._schema}].[{table_name}] AS target
USING (
    SELECT
        ? AS record_id,
        ? AS owner_id,
        ? AS owner_name,
        ? AS created_time_utc,
        ? AS modified_time_utc,
        ? AS payload_json
) AS source
ON target.record_id = source.record_id
WHEN MATCHED THEN
    UPDATE SET
        target.owner_id = source.owner_id,
        target.owner_name = source.owner_name,
        target.created_time_utc = source.created_time_utc,
        target.modified_time_utc = source.modified_time_utc,
        target.payload_json = source.payload_json,
        target.last_synced_at_utc = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (
        record_id,
        owner_id,
        owner_name,
        created_time_utc,
        modified_time_utc,
        payload_json,
        last_synced_at_utc
    )
    VALUES (
        source.record_id,
        source.owner_id,
        source.owner_name,
        source.created_time_utc,
        source.modified_time_utc,
        source.payload_json,
        SYSUTCDATETIME()
    );
"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                for record in records:
                    record_id = str(record.get("id", "")).strip()
                    if not record_id:
                        continue
                    owner = _get_owner(record)
                    cur.execute(
                        sql,
                        (
                            record_id,
                            owner.get("id"),
                            owner.get("name"),
                            _parse_datetime(record.get("Created_Time")),
                            _parse_datetime(record.get("Modified_Time")),
                            json.dumps(record, separators=(",", ":"), default=str),
                        ),
                    )
            conn.commit()

    def upsert_users(self, records: list[dict[str, Any]]) -> None:
        sql = f"""
MERGE [{self._schema}].[users_raw] AS target
USING (
    SELECT
        ? AS record_id,
        ? AS full_name,
        ? AS email,
        ? AS status,
        ? AS payload_json
) AS source
ON target.record_id = source.record_id
WHEN MATCHED THEN
    UPDATE SET
        target.full_name = source.full_name,
        target.email = source.email,
        target.status = source.status,
        target.payload_json = source.payload_json,
        target.last_synced_at_utc = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (
        record_id,
        full_name,
        email,
        status,
        payload_json,
        last_synced_at_utc
    )
    VALUES (
        source.record_id,
        source.full_name,
        source.email,
        source.status,
        source.payload_json,
        SYSUTCDATETIME()
    );
"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                for record in records:
                    record_id = str(record.get("id", "")).strip()
                    if not record_id:
                        continue
                    cur.execute(
                        sql,
                        (
                            record_id,
                            record.get("full_name") or record.get("name"),
                            record.get("email"),
                            record.get("status"),
                            json.dumps(record, separators=(",", ":"), default=str),
                        ),
                    )
            conn.commit()


def _get_owner(record: dict[str, Any]) -> dict[str, str | None]:
    owner_candidates = [
        "Owner",
        "Contact_Owner",
        "Account_Owner",
    ]
    owner_data: Any = {}
    for key in owner_candidates:
        value = record.get(key)
        if isinstance(value, dict) and value:
            owner_data = value
            break
    owner_id = owner_data.get("id") if isinstance(owner_data, dict) else None
    owner_name = owner_data.get("name") if isinstance(owner_data, dict) else None
    return {"id": owner_id, "name": owner_name}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
