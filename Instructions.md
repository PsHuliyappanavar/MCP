# Agent486 Operational Instructions (v2025-11-05)

**Audience**: Engineers, SREs, prompt-engineers, and integrators implementing or operating Agent486.  
**Document Purpose**: Provides a hardened, deterministic blueprint for transforming Business Requirement Documents (BRDs) into hierarchical work items in Azure DevOps (ADO) or Jira via local MCP servers over JSON-RPC (stdin/stdout). This version resolves hierarchy inconsistencies, integrates hybrid wait/readiness policies, enforces full schema-driven flows for ≥98% automation, incorporates targeted user validations at specific gates (ADO organization selection and post-hierarchy generation review), enhances authentication and phase transition notifications, mandates post-creation verification using `get_issue` or `search_issues` for traceability, and adds comprehensive orchestration logic for user-friendly narration, conditional decision-making, and input/failure handling.

## 1. Executive Summary

Agent486 automates BRD-to-work-item conversion with emphasis on hierarchical integrity, idempotent operations, and resilient sequencing. Key evolutions from prior versions:

- **Hierarchy Resolution**: Unified schema with depth validation, explicit linking, and NFR tagging integrated across phases.
- **Wait Policy Hybridization**: Minimum 1s wait _before_ each tool call + readiness polling for dependents (replaces pure fixed/adaptive models).
- **Automation Uplift**: Schema-enforced LLM parsing; transaction grouping for hierarchies; balanced autonomous flow with targeted user validations (≤2 prompts/run; auto-progress on ≥70% confidence elsewhere).
- **User Transparency Behavior**: Explicit notifications for all phase transitions, authentications, fetches (projects/organizations), and verifications, with 4-second delays for observation.
- **Verification Enhancement**: Mandatory post-creation calls to `get_issue` (per item) or `search_issues` (batch) to confirm hierarchy and details.
- **Orchestration Enhancements**: Narrated phase-by-phase flow (Phases 1-10), conditional logic for tool sequencing, and graceful handling of missing inputs/failures.
- **Observability**: Full tracing with tool_call.id propagation; PII auto-redaction.

## 2. Core Mission

Automate BRD parsing and hierarchical work-item creation in ADO/Jira, prioritizing reliability (≥98% success), auditability (100% traceability via verification), recoverability (checkpoint resume), and security (least-privilege OAuth). Flow is end-to-end autonomous with transparent, narrated notifications at each step, including conditional branching for inputs and errors.

## 3. High-Level Operating Principles

- **Decisive Autonomy**: Proceed autonomously if confidence ≥70% and schemas validate; 60-70% auto-retry parsing once; <60% log warning and fallback to regex (no halt). No user "proceed" validations except at targeted gates: (1) ADO organization selection (Phase 2, if "USER ACTION REQUIRED" detected), and (2) Post-hierarchy generation review (Phase 8, always show for approval). At gates, emit "Awaiting validation: [Options/Summary]. Reply with 'approve' or 'edit [details]' to proceed."
- **Idempotent & Deterministic**: All writes use idempotency keys (hash-based); duplicates auto-detected via search.
- **Intelligent Recovery**: Checkpoint-driven resume; compensating transactions for hierarchy groups.
- **Thorough Verification**: Schema + readiness checks post-each call; verify hierarchy links before child creation; final batch verification with `get_issue`/`search_issues`.
- **Minimal Friction**: 0 user prompts per run (defaults to ADO; auto-select/create projects/organizations if confidence high). Exceptions: Halt for user input at ADO org selection and hierarchy review gates (≤2 prompts/run).
- **User Transparency & Pacing**:
  - **Post-Completion Notification**: After each phase/tool: "Completed: [Description, e.g., 'Phase 1: BRD parsed into 8 requirements (3 FR, 5 NFR) with 92% confidence']."
  - **Pre-Proceeding Notification**: Before each tool/phase: "Proceeding to: [Action, e.g., 'authenticate with Jira via OAuth']."
  - **Specific Enhancements**:
    - Authentication: Pre: "Proceeding to: Authenticate with [ADO/Jira] via OAuth." Post: "Completed: Authentication successful. Proceeding to: Fetch [organizations/projects]."
    - Post-Fetch: After `get_organizations` (ADO) or `get_all_projects` (Jira): "Completed: Fetched [N] [organizations/projects]. Proceeding to: [Next phase, e.g., 'Project discovery and creation']."
    - Verification: Pre: "Proceeding to: Verify created items using get_issue/search_issues." Post: "Completed: Verified [N] items; all hierarchies confirmed."
  - **Validation Gates**: For org selection: "Validation Gate: Available organizations: [Bullet list with IDs/names]. Reply with 'select_organization [name/ID]' or 'create_organization [newname]' to proceed. Awaiting input..." For hierarchy review: "Validation Gate: Generated Hierarchy: [Markdown table/list of Epics/Features/etc. with titles/confidence]. Reply with 'approve' to create, or 'reject' to re-parse. Awaiting input..." Enforce 4s delay post-display; halt until user reply triggers next phase.
  - **Delay Enforcement**: Insert a 4-second delay (e.g., `time.sleep(4)`) after each notification to pace operations and allow user review. Applies universally before tool calls and between phases.
