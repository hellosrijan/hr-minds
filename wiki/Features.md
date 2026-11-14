# Features

In HR Minds, a **Feature** represents a functional domain of the platform. Features serve as the foundational building blocks for both module routing and the Role-Based Access Control (RBAC) permission system.

---

## 🏗️ How Features Work

1. **Feature Registry (`src/hr_minds/settings/features.py`)**:
   - Acts as the single code-level source of truth for all system capabilities.
   - Each feature defines a unique slug (`FeatureSlug`), human-readable name, base URL path, and description.
2. **Database Synchronization (`sync-features`)**:
   - Code-defined features are synced to the database `feature` table via the CLI:
     ```bash
     uv run python -m hr_minds.auth.cli sync-features
     ```
   - Each registered feature automatically generates standard CRUD actions in the `permission` table: `create`, `read`, `update`, `delete`.
3. **Endpoint Authorization (`require`)**:
   - Endpoints secure access by requiring a specific feature and action pair:
     ```python
     membership: Membership = Depends(require(FeatureSlug.ROLES, "create"))
     ```

---

## 📋 Feature Catalog

| Feature | Slug | Status | Description | Standard Actions |
| :--- | :--- | :--- | :--- | :--- |
| **RBAC: Members** | `members` | **Active** | Invite organization members and manage member roles | `create`, `read`, `update`, `delete` |
| **RBAC: Roles** | `roles` | **Active** | Create and manage custom organization roles and permissions | `create`, `read`, `update`, `delete` |
| **Media** | `media` | **Active** | Scan local folders of candidate resumes | `create`, `read`, `update`, `delete` |
| **Conversation** | `conversation` | **Active** | Chat sessions and messages, private to each user | `create`, `read`, `update`, `delete` |
| **Recruitment** | `recruitment` | *Roadmap* | Candidate pipeline, job postings, and Agentic RAG filtering | `create`, `read`, `update`, `delete` |
| **Attendance** | `attendance` | *Roadmap* | Employee check-in, check-out, and shift tracking | `create`, `read`, `update`, `delete` |

---

## 🔐 Implemented Features

### Role-Based Access Control (RBAC)
The first fully active feature set in HR Minds is **RBAC** (encompassing `roles` and `members`). It provides organization-scoped multi-tenancy, custom role definitions, escalation guards, and team invitations.

For detailed architecture, model relationships, and authorization rules:
➡️ **[RBAC Documentation](RBAC)**

For complete HTTP request and response specifications:
➡️ **[API Reference](API-Endpoints)**

### Media (Local Resume Scanner)
The **Media** feature provides filesystem-based candidate resume discovery and indexing. Organizations can register local directories containing resumes (PDFs, Word documents, images), track filesystem modifications, and stream scanning operations via Server-Sent Events (SSE).

For detailed architecture, model relationships, and SSE protocols:
➡️ **[Media Documentation](Media)**

For complete HTTP request and response specifications:
➡️ **[API Reference](API-Endpoints)**

### Conversation (Chat Sessions)
The **Conversation** feature is the central store for chat sessions. Each conversation is private to the user who started it, inside one organization, and holds an ordered list of messages. Other modules can attach a chat to something of theirs through an optional context, without this module depending on them.

For the data model, privacy rules, and the guard against forged assistant messages:
➡️ **[Conversation Documentation](Conversation)**

For complete HTTP request and response specifications:
➡️ **[API Reference](API-Endpoints#conversations)**
