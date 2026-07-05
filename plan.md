# Factory Orchestrator V1 Technical Plan (NeMo Integrated Edition)

## Architecture Vision

Factory Orchestrator là trung tâm điều phối toàn bộ Smart Software Factory.

NVIDIA NeMo Agent Toolkit được sử dụng làm Agent Runtime Layer.

Nguyên tắc:

* Factory Orchestrator quản lý workflow.
* NeMo quản lý agent.
* Agent không được tự gọi agent khác.
* Mọi điều phối đều đi qua Orchestrator.

---

# High Level Architecture

```text
┌──────────────────────────────┐
│         Frontend UI          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      API Gateway (NestJS)    │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     Factory Orchestrator     │
│                              │
│ Workflow Engine              │
│ Task Engine                  │
│ State Manager                │
│ Approval Engine              │
│ Agent Registry               │
│ Audit Engine                 │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│    NeMo Agent Runtime        │
└──────────────┬───────────────┘
               │
 ┌─────────────┼─────────────┐
 ▼             ▼             ▼

Architect   Developer      QA
Agent       Agent          Agent

Planner     Reviewer       DevOps
Agent       Agent          Agent

               │
               ▼

        Tool Layer

    Git
    Filesystem
    Terminal
    Docker
    Kubernetes
    PostgreSQL
    Search

               │
               ▼

 PostgreSQL / Redis / NATS
```

---

# Updated Microservice Architecture

```text
factory-platform
│
├── apps
│   ├── api-gateway
│   └── frontend
│
├── services
│   ├── orchestrator-service
│   ├── workflow-service
│   ├── task-service
│   ├── agent-registry-service
│   ├── agent-runtime-service
│   ├── approval-service
│   └── audit-service
│
├── packages
│   ├── shared-contracts
│   ├── shared-events
│   └── shared-types
│
├── infra
│   ├── postgres
│   ├── redis
│   ├── nats
│   ├── grafana
│   └── prometheus
│
└── docs
```

---

# New Service: Agent Runtime Service

Technology:

* Python 3.13
* FastAPI
* NVIDIA NeMo Agent Toolkit

Responsibilities:

* Run agents
* Manage agent memory
* Manage tool execution
* Reflection
* Planning
* Reasoning

Not responsible for:

* Workflow execution
* Approval
* Audit
* Task orchestration

---

# Agent Registry V2

Agent Registry không chỉ lưu metadata.

Nó phải liên kết với NeMo Runtime.

Schema:

```json
{
  "agent_id": "developer_agent",
  "name": "Developer Agent",
  "role": "developer",
  "runtime": "nemo",
  "capabilities": [
    "coding",
    "refactoring",
    "testing"
  ],
  "tools": [
    "filesystem",
    "git",
    "terminal"
  ],
  "status": "healthy"
}
```

---

# Agent Contract

Tất cả agent chạy trong NeMo phải tuân thủ:

```python
class BaseAgent:

    async def execute(
        self,
        task,
        context
    ):
        pass
```

Input:

```json
{
  "workflow_id": "wf_001",
  "task_id": "task_001",
  "goal": "Build authentication module",
  "context": {},
  "constraints": {}
}
```

Output:

```json
{
  "success": true,
  "summary": "",
  "artifacts": [],
  "metrics": {},
  "next_action": null
}
```

---

# Agent Lifecycle

Mọi agent trong NeMo đều dùng lifecycle chung.

```text
Receive Task
      ↓
Understand
      ↓
Plan
      ↓
Execute
      ↓
Validate
      ↓
Reflect
      ↓
Report
```

---

# Core Agents

## Architect Agent

Tools:

* Search Tool
* Documentation Tool

Outputs:

* Architecture Document
* Service Design
* Database Design

---

## Planner Agent

Tools:

* Planning Tool

Outputs:

* Epics
* Stories
* Tasks

---

## Developer Agent

Tools:

* Git Tool
* File System Tool
* Terminal Tool
* Search Tool

Outputs:

* Source Code
* Tests
* Pull Request Summary

---

## Reviewer Agent

Tools:

* Code Analysis Tool

Outputs:

* Review Report
* Approval Status

---

## QA Agent

Tools:

* Test Runner Tool

Outputs:

* Test Report
* Defect Report

---

## DevOps Agent

Tools:

* Docker Tool
* Kubernetes Tool

Outputs:

* Deployment Report
* Rollback Report

---

# Memory Architecture

## Short-Term Memory

Storage:

Redis

Purpose:

* Current workflow execution
* Current task context
* Current conversation

---

## Long-Term Memory

Storage:

PostgreSQL

Tables:

```text
agent_memories
agent_sessions
agent_artifacts
```

Purpose:

* Design decisions
* Architecture decisions
* Historical executions
* Learned project context

---

# Tool Framework

Base Tool Contract

```python
class Tool:

    async def execute(
        self,
        input
    ):
        pass
```

Tools V1:

* Filesystem Tool
* Git Tool
* Terminal Tool
* Search Tool
* Docker Tool
* PostgreSQL Tool

Tools V2:

* Kubernetes Tool
* Browser Tool
* Jira Tool
* GitLab Tool
* GitHub Tool

---

# Updated Workflow Execution Flow

```text
User Request
      ↓
Factory Orchestrator
      ↓
Create Workflow
      ↓
Create Task
      ↓
Resolve Agent
      ↓
Send Task
      ↓
NeMo Runtime
      ↓
Execute Agent
      ↓
Use Tools
      ↓
Generate Result
      ↓
Return Result
      ↓
Factory Orchestrator
      ↓
Next Task
```

---

# Sprint Plan

Sprint 1

* Infrastructure
* PostgreSQL
* Redis
* NATS
* NestJS Gateway

Sprint 2

* Workflow Service
* Task Service
* Agent Registry

Sprint 3

* NeMo Agent Runtime Service
* Base Agent
* Base Tool
* Architect Agent

Sprint 4

* Planner Agent
* Developer Agent
* Reviewer Agent

Sprint 5

* QA Agent
* DevOps Agent
* Memory Layer

Sprint 6

* Dashboard
* Monitoring
* Observability

Sprint 7

* Production Hardening
* CI/CD
* Security
* Load Testing

---

# Definition Of Done

Factory Orchestrator V1 được xem là hoàn thành khi:

* Workflow Engine hoạt động.
* Task Engine hoạt động.
* NeMo Agent Runtime hoạt động.
* 6 Core Agents hoạt động.
* Tool Layer hoạt động.
* Memory Layer hoạt động.
* Approval hoạt động.
* Audit hoạt động.
* Dashboard hoạt động.
* Monitoring hoạt động.

Kết quả cuối cùng là một Smart Software Factory có khả năng điều phối và vận hành nhiều AI Agent thông qua NVIDIA NeMo Agent Toolkit nhưng vẫn giữ Factory Orchestrator là trung tâm điều khiển.
