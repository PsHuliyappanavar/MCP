# Agent486 Deployment Guide

This guide walks you through deploying Agent486 as a GitHub Copilot custom agent.

## Prerequisites

- [ ] GitHub Copilot subscription (Pro, Pro+, Business, or Enterprise)
- [ ] GitHub repository to host the agent
- [ ] Python 3.8 or higher installed locally
- [ ] Azure DevOps and/or Jira account
- [ ] OAuth credentials for ADO and/or Jira

## Deployment Steps

### 1. Clone/Push Repository to GitHub

If you haven't already, push this repository to GitHub:

```bash
# Initialize git if not already done
git init

# Add remote (replace with your repository URL)
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git

# Add all files
git add .

# Commit
git commit -m "Add Agent486 custom agent for GitHub Copilot"

# Push to main branch
git push -u origin main
```

### 2. Configure GitHub Repository Secrets

#### For Codespaces/Local VS Code Integration:

1. Go to your repository on GitHub
2. Navigate to **Settings → Secrets and variables → Codespaces**
3. Click **New repository secret**
4. Add the following secrets:

**Azure DevOps Secrets:**

- **Name**: `ADO_CLIENT_ID`
  - **Value**: Your Azure AD application client ID
- **Name**: `ADO_CLIENT_SECRET`
  - **Value**: Your Azure AD application client secret
- **Name**: `ADO_TENANT_ID`
  - **Value**: Your Azure AD tenant ID

**Jira Secrets:**

- **Name**: `ATLASSIAN_CLIENT_ID`
  - **Value**: Your Atlassian OAuth client ID
- **Name**: `ATLASSIAN_CLIENT_SECRET`
  - **Value**: Your Atlassian OAuth client secret

### 3. Set Up OAuth Applications

#### Azure DevOps OAuth Setup

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Azure Active Directory → App registrations**
3. Click **New registration**
4. Configure:
   - **Name**: `Agent486 ADO Integration`
   - **Supported account types**: Accounts in this organizational directory only
   - **Redirect URI**: Select "Web" and enter `http://localhost:9001/oauth/callback`
5. Click **Register**
6. On the app overview page, copy:
   - **Application (client) ID** → Use as `ADO_CLIENT_ID`
   - **Directory (tenant) ID** → Use as `ADO_TENANT_ID`
7. Go to **Certificates & secrets**
8. Click **New client secret**
   - **Description**: `Agent486 Secret`
   - **Expires**: Choose appropriate duration
9. **IMPORTANT**: Copy the secret value immediately → Use as `ADO_CLIENT_SECRET`
10. Go to **API permissions**
11. Click **Add a permission → Azure DevOps**
12. Select **Delegated permissions**
13. Check **user_impersonation**
14. Click **Add permissions**
15. Click **Grant admin consent** (requires admin rights)

#### Jira OAuth Setup

1. Go to [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)
2. Click **Create → OAuth 2.0 integration**
3. Configure:
   - **Name**: `Agent486 Jira Integration`
4. Click **Create**
5. On the app page:
   - Copy **Client ID** → Use as `ATLASSIAN_CLIENT_ID`
   - Copy **Secret** → Use as `ATLASSIAN_CLIENT_SECRET`
6. Click **Permissions**
7. Click **Add** for the Jira API
8. Configure OAuth 2.0 (3LO):
   - Add **Callback URL**: `http://localhost:9000/oauth/callback`
9. Add the following scopes:
   - `read:jira-work` - Read Jira issues
   - `write:jira-work` - Create and update Jira issues
   - `write:project:jira` - Create projects
   - `read:jira-user` - Read user information
   - `manage:jira-project` - Manage projects
   - `manage:jira-configuration` - Manage Jira configuration
   - `offline_access` - Refresh token support
10. Click **Save**
11. Go to **Distribution**
12. Click **Edit** and select **Sharing**
13. Change to **Unlisted** or public (required for OAuth flow)
14. Click **Save changes**

### 4. Configure MCP Servers for Local VS Code

For local VS Code usage with GitHub Copilot, configure MCP servers:

**Windows:**

1. Create/edit: `%APPDATA%\Code\User\globalStorage\github.copilot-chat\mcp.json`

**Mac/Linux:**

1. Create/edit: `~/.config/Code/User/globalStorage/github.copilot-chat/mcp.json`

**Content:**

```json
{
  "mcpServers": {
    "ado-mcp-server": {
      "command": "python",
      "args": [
        "C:\\Users\\sandeepk\\Favorites\\Building\\deployMCP\\ado_mcp_stdio.py"
      ],
      "env": {
        "ADO_CLIENT_ID": "your-actual-client-id",
        "ADO_CLIENT_SECRET": "your-actual-client-secret",
        "ADO_TENANT_ID": "your-actual-tenant-id"
      }
    },
    "jira-mcp-server": {
      "command": "python",
      "args": [
        "C:\\Users\\sandeepk\\Favorites\\Building\\deployMCP\\jira_mcp_stdio.py"
      ],
      "env": {
        "ATLASSIAN_CLIENT_ID": "your-actual-client-id",
        "ATLASSIAN_CLIENT_SECRET": "your-actual-client-secret"
      }
    }
  }
}
```

