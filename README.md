# GitHub Copilot Custom Agent - Agent486

This repository contains **Agent486**, a custom GitHub Copilot agent that automates the transformation of Business Requirement Documents (BRDs) into hierarchical work items in Azure DevOps (ADO) or Jira.

## 🚀 Quick Start

### Prerequisites

1. **GitHub Copilot Pro, Pro+, Business, or Enterprise** subscription
2. **Azure DevOps** and/or **Jira** account with appropriate permissions
3. **OAuth 2.0 credentials** for ADO and/or Jira

### Agent Configuration Options

This repository provides **TWO** agent configurations:

1. **Repository-Level Agent** (`.github/agents/agent486.md`)
   - For individual repository use
   - Requires MCP servers configured separately in VS Code settings
   - Use for testing or single-repository deployments

2. **Organization/Enterprise-Level Agent** (`agents/agent486.md`) ✅ **RECOMMENDED**
   - For organization-wide or enterprise-wide use
   - MCP servers embedded in YAML frontmatter with secret references
   - Available across all repositories in your organization
   - Requires GitHub Copilot Business or Enterprise subscription

### Setup Instructions

⚠️ **For Organization/Enterprise Users**: Use the agent in `agents/agent486.md` (already configured with MCP servers)

**Option A: For Local VS Code Usage**

1. Ensure Python 3.8+ is installed
2. Install required dependencies:

   ```bash
   pip install flask requests
   ```

3. Configure the MCP servers in your local VS Code by adding to `~/.config/Code/User/globalStorage/github.copilot-chat/mcp.json` (Mac/Linux) or `%APPDATA%\Code\User\globalStorage\github.copilot-chat\mcp.json` (Windows):

