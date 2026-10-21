# Copy job: cj_mip (MIP general ledger, on-premises SQL Server → gateway → lh_bronze)

Copies new and changed ledger rows from the MIP Fund Accounting database into Bronze. It's the same pattern as [`cj_tessitura`](copy_job_tessitura.md), on purpose: a second on-premises database is a new connection and a new Copy job, nothing else. Built in the Fabric UI in `hh-dataplatform-dev`, then saved to Git.

## Before you start

1. Load the data: `uv run python scripts/11_load_source_db.py --source mip_db`. This creates database `HarmoniaMIP` with four tables in `dbo`: `gl_account`, `department`, `fund`, `gl_transaction`.
2. A **separate** read-only login for the ledger. Finance owns MIP, so its access is granted, reviewed and revoked on its own, not shared with Tessitura's login. In SSMS:

   ```sql
   CREATE LOGIN svc_fabric_mip_reader WITH PASSWORD = '<strong password>', CHECK_POLICY = ON;
   USE HarmoniaMIP;
   CREATE USER svc_fabric_mip_reader FOR LOGIN svc_fabric_mip_reader;
   GRANT SELECT ON SCHEMA::dbo TO svc_fabric_mip_reader;   -- read the ledger, nothing else
   DENY  SELECT ON OBJECT::dbo._load_history TO svc_fabric_mip_reader;
   ```
3. A connection: Fabric › Settings › **Manage connections and gateways** › New › **On-premises**. Use your gateway, **SQL Server**, server `localhost`, database `HarmoniaMIP`, **Basic** as `svc_fabric_mip_reader`. Name it `harmonia-hall-mip-sql-connect`.

## Build it

1. `hh-dataplatform-dev` › **New item › Copy job**. Name it `cj_mip`.
2. **Source:** SQL Server database, the connection above.
3. **Tables:** the four tables in `dbo`. Skip `_load_history` and anything starting with `_stage_`.
4. **Destination:** Lakehouse `lh_bronze` › **Tables**, schema **mip**, same table names.
5. **Copy mode:** **Incremental copy**, incremental column **updated_at** for every table.
6. **Update method:** **Append**.
7. **Schedule:** off. `pl_daily_load` runs it.
8. Save and **Run** once.

## Check it

- `lh_bronze` › Tables › `mip` has four tables. `gl_transaction` has about 11,000 rows on the first run.
- Every journal balances: `SELECT journal_id FROM mip.gl_transaction GROUP BY journal_id HAVING SUM(credit_amount) <> SUM(debit_amount)` returns nothing.

## Why these choices

| Choice | Why | Alternative |
|---|---|---|
| Its own login and connection | Different system, different owner (the controller). Separate credentials mean finance can revoke Fabric's access to the ledger without touching ticketing. | One shared login: fewer secrets, but one leak exposes both systems |
| Copy job after the nightly close | Finance needs exact, auditable copies of posted journals; a Copy job reads only what changed. | Mirroring, if finance owned the server and allowed change tracking |
| Journal lines, not balances | Lines can be summed to any balance, by any period, fund or department, and traced back to the posting. | Monthly trial balance extract: smaller, but loses the drill-down |
