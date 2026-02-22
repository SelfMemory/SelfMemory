---
sidebar_position: 6
slug: /api-reference
---

# API Reference

The SelfMemory REST API lets you store, search, and manage memories programmatically. The server runs on `http://localhost:8081` by default.

## Authentication

All API requests require authentication via one of these methods:

| Method | Header | Use Case |
|--------|--------|----------|
| API Key | `Authorization: Bearer sk_im_...` | SDK and programmatic access |
| Session Cookie | `ory_kratos_session` | Dashboard and browser access |
| OAuth 2.1 Token | `Authorization: Bearer <token>` | MCP and third-party integrations |

API keys are scoped to a single project. Generate them from the dashboard under **API Keys**.

---

## Memories

### Create Memory

```
POST /api/memories
```

Store a new memory with optional metadata.

**Request Body:**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "I have a meeting with Alice on Friday"
    }
  ],
  "metadata": {
    "tags": "work,meeting",
    "people_mentioned": "Alice",
    "topic_category": "schedule"
  }
}
```

**Response:**

```json
{
  "message": "Memory created successfully",
  "memory_id": "mem_abc123"
}
```

---

### List Memories

```
GET /api/memories
```

Retrieve all memories for the authenticated user/project.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Max results to return |
| `offset` | integer | Pagination offset |
| `user_id` | string | Filter by user ID |
| `project_id` | string | Filter by project ID |

**Response:**

```json
{
  "results": [
    {
      "id": "mem_abc123",
      "content": "I have a meeting with Alice on Friday",
      "metadata": { "tags": "work,meeting" },
      "created_at": "2026-02-22T10:30:00Z"
    }
  ]
}
```

---

### Get Memory

```
GET /api/memories/{memory_id}
```

Retrieve a single memory by ID.

---

### Search Memories

```
POST /api/memories/search
```

Semantic search across memories using AI-powered embeddings.

**Request Body:**

```json
{
  "query": "meetings this week",
  "filters": {},
  "project_id": "proj_xyz"
}
```

**Response:**

```json
{
  "results": [
    {
      "content": "I have a meeting with Alice on Friday",
      "score": 0.92,
      "metadata": { "tags": "work,meeting" }
    }
  ]
}
```

---

### Delete Memory

```
DELETE /api/memories/{memory_id}
```

Delete a specific memory. Requires write permission.

---

### Delete All Memories

```
DELETE /api/memories
```

Delete all memories for the current project scope. This action is irreversible.

---

## Organizations

### Create Organization

```
POST /api/organizations
```

**Request Body:**

```json
{
  "name": "My Team"
}
```

---

### List Organizations

```
GET /api/organizations
```

Returns all organizations the authenticated user belongs to, along with their role.

---

### Get Organization

```
GET /api/organizations/{org_id}
```

---

### Delete Organization

```
DELETE /api/organizations/{org_id}
```

Deletes the organization and cascades to all projects, members, invitations, and API keys. Only the owner can perform this action.

---

### List Members

```
GET /api/organizations/{org_id}/members
```

---

### Update Member Role

```
PUT /api/organizations/{org_id}/members/{user_id}
```

**Request Body:**

```json
{
  "role": "admin"
}
```

---

### Remove Member

```
DELETE /api/organizations/{org_id}/members/{user_id}
```

---

### Invite User

```
POST /api/organizations/{org_id}/invitations
```

**Request Body:**

```json
{
  "email": "user@example.com",
  "role": "member",
  "projectIds": ["proj_xyz"],
  "projectRoles": { "proj_xyz": "editor" }
}
```

---

### Transfer Ownership

```
PUT /api/organizations/{org_id}/transfer-ownership
```

**Request Body:**

```json
{
  "new_owner_id": "user_abc"
}
```

---

## Projects

### Create Project

```
POST /api/projects
```

**Request Body:**

```json
{
  "name": "My Project",
  "organization_id": "org_abc"
}
```

---

### List Projects

```
GET /api/projects
```

Returns all projects the user owns or is a member of.

---

### Get Project

```
GET /api/projects/{project_id}
```

---

### Delete Project

```
DELETE /api/projects/{project_id}
```

Cascades to members, invitations, API keys, and memories.

---

### List Project Members

```
GET /api/projects/{project_id}/members
```

---

### Add Project Member

```
POST /api/projects/{project_id}/members
```

---

### Update Project Member Role

```
PUT /api/projects/{project_id}/members/{user_id}
```

---

### Remove Project Member

```
DELETE /api/projects/{project_id}/members/{user_id}
```

---

### Invite to Project

```
POST /api/projects/{project_id}/invitations
```

---

## API Keys

### Create API Key

```
POST /api/projects/{project_id}/api-keys
```

**Request Body:**

```json
{
  "name": "Production Key",
  "permissions": ["read", "write"],
  "expires_in_days": 90
}
```

**Response:**

```json
{
  "api_key": "sk_im_abc123...",
  "prefix": "sk_im_abc",
  "name": "Production Key",
  "permissions": ["read", "write"]
}
```

:::caution
The full API key is only returned once at creation. Store it securely.
:::

---

### List API Keys

```
GET /api/projects/{project_id}/api-keys
```

Returns all keys for the project (secrets are redacted).

---

### Delete API Key

```
DELETE /api/projects/{project_id}/api-keys/{key_id}
```

---

## Invitations

### List Pending Invitations

```
GET /api/invitations/pending
```

---

### Get Invitation Details

```
GET /api/invitations/{token}
```

No authentication required — the token itself serves as authorization.

---

### Accept Invitation

```
POST /api/invitations/{token}/accept
```

---

## Notifications

### List Notifications

```
GET /api/notifications
```

Returns the last 50 notifications with unread count.

---

### Mark as Read

```
PUT /api/notifications/{notification_id}/read
```

---

### Mark All as Read

```
PUT /api/notifications/read-all
```

---

## User Account

### Get Current User

```
GET /api/users/me
```

---

### Delete Account

```
DELETE /api/users/me
```

Deactivates the account and cascades cleanup. The user must not be the sole owner of any organization.

---

## Health Checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Full system health (DB, memory, disk) |
| `GET /health/live` | Kubernetes liveness probe |
| `GET /health/ready` | Kubernetes readiness probe |

---

## Rate Limiting

The API enforces rate limits on the following operations:

- Memory creation
- Memory search
- Organization creation
- Project creation
- Invitation sending

When rate limited, the API returns `429 Too Many Requests`. Retry after the duration specified in the `Retry-After` header.

---

## Errors

All error responses follow a consistent format:

```json
{
  "detail": "Error description"
}
```

| Status Code | Meaning |
|-------------|---------|
| `400` | Bad request — invalid parameters |
| `401` | Unauthorized — missing or invalid auth |
| `403` | Forbidden — insufficient permissions |
| `404` | Not found |
| `429` | Rate limited |
| `500` | Internal server error |