**Important**: Replace paths and credentials with your actual values.

### 5. Install Python Dependencies

```bash
pip install flask requests
```

### 6. Verify Agent Installation

1. Open VS Code
2. Open the repository folder
3. Open GitHub Copilot Chat (Ctrl+Alt+I or Cmd+Alt+I)
4. Click the agent selector dropdown (should show "@workspace" by default)
5. You should see **@agent486** in the list
6. Select **@agent486**

### 7. Test the Agent

Try this test prompt:

```
@agent486 Transform this simple BRD into Azure DevOps work items:

# Test Project

## Functional Requirements
1. User Login
   - Username/password authentication
   - Remember me functionality

## Non-Functional Requirements
- Security: Password must be encrypted
```

The agent should:

1. Authenticate with ADO (opens browser)
2. Fetch organizations
3. Parse the BRD
4. Show hierarchy for review
5. Create work items after approval
6. Verify all created items

## Troubleshooting

### Agent Not Showing in VS Code

1. **Restart VS Code** after adding the agent profile
2. **Check file location**: Must be `.github/agents/agent486.md`
3. **Verify YAML frontmatter**: Must have `name`, `description`, and `tools`
4. **Pull latest changes**: Run `git pull` if added via GitHub.com

### MCP Server Connection Issues

1. **Check Python path**: Ensure `python` command works in terminal
2. **Verify file paths**: Use absolute paths in MCP configuration
3. **Test MCP servers manually**:
   ```bash
   python ado_mcp_stdio.py
   # Should start and wait for input (Ctrl+C to exit)
   ```
4. **Check VS Code logs**: Help → Toggle Developer Tools → Console

### OAuth Authentication Fails

**Azure DevOps:**

1. Verify redirect URI exactly matches: `http://localhost:9001/oauth/callback`
2. Check admin consent was granted
3. Ensure user_impersonation scope is added
4. Verify tenant ID is correct

**Jira:**

1. Verify redirect URI exactly matches: `http://localhost:9000/oauth/callback`
2. Check app is distributed (unlisted/public)
3. Ensure all required scopes are added
4. Try revoking and re-authorizing: https://id.atlassian.com/manage-profile/apps

### Rate Limiting

Agent486 includes built-in rate limiting (1s minimum between calls), but if you still hit limits:

1. Check for other processes using ADO/Jira APIs
2. Review API quotas in your ADO/Jira admin console
3. Consider implementing longer delays in `ado_mcp_stdio.py` and `jira_mcp_stdio.py` (adjust `safe_call` sleep time)

### BRD Parsing Confidence Low

If confidence is consistently <60%:

1. **Structure your BRD clearly**:
   - Use clear headings (## Functional Requirements, ## Non-Functional Requirements)
   - Number requirements
   - Include descriptions
2. **Avoid overly complex hierarchies** (max 4 levels)
3. **Be explicit** about parent-child relationships

## Advanced Configuration

### Custom Tool Selection

Edit `.github/agents/agent486.md` to limit tools:

```yaml
---
name: agent486
description: ...
tools: ["read", "ado-mcp-server/authenticate", "ado-mcp-server/create_issue"]
---
```

### Modify Wait Times

Edit `ado_mcp_stdio.py` or `jira_mcp_stdio.py`:

```python
def safe_call(tool_func, *args, **kwargs):
    """Change sleep time here"""
    time.sleep(2)  # Change to 3 or 5 for more conservative rate limiting
    return tool_func(*args, **kwargs)
```

### Add Custom Field Mappings

Edit the Field Mapping section in `.github/agents/agent486.md` to add your custom fields.

## Security Best Practices

1. **Never commit secrets** to the repository
2. **Rotate OAuth secrets** regularly (every 90 days recommended)
3. **Use minimal scopes** required for operation
4. **Monitor OAuth app usage** in Azure/Atlassian admin consoles
5. **Revoke access** for unused apps
6. **Enable MFA** on accounts with OAuth app management permissions

## Next Steps

Once deployed successfully:

1. **Test with real BRDs** in your workflow
2. **Customize prompts** in `agent486.md` for your organization
3. **Add organization-specific field mappings**
4. **Set up monitoring** for API usage and rate limits
5. **Train team members** on using the agent
6. **Gather feedback** and iterate on the agent profile

## Support

For issues:

1. Check this guide
2. Review [README.md](README.md)
3. Check [Instructions.md](Instructions.md) for detailed operational logic
4. Open an issue in the repository

---

**Ready to automate your BRD-to-work-item workflow with Agent486!**
