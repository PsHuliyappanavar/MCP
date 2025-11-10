#!/bin/bash

# Azure App Service Deployment Script for MCP Servers
# This script automates the deployment of ADO and Jira MCP servers to Azure

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        print_message "$RED" "❌ Azure CLI is not installed. Please install it first."
        echo "Visit: https://docs.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    fi
    print_message "$GREEN" "✅ Azure CLI found"
}

# Function to check if user is logged in
check_azure_login() {
    if ! az account show &> /dev/null; then
        print_message "$YELLOW" "⚠️  Not logged in to Azure. Initiating login..."
        az login
    else
        print_message "$GREEN" "✅ Already logged in to Azure"
    fi
}

# Function to load environment variables
load_env_vars() {
    if [ -f .env ]; then
        print_message "$GREEN" "✅ Loading environment variables from .env file"
        export $(cat .env | grep -v '^#' | xargs)
    else
        print_message "$YELLOW" "⚠️  No .env file found. Using environment variables."
    fi
}

# Function to validate required environment variables
validate_env_vars() {
    local server_type=$1
    local missing_vars=()

    if [ "$server_type" == "ado" ]; then
        [ -z "$ADO_CLIENT_ID" ] && missing_vars+=("ADO_CLIENT_ID")
        [ -z "$ADO_CLIENT_SECRET" ] && missing_vars+=("ADO_CLIENT_SECRET")
        [ -z "$ADO_TENANT_ID" ] && missing_vars+=("ADO_TENANT_ID")
    elif [ "$server_type" == "jira" ]; then
        # Check for OAuth credentials (required)
        [ -z "$ATLASSIAN_CLIENT_ID" ] && missing_vars+=("ATLASSIAN_CLIENT_ID")
        [ -z "$ATLASSIAN_CLIENT_SECRET" ] && missing_vars+=("ATLASSIAN_CLIENT_SECRET")
    fi

    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_message "$RED" "❌ Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "   - $var"
        done
        exit 1
    fi
    print_message "$GREEN" "✅ All required environment variables present"
}

# Function to create resource group
create_resource_group() {
    local rg_name=$1
    local location=$2

    if az group show --name "$rg_name" &> /dev/null; then
        print_message "$YELLOW" "⚠️  Resource group '$rg_name' already exists"
    else
        print_message "$YELLOW" "📦 Creating resource group '$rg_name' in '$location'..."
        az group create --name "$rg_name" --location "$location"
        print_message "$GREEN" "✅ Resource group created"
    fi
}

# Function to deploy web app
deploy_webapp() {
    local app_name=$1
    local rg_name=$2
    local server_type=$3

    print_message "$YELLOW" "🚀 Deploying '$app_name' to Azure App Service..."

    # Create/update the web app
    az webapp up \
        --name "$app_name" \
        --resource-group "$rg_name" \
        --runtime "PYTHON:3.11" \
        --sku B1 \
        --location eastus

    print_message "$GREEN" "✅ Web app deployed"
}

# Function to configure app settings
configure_app_settings() {
    local app_name=$1
    local rg_name=$2
    local server_type=$3

    print_message "$YELLOW" "⚙️  Configuring app settings for '$app_name'..."

    if [ "$server_type" == "ado" ]; then
        az webapp config appsettings set \
            --name "$app_name" \
            --resource-group "$rg_name" \
            --settings \
                MCP_SERVER=ado \
                ADO_CLIENT_ID="$ADO_CLIENT_ID" \
                ADO_CLIENT_SECRET="$ADO_CLIENT_SECRET" \
                ADO_TENANT_ID="$ADO_TENANT_ID" \
            --output none
    elif [ "$server_type" == "jira" ]; then
        az webapp config appsettings set \
            --name "$app_name" \
            --resource-group "$rg_name" \
            --settings \
                MCP_SERVER=jira \
                ATLASSIAN_CLIENT_ID="$ATLASSIAN_CLIENT_ID" \
                ATLASSIAN_CLIENT_SECRET="$ATLASSIAN_CLIENT_SECRET" \
            --output none
    fi

    print_message "$GREEN" "✅ App settings configured"
}

