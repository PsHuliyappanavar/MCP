# Azure App Service Deployment Package

## 📦 Package Contents

✅ **Complete deployment package ready for Azure App Service**

### Core MCP Servers

- `ado_mcp_stdio.py` - Azure DevOps MCP Server (1785 lines)
- `jira_mcp_stdio.py` - Jira MCP Server (1284 lines)

### Deployment Files

- `startup.py` - Azure App Service entry point
- `requirements.txt` - Python dependencies
- `runtime.txt` - Python 3.11 specification
- `.env.example` - Environment variable template
- `.gitignore` - Version control exclusions

### Deployment Scripts

- `deploy.sh` - Bash deployment script (Linux/Mac)
- `deploy.ps1` - PowerShell deployment script (Windows)

### Documentation

- `README.md` - Complete deployment guide
- `QUICKSTART.md` - 5-minute setup guide
- `COMPLIANCE.md` - JSON-RPC 2.0 validation
- `DEPLOYMENT_SUMMARY.md` - This file

## ✅ Validation Checklist

### Security ✓

- [x] No hardcoded credentials in any file
- [x] All credentials from environment variables
- [x] OAuth 2.0 implementation
- [x] Session-based token management
- [x] Tokens cleared after use
- [x] .env in .gitignore

### JSON-RPC 2.0 Compliance ✓

- [x] Proper request/response format
- [x] stdin/stdout communication
- [x] Logging to stderr only
- [x] Standard error codes (-32601, -32603)
- [x] Initialize method implemented
- [x] Tools/list method implemented
- [x] Tools/call method implemented
- [x] Notification handling

### Azure App Service Ready ✓

- [x] runtime.txt with Python 3.11
- [x] requirements.txt with all dependencies
- [x] Startup command configured
- [x] Environment variable routing
- [x] Multiple server support (ADO/Jira)
- [x] No interactive prompts in deployment

### Tool Call Protection ✓

- [x] JSON-RPC format preserved
- [x] No deployment influence on responses
- [x] Consistent error handling
- [x] Rate limiting implemented
- [x] Async operation support

## 🚀 Deployment Options

### Option 1: Automated Script Deployment

**Windows:**

```powershell
.\deploy.ps1 -ServerType ado -AppName your-ado-server
.\deploy.ps1 -ServerType jira -AppName your-jira-server
```

**Linux/Mac:**

```bash
./deploy.sh ado your-ado-server
./deploy.sh jira your-jira-server
```

### Option 2: Azure CLI Manual

```bash
# Create resource group
az group create --name mcp-servers-rg --location eastus

# Deploy app
az webapp up --name your-mcp-server --runtime "PYTHON:3.11" --sku B1

# Configure settings
az webapp config appsettings set --name your-mcp-server --settings \
  MCP_SERVER=ado \
  ADO_CLIENT_ID="..." \
  ADO_CLIENT_SECRET="..." \
  ADO_TENANT_ID="..."

# Set startup
az webapp config set --name your-mcp-server --startup-file "python startup.py"
```

### Option 3: Azure Portal

1. Upload files via Git/FTP
2. Configure environment variables in Portal
3. Set startup command in Configuration
4. Restart app

## 🔧 Configuration Requirements

### ADO Server Environment Variables

```
ADO_CLIENT_ID        - Azure AD Application (client) ID
ADO_CLIENT_SECRET    - Azure AD Client secret value
ADO_TENANT_ID        - Azure AD Directory (tenant) ID
MCP_SERVER          - Set to "ado"
```

### Jira Server Environment Variables

**OAuth 2.0 (Required):**

```
ATLASSIAN_CLIENT_ID     - Atlassian OAuth client ID
ATLASSIAN_CLIENT_SECRET - Atlassian OAuth client secret
MCP_SERVER             - Set to "jira"
```

## 📊 Feature Matrix

| Feature                  | ADO Server | Jira Server |
| ------------------------ | ---------- | ----------- |
| JSON-RPC 2.0             | ✅         | ✅          |
| OAuth 2.0                | ✅         | ✅          |
| Organization Management  | ✅         | ❌          |
| Project Management       | ✅         | ✅          |
| Work Item/Issue Creation | ✅         | ✅          |
| Hierarchy Support        | ✅         | ✅          |
| Rate Limiting            | ✅ (2s)    | ✅ (2s)     |
| Token Refresh            | ✅         | ✅          |
| Session Management       | ✅         | ✅          |

## 🔍 Testing the Deployment

### 1. Initialize Test

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | \
  az webapp ssh --name your-mcp-server --resource-group mcp-servers-rg
```

**Expected Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": { "tools": {} },
    "serverInfo": { "name": "ado-mcp-server", "version": "1.0.0" }
  }
}
```

### 2. Tools List Test

```bash
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | \
  az webapp ssh --name your-mcp-server --resource-group mcp-servers-rg
```

### 3. View Logs

```bash
az webapp log tail --name your-mcp-server --resource-group mcp-servers-rg
```

## 📝 Pre-Deployment Checklist

### Before Deployment

- [ ] Azure CLI installed and logged in
- [ ] Azure subscription active
- [ ] Credentials obtained (ADO/Jira)
- [ ] .env file configured
- [ ] App name decided (unique globally)
- [ ] Resource group name decided