```json
{
  "mcpServers": {
    "ado-mcp-server": {
      "command": "python",
      "args": ["path/to/deployMCP/ado_mcp_stdio.py"],
      "env": {
        "ADO_CLIENT_ID": "your-client-id",
        "ADO_CLIENT_SECRET": "your-client-secret",
        "ADO_TENANT_ID": "your-tenant-id"
      }
    },
    "jira-mcp-server": {
      "command": "python",
      "args": ["path/to/deployMCP/jira_mcp_stdio.py"],
      "env": {
        "ATLASSIAN_CLIENT_ID": "your-client-id",
        "ATLASSIAN_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

**Option B: For GitHub.com Usage**

GitHub Copilot on GitHub.com requires MCP servers to be accessible via HTTP endpoints. You'll need to deploy the MCP servers as web services. (Documentation for this coming soon)

#### Step 2: Configure GitHub Secrets

Add the following secrets to your repository:

1. Go to **Settings → Secrets and variables → Codespaces**
2. Add the following secrets:

**For Azure DevOps:**

- `ADO_CLIENT_ID`: Your Azure AD application client ID
- `ADO_CLIENT_SECRET`: Your Azure AD application client secret
- `ADO_TENANT_ID`: Your Azure AD tenant ID

**For Jira:**

- `ATLASSIAN_CLIENT_ID`: Your Atlassian OAuth client ID
- `ATLASSIAN_CLIENT_SECRET`: Your Atlassian OAuth client secret

##### How to Get Azure DevOps OAuth Credentials

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Azure Active Directory → App registrations**
3. Click **New registration**
4. Name: "Agent486 ADO Integration"
5. Redirect URI: `http://localhost:9001/oauth/callback`
6. After creation, note the **Application (client) ID** and **Directory (tenant) ID**
7. Go to **Certificates & secrets → New client secret**
8. Copy the secret value immediately (it won't be shown again)
9. Go to **API permissions → Add a permission → Azure DevOps**
10. Add: `user_impersonation` (delegated)
11. Grant admin consent

##### How to Get Jira OAuth Credentials

1. Go to [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)
2. Click **Create → OAuth 2.0 integration**
3. Name: "Agent486 Jira Integration"
4. Add Callback URL: `http://localhost:9000/oauth/callback`
5. Add Permissions:
   - `read:jira-work`
   - `write:jira-work`
   - `write:project:jira`
   - `read:jira-user`
   - `manage:jira-project`
   - `manage:jira-configuration`
   - `offline_access`
6. After creation, note the **Client ID** and **Secret**
7. Distribute the app (required for OAuth flow)

#### Step 3: Use the Custom Agent

1. Navigate to your repository on GitHub.com
2. Open the [Copilot Agents tab](https://github.com/copilot/agents)
3. Select your repository from the dropdown
4. You should see **agent486** in the agent list
5. In any issue or PR, click the Copilot icon and select **agent486** from the dropdown
6. Start with a prompt like:
   ```
   Transform this BRD into work items in Azure DevOps:
   [Paste your BRD content here]
   ```

## 📁 Repository Structure

```
deployMCP/
├── .github/
│   └── agents/
│       └── agent486.md          # Custom agent profile
├── ado_mcp_stdio.py             # Azure DevOps MCP server
├── jira_mcp_stdio.py            # Jira MCP server
├── Instructions.md              # Detailed operational instructions
├── mcp.json                     # Local MCP configuration (for AI Toolkit)
└── README.md                    # This file
```

## 🎯 Agent Capabilities

### Supported Platforms

- **Azure DevOps**: Epic → Feature → PBI → Task (4-level hierarchy)
- **Jira**: Epic → Story → Sub-task → Bug (4-level hierarchy)

### Key Features

✅ **Autonomous Operation**: 98%+ automation with minimal user prompts (only 2 validation gates)
✅ **Smart Parsing**: LLM-based BRD parsing with 70%+ confidence thresholds
✅ **Hierarchical Creation**: Parent-first ordering with automatic relationship linking
✅ **Verification**: Post-creation validation of all items and hierarchy links
✅ **Idempotency**: Hash-based duplicate detection and prevention
✅ **Error Recovery**: Exponential backoff with checkpointing for resume
✅ **PII Protection**: Automatic detection and redaction of sensitive data
✅ **Full Traceability**: Complete audit logs with tool call tracking

### Workflow Phases

1. **Authentication**: OAuth 2.0 with auto-refresh
2. **Organization/Project Discovery**: Auto-select or prompt for selection
3. **BRD Parsing**: Extract requirements with FR/NFR classification
4. **Hierarchy Structuring**: Build parent-child relationships
5. **Confidence Validation**: Auto-advance or retry based on confidence scores
6. **Project Management**: Create or select target project
7. **Type Mapping**: Map to platform-specific issue types
8. **Review Gate**: User approval of generated hierarchy
9. **Creation & Verification**: Idempotent creation with mandatory verification
10. **Artifact Generation**: Markdown summary and JSON trace logs

## 🛠️ MCP Server Tools

### Azure DevOps Tools (`ado-mcp-server/*`)

- `authenticate`: OAuth 2.0 authentication
- `get_organizations`: Fetch available organizations
- `create_project`, `get_project`: Project management
- `create_issue`, `update_issue`, `get_issue`: Work item CRUD
- `search_issues`: WIQL-based batch queries
- `get_issue_types`: Fetch valid work item types
- `clear_session`: Session cleanup

### Jira Tools (`jira-mcp-server/*`)

- `authenticate`: OAuth 2.0 authentication
- `get_all_projects`: Fetch accessible projects
- `create_project`: Project creation
- `create_issue`, `update_issue`, `get_issue`: Issue CRUD
- `search_issues`: JQL-based batch queries
- `get_issue_types`: Fetch valid issue types
- `clear_session`: Session cleanup

## 📊 Success Metrics

| Metric              | Target            |
| ------------------- | ----------------- |
| Automation Rate     | ≥98%              |
| User Prompts        | ≤2 per run        |
| Traceability        | 100%              |
| Response Time       | 99% <15s per call |
| Hierarchy Integrity | 100% valid links  |

## 🔒 Security

- **OAuth 2.0**: All authentication via industry-standard OAuth
- **Secrets Management**: GitHub repository secrets for credential storage
- **PII Protection**: Automatic regex-based detection and redaction
- **Audit Logging**: Full traceability with `tool_call.id` propagation
- **Least Privilege**: Scoped tokens (ADO: `vso.work`, Jira: `write:jira-work`)

## 📝 Usage Example

```
User: Transform this BRD into Azure DevOps work items:

# E-Commerce Platform Modernization

## Functional Requirements
1. User Authentication System
   - Social login integration (OAuth 2.0)
   - Multi-factor authentication
   - Password reset functionality

2. Product Catalog Management
   - Category hierarchy
   - Product search with filters
   - Inventory tracking

## Non-Functional Requirements
- Performance: Page load <2 seconds
- Security: PCI DSS compliance
- Scalability: Support 10K concurrent users

Agent486: Let's begin the process of transforming the E-Commerce Platform Modernization BRD
into hierarchical work items for Azure DevOps.

Phase 1: Authenticating with ADO via OAuth...
[Opens browser for authentication]

Completed: Authentication successful. Proceeding to Phase 2: Fetch organizations.

Phase 2: Fetching organizations from ADO.
Available organizations:
1. MyCompany (ID: abc123)
2. TestOrg (ID: def456)

Validation Gate: Reply with 'select_organization MyCompany' to proceed.

User: select_organization MyCompany

Agent486: Organization selected: MyCompany. Proceeding to Phase 3: Parse BRD.

Phase 3: Parsing BRD into requirements.
Extracted 6 items (4 FR, 2 NFR). Confidence: 92%.

Phase 4: Structuring into hierarchy.
Validated depth/links. Total items: 12 (including sub-items).

...

Phase 8: Generated Hierarchy for Review:

| Level   | Title                          | Type | Children |
|---------|--------------------------------|------|----------|
| Epic    | E-Commerce Platform Modernization | FR   | 2        |
| Feature | User Authentication System     | FR   | 3        |
| PBI     | Social login integration       | FR   | 2        |
| Task    | Implement OAuth 2.0 provider   | FR   | 0        |
...

Total: 12 items

Reply with 'approve' to create in ADO.

User: approve

Agent486: Review approved. Proceeding to Phase 9: Creating items and verifying hierarchies.

Created Epic CFP-1: E-Commerce Platform Modernization
Verified CFP-1: ✓
Created Feature CFP-2: User Authentication System
Verified CFP-2: ✓ (parent: CFP-1)
...

Phase 10: Closing session and generating artifacts.
Completed: Full run successful. Artifacts generated.

Summary: 12 work items created in Azure DevOps
- 1 Epic: CFP-1
- 2 Features: CFP-2, CFP-7
- 5 PBIs: CFP-3, CFP-4, CFP-5, CFP-8, CFP-9
- 4 Tasks: CFP-6, CFP-10, CFP-11, CFP-12

All items verified with 100% hierarchy integrity.
```

## 🐛 Troubleshooting

### Common Issues

**Issue**: "MCP server not found"

- **Solution**: Ensure MCP servers are configured in VS Code settings or deployed as web services for GitHub.com usage

**Issue**: "Authentication failed"

- **Solution**: Verify OAuth credentials are correct and have required permissions. Check redirect URIs match exactly.

**Issue**: "Rate limit exceeded"

- **Solution**: Agent486 includes automatic 1-second delays between calls. If still hitting limits, check for other processes using the APIs.

**Issue**: "Hierarchy validation failed"

- **Solution**: Review BRD structure. Ensure requirements can be grouped into max 4-level hierarchy.

### Debug Mode

To enable detailed logging, set environment variable:

```bash
export AGENT486_DEBUG=true
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is provided as-is for use with GitHub Copilot.

## 📞 Support

For issues or questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [Instructions.md](Instructions.md) for detailed operational guidance
3. Open an issue in this repository

---

**Agent486** - Transforming BRDs into organized work items with full automation and reliability.
