param(
    [Parameter(Mandatory = $true)]
    [string]$FunctionAppName,
    [string]$ResourceGroup = "valuequest-ai",
    [string]$SubscriptionId = "64ea8ac1-c0a2-402c-95ef-6c04525cb41a",

    [Parameter(Mandatory = $true)]
    [string]$ZohoClientId,
    [Parameter(Mandatory = $true)]
    [string]$ZohoClientSecret,
    [Parameter(Mandatory = $true)]
    [string]$ZohoRefreshToken,
    [string]$ZohoBaseUrl = "https://www.zohoapis.in",
    [string]$ZohoAccountsBaseUrl = "https://accounts.zoho.in",

    [Parameter(Mandatory = $true)]
    [string]$SqlServer,
    [Parameter(Mandatory = $true)]
    [string]$SqlDatabase,
    [int]$SqlPort = 1433,
    [ValidateSet("managed_identity", "sql_password")]
    [string]$SqlAuthMode = "managed_identity",
    [string]$SqlManagedIdentityClientId = "",
    [string]$SqlUsername = "",
    [string]$SqlPassword = "",

    [string]$DealsModuleApiName = "Deals",
    [string]$ContactsModuleApiName = "Contacts"
)

$ErrorActionPreference = "Stop"

az account set --subscription $SubscriptionId | Out-Null

$settings = @(
    "ZOHO_CLIENT_ID=$ZohoClientId",
    "ZOHO_CLIENT_SECRET=$ZohoClientSecret",
    "ZOHO_REFRESH_TOKEN=$ZohoRefreshToken",
    "ZOHO_BASE_URL=$ZohoBaseUrl",
    "ZOHO_ACCOUNTS_BASE_URL=$ZohoAccountsBaseUrl",
    "ZOHO_CONTACTS_MODULE=$ContactsModuleApiName",
    "ZOHO_DEALS_MODULE=$DealsModuleApiName",
    "SQL_SERVER=$SqlServer",
    "SQL_DATABASE=$SqlDatabase",
    "SQL_PORT=$SqlPort",
    "SQL_AUTH_MODE=$SqlAuthMode"
)

if ($SqlAuthMode -eq "managed_identity") {
    $settings += "SQL_MANAGED_IDENTITY_CLIENT_ID=$SqlManagedIdentityClientId"
}
else {
    if ([string]::IsNullOrWhiteSpace($SqlUsername) -or [string]::IsNullOrWhiteSpace($SqlPassword)) {
        throw "SqlUsername and SqlPassword are required when SqlAuthMode=sql_password."
    }
    $settings += "SQL_USERNAME=$SqlUsername"
    $settings += "SQL_PASSWORD=$SqlPassword"
}

az functionapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $FunctionAppName `
    --settings $settings | Out-Null

Write-Host "App settings updated." -ForegroundColor Green
