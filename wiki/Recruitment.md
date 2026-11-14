# Recruitment (Job Postings & Candidate Pipeline)

Code location: `src/hr_minds/recruitment/`.

The Recruitment module tracks what an organization is hiring for and who is under consideration. A **job posting** describes an opening and its requirements; a **candidate** is a resume (from the [Media](Media) module) a user has selected for one posting, with a status that moves through a pipeline.

This is the manual half of hiring. The automated half — parsing resumes, scoring them against a posting, and suggesting who to shortlist — is the Agentic RAG work still on the roadmap (see [Home](Home)). Recruitment is deliberately built so that work can plug into it later without changing this module: an automated suggestion would just be another way of calling `POST .../candidates`.

---

## 🏗️ Concepts

```text
JobPosting (title, description)
      │
      ├── JobRequirement* (text, must_have)       — what the role needs
      │
      └── JobCandidate*                            — who's being considered
               │
               ├── resume ──────────────────────► LocalMedia (from Media)
               └── status: shortlisted → interviewing → offered → hired
                                                  ↘ rejected (from any stage)
```

- **A resume can be a candidate for more than one posting.** Selecting it twice for the *same* posting is rejected (`409`); selecting it for two different postings is fine.
- **Selecting a resume never copies or modifies it.** `JobCandidate` only links to an existing `LocalMedia` row; removing a candidate or deleting a posting never touches the resume file or its database record.
- **Status is free-form movement, not a workflow.** Any status can follow any other (there's no "can't go from hired back to shortlisted" rule) — this module just records where a candidate stands, not how they got there.

---

## 🗄️ Database Schema

### `JobPosting`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` | Primary key |
| `org_id` | `Integer` (FK → `organization.id`) | Tenant organization (CASCADE) |
| `created_by_id` | `Integer` (FK → `user.id`) | Who created it (CASCADE) |
| `title` | `String(255)` | |
| `description` | `Text` | The job description text |
| `created` / `modified` | `DateTime(timezone=True)` | Audit timestamps |

### `JobRequirement`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` | Primary key |
| `job_posting_id` | `Integer` (FK → `job_posting.id`) | Parent posting (CASCADE) |
| `text` | `String(500)` | One requirement, e.g. "5+ years of Python" |
| `must_have` | `Boolean` | `true` for a must-have, `false` for nice-to-have |

Up to 50 requirements per posting. `PATCH` on a posting replaces the whole list at once (see below) — there's no endpoint to edit a single requirement in place.

### `JobCandidate`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` | Primary key |
| `job_posting_id` | `Integer` (FK → `job_posting.id`) | Which posting (CASCADE) |
| `org_id` | `Integer` (FK → `organization.id`) | Tenant organization (CASCADE) |
| `local_media_id` | `Integer` (FK → `local_media.id`) | The selected resume (CASCADE) |
| `status` | `String(20)` | `shortlisted`, `interviewing`, `offered`, `hired`, or `rejected` |
| `selected_by_id` | `Integer` (FK → `user.id`, nullable) | Who selected it (SET NULL) |
| `created` / `modified` | `DateTime(timezone=True)` | `created` is when it was selected; `modified` moves on every status change |

**Unique constraint:** `(job_posting_id, local_media_id)` — a resume can't be selected twice for the same posting.

**Cascades:**
- Deleting a `JobPosting` removes its requirements and candidates. The resumes themselves (`LocalMedia` rows) are untouched.
- Deleting a `JobCandidate` (via the API) only removes that selection. The resume and the posting are untouched.

> ⚠️ **Known tradeoff:** `local_media_id` cascades on delete, so if a resume file is later removed from disk and a rescan prunes its `LocalMedia` row (see [Media](Media)'s `last_seen_at` pruning), every `JobCandidate` selection built on that file disappears too, silently. There's no history kept of who was selected once their file is gone. Denormalizing the file's name onto `JobCandidate` would survive that, at the cost of a snapshot that can go stale — not done yet; add it if this bites.

---

## 🔐 RBAC & Permissions

One feature, `recruitment`, covers both job postings and the candidate pipeline — they're split by HTTP action, not by a second feature slug. Split them into separate features later if an organization wants, say, hiring managers who can manage candidates but not edit postings.

| Endpoint | Required Permission |
| :--- | :--- |
| `POST /api/v1/recruitment/job-postings` | `recruitment:create` |
| `GET /api/v1/recruitment/job-postings` | `recruitment:read` |
| `GET /api/v1/recruitment/job-postings/{id}` | `recruitment:read` |
| `PATCH /api/v1/recruitment/job-postings/{id}` | `recruitment:update` |
| `DELETE /api/v1/recruitment/job-postings/{id}` | `recruitment:delete` |
| `POST /api/v1/recruitment/job-postings/{id}/candidates` | `recruitment:create` |
| `GET /api/v1/recruitment/job-postings/{id}/candidates` | `recruitment:read` |
| `PATCH .../candidates/{candidate_id}` | `recruitment:update` |
| `DELETE .../candidates/{candidate_id}` | `recruitment:delete` |

After adding the feature, run `uv run python -m hr_minds.auth.cli sync-features` so roles can be granted these permissions. Organization owners have them automatically.

Selecting a resume from another organization is refused the same way a missing posting is: `404 Resume not found`, not `403` — existence isn't leaked across organizations.

---

## 📏 Limits

- `title`: 1–255 characters. `description`: 1–20,000 characters.
- Up to 50 requirements per posting; each requirement's `text` is 1–500 characters.
- Lists are [paginated](API-Endpoints#pagination): postings and candidates default to 20 per page (maximum 100).

For the full HTTP specification and real request/response examples, see the [API Reference](API-Endpoints#recruitment).
