# Azure App Service Deployment Script for MCP Servers (PowerShell)
# This script automates the deployment of ADO and Jira MCP servers to Azure

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("ado", "jira")]
    [string]$ServerType,
    
    [Parameter(Mandatory = $true)]
    [string]$AppName,
    
    [Parameter(Mandatory = $false)]
    [string]$ResourceGroup = "mcp-servers-rg",
    
    [Parameter(Mandatory = $false)]
    [string]$Location = "eastus"
)

# Color functions
function Write-ColorOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,
        
        [Parameter(Mandatory = $false)]
        [ValidateSet("Green", "Yellow", "Red", "Cyan")]
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# Check if Azure CLI is installed
function Test-AzureCLI {
    try {
        $null = az --version 2>&1
        Write-ColorOutput "✅ Azure CLI found" -Color Green
        return $true
    }
    catch {
        Write-ColorOutput "❌ Azure CLI is not installed. Please install it first." -Color Red
        Write-ColorOutput "Visit: https://docs.microsoft.com/cli/azure/install-azure-cli" -Color Yellow
        return $false
    }
}

# Check if user is logged in to Azure
function Test-AzureLogin {
    try {
        $null = az account show 2>&1
        Write-ColorOutput "✅ Already logged in to Azure" -Color Green
        return $true
    }
    catch {
        Write-ColorOutput "⚠️  Not logged in to Azure. Initiating login..." -Color Yellow
        az login
        return $?
    }
}

