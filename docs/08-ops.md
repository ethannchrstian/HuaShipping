# 08 — Operations: Hosting, Backups, Security

## Hosting decision

**Start on a PaaS — Railway or Render, Singapore region (~US$5–15/mo).**
Rationale: deploy-from-GitHub, managed PostgreSQL **with automated backups**,
automatic HTTPS, zero server administration — right trade for a new solo dev
whose #1 fear is losing/corrupting business data. Nothing app-side is
PaaS-specific (standard Django + Postgres + gunicorn + WhiteNoise), so the exit
path stays open.

```
Browser (office PCs / phones)
   │ HTTPS
PaaS: gunicorn + Django  ──  managed PostgreSQL (auto backups)
   │                              │
GitHub (push → CI green → deploy) └─ nightly pg_dump → object storage (2nd copy)
```

**Exit path (documented, not built): plain VPS** — DigitalOcean/Vultr Singapore
or Indonesian providers (IDCloudHost, Biznet Gio) ~$6–12/mo; Docker Compose
(app + Postgres) behind Caddy (auto-HTTPS); you own OS patching and backups.
Only worth it if PaaS cost ever matters.

## Backups (the "untested backup is not a backup" rule)

1. PaaS managed-Postgres automated backups ON (verify retention ≥ 7 days)
2. **Second copy we own:** nightly `pg_dump` (scheduled job) → S3-compatible
   object storage (e.g. Cloudflare R2, free tier) → keep 30 daily + 12 monthly
3. **Restore drill every 3 months:** restore latest dump into a local Postgres,
   run the app against it, open a voyage, check totals. Calendar reminder;
   log the drill date at the bottom of this file.
4. Before every schema migration in production: manual dump.

## Security checklist

- [ ] `DEBUG=False` in production; `SECRET_KEY` from env, never in git
- [ ] `ALLOWED_HOSTS` exact; HTTPS only: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS
- [ ] `manage.py check --deploy` clean — enforced in CI
- [ ] Argon2 password hasher (one setting + `argon2-cffi`)
- [ ] Per-user accounts only; strong passwords; admin URL not `/admin/` (mild obscurity) + admin restricted to superuser
- [ ] Dependabot/pip-audit in CI; apply Django security releases within days (subscribe to django-announce)
- [ ] DB not publicly reachable (PaaS internal networking)
- [ ] No real company data in error messages to third-party services; if adding error tracking (Sentry), scrub PII

## Environments

- **dev**: local, SQLite or dockerized Postgres, seed = imported real data
- **prod**: PaaS. (Skip a staging env at this scale; CI + local parity covers it. Revisit if a second developer ever joins.)

## Incident basics

- App down → PaaS dashboard → redeploy last green build (one click / `git revert` + push)
- Data mistake by a user → simple-history restore of the record (document the how-to when built)
- Disaster → restore latest dump to a fresh Postgres (the drilled procedure)

## Cost summary

PaaS app + DB ≈ $5–15/mo · R2 backup storage ≈ $0 · domain ≈ $10–15/yr.
Who pays: open question #13.

---
*Restore drills performed: (none yet — first one after first production deploy)*
