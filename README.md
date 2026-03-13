# Zoho CRM -> VQ-Data Sync (Azure Function App)

Daily sync from Zoho CRM modules:
- `Contacts`
- `Deals` (your "Account" business object)
- `Users` export for owner ID -> owner name mapping

The app performs:
- Initial full backfill when no checkpoint exists
- Daily incremental sync using Zoho `Modified_Time` (`If-Modified-Since`)
- Upsert by Zoho `record_id` (`id` field)

Data is written into SQL schema `zoho` (auto-created):
- `zoho.contacts_raw`
- `zoho.deals_raw`
- `zoho.users_raw`
- `zoho.sync_state`
- `zoho.vw_owner_mapping`

SQL authentication modes:
- `managed_identity` (recommended/default for Azure)
- `sql_password` (fallback for local/testing)

## Runtime
- Azure Functions v4
- Python 3.11

## Local setup
1. Create venv and install dependencies:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
2. Copy `local.settings.sample.json` to `local.settings.json` and fill values.
3. Run locally:
```powershell
func start
```

Manual full sync trigger:
```powershell
curl -X POST "http://localhost:7071/api/sync" -H "Content-Type: application/json" -d "{\"force_full\": true}"
```

Ad-hoc trigger (GET or POST):
```powershell
curl "http://localhost:7071/api/adhoc-run?force_full=true"
```

## Azure deploy
Resource group and subscription are prefilled for your environment:
- Resource Group: `valuequest-ai`
- Region: `centralindia`
- Subscription: `64ea8ac1-c0a2-402c-95ef-6c04525cb41a`

1. Create infrastructure + publish code:
```powershell
.\scripts\deploy_azure.ps1 -FunctionAppName <your-function-app-name>
```

2. Grant DB access to Function App managed identity (run as DB admin):
```sql
CREATE USER [<your-function-app-name>] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [<your-function-app-name>];
ALTER ROLE db_datawriter ADD MEMBER [<your-function-app-name>];
```

If app will auto-create schema/tables/view (`SQL_AUTO_INIT_SCHEMA=true`), also grant:
```sql
ALTER ROLE db_ddladmin ADD MEMBER [<your-function-app-name>];
```

Reference script: `sql/grant_function_mi_access.sql`

3. Configure Zoho + DB endpoint settings (Managed Identity mode):
```powershell
.\scripts\configure_app_settings.ps1 `
  -FunctionAppName <your-function-app-name> `
  -ZohoClientId "<id>" `
  -ZohoClientSecret "<secret>" `
  -ZohoRefreshToken "<refresh-token>" `
  -SqlServer "<server>.database.windows.net" `
  -SqlDatabase "<db-name>"
```

4. Optional: if your Deal module API name is not `Deals`, set:
```powershell
.\scripts\configure_app_settings.ps1 ... -DealsModuleApiName "<actual-api-name>"
```

5. Optional: SQL username/password mode:
```powershell
.\scripts\configure_app_settings.ps1 ... -SqlAuthMode sql_password -SqlUsername "<user>" -SqlPassword "<password>"
```

## Schedule
- Default cron: `0 30 1 * * *` (daily at 01:30 UTC = 07:00 IST)
- Change via `SYNC_CRON` app setting.

## Notes
- `payload_json` stores full Zoho record for lossless ingest.
- `owner_id` and `owner_name` are extracted for convenience.
- `sync_state` stores last successful `Modified_Time` checkpoint by entity.
