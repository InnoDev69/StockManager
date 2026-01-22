# Roles and permissions

This document explains how roles are represented and enforced in the project (UI + backend).

## Existing roles

In practice there are **two profiles**:

- **Seller (Vendedor)**: can perform sales and view general information.
- **Administrator (Administrador)**: can manage the catalog (CRUD) and import products.

### Actual role values

The role is stored in:

- Database: `users.role` column.
- Flask session: `session["role"]` (loaded at login).

Important:
- Backend permission checks compare against the literal **`"admin"`**.
- The registration UI offers:
  - `Vendedor` (value `"Vendedor"`)
  - `Administrador` (value `"admin"`)

So **“Administrator” in the UI corresponds to `role == "admin"` in the backend**.

## Where permissions are enforced

### Backend (Flask HTML routes)

In `main.py` some routes are protected by role, for example:

- Create product (`/products/new`): requires login and `session.get("role") == "admin"`.
- CSV import (`/import` and `/import/confirm`): admin-only.

If not allowed, the user is redirected to the dashboard.

### Backend (REST API)

In `api/API.py`:

- Authentication: `require_auth()` requires `session["user_id"]` for most endpoints.
- Admin authorization (returns `403`):
  - `POST /api/products`
  - `PUT /api/products/<id>`
  - `DELETE /api/products/<id>` (soft delete via `status=0`)

## UI is not security

Templates use the role to show/hide sections (e.g., “admin-only” buttons).

This is **presentation only**; real security must rely on server-side checks (`main.py` and `api/API.py`).

## Notes and consistency

- The dashboard uses `session.get("role", "Vendedor")`; if `session["role"]` is missing for some reason, the UI will assume “Vendedor”.
- In `register_post()` the default role is `"user"`, but the HTML form usually submits `"Vendedor"` or `"admin"`.
  - Recommendation: treat any value other than `"admin"` as “non-admin” (Seller).