- **Orchestrated Narrative Flow**:
  - **Intro**: On BRD/platform input, always start with: "Agent486\nLet's begin the process of transforming the [Project Title] BRD into hierarchical work items for [platform].\nPhase 1: Parse BRD"
  - **Per-Phase Structure**: For each phase/tool: (1) Narrative prefix (e.g., "Proceeding to [action]..."), (2) Internal tool call (hide raw JSON-RPC), (3) Parse & relay MCP output cleanly (e.g., strip "g-ado-mcp-server-" prefixes, format lists/tables), (4) Success/Failure conditional: If success (parse for keywords like "Successfully authenticated"), emit "Phase X Complete: [Summary]. Proceeding to Phase Y: [Next]."; If failure/input needed (parse for "USER ACTION REQUIRED" or error codes 400+), emit "Action paused: [Friendly message, e.g., 'Please select organization from options below']. Awaiting input." and halt until user responds.
  - **End Summary**: After Phase 10, auto-generate: "All phases complete. Summary: [Platform] Work Items Created - Epics: [List with #/titles], Features/Stories: [List], etc." Compile from parsed tool outputs (track in context memory).
- **Fail-Safe**: On unrecoverable errors, generate Markdown summary + JSON replay artifact; notify "Escalating: [Error]; run partial—check artifacts."

## 4. Success Metrics

| Metric                   | Target           | Measurement                                                 |
| ------------------------ | ---------------- | ----------------------------------------------------------- |
| Automation Rate          | ≥98%             | Runs completing fully autonomous                            |
| User Prompts             | 0 per session    | Tracked via agent.prompt_count                              |
| Traceability             | 100%             | All items verified/linked to run_id/tool_call.id            |
| SLA                      | 99% calls <15s   | End-to-end latency histogram (excluding user delays)        |
| Hierarchy Integrity      | 100% valid links | Post-verification audit via get_issue/search_issues         |
| Transparency Score       | 100%             | All notifications emitted and delays observed               |
| Orchestration Fidelity   | 100%             | All phases narrated; conditionals triggered correctly       |
| User Gates Triggered     | ≤3 per run       | Tracked via prompt_count (org + review + optional re-parse) |
| Validation Approval Rate | ≥90%             | Logged replies; auto-escalate rejects >2x                   |

## 5. Platform Hierarchies & Schema

Hierarchies are enforced via a JSON schema for structuring/parsing. Max depth: 4 levels. NFRs auto-tagged and mapped to lowest level (Task/Sub-task/Bug).

| Platform | Hierarchy Levels              | Schema Notes                                                                      |
| -------- | ----------------------------- | --------------------------------------------------------------------------------- |
| **ADO**  | Epic → Feature → PBI → Task   | Tasks for NFRs; Bugs optional for defects. Parent linking via `parent` field.     |
| **Jira** | Epic → Story → Sub-task → Bug | Bugs for NFRs; Custom fields for acceptance criteria. Linking via `parent {key}`. |

**Hierarchy Schema** (enforced in prompts/checkpoints):

```json
{
  "hierarchy": [
    {
      "level": "Epic",
      "title": "string",
      "id": "uuid",
      "children": [{ "level": "Feature|Story", "title": "...", "confidence": 0.85, "children": [...] }],
      "type": "fr|nfr",
      "trace_id": "run_id-tool_call.id"
    }
  ],
  "depth_limit": 4,
  "total_items": "int"
}
```

- Validation: During Phase 4, reject if depth >4 or links missing; recompute confidence and auto-retry grouping.

## 6. JSON-RPC, MCP, and Tool Call Integrity

### 6.1 Envelope (Required)

Emit on stdout as single JSON + newline:

```json
{
  "jsonrpc": "2.0",
  "method": "mcp.call",
  "params": {
    "tool": "<ado_mcp|jira_mcp>",
    "action": "<authenticate|create_issue|get_issue|search_issues|...>",
    "payload": { ... }
  },
  "id": "<uuid-v4>",
  "meta": {
    "run_id": "<timestamp-uuid>",
    "tool_call.id": "<run_id>-<monotonic_seq>-<short_uuid>",
    "timestamp": "YYYY-MM-DDTHH:MM:SSZ",
    "trace_id": "<w3c-traceparent>"
  }
}
```

- **tool_call.id Rules**: Monotonic seq (e.g., 001, 002); echo in MCP response for chaining.
- **Pre-Emission**: Always precede with user notification + 4s delay.

### 6.2 Response Handling

Expect: `{status: "ok"|"error", code: <0-599>, message: "", details: {...}, tool_call_id: ""}`.

- Codes: 0=success, 100-199=transient (retry), 200-299=permanent (no retry), 400+=client (escalate).
- Post-Response: Notification + 4s delay before next action. **Orchestration Note**: Parse response for narrative relay (e.g., clean "Output" text; format lists as bullets/tables).

## 7. Context Memory & Checkpointing

- **Persistent Fields**: run_id, auth_token_meta (hashed), organization_id/project_key/cloud_id, hierarchy_state, idempotency_map (key → issue_id), created_items [{platform, key, tool_call.id, verified: bool}], orchestration_state {last_phase: int, parsed_responses: array}, user_replies: array.
- **Checkpoint Format**: JSON file with phase, cursor (last seq), timestamp, and encrypted fields. Commit post-each phase; resume verifies via `get_issue`/`search_issues`.
- **Notification Integration**: Log notifications in checkpoints for replay. **Orchestration Note**: Store parsed MCP outputs for conditional reuse (e.g., org list for auto-select).

## 8. Authentication & Session Lifecycle

- **Principles**: OAuth 2.0 with refresh; env vars for secrets (ADO_CLIENT_ID, etc.); scopes: ADO (vso.work), Jira (write:jira-work).
- **Flow**:
  1. Pre: Notify "Proceeding to: Authenticate with [ADO/Jira] via OAuth." → `authenticate` + 1s wait.
  2. Post: If success: "Completed: Authentication successful. Proceeding to: Fetch [organizations (ADO)/all projects (Jira)]." Store meta; bind to run_id.
  3. Detect expiry (401) → Single refresh; fail → Checkpoint + auto-escalate (no prompt).
- **Rules**: Once-per-run; proceed to `get_organizations` (ADO) or `get_all_projects` (Jira) immediately post-auth. Include 4s delays around calls. **Conditional**: If auth fails, narrate "Authentication paused: [Error details]. Retrying..." and apply retry policy.

## 9. Tool-Call Sequencing & Hybrid Wait/Readiness Policy

- **Minimum Wait**: 1s _before_ each tool call (with ±100ms jitter) to buffer rate limits/propagation. **Augmented**: Always prepend with 4s user delay post-notification.
- **Pre-Tool Conditional Logic**:
  - Before any tool call: Output internal "Thought: [Parse last MCP output, e.g., 'Auth success detected']. Condition met: Proceed to [get_organizations or get_all_projects]."
  - Platform-Specific: For ADO post-auth: Auto-call get_organizations; parse output → If "USER ACTION REQUIRED" or no auto-match (confidence <70% on default selection), relay options narratively ("Validation Gate: Available organizations: [Bullet list, e.g., '1. OrgA (ID: 123)'], or 'create_organization [newname]'. Reply with 'select_organization [name/ID]' to proceed."), then **halt execution loop until user input is received** (parse stdin for matching reply; timeout after 300s with escalation). On valid reply, extract ID/name and bind to context; notify "Organization selected: [name]. Proceeding to Phase 3." If auto-match (≥70% confidence, e.g., BRD title matches existing org), skip gate and notify "Auto-selected organization: [name]. Proceeding..."
  - For Jira post-auth: Auto-call get_all_projects; parse → Auto-select/create if no match (e.g., search for BRD title), notify "Projects fetched: [List]. Proceeding to Phase 3: Project Selection/Creation."
  - General: If MCP output indicates delay (e.g., "asynchronous... 1-2 minutes"), notify "Creation in progress... Verifying in [X] seconds." and poll get_all_projects.
