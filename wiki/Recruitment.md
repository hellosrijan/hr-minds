# Recruitment (Job Postings & Candidate Pipeline)

Code location: `src/hr_minds/recruitment/`.

The Recruitment module tracks what an organization is hiring for and who is under consideration. A **job posting** describes an opening, hiring company, location, experience, salary, and structured skills; a **candidate** is a resume (from the [Media](Media) module) a user has selected for one posting, with a status that moves through a pipeline.

This is the manual half of hiring. The automated half — parsing resumes, scoring them against a posting, and suggesting who to shortlist — is the Agentic RAG work still on the roadmap (see [Home](Home)). Recruitment is deliberately built so that work can plug into it later without changing this module: an automated suggestion would just be another way of calling `POST .../candidates`.

---

## 🏗️ Concepts

```text
JobPosting (company_name, title, description, department, employment_type, work_mode, location, experience, salary, openings, status)
      │
      ├── JobSkill* (name, name_normalized, must_have, min_years) — what the role needs
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
| `org_id` | `Integer` (FK → `organization.id`) | Tenant organization (CASCADE, indexed) |
| `created_by_id` | `Integer` (FK → `user.id`) | Who created it (CASCADE, indexed) |
| `company_name` | `String(255)` | The hiring company or client |
| `title` | `String(255)` | Role title |
| `description` | `Text` | The job description text |
| `department` | `String(100)`, nullable | Department name |
| `employment_type` | `String(20)` | `full_time`, `part_time`, `contract`, or `internship` (default `full_time`) |
| `work_mode` | `String(20)` | `onsite`, `hybrid`, or `remote` (default `onsite`) |
| `location_city` | `String(100)`, nullable | City (null for location-independent remote roles) |
| `location_region` | `String(100)`, nullable | State or region |
| `location_country` | `String(100)`, nullable | Country |
| `experience_min_years` | `Integer` | Minimum years of experience (default `0`) |
| `experience_max_years` | `Integer`, nullable | Maximum years of experience (null = no upper limit) |
| `salary_min` | `Integer`, nullable | Minimum salary in whole currency units |
| `salary_max` | `Integer`, nullable | Maximum salary in whole currency units |
| `salary_currency` | `String(3)`, nullable | 3-letter currency code (ISO 4217, e.g. `INR`, `USD`) |
| `openings` | `Integer` | Number of vacancies (default `1`) |
| `status` | `String(20)` | `draft`, `open`, `on_hold`, or `closed` (default `open`) |
| `created` / `modified` | `DateTime(timezone=True)` | Audit timestamps |

### `JobSkill`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` | Primary key |
| `job_posting_id` | `Integer` (FK → `job_posting.id`) | Parent posting (CASCADE, indexed) |
| `name` | `String(100)` | Skill name as displayed |
| `name_normalized` | `String(100)` | Lowercase form used for matching (indexed) |
| `must_have` | `Boolean` | `true` for mandatory skill, `false` for nice-to-have (default `false`) |
| `min_years` | `Integer`, nullable | Minimum years wanted for this skill (null = any) |
| `created` / `modified` | `DateTime(timezone=True)` | Audit timestamps |

Up to 50 skills per posting. `PATCH` on a posting with `skills` replaces the whole list at once (an empty list `[]` clears all skills) — there is no endpoint to edit a single skill in place.

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
- Deleting a `JobPosting` removes its skills and candidates. The resumes themselves (`LocalMedia` rows) are untouched.
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

## 📏 Limits & Validation

- `company_name`: 1–255 characters (required).
- `title`: 1–255 characters (required).
- `description`: 1–20,000 characters (required).
- `department`, `location_city`, `location_region`, `location_country`: optional, up to 100 characters each.
- `employment_type`: `full_time`, `part_time`, `contract`, `internship` (default `full_time`).
- `work_mode`: `onsite`, `hybrid`, `remote` (default `onsite`).
- `experience_min_years`: 0–60 (default `0`); `experience_max_years`: 0–60, nullable.
- `salary_min`, `salary_max`: non-negative integers; `salary_currency`: 3 uppercase letters (ISO 4217).
- `openings`: 1–1,000 (default `1`).
- `status`: `draft`, `open`, `on_hold`, `closed` (default `open`).
- Up to 50 skills per posting; each skill has `name` (1–100 characters), `must_have` (boolean, default `false`), and `min_years` (0–60 or null).
- **Validation rules (`400 Bad Request`):**
  - Maximum experience must not be below minimum experience (`experience_max_years < experience_min_years`).
  - Maximum salary must not be below minimum salary (`salary_max < salary_min`).
  - Specifying a salary (`salary_min` or `salary_max`) requires a currency (`salary_currency`).
- **PATCH semantics:**
  - Omitted fields remain unchanged.
  - For nullable fields (`department`, `location_city`, `location_region`, `location_country`, `experience_max_years`, `salary_min`, `salary_max`, `salary_currency`), sending `null` clears the field.
  - For other fields, `null` means "leave it alone".
  - Sending `skills` replaces the entire skill list; sending `[]` removes all skills.
- Lists are [paginated](API-Endpoints#pagination): postings and candidates default to 20 per page (maximum 100).

For the full HTTP specification and real request/response examples, see the [API Reference](API-Endpoints#recruitment).
