/*
Run this in target Azure SQL database as AAD admin (or privileged user).
Replace <function-app-name> with your function app name:
    func-zoho-sync-vq-prod
*/

CREATE USER [<function-app-name>] FROM EXTERNAL PROVIDER;
GO

ALTER ROLE db_datareader ADD MEMBER [<function-app-name>];
ALTER ROLE db_datawriter ADD MEMBER [<function-app-name>];
GO

-- Required only when SQL_AUTO_INIT_SCHEMA=true (app creates schema/tables/view):
ALTER ROLE db_ddladmin ADD MEMBER [<function-app-name>];
GO
