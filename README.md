# Certify — Certificate issuance demo

A polished front-end demonstration of an internal certificate console, inspired by the supplied blue-and-gold certificate reference. It is deliberately a **client-only demo**: records are kept in browser `localStorage`, and neither authorization nor storage is secure enough for real certificates.

## Run it

Open `index.html` in a browser, or serve the folder with any static server, for example:

```powershell
npx serve .
```

The demo lets an operator:

- issue an individual certificate with a CSPRNG-generated public ID;
- preview a reusable template with dynamic name, event, date, and certificate ID fields;
- validate a CSV/bulk sample for missing fields, invalid emails, and duplicates;
- queue a bulk job, search certificates, revoke a record, and inspect an audit trail;
- search the internal registry using a certificate ID, recipient, or event.

## What is intentionally mocked

The console demonstrates the user workflow—not the production trust boundary. The browser must never be the source of truth. Replace its behavior with a server-side API, authenticated session, database uniqueness constraints, private object storage, and background workers before use.

## Production recommendation

Build the main product rather than cloning a project. Use selected standards/components where they bring genuine value:

| Candidate | Fit | Decision |
|---|---|---|
| [Certo](https://github.com/Schroedinger-Hat/certo) | Full Open Badges 3.0/VC platform with CSV batch issuance and public verification. AGPL-3.0. | Evaluate for a standards-first program; do not embed/fork into a proprietary system without accepting AGPL obligations. |
| [DCC issuer-coordinator](https://github.com/digitalcredentials/issuer-coordinator) | MIT-licensed, Docker-oriented VC signing and status component. | Reuse/evaluate only when interoperable wallet credentials are a requirement. Keep issuance records and office UI in the main product. |
| [Badgr Server](https://github.com/open-educational-badges/badgr-server) | Django Open Badges reference backend with an issuer API and self-hosting. AGPL-3.0. | Useful reference, but not a low-friction base for a custom certificate-PDF workflow. |
| [Privado ID Issuer Node](https://github.com/PrivadoID/issuer-node) | Self-hosted VC issuer UI/API and revocation, Apache-2.0/MIT. | Consider only for a Polygon/Privado credential ecosystem; operationally heavier than a conventional PDF certificate platform. |

This recommendation is based on the repositories' documented features, licensing and deployment material, checked 10 September 2026. Certo documents CSV batch issuance, public verification and Docker Compose; DCC documents its own signing key and Docker components; Badgr documents a Django issuer API; Privado documents self-hosted issuance/revocation and its environment constraints. Confirm project health, license compatibility, CVEs, maintainer responsiveness, and a production proof-of-concept before adopting any dependency.

## Target architecture

```text
Admin Web (Next.js) ── HTTPS ──> API (FastAPI or NestJS)
                                      ├─ PostgreSQL: users, roles, templates, batches,
                                      │  recipients, certificates, verification_tokens, audit_logs
                                      ├─ Redis queue ──> worker pool ──> HTML/PDF renderer
                                      │                                      └─ S3/MinIO private objects
                                      └─ authenticated certificate registry and download endpoints
```

Start as a modular monolith: one web app, one API, PostgreSQL, Redis worker, and S3-compatible storage in Docker Compose. Scale the worker deployment independently for large batches. The internal registry searches certificate IDs and uses the database as its source of truth.

## Production workflow and APIs

1. Manager authenticates, selects an approved template, submits one record or CSV.
2. API validates inputs and authorizes the action; it creates a batch and idempotent recipient rows.
3. Worker transactionally assigns an internal UUID and non-guessable public ID; it writes the certificate record and audit event.
4. Worker renders the approved HTML template/PDF, stores the PDF privately, then marks that record complete.
5. Distribution jobs email/download independently. A delivery error does not undo issuance.
6. Authorized staff search the certificate registry by certificate ID, recipient, event, or batch and can see the current issuance status.

Suggested endpoints:

- `POST /v1/batches`, `GET /v1/batches/:id`, `POST /v1/batches/:id/retry-failed`
- `POST /v1/certificates`, `GET /v1/certificates?query=`, `POST /v1/certificates/:id/revoke`
- `POST /v1/templates`, `GET /v1/templates`
- `GET /v1/certificates/:id/download` (authorized, short-lived signed URL)

## Security baseline

- Enforce SSO/MFA and role checks server-side (Super Admin, Manager, Operator, Auditor); recipients have no issuance endpoint.
- Use TLS, a CSPRNG token of at least 128 bits, an internal UUID, database unique indexes, idempotency keys, and rate limits on login, issuance, and verification.
- Protect signing keys in a KMS/Vault when signing is introduced; scan and size-limit uploads; validate CSV/XLSX server-side.
- Preserve append-only audit events for issuance, approval, download, verification, revocation, and retries. Limit public data disclosure.
- Put generated PDFs in private object storage; issue time-limited download URLs. Back up PostgreSQL and objects; test recovery.

## Delivery roadmap

1. Establish auth/RBAC, template approval, schema migrations, audit logging, and internal certificate registry.
2. Add single issuance plus asynchronous PDF worker and storage.
3. Add CSV/XLSX validation, idempotent batches, retry-by-record, ZIP export, and monitoring.
4. Add email distribution, observability, security testing, backups, and load tests (10/1,000/10,000 records).
5. Optionally add Open Badges/VC signing as a separate capability—not a replacement for the operational certificate registry.