# Load environment variables from .env file
function Import-EnvFile {
    if (Test-Path .env) {
        Write-ColorOutput "✅ Loading environment variables from .env file" -Color Green
        Get-Content .env | ForEach-Object {
            if ($_ -match '^([^#].+?)=(.+)$') {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim()
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
        return $true
    }
    else {
        Write-ColorOutput "⚠️  No .env file found. Using existing environment variables." -Color Yellow
        return $false
    }
}

# Validate required environment variables
function Test-EnvVars {
    param([string]$ServerType)
    
    $missingVars = @()
    
    if ($ServerType -eq "ado") {
        if (-not $env:ADO_CLIENT_ID) { $missingVars += "ADO_CLIENT_ID" }
        if (-not $env:ADO_CLIENT_SECRET) { $missingVars += "ADO_CLIENT_SECRET" }
        if (-not $env:ADO_TENANT_ID) { $missingVars += "ADO_TENANT_ID" }
    }
    elseif ($ServerType -eq "jira") {
        # Check for OAuth credentials (required)
        if (-not $env:ATLASSIAN_CLIENT_ID) { $missingVars += "ATLASSIAN_CLIENT_ID" }
        if (-not $env:ATLASSIAN_CLIENT_SECRET) { $missingVars += "ATLASSIAN_CLIENT_SECRET" }
    }
    
    if ($missingVars.Count -gt 0) {
        Write-ColorOutput "❌ Missing required environment variables:" -Color Red
        foreach ($var in $missingVars) {
            Write-Host "   - $var"
        }
        return $false
    }
    
    Write-ColorOutput "✅ All required environment variables present" -Color Green
    return $true
}

# Create resource group
function New-AzureResourceGroup {
    param(
        [string]$Name,
        [string]$Location
    )
    
    try {
        $rg = az group show --name $Name 2>&1
        if ($?) {
            Write-ColorOutput "⚠️  Resource group '$Name' already exists" -Color Yellow
        }
    }
    catch {
        Write-ColorOutput "📦 Creating resource group '$Name' in '$Location'..." -Color Cyan
        az group create --name $Name --location $Location --output none
        Write-ColorOutput "✅ Resource group created" -Color Green
    }
}

# Deploy web app
function Deploy-WebApp {
    param(
        [string]$AppName,
        [string]$ResourceGroup
    )
    
    Write-ColorOutput "🚀 Deploying '$AppName' to Azure App Service..." -Color Cyan
    
    az webapp up `
        --name $AppName `
        --resource-group $ResourceGroup `
        --runtime "PYTHON:3.11" `
        --sku B1 `
        --location eastus `
        --output none
    
    Write-ColorOutput "✅ Web app deployed" -Color Green
}

# Configure app settings
function Set-AppSettings {
    param(
        [string]$AppName,
        [string]$ResourceGroup,
        [string]$ServerType
    )
    
    Write-ColorOutput "⚙️  Configuring app settings for '$AppName'..." -Color Cyan
    
    if ($ServerType -eq "ado") {
        az webapp config appsettings set `
            --name $AppName `
            --resource-group $ResourceGroup `
            --settings `
            MCP_SERVER=ado `
            ADO_CLIENT_ID="$env:ADO_CLIENT_ID" `
            ADO_CLIENT_SECRET="$env:ADO_CLIENT_SECRET" `
            ADO_TENANT_ID="$env:ADO_TENANT_ID" `
            --output none
    }
    elseif ($ServerType -eq "jira") {
        az webapp config appsettings set `
            --name $AppName `
            --resource-group $ResourceGroup `
            --settings `
            MCP_SERVER=jira `
            ATLASSIAN_CLIENT_ID="$env:ATLASSIAN_CLIENT_ID" `
            ATLASSIAN_CLIENT_SECRET="$env:ATLASSIAN_CLIENT_SECRET" `
            --output none
    }
    
    Write-ColorOutput "✅ App settings configured" -Color Green
}

# Set startup command
function Set-StartupCommand {
    param(
        [string]$AppName,
        [string]$ResourceGroup
    )
    
    Write-ColorOutput "🔧 Setting startup command..." -Color Cyan
    
    az webapp config set `
        --name $AppName `
        --resource-group $ResourceGroup `
        --startup-file "python startup.py" `
        --output none
    
    Write-ColorOutput "✅ Startup command configured" -Color Green
}

# Restart web app
function Restart-WebApp {
    param(
        [string]$AppName,
        [string]$ResourceGroup
    )
    
    Write-ColorOutput "🔄 Restarting '$AppName'..." -Color Cyan
    az webapp restart --name $AppName --resource-group $ResourceGroup --output none
    Write-ColorOutput "✅ Web app restarted" -Color Green
}

# Display deployment summary
function Show-DeploymentSummary {
    param(
        [string]$AppName,
        [string]$ResourceGroup
    )
    
    Write-Host ""
    Write-ColorOutput "=========================================" -Color Green
    Write-ColorOutput "🎉 Deployment Complete!" -Color Green
    Write-ColorOutput "=========================================" -Color Green
    Write-Host ""
    Write-Host "App Name: $AppName"
    Write-Host "Resource Group: $ResourceGroup"
    Write-Host "URL: https://$AppName.azurewebsites.net"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  View logs: az webapp log tail --name $AppName --resource-group $ResourceGroup"
    Write-Host "  SSH access: az webapp ssh --name $AppName --resource-group $ResourceGroup"
    Write-Host "  Stop app: az webapp stop --name $AppName --resource-group $ResourceGroup"
    Write-Host "  Start app: az webapp start --name $AppName --resource-group $ResourceGroup"
    Write-Host ""
}

# Main deployment function
function Start-MCPServerDeployment {
    Write-Host ""
    Write-ColorOutput "=========================================" -Color Green
    Write-ColorOutput "Starting $ServerType MCP Server Deployment" -Color Green
    Write-ColorOutput "=========================================" -Color Green
    Write-Host ""
    
    # Validation
    if (-not (Test-AzureCLI)) { exit 1 }
    if (-not (Test-AzureLogin)) { exit 1 }
    Import-EnvFile
    if (-not (Test-EnvVars -ServerType $ServerType)) { exit 1 }
    
    # Deployment steps
    New-AzureResourceGroup -Name $ResourceGroup -Location $Location
    Deploy-WebApp -AppName $AppName -ResourceGroup $ResourceGroup
    Set-AppSettings -AppName $AppName -ResourceGroup $ResourceGroup -ServerType $ServerType
    Set-StartupCommand -AppName $AppName -ResourceGroup $ResourceGroup
    Restart-WebApp -AppName $AppName -ResourceGroup $ResourceGroup
    
    # Summary
    Show-DeploymentSummary -AppName $AppName -ResourceGroup $ResourceGroup
}

# Execute deployment
Start-MCPServerDeployment
