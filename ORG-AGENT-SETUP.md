# Agent486 Setup Guide - Organization/Enterprise Level

## Overview
Agent486 is a GitHub Copilot custom agent that automates BRD (Business Requirements Document) parsing and hierarchical work item creation in Azure DevOps and Jira using MCP (Model Context Protocol) servers.

## Architecture

### Components
1. **Custom Agent**: `agents/agent486.md` - Organization-level agent profile
2. **MCP Servers**: 
   - `ado_mcp_stdio.py` - Azure DevOps MCP server
   - `jira_mcp_stdio.py` - Jira MCP server
3. **Setup Workflow**: `.github/workflows/copilot-setup-steps.yml` - Installs dependencies
4. **Secrets**: OAuth credentials stored in GitHub repository's Copilot environment

### Why VS Code Chat Modes Don't Work
- ❌ **VS Code `.chatmode.md` files**: Context/personality only, NO MCP support
- ✅ **Organization agents (`agents/*.md`)**: Full MCP support with embedded server configs
- ❌ **Repository agents (`.github/agents/*.md`)**: NO MCP server configuration support

## Prerequisites

### 1. GitHub Enterprise Cloud
- Organization must have **GitHub Copilot Enterprise**
- Custom agents feature must be enabled (contact GitHub admin if not available)

### 2. Repository Access
- Repository must be in the organization
- You must be a **repository administrator** to configure secrets

### 3. OAuth Applications

#### Azure DevOps (ADO)
- Azure AD application with:
  - Client ID: `25a1e0db-fb5f-4baf-b542-af6de0ebe24f`
  - Client Secret: `Xjz8Q~A3VbHe-yugbKhi-LVpRHwUzQ8owEWVBbt0`
  - Tenant ID: `0c88fa98-b222-4fd8-9414-559fa424ce64`
  - Redirect URI: `http://localhost:9001/oauth/callback`
  - Scopes: `https://app.vssps.visualstudio.com/user_impersonation offline_access`

#### Jira/Atlassian
- Atlassian OAuth 2.0 app with:
  - Client ID: `rTGWKW1Ogs2BFloYan82z9Pqg8IUIzQK`
  - Client Secret: `ATOAO6nNJmT8-b2nQbh3eq-MiHdVlY7PDZipki9vHgKfTINYwVhoEz64YNIbmUAQ9lR_503D4DB8`
  - Callback URL: `http://localhost:9001/callback`
  - Scopes: `read:jira-work write:jira-work offline_access`

## Setup Instructions

### Step 1: Push Code to GitHub

The repository is already pushed to: `https://github.com/PsHuliyappanavar/MCP`

Verify files exist:
```bash
git ls-files
```

Expected files:
- `agents/agent486.md` ✅
- `.github/workflows/copilot-setup-steps.yml` ✅
- `ado_mcp_stdio.py` ✅
- `jira_mcp_stdio.py` ✅

### Step 2: Create Copilot Environment and Secrets

1. Go to repository on GitHub.com:
   ```
   https://github.com/PsHuliyappanavar/MCP
   ```

2. Click **Settings** tab

3. In left sidebar, click **Environments**

4. Click **New environment**

5. Name it exactly: `copilot`

6. Click **Configure environment**

7. Add the following secrets (click "Add environment secret" for each):

   | Secret Name | Value |
   |------------|-------|
   | `COPILOT_MCP_ADO_CLIENT_ID` | `25a1e0db-fb5f-4baf-b542-af6de0ebe24f` |
   | `COPILOT_MCP_ADO_CLIENT_SECRET` | `Xjz8Q~A3VbHe-yugbKhi-LVpRHwUzQ8owEWVBbt0` |
   | `COPILOT_MCP_ADO_TENANT_ID` | `0c88fa98-b222-4fd8-9414-559fa424ce64` |
   | `COPILOT_MCP_ATLASSIAN_CLIENT_ID` | `rTGWKW1Ogs2BFloYan82z9Pqg8IUIzQK` |
   | `COPILOT_MCP_ATLASSIAN_CLIENT_SECRET` | `ATOAO6nNJmT8-b2nQbh3eq-MiHdVlY7PDZipki9vHgKfTINYwVhoEz64YNIbmUAQ9lR_503D4DB8` |

   **Important**: All secret names MUST start with `COPILOT_MCP_` prefix!

### Step 3: Update Agent Configuration

The `agents/agent486.md` file references secrets using the `${{ secrets.* }}` syntax:

```yaml
mcp-servers:
  ado-mcp-server:
    env:
      ADO_CLIENT_ID: ${{ secrets.ADO_CLIENT_ID }}
      ADO_CLIENT_SECRET: ${{ secrets.ADO_CLIENT_SECRET }}
      ADO_TENANT_ID: ${{ secrets.ADO_TENANT_ID }}
```

**BUT** the actual secret names in the Copilot environment have the `COPILOT_MCP_` prefix.

GitHub automatically maps:
- `${{ secrets.ADO_CLIENT_ID }}` → `COPILOT_MCP_ADO_CLIENT_ID`
- `${{ secrets.ADO_CLIENT_SECRET }}` → `COPILOT_MCP_ADO_CLIENT_SECRET`
- etc.

