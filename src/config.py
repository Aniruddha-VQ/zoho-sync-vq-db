import os
from dataclasses import dataclass


def _read_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required setting: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    zoho_base_url: str
    zoho_accounts_base_url: str
    zoho_client_id: str
    zoho_client_secret: str
    zoho_refresh_token: str
    contacts_module: str
    deals_module: str
    schema_name: str
    auto_init_schema: bool
    sync_lookback_minutes: int
    sql_server: str
    sql_database: str
    sql_port: int
    sql_auth_mode: str
    sql_username: str
    sql_password: str
    sql_managed_identity_client_id: str
    sql_odbc_driver: str

    @staticmethod
    def from_env() -> "Settings":
        sql_auth_mode = os.getenv("SQL_AUTH_MODE", "managed_identity").strip().lower()
        if sql_auth_mode not in ("managed_identity", "sql_password"):
            raise ValueError(
                "SQL_AUTH_MODE must be one of: managed_identity, sql_password"
            )
        settings = Settings(
            zoho_base_url=os.getenv("ZOHO_BASE_URL", "https://www.zohoapis.in").strip(),
            zoho_accounts_base_url=os.getenv(
                "ZOHO_ACCOUNTS_BASE_URL", "https://accounts.zoho.in"
            ).strip(),
            zoho_client_id=_read_required("ZOHO_CLIENT_ID"),
            zoho_client_secret=_read_required("ZOHO_CLIENT_SECRET"),
            zoho_refresh_token=_read_required("ZOHO_REFRESH_TOKEN"),
            contacts_module=os.getenv("ZOHO_CONTACTS_MODULE", "Contacts").strip(),
            deals_module=os.getenv("ZOHO_DEALS_MODULE", "Deals").strip(),
            schema_name=os.getenv("ZOHO_SCHEMA", "zoho").strip(),
            auto_init_schema=os.getenv("SQL_AUTO_INIT_SCHEMA", "true").strip().lower()
            in ("1", "true", "yes", "y"),
            sync_lookback_minutes=int(os.getenv("SYNC_LOOKBACK_MINUTES", "5")),
            sql_server=_read_required("SQL_SERVER"),
            sql_database=_read_required("SQL_DATABASE"),
            sql_port=int(os.getenv("SQL_PORT", "1433")),
            sql_auth_mode=sql_auth_mode,
            sql_username=os.getenv("SQL_USERNAME", "").strip(),
            sql_password=os.getenv("SQL_PASSWORD", "").strip(),
            sql_managed_identity_client_id=os.getenv(
                "SQL_MANAGED_IDENTITY_CLIENT_ID", ""
            ).strip(),
            sql_odbc_driver=os.getenv("SQL_ODBC_DRIVER", "ODBC Driver 18 for SQL Server").strip(),
        )
        if settings.sql_auth_mode == "sql_password" and (
            not settings.sql_username or not settings.sql_password
        ):
            raise ValueError(
                "SQL_USERNAME and SQL_PASSWORD are required when SQL_AUTH_MODE=sql_password"
            )
        return settings