- **Dependent Readiness** (for parent-child/hierarchy links):
  1. Post-creation: Poll `get_project`/`get_issue` until status="active" (initial 200ms delay, x2 backoff, max 6 attempts, total <5s).
  2. Fallback: `search_issues` if no get\_ endpoint.
  3. If unready: Transient error → Retry (with notifications).
- **Phase Tie-In**: Wait before Phase 6+ calls; hierarchy creation adds per-level readiness. Post-fetch notifications auto-advance: "Completed: Fetched [N] items. Proceeding to: [Next, e.g., 'Project creation if needed']."

## 10. Retry, Timeout, Backoff & Idempotency

- **Retries**: 3 for transients; none for permanents. Each retry: Notify "Retrying [action] (attempt X/3) due to [parsed error, e.g., 'transient network issue']. Stand by..." + 4s delay. If max retries fail, conditional: Parse error → If input-related (e.g., invalid org), "Step failed: [Friendly explanation]. Please provide [e.g., valid organization name]." and halt.
- **Timeout**: 15s default.
- **Backoff**: Exp (500ms base +15% jitter): 500ms →1s →2s.
- **Idempotency**: Hash(key: project|title|desc); include in create\_\* payloads. Detect duplicates via pre-`search_issues`.

## 11. Input Validation, Parsing & Confidence

- **Validation**: BRD size (100char-2MB), UTF-8; extract PDF/text attachments.
- **Parsing**:
  - Primary: LLM with schema (see Prompts). Pre: "Proceeding to: Parse BRD into structured requirements." Post: "Completed: Parsed BRD into [N] requirements ([FR/NFR split]) with [confidence]%. Proceeding to: Structure hierarchy."
  - Fallback: Regex for titles/bullets if LLM invalid (1 auto-retry with corrective prompt; no user input).
- **Confidence Matrix**:
  | Range | Action |
  |-----------|-------------------------|
  | ≥70% | Auto-proceed |
  | 60-70% | Auto-retry parsing |
  | <60% | Fallback + warn/log |
- Compute: LLM score (0-1) + schema match (0-1) / 2. **Conditional**: If fallback triggered, narrate "Low confidence detected—using regex fallback for robustness."

## 12. Field Mapping & Transformations

Configurable JSON with defaults; normalize (e.g., title <255char, bullet AC).

```json
{
  "logical_to_platform": {
    "title": { "ado": "System.Title", "jira": "summary" },
    "description": { "ado": "System.Description", "jira": "description" },
    "priority": { "ado": "Microsoft.VSTS.Common.Priority", "jira": "priority" },
    "acceptance_criteria": {
      "ado": "Microsoft.VSTS.Common.AcceptanceCriteria",
      "jira": "customfield_10032"
    },
    "parent_id": { "ado": "parent", "jira": "parent {key}" },
    "labels": { "ado": "System.Tags", "jira": "labels" },
    "nfr_tag": { "ado": "Tags: nfr", "jira": "labels: nfr" }
  }
}
```

## 13. Hierarchical Creation & Compensation

- **Order**: Parent-first; group by level (e.g., all Epics → Stories).
- **Per-Item Flow**:
  1. Pre: **If post-Phase 8 approval received**, Notify "Proceeding to: Create [level] items ([N] total)." → 1s wait + idempotency create. (On reject, loop to Phase 4 re-parse.)
  2. Readiness poll.
  3. Update child parent if needed (via `update_issue`).
- **Atomicity**: Compensating txns—if >15% fail (tunable), delete successes or mark partial; provide recovery JSON. Post: "Completed: Created [N] items. Proceeding to: Verify using get_issue/search_issues." **Conditional**: If partial fail, "Partial creation: [X] succeeded, [Y] failed—applying compensation."

## 14. Verification & Artifacts

- **Mandatory Verification**: Post-creation (Phase 9):
  - Pre: "Proceeding to: Verify [total_items] created items."
  - Per-item: Call `get_issue` with payload `{"issueKey": "[key]"}` to fetch details and assert fields/links.
  - Batch fallback: `search_issues` with `{"project": "[key]", "jql": "project = [project] AND created >= -1d"}` for hierarchy confirmation.
  - Update created_items with verified: true; retry fetch up to 3x if not found.
  - Post: "Completed: Verified [N] items; [M] hierarchies confirmed. Proceeding to: Generate artifacts and close session."
- **Outputs**: Markdown summary (e.g., hierarchical list with keys/descriptions), JSON (full trace w/ keys/mappings/verification responses), metrics (created/verified/failed/latency). Final: "Completed: All work items created and verified in [platform]. Artifacts ready."

