-- Optional manual setup script.
-- The function app creates these objects automatically as well.

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'zoho')
BEGIN
    EXEC('CREATE SCHEMA [zoho]')
END
GO

IF OBJECT_ID('zoho.contacts_raw', 'U') IS NULL
BEGIN
    CREATE TABLE [zoho].[contacts_raw](
        [record_id] NVARCHAR(100) NOT NULL PRIMARY KEY,
        [owner_id] NVARCHAR(100) NULL,
        [owner_name] NVARCHAR(255) NULL,
        [created_time_utc] DATETIME2 NULL,
        [modified_time_utc] DATETIME2 NULL,
        [payload_json] NVARCHAR(MAX) NOT NULL,
        [last_synced_at_utc] DATETIME2 NOT NULL CONSTRAINT DF_contacts_last_synced DEFAULT SYSUTCDATETIME()
    )
    CREATE INDEX IX_contacts_modified_time_utc ON [zoho].[contacts_raw]([modified_time_utc])
END
GO

IF OBJECT_ID('zoho.deals_raw', 'U') IS NULL
BEGIN
    CREATE TABLE [zoho].[deals_raw](
        [record_id] NVARCHAR(100) NOT NULL PRIMARY KEY,
        [owner_id] NVARCHAR(100) NULL,
        [owner_name] NVARCHAR(255) NULL,
        [created_time_utc] DATETIME2 NULL,
        [modified_time_utc] DATETIME2 NULL,
        [payload_json] NVARCHAR(MAX) NOT NULL,
        [last_synced_at_utc] DATETIME2 NOT NULL CONSTRAINT DF_deals_last_synced DEFAULT SYSUTCDATETIME()
    )
    CREATE INDEX IX_deals_modified_time_utc ON [zoho].[deals_raw]([modified_time_utc])
END
GO

IF OBJECT_ID('zoho.users_raw', 'U') IS NULL
BEGIN
    CREATE TABLE [zoho].[users_raw](
        [record_id] NVARCHAR(100) NOT NULL PRIMARY KEY,
        [full_name] NVARCHAR(255) NULL,
        [email] NVARCHAR(320) NULL,
        [status] NVARCHAR(100) NULL,
        [payload_json] NVARCHAR(MAX) NOT NULL,
        [last_synced_at_utc] DATETIME2 NOT NULL CONSTRAINT DF_users_last_synced DEFAULT SYSUTCDATETIME()
    )
END
GO

IF OBJECT_ID('zoho.sync_state', 'U') IS NULL
BEGIN
    CREATE TABLE [zoho].[sync_state](
        [entity_name] NVARCHAR(50) NOT NULL PRIMARY KEY,
        [last_modified_time_utc] DATETIME2 NULL,
        [updated_at_utc] DATETIME2 NOT NULL CONSTRAINT DF_sync_state_updated DEFAULT SYSUTCDATETIME()
    )
END
GO

CREATE OR ALTER VIEW [zoho].[vw_owner_mapping]
AS
SELECT
    o.owner_id AS zoho_owner_id,
    COALESCE(u.full_name, o.owner_name) AS owner_name,
    u.email
FROM (
    SELECT owner_id, owner_name FROM [zoho].[contacts_raw] WHERE owner_id IS NOT NULL
    UNION
    SELECT owner_id, owner_name FROM [zoho].[deals_raw] WHERE owner_id IS NOT NULL
) o
LEFT JOIN [zoho].[users_raw] u
    ON u.record_id = o.owner_id;
GO
