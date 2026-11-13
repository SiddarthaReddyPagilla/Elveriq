# Elveriq — Git Integration and Safe Release Checklist

This archive was built from the user-provided `Elveriq-main.zip` snapshot. It has a **new local Git history**, **no authenticated GitHub remote**, and **nothing was pushed to your repository by the assistant**. The five replayable feature commits (three Phase 1 plus two Phase 1.1) are separately exported as `git-format-patch` files (see package README). The initial imported-baseline commit exists only to make those patches replayable; it is **not** the actual history of your GitHub repository.

## A. Review and apply commits on your Mac (recommended)

```bash
# In your OWN existing Elveriq Git clone, not inside this detached ZIP snapshot:
cd /path/to/your/Elveriq

git status                 # Confirm no uncommitted changes; back them up if present
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feature/warehouse-execution-phase1

# Replace /path/to/package with the extracted delivery package's patches directory:
git am /path/to/package/patches/*.patch

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check dispatchforge_app/static/app.js

git log --oneline -4
git status
# ONLY after reviewing migrations and test results:
git push -u origin feature/warehouse-execution-phase1
```

`git am` preserves the patch commit messages. If patches fail because `origin/main` changed since the ZIP snapshot, **do not force merge**: run `git am --abort`, compare the `Elveriq/` folder against your current branch, resolve the source differences in a separate branch and rerun tests. Do not overwrite `.git` from an unrelated repository or use `git push --force`. Use a pull request and CI checks before merging to `main`.

## B. Safe deployment to your hosted environment

- [ ] Verify you are deploying the intended Git branch and service and that no credentials entered source control.
- [ ] Snapshot / back up the existing PostgreSQL database and prove restore in staging.
- [ ] Check the current migration version. The prior transfer migration may already be applied; do not assume its status.
- [ ] Run the **additive PostgreSQL migration before the new code**:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261113_warehouse_execution.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/20261113_bin_cycle_counts.sql
```

- [ ] Run migrations on staging first. **Never run the concurrency-test suite against production.**
- [ ] Run `python -m pytest -q` with disposable PostgreSQL credentials supplied as `ELVERIQ_TEST_POSTGRES_URL`.
- [ ] Test two tenants, distinct warehouse bins, manager/staff permissions, scan mismatch, retry replay, capacity and pending putaway.
- [ ] Test physical bin counts: zero/positive/negative variance, concurrent posting, active moves, changing reservations, stale watermarks and owner-only approval. The new `bin_cycle_counts` migration MUST come after the warehouse execution migration.
- [ ] Validate that existing receipts, reservations, fulfillment, purchases, returns, stock adjustments and transfers still work on migrated staging data.
- [ ] Check application logs, database locks/error rates and location reconciliation after the pilot exercise.
- [ ] Merge only after passing code review, CI and staging acceptance; then deploy gradually to real users.

## C. Merge policy and rollback

**If tests fail:** stop, use `git am --abort` if the patch application itself is incomplete or revert the change on the feature branch. **If migration has been applied:** it is intentionally additive and can remain in the database until a reviewed rollback is prepared. Do not delete tasks/bin balances during a rushed rollback. **If the new service fails post-release:** roll back the application deployment while preserving database data, freeze new warehouse execution work and reconcile before re-enabling. Keep the migrated schema intact unless the DBA approves a data-preserving rollback.

## D. What was and was not validated

- **Validated locally:** existing Python tests and new SQLite API/invariant tests; JavaScript syntax via Node.
- **Not validated locally:** live PostgreSQL concurrency (database service unavailable here), browser automation on Mac/real scanner hardware, production configuration, backup restoration, actual GitHub push, and any vendor parity claim.

The research paper and 300-feature CSV are now versioned in `docs/research/`. Always associate future engineering tickets with feature IDs from that register.
