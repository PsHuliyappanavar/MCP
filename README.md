# MCP Servers Deployment for Azure App Service

This repository contains two Model Context Protocol (MCP) servers ready for deployment to Azure App Service:

- **ADO MCP Server**: Azure DevOps integration with OAuth 2.0
- **Jira MCP Server**: Jira integration with OAuth 2.0

## Features

✅ **JSON-RPC 2.0 Compliant**: Both servers follow the Model Context Protocol specification
✅ **No Hardcoded Credentials**: All credentials sourced from environment variables
✅ **Azure App Service Ready**: Includes all deployment configurations
✅ **OAuth 2.0 Support**: Secure authentication for ADO and Jira
✅ **Rate Limiting**: Built-in 2-second delays to prevent API throttling

## Prerequisites

- Azure CLI installed
- Azure subscription with App Service capability
- For ADO: Azure AD App Registration with DevOps permissions
- For Jira: Atlassian OAuth app or API token

## Quick Start

### 1. Clone and Configure

```bash
cd deployMCP
cp .env.example .env
# Edit .env with your credentials
```

### 2. Configure Environment Variables

#### For Azure DevOps MCP Server:

```bash
ADO_CLIENT_ID=<your-azure-ad-client-id>
ADO_CLIENT_SECRET=<your-azure-ad-client-secret>
ADO_TENANT_ID=<your-azure-tenant-id>
```

**How to get ADO credentials:**

1. Go to Azure Portal → Azure Active Directory → App registrations
2. Create new registration or select existing
3. Add API permission: Azure DevOps → user_impersonation
4. Create client secret under Certificates & secrets
5. Copy Application (client) ID and Directory (tenant) ID

#### For Jira MCP Server (OAuth):

```bash
ATLASSIAN_CLIENT_ID=<your-atlassian-oauth-client-id>
ATLASSIAN_CLIENT_SECRET=<your-atlassian-oauth-client-secret>
```

**How to get Jira OAuth credentials:**

1. Go to https://developer.atlassian.com/console/myapps/
2. Create OAuth 2.0 integration
3. Add callback URL: http://localhost:9000/oauth/callback
4. Configure permissions: Jira API (read/write)
5. Copy Client ID and Secret

### 3. Deploy to Azure App Service

#### Option A: Using Azure CLI (Recommended)

```bash
# Login to Azure
az login

# Create resource group
az group create --name mcp-servers-rg --location eastus

# Deploy ADO MCP Server
az webapp up --name ado-mcp-server --resource-group mcp-servers-rg --runtime "PYTHON:3.11" --sku B1

# Configure ADO MCP Server
az webapp config appsettings set --name ado-mcp-server --resource-group mcp-servers-rg --settings \
  MCP_SERVER=ado \
  ADO_CLIENT_ID="${ADO_CLIENT_ID}" \
  ADO_CLIENT_SECRET="${ADO_CLIENT_SECRET}" \
  ADO_TENANT_ID="${ADO_TENANT_ID}"

# Deploy Jira MCP Server
az webapp up --name jira-mcp-server --resource-group mcp-servers-rg --runtime "PYTHON:3.11" --sku B1

# Configure Jira MCP Server (OAuth)
az webapp config appsettings set --name jira-mcp-server --resource-group mcp-servers-rg --settings \
  MCP_SERVER=jira \
  ATLASSIAN_CLIENT_ID="${ATLASSIAN_CLIENT_ID}" \
  ATLASSIAN_CLIENT_SECRET="${ATLASSIAN_CLIENT_SECRET}"

# Set startup command
az webapp config set --name ado-mcp-server --resource-group mcp-servers-rg --startup-file "python startup.py"
az webapp config set --name jira-mcp-server --resource-group mcp-servers-rg --startup-file "python startup.py"
```

#### Option B: Using Azure Portal

1. Go to Azure Portal → App Services → Create
2. Configure:
   - Runtime: Python 3.11
   - Operating System: Linux
   - App Service Plan: B1 or higher
3. After creation, go to Configuration → Application settings
4. Add environment variables from `.env.example`
5. Add `MCP_SERVER` setting: `ado` or `jira`
6. Go to Deployment Center → Deploy code via Local Git/GitHub
7. Under Configuration → General settings → Startup Command: `python startup.py`

