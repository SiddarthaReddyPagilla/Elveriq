# Security / Production Readiness

This is a public **educational MVP**, not a production-hardened inventory platform. **Do not store real customer secrets, regulated information, or business-critical stock data in it yet.**

## Safeguards currently included

- Passwords are salted and hashed with PBKDF2-HMAC-SHA256 (260,000 iterations), not stored in plain text.
- Signed session cookies (SameSite=Lax; `Secure` in production mode).
- CSRF tokens required for mutating routes.
- Tenant filtering on all workspace-owned API operations.
- Owner-only SKU creation, warehouse creation, manual stock adjustments and supplier creation.
- Conditional stock updates to avoid overselling in normal workflows.
- Private values escaped in the frontend; CSV export guards against formula injection.
- Parameterized SQLAlchemy queries, stock quantity constraints, and movement history.
- Production mode refuses to start without a strong `APP_SECRET` and PostgreSQL configuration.

## Mandatory work **before real customers**

1. Add email verification, password reset / account recovery, and employee invitations. Prefer professionally maintained authentication services or security-reviewed auth libraries.
2. Add request / authentication rate limiting, abuse controls, stronger account enumeration protections and optional MFA.
3. Add audit retention and deletion rules, secure logs, backup/restore drills, and database migration management.
4. Review tenant authorization on every endpoint, complete security tests, and commission a security review before pilot operations.
5. Move hosting behind HTTPS, restrict database privileges, manage secrets through the hosting platform, and rotate secrets on compromise.
6. Establish privacy policy, terms of service, data handling agreements, incident response and customer support processes.
7. Stress-test transaction integrity, concurrent reservations and performance on PostgreSQL.
8. Decide authorized operational roles and ensure staff invitations do not expose credentials.

## Demo data

The demo tenant is deliberately fictional and read-only. Its products, warehouses, suppliers, and orders are *not* references to real business inventory. Registered accounts are intended for trying the application with synthetic data only.

## Responsible disclosure

Please do not upload secrets or test other organizations' systems without permission. Report suspected issues privately to the project owner before using any service in production.
