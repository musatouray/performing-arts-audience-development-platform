# Copy job: cj_ticketing (on-premises SQL Server → gateway → lh_bronze)

Copies new and changed ticketing rows from the on-premises SQL Server into Bronze, through the on-premises data gateway. Built in the Fabric UI in `hh-dataplatform-dev`, then saved to Git and promoted like any other item.

## Before you start

Runbook Phase 8.1: the data loaded with `scripts/11_load_ticketing_db.py`, the read-only login `svc_fabric_reader`, and a SQL Server connection through your gateway.

## Build it

1. `hh-dataplatform-dev` › **New item › Copy job**. Name it `cj_ticketing`.
2. **Source:** SQL Server database. Choose the existing **on-premises connection** (it goes through your gateway and signs in as `svc_fabric_reader`).
3. **Tables:** select the seven tables in schema `tix`: `customers`, `seasons`, `venues`, `performances`, `orders`, `order_lines`, `subscriptions`. Skip `_load_history` and anything starting with `_stage_`.
4. **Destination:** Lakehouse `lh_bronze` › **Tables**, schema **ticketing**, same table names.
5. **Copy mode:** **Incremental copy**. For every table, set the incremental column to **updated_at**.
6. **Update method:** **Append**. Bronze keeps every version of a row; Silver keeps the latest one.
7. **Schedule:** leave it off. `pl_daily_load` runs it (see `src/pipelines/pl_daily_load.md`).
8. Save and **Run** once.

## Check it

- The first run copies everything (~510k rows); later runs copy only the rows changed since the last one.
- `lh_bronze` › Tables › `ticketing` has seven tables with real data types (not text).
- Run `11_load_ticketing_db.py` again after an incremental generator run, then run the Copy job: the row counts should be in the hundreds, not thousands.

## Why these choices

| Choice | Why | Alternative |
|---|---|---|
| Copy job, not Mirroring | Tessitura is usually vendor-hosted or run by another team. You get a read-only login, not the server admin rights Mirroring needs to turn on change tracking. A Copy job only needs `SELECT`. | Mirroring if you own the database (SQL Server 2016–2022 can be mirrored through the gateway) |
| On-premises data gateway | The database sits inside the organization's network, so Fabric can't reach it directly. The gateway makes an outbound-only connection, so no firewall port has to be opened to the internet. | A virtual network gateway, for sources in an Azure virtual network |
| Read-only SQL login | The connection can read `tix` and nothing else, and doesn't depend on any person's account. | A Windows service account, where the domain allows it |
| Incremental on `updated_at` | The source sets it whenever a row changes, and it's indexed, so each run reads only the changes. | Full copy every day: simple, but reads ~510k rows to find a few hundred changes |
| Append, not Merge | Bronze is the history. Merge would overwrite it, and reprocessing Silver would no longer be possible. | Merge into Silver directly: fewer layers, no history |
| Typed columns in Bronze | They come typed from a database, so there's nothing to lose. File sources land as text because files can't be trusted to keep their types. | — |