**No changes needed** - the mapping happens automatically!

### Step 4: Verify Custom Agent Available

1. Check if organization has custom agents enabled:
   - Organization Settings → Copilot → Policies
   - Look for "Custom Agents" or "Coding Agent" settings

2. If not available, contact your GitHub organization administrator

### Step 5: Test the Agent

#### Option A: Via GitHub.com Issue (Recommended)

1. Create a test issue in the repository:
   ```
   Title: Test Agent486 with ADO
   Body: Parse this BRD and create work items in Azure DevOps
   ```

2. Assign the issue to **@agent486**

3. Wait for Copilot to respond (look for 👀 reaction, then PR creation)

4. Click the PR and view the Copilot session logs

5. Check "Start MCP Servers" step to verify:
   - `ado-mcp-server` started successfully
   - `jira-mcp-server` started successfully
   - Tools are listed

#### Option B: Via GitHub Copilot Chat (if available)

1. Open GitHub Copilot Chat on GitHub.com

2. Type:
   ```
   @agent486 authenticate with Azure DevOps
   ```

3. The agent should:
   - Invoke the `authenticate` tool from `ado-mcp-server`
   - Start OAuth flow (may require additional configuration for OAuth callbacks in GitHub's environment)

## Troubleshooting

### Issue: "Agent not found" or "@agent486 not recognized"

**Cause**: Organization doesn't have custom agents feature enabled

**Solution**:
1. Contact GitHub organization administrator
2. Request enabling "GitHub Copilot Custom Agents" feature
3. May require GitHub Copilot Enterprise license

### Issue: MCP servers fail to start

**Symptoms**: In Copilot session logs, "Start MCP Servers" step shows errors

**Possible causes**:
1. **Missing dependencies**: Python packages not installed
   - Fix: Verify `.github/workflows/copilot-setup-steps.yml` runs successfully
   
2. **Secret mapping issue**: Environment variables not passed correctly
   - Fix: Double-check secret names have `COPILOT_MCP_` prefix
   - Fix: Verify secrets exist in the `copilot` environment (not repository secrets)

3. **Python version issue**: MCP servers require Python 3.11+
   - Fix: Update `copilot-setup-steps.yml` to use `python-version: '3.11'`

### Issue: OAuth flow doesn't work

**Symptom**: `authenticate` tool is invoked but OAuth fails

**Cause**: GitHub's environment doesn't support localhost callbacks

**Solution**: This is a known limitation. OAuth-based MCP servers work better in local environments. For GitHub Copilot coding agent:
- Consider using service principal authentication instead of OAuth
- Or pre-authenticate and store long-lived tokens in secrets

### Issue: Tools are recognized but not executing correctly

**Debug steps**:
1. Check Copilot session logs for tool invocation details
2. Look for error messages in MCP server output
3. Verify the `tools: ["*"]` property in agent profile
4. Test MCP servers locally with `direct_mcp_cli.py`

## Validation Checklist

- [ ] Repository pushed to GitHub with all required files
- [ ] `copilot` environment created in repository settings
- [ ] All 5 secrets added with `COPILOT_MCP_` prefix
- [ ] `.github/workflows/copilot-setup-steps.yml` exists
- [ ] Organization has custom agents feature enabled
- [ ] Test issue created and assigned to @agent486
- [ ] Copilot responds with 👀 reaction
- [ ] PR created by Copilot
- [ ] MCP servers listed in Copilot session logs
- [ ] Tools show as available in logs

## Current Status

### ✅ Completed
- Agent profile created (`agents/agent486.md`)
- MCP servers implemented (ADO + Jira)
- Setup workflow configured
- Repository pushed to GitHub
- VS Code chat mode removed (doesn't support MCP)

### ⏳ Pending
- Create `copilot` environment in repository
- Add secrets to Copilot environment
- Test agent with issue assignment
- Verify MCP server startup in logs
- Test complete BRD→work item workflow

### ❓ Requires Verification
- Organization has custom agents feature enabled
- OAuth callbacks work in GitHub's environment (may need alternative auth)

## Alternative: Local Testing

If organization-level agents aren't available, test locally with:

```bash
python direct_mcp_cli.py
```

This script:
1. Starts the ADO MCP server
2. Initializes the connection
3. Lists available tools
4. Tests authentication (opens browser for OAuth)
5. Fetches organizations
6. Displays results

This validates that the MCP servers work correctly, even if GitHub's custom agent feature isn't accessible yet.

## Next Steps

1. **Create Copilot environment and add secrets** (Step 2 above)
2. **Verify organization has custom agents enabled**
3. **Test with issue assignment** (Step 5, Option A)
4. **Review Copilot session logs** to verify MCP servers started
5. **Test complete BRD parsing workflow** once authentication works

## Documentation References

- [GitHub Custom Agents Configuration](https://docs.github.com/en/enterprise-cloud@latest/copilot/reference/custom-agents-configuration)
- [Extending Coding Agent with MCP](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Creating Custom Agents](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents)