### 4. Testing the Deployment

#### Test ADO MCP Server:

```bash
# Test with echo command
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | \
  az webapp ssh --name ado-mcp-server --resource-group mcp-servers-rg

# Expected response:
# {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"ado-mcp-server","version":"1.0.0"}}}
```

#### Test Jira MCP Server:

```bash
# Test with echo command
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | \
  az webapp ssh --name jira-mcp-server --resource-group mcp-servers-rg

# Expected response:
# {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"jira-mcp-server","version":"1.0.0"}}}
```

## Architecture

### Communication Protocol

Both MCP servers implement **JSON-RPC 2.0** over **stdin/stdout**:

```json
// Request Format
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "create_project",
    "arguments": {
      "projectName": "My Project"
    }
  }
}

// Response Format
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Project created successfully"
      }
    ]
  }
}
```

### ADO MCP Server Tools

1. **authenticate** - OAuth 2.0 authentication
2. **list_organizations** - List available ADO organizations
3. **select_organization** - Select working organization
4. **get_all_projects** - List all projects
5. **create_project** - Create new project
6. **create_work_item** - Create work items with parent linking
7. **update_work_item** - Update existing work items
8. **get_work_item** - Get work item details

### Jira MCP Server Tools

1. **authenticate** - OAuth 2.0 authentication
2. **get_all_projects** - List all projects
3. **create_project** - Create new project
4. **get_issue_types** - Get available issue types
5. **create_issue** - Create issues with parent linking
6. **update_issue** - Update existing issues
7. **get_issue** - Get issue details
8. **search_issues** - JQL-based search

## Security Best Practices

### Environment Variables

- ✅ Never commit `.env` file to version control
- ✅ Use Azure Key Vault for production secrets
- ✅ Rotate credentials regularly
- ✅ Use managed identities where possible

### OAuth Configuration

- ✅ Register redirect URIs correctly
- ✅ Use HTTPS in production
- ✅ Implement token refresh logic
- ✅ Clear tokens after session completion

### API Rate Limiting

Both servers include built-in rate limiting (2-second delays) to prevent API throttling. Adjust the `safe_call` functions if needed:

```python
def safe_call(tool_func, *args, **kwargs):
    time.sleep(2)  # Adjust delay as needed
    return tool_func(*args, **kwargs)
```

## Monitoring and Troubleshooting

### View Logs

```bash
# Stream logs
az webapp log tail --name ado-mcp-server --resource-group mcp-servers-rg

# Download logs
az webapp log download --name ado-mcp-server --resource-group mcp-servers-rg --log-file logs.zip
```

### Common Issues

#### OAuth Browser Opens on Server

**Issue**: OAuth flow tries to open browser on Azure server
**Solution**: Use environment variable redirect or manual token injection

#### Token Expiration

**Issue**: Access tokens expire during long sessions
**Solution**: Servers automatically refresh tokens using refresh_token

#### Rate Limiting

**Issue**: 429 Too Many Requests errors
**Solution**: Increase delay in `safe_call` functions

## Cost Optimization

- **Free Tier**: Use F1 tier for development/testing
- **Basic Tier (B1)**: Recommended for production (~$13/month)
- **Auto-scaling**: Configure based on load

## File Structure

```
deployMCP/
├── ado_mcp_stdio.py          # ADO MCP server implementation
├── jira_mcp_stdio.py          # Jira MCP server implementation
├── startup.py                 # Azure App Service entry point
├── requirements.txt           # Python dependencies
├── runtime.txt                # Python version specification
├── .env.example               # Environment variable template
└── README.md                  # This file
```

## Contributing

Improvements welcome! Please ensure:

- No hardcoded credentials
- JSON-RPC 2.0 compliance
- Proper error handling
- Logging to stderr (not stdout)

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:

1. Check Azure App Service logs
2. Verify environment variables are set correctly
3. Test JSON-RPC requests manually
4. Review OAuth callback configurations

## Additional Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Azure App Service Documentation](https://docs.microsoft.com/azure/app-service/)
- [Azure DevOps REST API](https://docs.microsoft.com/rest/api/azure/devops/)
- [Jira REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
