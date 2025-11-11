# Organization/Enterprise Agent Configuration - Quick Guide

## ✅ What Was Done

Based on the GitHub documentation for organization and enterprise-level custom agents, I've created the correct configuration:

### 1. **Created Organization-Level Agent Profile**

- **Location**: `agents/agent486.md` (root level, NOT `.github/agents/`)
- **Key Feature**: MCP servers embedded directly in YAML frontmatter
- **Benefit**: Available across ALL repositories in your organization

### 2. **Embedded MCP Server Configuration**

The YAML frontmatter now includes:

```yaml
---
name: agent486
description: Automates BRD parsing and hierarchical work-item creation in Azure DevOps and Jira
tools: ["read", "search", "edit", "ado-mcp-server/*", "jira-mcp-server/*"]
mcp-servers:
  ado-mcp-server:
    type: local
    command: python
    args:
      - "C:\\Users\\sandeepk\\Favorites\\Building\\deployMCP\\ado_mcp_stdio.py"
    tools: ["*"]
    env:
      ADO_CLIENT_ID: ${{ secrets.ADO_CLIENT_ID }}
      ADO_CLIENT_SECRET: ${{ secrets.ADO_CLIENT_SECRET }}
      ADO_TENANT_ID: ${{ secrets.ADO_TENANT_ID }}
  jira-mcp-server:
    type: local
    command: python
    args:
      - "C:\\Users\\sandeepk\\Favorites\\Building\\deployMCP\\jira_mcp_stdio.py"
    tools: ["*"]
    env:
      ATLASSIAN_CLIENT_ID: ${{ secrets.ATLASSIAN_CLIENT_ID }}
      ATLASSIAN_CLIENT_SECRET: ${{ secrets.ATLASSIAN_CLIENT_SECRET }}
---
```

## 🔑 Key Differences: Repository vs Organization Level

| Aspect           | Repository-Level               | Organization/Enterprise-Level |
| ---------------- | ------------------------------ | ----------------------------- |
| **Location**     | `.github/agents/`              | `agents/` (root)              |
| **MCP Config**   | Separate (in VS Code settings) | Embedded in YAML frontmatter  |
| **Secrets**      | Local environment variables    | `${{ secrets.NAME }}` syntax  |
| **Scope**        | Single repository              | All repos in org/enterprise   |
| **Subscription** | Any Copilot plan               | Business or Enterprise only   |

## 📁 Repository Structure

```
MCP/
├── .github/
│   └── agents/
│       └── agent486.md          # Repository-level (for reference)
├── agents/
│   └── agent486.md              # ✅ Organization-level (ACTIVE)
├── ado_mcp_stdio.py
├── jira_mcp_stdio.py
├── Instructions.md
├── DEPLOYMENT.md
└── README.md
```

## 🚀 How to Use

### For VS Code (Local Development)

1. **Ensure MCP servers are configured** in VS Code:

   - File: `%APPDATA%\Code\User\globalStorage\github.copilot-chat\mcp.json`
   - Already configured with your credentials

2. **Restart VS Code**

3. **Open GitHub Copilot Chat** (Ctrl+Alt+I)

4. **Select @agent486** from the agent dropdown

5. **Test with a BRD prompt**

### For GitHub.com (Organization/Enterprise)

1. **Navigate to**: https://github.com/copilot/agents

2. **Select your repository**: `PsHuliyappanavar/MCP`

3. **You should see agent486** in the agent list

4. **Use in any repository** within your organization by selecting it from the Copilot dropdown

## ⚙️ Configuration Notes

### MCP Server Paths

The agent profile uses **absolute paths** to the MCP server scripts:

- `C:\\Users\\sandeepk\\Favorites\\Building\\deployMCP\\ado_mcp_stdio.py`
- `C:\\Users\\sandeepk\\Favorites\\Building\\deployMCP\\jira_mcp_stdio.py`

**Important**:

- For local VS Code usage, these paths work as-is
- For GitHub.com/Codespaces, you may need to deploy the MCP servers as accessible services
- Consider using relative paths or environment variables for more flexibility

### Secrets Management

The organization-level agent references secrets using GitHub Actions syntax:

```yaml
ADO_CLIENT_ID: ${{ secrets.ADO_CLIENT_ID }}
```

**To configure secrets**:

1. Go to your organization settings on GitHub
2. Navigate to **Settings → Secrets and variables → Copilot**
3. Add the 5 required secrets (see DEPLOYMENT.md)

## 🔍 Verification Steps

### 1. Check Agent Availability

- Open any repository in your organization
- Open Copilot Chat
- Look for `@agent486` in the dropdown

### 2. Test MCP Server Connection

```bash
# Test ADO MCP server
python ado_mcp_stdio.py
# Should start and wait for input (Ctrl+C to exit)

# Test Jira MCP server
python jira_mcp_stdio.py
# Should start and wait for input (Ctrl+C to exit)
```

### 3. Test Agent with Simple BRD

```
@agent486 Transform this BRD into Azure DevOps work items:

# Simple Test

## Functional Requirements
1. User login with password
2. Dashboard display

## Non-Functional Requirements
- Response time < 2 seconds
```

## 📖 Documentation References

- **GitHub Docs**: [Creating custom agents](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents)
- **Custom Agents Configuration**: [Reference](https://docs.github.com/en/enterprise-cloud@latest/copilot/reference/custom-agents-configuration)
- **Your README.md**: Complete setup and usage guide
- **Your DEPLOYMENT.md**: Detailed deployment instructions with OAuth setup

## 🐛 Troubleshooting

### Agent Not Appearing

**Issue**: `@agent486` doesn't show in dropdown

**Solutions**:

1. Verify file is in `agents/` (not `.github/agents/`)
2. Check YAML frontmatter is valid (use a YAML validator)
3. Ensure repository is accessible to your organization
4. Restart VS Code
5. Clear VS Code cache: Developer Tools → Application → Storage → Clear Site Data

### MCP Server Not Loading

**Issue**: Tools not working when agent is invoked

**Solutions**:

1. Verify Python is in PATH: `python --version`
2. Check MCP server paths are correct (absolute paths)
3. Ensure secrets are configured in organization settings
4. Test MCP servers manually (see Verification Steps above)
5. Check VS Code Output panel: GitHub Copilot Chat for errors

### Authentication Failures

**Issue**: OAuth fails when agent tries to authenticate

**Solutions**:

1. Verify redirect URIs in Azure AD / Atlassian console:
   - ADO: `http://localhost:9001/oauth/callback`
   - Jira: `http://localhost:9000/oauth/callback`
2. Check secrets are correct (no extra spaces/characters)
3. Ensure OAuth apps have required permissions:
   - ADO: `user_impersonation`
   - Jira: `read:jira-work`, `write:jira-work`, etc.
4. Try revoking and re-authorizing the OAuth apps

## 🎯 Next Steps

1. ✅ **Organization-level agent is configured and pushed**
2. ⏭️ **Configure secrets in your organization settings** (if not already done)
3. ⏭️ **Test the agent in VS Code**
4. ⏭️ **Verify agent appears on GitHub.com** at https://github.com/copilot/agents
5. ⏭️ **Train team members** on using the agent
6. ⏭️ **Gather feedback** and iterate

---

**Your Agent486 is now properly configured as an organization-level custom agent! 🎉**
