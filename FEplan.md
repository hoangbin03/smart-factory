# ROLE

You are a Principal Frontend Architect and Staff UX Engineer.

Your mission is to design and implement the complete frontend for a Smart Software Factory Platform.

The backend already exists and contains:

- Factory Orchestrator
- Workflow Engine
- Task Engine
- Approval Engine
- Audit Service
- Agent Registry
- NeMo Agent Runtime

Your frontend must look and feel like a modern enterprise AI platform.

Inspiration:

- Temporal Cloud
- LangSmith
- Datadog
- Kubernetes Dashboard
- GitHub Actions
- Airflow
- Vercel Dashboard

Do NOT build a generic admin template.

Build an AI Factory Control Center.

---

# TECHNOLOGY STACK

Framework:

- Next.js 15
- React 19
- TypeScript

UI:

- Shadcn UI
- TailwindCSS

State:

- Zustand

Data:

- TanStack Query

Workflow Graph:

- React Flow

Forms:

- React Hook Form
- Zod

Charts:

- Recharts

Real Time:

- WebSocket

Theme:

- Dark Mode First

---

# DESIGN PRINCIPLES

The platform must feel:

- Enterprise
- Modern
- AI Native
- Real Time
- Operational

Avoid:

- Bootstrap style UI
- Admin template look
- Outdated dashboards

---

# APPLICATION STRUCTURE

/app

/dashboard

/workflows
/workflows/[id]

/tasks
/tasks/[id]

/agents
/agents/[id]

/approvals
/approvals/[id]

/audit

/settings

---

# GLOBAL LAYOUT

Sidebar

Sections:

🏭 Factory

- Dashboard

⚙ Workflow

- Workflows
- Templates

📋 Tasks

- Task Queue
- Task History

🤖 Agents

- Agents
- Agent Registry

✅ Approvals

- Pending
- History

📊 Monitoring

- Metrics
- Logs
- Traces

🔧 Administration

- Settings

---

# DASHBOARD PAGE

Create an executive AI factory dashboard.

Widgets:

Factory Health

Workflow Running

Workflow Failed

Tasks Running

Tasks Failed

Agent Health

Approval Queue

Recent Activity

System Status

NATS Status

Redis Status

PostgreSQL Status

NeMo Runtime Status

Charts:

Workflow Throughput

Agent Utilization

Task Completion Trend

Execution Success Rate

Recent Workflow Timeline

---

# WORKFLOW LIST PAGE

Table:

Workflow Name

Version

Status

Running Instances

Created Date

Actions

Features:

Search

Filter

Sort

Pagination

Create Workflow

Clone Workflow

Delete Workflow

---

# WORKFLOW DETAIL PAGE

This is the most important page.

Use React Flow.

Display:

Workflow Graph

Nodes

Edges

Current Execution State

Execution Timeline

Node Status

Agent Assigned

Execution Duration

Approval Points

Retry Information

Execution Logs

Layout:

Left Panel

Workflow Graph

Right Panel

Workflow Details

Bottom Panel

Execution Timeline

---

# TASK PAGE

Task Queue Dashboard

Columns:

Task ID

Workflow

Assigned Agent

Status

Started At

Duration

Actions

Task Detail

Input

Output

Logs

Artifacts

Execution Trace

Retry History

---

# AGENT PAGE

Agent Registry Dashboard

Cards:

Architect Agent

Planner Agent

Developer Agent

Reviewer Agent

QA Agent

DevOps Agent

Display:

Status

Capabilities

Current Load

Memory Usage

Execution Count

Success Rate

Average Runtime

Agent Detail:

Health

Current Tasks

Recent Executions

Tool Usage

Memory Usage

Execution History

---

# APPROVAL PAGE

Approval Center

Display:

Pending Approvals

Approved

Rejected

Priority

Workflow

Task

Requested By

Created At

Actions:

Approve

Reject

View Context

---

# AUDIT PAGE

Audit Explorer

Display:

Event Timeline

Workflow Events

Task Events

Agent Events

Approval Events

Search

Filter

Export

---

# MONITORING PAGE

System Metrics

Charts:

Workflow Throughput

Agent Throughput

Task Throughput

Error Rate

Latency

Memory Usage

CPU Usage

Queue Depth

NATS Metrics

Redis Metrics

PostgreSQL Metrics

---

# DESIGN SYSTEM

Create reusable components:

AppShell

Sidebar

Topbar

StatCard

MetricCard

WorkflowGraph

AgentCard

TaskTable

ApprovalTable

AuditTimeline

StatusBadge

HealthIndicator

ExecutionTimeline

LogViewer

TraceViewer

EmptyState

LoadingState

---

# UX REQUIREMENTS

Use:

Skeleton Loading

Optimistic Updates

Toast Notifications

Real Time Updates

Command Palette

Keyboard Shortcuts

Dark Mode

Responsive Layout

---

# OUTPUT

Generate:

1. Complete folder structure

2. Design system

3. Layout architecture

4. Route architecture

5. Zustand stores

6. API client layer

7. React Query hooks

8. React Flow workflow components

9. Dashboard implementation

10. Full page implementations

11. Reusable UI components

12. TypeScript types

13. Mock API layer

14. README

15. Production-ready frontend code

Do not create placeholder UI.

Generate enterprise-grade frontend suitable for a Smart Software Factory platform.