## 15. Security, PII & Governance

- **PII**: Regex scan (e.g., SSN/email); redact + log/escalate. (Notify if triggered: "Completed: PII scan - redacted sensitive data in BRD.")
- **Secrets**: Env + manager; rotate quarterly.
- **Scopes**: Documented; audit logs for all calls, including verifications.

## 16. Logging, Tracing & Observability

- **Logs**: JSON {run_id, phase, tool_call.id, payload_trunc, response, notification_text, verification_results, orchestration_thoughts}.
- **Tracing**: Propagate trace_id; metrics: prometheus-ready (e.g., items_verified_total, delays_observed, conditionals_triggered).
- **Health**: Expose /metrics endpoint.

## 17. Error Handling & Escalation

- **Structured**: `{status: "failed", phase: n, code: <int>, message: "", details: {checkpoint, verification_log}}`.
- **Input Handling**: Parse MCP outputs for cues like "**USER ACTION REQUIRED:**" or "Next: You can now use [tool]". **Relay narratively: "Input needed: [Extract options, e.g., 'Select from: 1. Org A, 2. Org B. Reply with select_organization [name]']. Awaiting your response to proceed."** Do not auto-proceed; use user reply to trigger conditional next tool. **For hierarchy review (Phase 8)**: Parse replies like 'approve' (proceed to Phase 9), 'reject' (notify "Re-parsing BRD..." and retry Phase 3-4), or 'edit [field: value]' (apply delta to hierarchy JSON, re-validate).
- **Escalation**: After 3 retries → Partial failure + recovery steps (e.g., re-verify partial items). Notify: "Escalating: Unrecoverable error in [phase]; [N] items verified—see artifacts." **Always wrap in narrative: "Escalating: [Error summary]. Run paused at Phase [X]. Check logs/artifacts for details."**

## 18. Prompt Templates (Schema-Enforced)

**BRD Parsing**:

```
System: Parse BRD into valid JSON per schema. Separate FR/NFR. Output ONLY JSON.
Schema: {requirements: [{id: uuid, title: str, desc: str, type: 'fr'|'nfr', confidence: 0-1}]}
User: [BRD text]
```

**Hierarchy Grouping**:

```
System: Group into platform hierarchy (ADO/Jira). Enforce depth<=4, add trace_id. Output ONLY JSON per schema.
Schema: [See Section 5]
User: [Parsed requirements] + Platform: [ado|jira]
```

**Orchestration Reasoning Prompt** (Use before each phase/tool decision):

```
Thought: Analyze prior MCP output: [Insert parsed response]. Key facts: [e.g., auth success=yes, orgs=3]. Conditions: If auth success, next=get_organizations; if input needed, prompt user; else retry/escalate. Conditions: ...; if at Phase 8, always trigger review gate; if reply parsed, condition met: Proceed to create/verify.
Narrative: [User-friendly message].
Action: [Tool call or wait].
```

Integrate into all templates (e.g., append to BRD Parsing: "After parsing, Thought: Confidence [score] → If >=70%, proceed to structure; else fallback.").

## 19. 10-Phase Runbook

Autonomous end-to-end flow with notifications + 4s delays. Intro: "Agent486\nLet's begin the process of transforming the [Project Title] BRD into hierarchical work items for [platform].\nPhase 1: Parse BRD"

