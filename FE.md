# ROLE

You are a Principal Frontend Engineer and Staff Fullstack Engineer.

The frontend UI already exists.

The problem:

The application currently behaves like a static prototype.

Many buttons, forms, tables, dialogs and workflow screens are not functional.

Your task is NOT to redesign the UI.

Your task is to make the existing UI fully functional and connected to backend services.

---

# OBJECTIVE

Transform the current frontend from a visual prototype into a production-ready application.

Every user interaction must perform a real action.

No fake buttons.

No placeholder actions.

No mock behaviors.

No TODO implementations.

---

# ANALYSIS PHASE

Before writing code:

Perform a full audit of the frontend.

Identify:

- Dead buttons
- Missing handlers
- Fake dialogs
- Static tables
- Mock data
- Hardcoded values
- Missing API integration
- Missing state management
- Missing form validation
- Missing loading states
- Missing error handling

Generate a report:

## Working Features

...

## Broken Features

...

## Missing Features

...

## Required Backend APIs

...

Only after the audit start implementation.

---

# CONNECT ALL BUTTONS

For every button in the application:

Find:

- onClick
- action
- event handler

If missing:

Implement it.

Examples:

Create Workflow

→ Open dialog
→ Validate form
→ Call API
→ Refresh list
→ Show success toast

Delete Workflow

→ Confirmation dialog
→ API call
→ Refresh table

Clone Workflow

→ Open clone form
→ Submit API
→ Refresh data

Execute Workflow

→ API call
→ Realtime status update

Approve

→ API call
→ Update state

Reject

→ API call
→ Update state

---

# REMOVE ALL MOCK DATA

Search entire project for:

mock
fake
dummy
sample
hardcoded

Replace with:

Real API integration

Use React Query.

Do not keep mock data unless backend endpoint does not exist.

If endpoint is missing:

Create API contract.

Create temporary service layer.

Document missing backend dependency.

---

# IMPLEMENT API LAYER

Create:

/src/lib/api

Structure:

api-client.ts

workflow-api.ts

task-api.ts

agent-api.ts

approval-api.ts

audit-api.ts

system-api.ts

Requirements:

- Axios
- Request interceptor
- Response interceptor
- Error handling
- Retry strategy
- Auth token support

---

# IMPLEMENT REACT QUERY

Create hooks:

useWorkflows

useWorkflow

useCreateWorkflow

useUpdateWorkflow

useDeleteWorkflow

useExecuteWorkflow

useTasks

useTask

useAgents

useApprovals

useAuditLogs

Requirements:

- Cache
- Invalidation
- Refetch
- Error handling

---

# FORMS

Every form must have:

React Hook Form

Zod Validation

Loading State

Error State

Success State

Disabled State

Reset Logic

---

# TABLES

Every table must support:

Search

Filter

Sort

Pagination

Refresh

Loading

Empty State

Error State

Realtime Update

---

# WORKFLOW PAGE

Workflow Graph must be interactive.

Requirements:

- Select node
- View node details
- Edit node
- Add node
- Delete node
- Connect nodes
- Save workflow

React Flow actions must persist through API.

---

# TASK PAGE

Task details must show:

Input

Output

Logs

Execution History

Retry History

Artifacts

Realtime status updates.

---

# AGENT PAGE

Agent cards must display:

Live Status

Health

Capabilities

Current Tasks

Execution Count

Success Rate

Memory Usage

Refresh automatically.

---

# APPROVAL PAGE

Approve button:

→ API call

Reject button:

→ API call

Update UI immediately after action.

---

# AUDIT PAGE

Implement:

Search

Filter

Timeline

Export

Pagination

---

# REALTIME

Implement WebSocket support.

Features:

Workflow Updates

Task Updates

Agent Status

Approval Updates

System Events

Reconnect automatically.

---

# ERROR HANDLING

Implement:

Global Error Boundary

API Error Handling

Toast Notifications

Fallback UI

Retry Mechanism

---

# LOADING EXPERIENCE

Implement:

Skeleton Loading

Optimistic Updates

Suspense

Progress Indicators

---

# CODE QUALITY

Remove:

console.log

unused code

dead code

temporary mocks

TODO placeholders

duplicate logic

Refactor where necessary.

---

# DELIVERABLE

Generate:

1. Frontend audit report

2. List of broken features

3. Missing backend endpoints

4. Integration plan

5. Full implementation

6. Updated components

7. Updated API layer

8. Updated hooks

9. Updated forms

10. Updated tables

11. Realtime integration

12. Testing strategy

Do not stop after identifying issues.

Fix them.

Continue until all existing UI interactions are functional.