### After Deployment

- [ ] App deployed successfully
- [ ] Environment variables set
- [ ] Startup command configured
- [ ] App restarted
- [ ] Logs showing "MCP Server started"
- [ ] Initialize test passed
- [ ] Tools list test passed

## 🛡️ Security Best Practices

### Production Deployment

1. **Use Azure Key Vault** for credentials
2. **Enable HTTPS Only** (default in Azure)
3. **Rotate credentials** every 90 days
4. **Enable diagnostic logging**
5. **Set up monitoring alerts**
6. **Use managed identities** where possible

### Credential Management

```bash
# Store in Key Vault
az keyvault secret set --vault-name your-vault --name ADO-CLIENT-ID --value "..."

# Reference in App Service
az webapp config appsettings set --name your-app --settings \
  ADO_CLIENT_ID="@Microsoft.KeyVault(SecretUri=https://your-vault.vault.azure.net/secrets/ADO-CLIENT-ID/)"
```

## 💡 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Azure App Service                      │
│                                                         │
│  ┌─────────────┐                                       │
│  │ startup.py  │ ← Entry Point                         │
│  └──────┬──────┘                                       │
│         │                                               │
│    Based on MCP_SERVER env var                         │
│         │                                               │
│    ┌────┴────┐                                         │
│    │         │                                         │
│  ┌─▼──────┐  │  ┌──────────┐                          │
│  │  ADO   │  └──►  Jira    │                          │
│  │  MCP   │     │   MCP    │                          │
│  │ Server │     │  Server  │                          │
│  └───┬────┘     └────┬─────┘                          │
│      │               │                                 │
│      │  JSON-RPC 2.0 │                                │
│      │  stdin/stdout │                                │
│      └───────┬───────┘                                │
│              │                                         │
│    ┌─────────▼─────────┐                              │
│    │  OAuth Manager    │                              │
│    │  Token Refresh    │                              │
│    │  Rate Limiting    │                              │
│    └─────────┬─────────┘                              │
└──────────────┼─────────────────────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
   ┌────▼────┐   ┌────▼────┐
   │   ADO   │   │  Jira   │
   │   API   │   │  API    │
   └─────────┘   └─────────┘
```

## 📈 Monitoring & Troubleshooting

### View Live Logs

```bash
az webapp log tail --name your-mcp-server --resource-group mcp-servers-rg
```

### Download Logs

```bash
az webapp log download --name your-mcp-server --resource-group mcp-servers-rg --log-file logs.zip
```

### Common Issues

| Issue                         | Solution                                          |
| ----------------------------- | ------------------------------------------------- |
| OAuth browser opens on server | Use environment-based redirect or token injection |
| Token expiration              | Server auto-refreshes tokens                      |
| Rate limiting (429)           | Increase delay in safe_call functions             |
| "Method not found"            | Check JSON-RPC request format                     |
| "Not authenticated"           | Call authenticate tool first                      |

## 💰 Cost Estimation

| Tier           | Monthly Cost | Use Case            |
| -------------- | ------------ | ------------------- |
| F1 (Free)      | $0           | Development/Testing |
| B1 (Basic)     | ~$13         | Small production    |
| S1 (Standard)  | ~$70         | Medium production   |
| P1V2 (Premium) | ~$150        | High traffic        |

**Recommendation:** Start with B1 for production

## 🔄 Update & Maintenance

### Update Deployment

```bash
# Re-run deployment script
./deploy.sh ado your-ado-server

# Or update via Git
git add .
git commit -m "Update"
git push azure main
```

### Update Environment Variables

```bash
az webapp config appsettings set --name your-app --settings NEW_VAR="value"
az webapp restart --name your-app --resource-group mcp-servers-rg
```

## 📚 Documentation Reference

| Document              | Purpose                                |
| --------------------- | -------------------------------------- |
| README.md             | Complete setup and configuration guide |
| QUICKSTART.md         | 5-minute deployment guide              |
| COMPLIANCE.md         | JSON-RPC 2.0 validation details        |
| DEPLOYMENT_SUMMARY.md | This checklist and overview            |

## ✅ Deployment Complete!

Your MCP servers are now:

- ✅ **Secure** - No hardcoded credentials
- ✅ **Compliant** - JSON-RPC 2.0 standard
- ✅ **Scalable** - Azure App Service platform
- ✅ **Reliable** - OAuth 2.0 with token refresh
- ✅ **Protected** - Rate limiting built-in
- ✅ **Maintainable** - Clean architecture

## 🎯 Next Steps

1. **Test your deployment** using the commands above
2. **Configure monitoring** in Azure Portal
3. **Set up alerts** for errors and performance
4. **Document your endpoints** for your team
5. **Integrate with AI Toolkit** or other MCP clients

## 📞 Support Resources

- [Model Context Protocol Spec](https://modelcontextprotocol.io/)
- [Azure App Service Docs](https://docs.microsoft.com/azure/app-service/)
- [Azure DevOps REST API](https://docs.microsoft.com/rest/api/azure/devops/)
- [Jira REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)

---

**Package Version:** 1.0.0  
**Last Updated:** 2025-11-10  
**Python Version:** 3.11  
**Platform:** Azure App Service (Linux)
