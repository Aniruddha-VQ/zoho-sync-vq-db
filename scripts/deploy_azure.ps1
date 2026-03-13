param(
    [Parameter(Mandatory = $true)]
    [string]$FunctionAppName,
    [string]$ResourceGroup = "valuequest-ai",
    [string]$Location = "centralindia",
    [string]$SubscriptionId = "64ea8ac1-c0a2-402c-95ef-6c04525cb41a",
    [string]$StorageAccountName = "",
    [ValidateSet("flexconsumption", "consumption")]
    [string]$HostingModel = "flexconsumption",
    [switch]$SkipPublish
)

$ErrorActionPreference = "Stop"

Write-Host "Setting subscription..." -ForegroundColor Cyan
az account set --subscription $SubscriptionId | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to set Azure subscription." }

$rgExists = az group exists --name $ResourceGroup | ConvertFrom-Json
if (-not $rgExists) {
    throw "Resource group '$ResourceGroup' does not exist."
}

if ([string]::IsNullOrWhiteSpace($StorageAccountName)) {
    $normalized = ($FunctionAppName.ToLower() -replace "[^a-z0-9]", "")
    if ($normalized.Length -gt 18) { $normalized = $normalized.Substring(0, 18) }
    $StorageAccountName = "st${normalized}zoho"
    if ($StorageAccountName.Length -gt 24) { $StorageAccountName = $StorageAccountName.Substring(0, 24) }
}

Write-Host "Using storage account: $StorageAccountName" -ForegroundColor Cyan

$storageExists = $false
try {
    $null = az storage account show --resource-group $ResourceGroup --name $StorageAccountName --query "name" --output tsv 2>$null
    if ($LASTEXITCODE -eq 0) { $storageExists = $true }
}
catch {
    $storageExists = $false
}

if (-not $storageExists) {
    Write-Host "Creating storage account..." -ForegroundColor Cyan
    az storage account create `
        --name $StorageAccountName `
        --resource-group $ResourceGroup `
        --location $Location `
        --sku Standard_LRS `
        --kind StorageV2 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to create storage account $StorageAccountName." }
}

$appExists = $false
try {
    $null = az functionapp show --resource-group $ResourceGroup --name $FunctionAppName --query "name" --output tsv 2>$null
    if ($LASTEXITCODE -eq 0) { $appExists = $true }
}
catch {
    $appExists = $false
}

if (-not $appExists) {
    Write-Host "Creating Function App..." -ForegroundColor Cyan
    if ($HostingModel -eq "flexconsumption") {
        az functionapp create `
            --name $FunctionAppName `
            --resource-group $ResourceGroup `
            --storage-account $StorageAccountName `
            --flexconsumption-location $Location `
            --runtime python `
            --runtime-version 3.11 `
            --functions-version 4 | Out-Null
    }
    else {
        az functionapp create `
            --name $FunctionAppName `
            --resource-group $ResourceGroup `
            --consumption-plan-location $Location `
            --runtime python `
            --runtime-version 3.11 `
            --functions-version 4 `
            --os-type Linux `
            --storage-account $StorageAccountName | Out-Null
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Function App $FunctionAppName using hosting model $HostingModel."
    }
}

Write-Host "Applying base app settings..." -ForegroundColor Cyan
az functionapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $FunctionAppName `
    --settings `
    "SYNC_CRON=0 30 1 * * *" `
    "ZOHO_SCHEMA=zoho" `
    "ZOHO_CONTACTS_MODULE=Contacts" `
    "ZOHO_DEALS_MODULE=Deals" `
    "SYNC_LOOKBACK_MINUTES=5" `
    "SQL_AUTH_MODE=managed_identity" `
    "SQL_AUTO_INIT_SCHEMA=false" `
    "SQL_ODBC_DRIVER=ODBC Driver 18 for SQL Server" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to set function app settings." }

Write-Host "Enabling system-assigned managed identity..." -ForegroundColor Cyan
az functionapp identity assign `
    --resource-group $ResourceGroup `
    --name $FunctionAppName | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to assign managed identity." }

$principalId = az functionapp identity show `
    --resource-group $ResourceGroup `
    --name $FunctionAppName `
    --query principalId `
    --output tsv
if ($LASTEXITCODE -ne 0) { throw "Failed to read managed identity principalId." }

Write-Host "Function App managed identity principalId: $principalId" -ForegroundColor Green

if (-not $SkipPublish) {
    Write-Host "Publishing function code..." -ForegroundColor Cyan
    func azure functionapp publish $FunctionAppName --python
    if ($LASTEXITCODE -ne 0) { throw "Failed to publish Function App code." }
}
else {
    Write-Host "Skipped code publish. Use: func azure functionapp publish $FunctionAppName --python" -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Green
