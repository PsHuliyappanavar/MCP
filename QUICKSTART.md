# Quick Start Guide - MCP Servers Deployment

## 🚀 5-Minute Setup

### Step 1: Get Your Credentials

#### For ADO (Azure DevOps):

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Click "New registration"
3. Add API permission: **Azure DevOps → user_impersonation**
4. Create client secret
5. Copy: Client ID, Tenant ID, and Client Secret

#### For Jira:

1. Go to [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)
2. Create OAuth 2.0 integration
3. Add callback: `http://localhost:9000/oauth/callback`
4. Copy: Client ID and Client Secret

### Step 2: Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit .env file with your credentials
notepad .env  # Windows
nano .env     # Linux/Mac
```

### Step 3: Deploy to Azure

**Windows (PowerShell):**

```powershell
# Deploy ADO Server
.\deploy.ps1 -ServerType ado -AppName ado-mcp-server

# Deploy Jira Server
.\deploy.ps1 -ServerType jira -AppName jira-mcp-server
```

**Linux/Mac (Bash):**

```bash
# Make script executable
chmod +x deploy.sh

# Deploy ADO Server
./deploy.sh ado ado-mcp-server

# Deploy Jira Server
./deploy.sh jira jira-mcp-server
```

### Step 4: Test Your Deployment

```bash
# Get your app URL
az webapp show --name ado-mcp-server --resource-group mcp-servers-rg --query defaultHostName -o tsv

# View live logs
az webapp log tail --name ado-mcp-server --resource-group mcp-servers-rg
```

## ✅ That's It!

Your MCP servers are now running on Azure App Service with:

- ✅ No hardcoded credentials
- ✅ JSON-RPC 2.0 compliant
- ✅ OAuth 2.0 authentication
- ✅ Rate limiting protection

## 📖 Next Steps

1. **Configure AI Toolkit**: Add your MCP server URL to AI Toolkit
2. **Test Tools**: Use `tools/list` to see available operations
3. **Monitor**: Check Azure Portal for metrics and logs

## 🆘 Need Help?

See the full [README.md](README.md) for:

- Detailed configuration options
- Troubleshooting guide
- Architecture documentation
- Security best practices

## 📝 Environment Variable Reference

### ADO Server

```env
ADO_CLIENT_ID=<from Azure AD>
ADO_CLIENT_SECRET=<from Azure AD>
ADO_TENANT_ID=<from Azure AD>
```

### Jira Server (OAuth)

```env
ATLASSIAN_CLIENT_ID=<from Atlassian>
ATLASSIAN_CLIENT_SECRET=<from Atlassian>
```

## 💰 Cost Estimate

- **Development**: Free Tier (F1) - $0/month
- **Production**: Basic (B1) - ~$13/month
- **High Traffic**: Standard (S1) - ~$70/month

Choose based on your needs!

## 🔐 Security Notes

- Environment variables are encrypted in Azure
- Use Azure Key Vault for production
- Enable HTTPS only (default in Azure)
- Rotate credentials every 90 days

## 📊 Tool Calls Won't Be Influenced

Both MCP servers maintain proper JSON-RPC format regardless of deployment environment. All tool calls return consistent responses:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [{ "type": "text", "text": "Response here" }]
  }
}
```

No deployment configuration affects the protocol!