# Function to set startup command
set_startup_command() {
    local app_name=$1
    local rg_name=$2

    print_message "$YELLOW" "🔧 Setting startup command..."

    az webapp config set \
        --name "$app_name" \
        --resource-group "$rg_name" \
        --startup-file "python startup.py" \
        --output none

    print_message "$GREEN" "✅ Startup command configured"
}

# Function to restart web app
restart_webapp() {
    local app_name=$1
    local rg_name=$2

    print_message "$YELLOW" "🔄 Restarting '$app_name'..."
    az webapp restart --name "$app_name" --resource-group "$rg_name" --output none
    print_message "$GREEN" "✅ Web app restarted"
}

# Function to display deployment summary
display_summary() {
    local app_name=$1
    local rg_name=$2

    print_message "$GREEN" "\n========================================="
    print_message "$GREEN" "🎉 Deployment Complete!"
    print_message "$GREEN" "=========================================\n"

    echo "App Name: $app_name"
    echo "Resource Group: $rg_name"
    echo "URL: https://$app_name.azurewebsites.net"
    echo ""
    echo "Useful commands:"
    echo "  View logs: az webapp log tail --name $app_name --resource-group $rg_name"
    echo "  SSH access: az webapp ssh --name $app_name --resource-group $rg_name"
    echo "  Stop app: az webapp stop --name $app_name --resource-group $rg_name"
    echo "  Start app: az webapp start --name $app_name --resource-group $rg_name"
    echo ""
}

# Main deployment function
deploy_mcp_server() {
    local server_type=$1
    local app_name=$2
    local rg_name=${3:-mcp-servers-rg}
    local location=${4:-eastus}

    print_message "$GREEN" "\n========================================="
    print_message "$GREEN" "Starting $server_type MCP Server Deployment"
    print_message "$GREEN" "=========================================\n"

    # Validation
    check_azure_cli
    check_azure_login
    load_env_vars
    validate_env_vars "$server_type"

    # Deployment steps
    create_resource_group "$rg_name" "$location"
    deploy_webapp "$app_name" "$rg_name" "$server_type"
    configure_app_settings "$app_name" "$rg_name" "$server_type"
    set_startup_command "$app_name" "$rg_name"
    restart_webapp "$app_name" "$rg_name"

    # Summary
    display_summary "$app_name" "$rg_name"
}

# Show usage
show_usage() {
    cat << EOF
Usage: ./deploy.sh [SERVER_TYPE] [APP_NAME] [RESOURCE_GROUP] [LOCATION]

Arguments:
  SERVER_TYPE       Either 'ado' or 'jira' (required)
  APP_NAME          Name for the Azure Web App (required)
  RESOURCE_GROUP    Resource group name (default: mcp-servers-rg)
  LOCATION          Azure region (default: eastus)

Examples:
  ./deploy.sh ado ado-mcp-server
  ./deploy.sh jira jira-mcp-server my-rg westus
  ./deploy.sh ado ado-mcp-server mcp-servers-rg eastus

Environment Variables Required:
  For ADO:
    - ADO_CLIENT_ID
    - ADO_CLIENT_SECRET
    - ADO_TENANT_ID

  For Jira (OAuth):
    - ATLASSIAN_CLIENT_ID
  For Jira (OAuth):
    - ATLASSIAN_CLIENT_ID
    - ATLASSIAN_CLIENT_SECRET

Create a .env file or set these in your environment before running.

EOF
}

# Main script execution
if [ $# -lt 2 ]; then
    show_usage
    exit 1
fi

SERVER_TYPE=$1
APP_NAME=$2
RESOURCE_GROUP=${3:-mcp-servers-rg}
LOCATION=${4:-eastus}

# Validate server type
if [ "$SERVER_TYPE" != "ado" ] && [ "$SERVER_TYPE" != "jira" ]; then
    print_message "$RED" "❌ Invalid server type. Must be 'ado' or 'jira'"
    show_usage
    exit 1
fi

# Execute deployment
deploy_mcp_server "$SERVER_TYPE" "$APP_NAME" "$RESOURCE_GROUP" "$LOCATION"
