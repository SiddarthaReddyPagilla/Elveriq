# Warehouse release preflight

Before enabling the inbound, outbound, exception or tracking UI in **staging**:

1. Take a database backup and verify you can restore it.
2. Review and apply versioned PostgreSQL migrations in dependency order (warehouse execution, bin counts, outbound, inbound, operations). Do not apply directly to production without staging verification.
3. In the application directory, with `DATABASE_URL` and `APP_ENV` configured for the intended environment, run:

   ```bash
   python -m scripts.check_schema_readiness
   ```

4. A return code of `0` confirms the presence of 17 required warehouse tables and the columns used by the current ORM models. Code `2` reports missing objects; code `1` indicates the preflight could not inspect the database.
5. Run `python -m pytest -q` and database-backed PostgreSQL concurrency tests, then exercise scans, inventory reconciliation, receiving, dispatch, and incident handling in staging.

The preflight performs **read-only metadata inspection**. It does not apply migrations, create tables, or prove that historical data, database privileges, constraints, indexes or concurrent workloads are safe. It never prints database credentials.