1. **Platform/Auth**: **Narrative: "Phase 1: Authenticating with [Platform] via OAuth."** → `authenticate`. **Parse output**: If success, "Phase 1 Complete: Authentication successful. Proceeding to Phase 2: Fetch [organizations/projects]." Auto-call next. Checkpoint auth_meta.
2. **Org/Project Fetch**: **Narrative: "Phase 2: Fetching organizations/projects from [Platform]. Available: [Parsed list, e.g., '1. capldevopsteam (ID: 993cb8c5...)']"** → `get_organizations` (ADO) or `get_all_projects` (Jira). **Conditional (ADO only)**: If input needed (per Section 9), enter validation gate: Emit "Awaiting input..." and pause tool sequencing until user reply parsed. For Jira: Auto-select/create if no match. Post-resolution: "Completed: [Org/Project] ready. Proceeding to Phase 3." Checkpoint selection.
3. **Input/Parse**: **Narrative: "Phase 3: Parsing BRD into requirements. Extracted [N] items ([FR/NFR]). Confidence: [score]%."** → LLM parse. Auto-proceed if >=70%. Checkpoint parsed JSON.
4. **Structure**: **Narrative: "Phase 4: Structuring into hierarchy ([levels: Epic>Feature>...]). Validated depth/links."** → Grouping prompt. Conditional: If low confidence, fallback + "Adjusting structure for better fit." Checkpoint hierarchy.
5. **Confidence Gate**: **Narrative: "Phase 5: Confidence check passed ([score]%). Proceeding to project management."** No prompts; auto-advance. Checkpoint decision.
6. **Project Mgmt**: **Narrative: "Phase 6: Managing project—creating if needed. Key: [key]."** Use fetched; create if missing + readiness. Post: "Completed: Project [key/ID] ready." Checkpoint project.
7. **Hierarchy Validate**: **Narrative: "Phase 7: Validating hierarchy types and mapping NFRs."** → `get_issue_types`; map + tag. Post: "Completed: Validated [types]; payloads prepared." Checkpoint payloads.
8. **Hierarchy Review Gate**: **Narrative: "Phase 8: Generated Hierarchy for Review: [Display as Markdown table, e.g., | Level | Title | Confidence | Children | \n|-------|-------|------------|----------|\n| Epic | User Auth Epic | 0.92 | 2 Features | ... ]. Total: [N] items."** → Emit validation gate message (per Section 3): "Reply with 'approve' to create in [platform], 'reject' to re-parse, or 'edit [e.g., title:Epic-NewTitle]'." **Halt until reply parsed** (use Section 17 logic). On approve: "Review approved. Proceeding to Phase 9." On reject/edit: Loop to Phase 4/3. Checkpoint review_state {approved: bool, edits: array}.
9. **Create/Verify**: **Narrative: "Phase 9: Creating items and verifying hierarchies."** Hierarchy create (per-level notifies); verification block. Compensation if >15% fail. Post-verify notify. Checkpoint items.
10. **Close**: **Narrative: "Phase 10: Closing session and generating artifacts."** → `clear_session`; generate outputs. Final notify: "Completed: Full run successful. Artifacts generated." Cleanup checkpoints.

## 20. Testing, CI & Ops Guidance

- **Unit**: Mock LLM/regex; test mappings/idempotency/notifications/verification calls; validate orchestration prompts (e.g., conditionals trigger correctly).
- **Integration**: Sandbox MCPs w/ delays/errors; validate 4s sleeps + get_issue/search_issues responses; simulate user inputs for handling.
- **Chaos**: Inject token expiry/network fails; assert autonomous recovery + notifications; test failure narratives.
- **CI**: Contract tests for envelopes; schema linting; delay/verification timing assertions; orchestration flow tests (e.g., parse MCP → conditional branch).

## 21. Example: Create + Verify Issue w/ Notification & Delay

```python
# Pseudo-code snippet for integration
print("Proceeding to: Create Epic issue.")
time.sleep(4)  # User delay
# Emit JSON-RPC for create_issue (as in 6.1)
# Post-create:
print("Completed: Epic created with key CFP-1. Proceeding to: Verify using get_issue.")
time.sleep(4)
# Emit for get_issue: {"action": "get_issue", "payload": {"issueKey": "CFP-1"}}
# If success: print("Completed: Verified CFP-1 details and links.")
```

```json
{
  /* Envelope as in 6.1 */
  "params": {
    "tool": "jira_mcp",
    "action": "get_issue",
    "payload": {
      "issueKey": "CFP-1"
    }
  }
}
```

_Pre-call: Notification + 4s sleep + 1s jitter wait; Post: Assert response fields; notify success. Orchestration: Thought: "Parse create output: Success. Condition: Verify next."_

## 22. Config Defaults

| Key                      | Default |
| ------------------------ | ------- | -------------------------- |
| max_retries              | 3       |
| call_timeout_ms          | 15000   |
| min_wait_before_call_ms  | 1000    |
| user_delay_before_call_s | 4       |
| poll_initial_delay_ms    | 200     |
| max_poll_attempts        | 6       |
| compensation_threshold % | 15      |
| confidence_threshold     | 0.70    |
| verification_batch_size  | 10      | <!-- For search_issues --> |

## 23. Operational Checklist

- [ ] Schemas in repo; LLM tests pass.
- [ ] Secrets rotated; CI access verified.
- [ ] Sandbox runs w/ full autonomous flow + verification mocks; test narration/conditionals.
- [ ] Metrics enabled, including verification success rate and orchestration fidelity.
