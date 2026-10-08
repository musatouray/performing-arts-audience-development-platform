-- ---------------------------------------------------------------------------
-- dim.patron keeps a history of address and patron type.
-- Contact details (email, phone) are just overwritten.
-- ---------------------------------------------------------------------------
CREATE   PROCEDURE etl.usp_load_dim_patron @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @now datetime2(6) = SYSUTCDATETIME(),
            @max int, @ins int, @upd int, @exp int;

    -- 1) Copy the latest patron records into a staging table, with a fingerprint of the tracked columns.
    DROP TABLE IF EXISTS etl.stg_patron;
    CREATE TABLE etl.stg_patron AS
    SELECT p.patron_id, p.first_name, p.last_name,
           CAST(CONCAT_WS(' ', p.first_name, p.last_name) AS varchar(210)) AS full_name,
           p.email, p.phone, p.address_line1, p.city, p.[state], p.postal_code, p.country,
           CAST(CASE WHEN p.city IN ('New York', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island') AND p.[state] = 'NY' THEN 'NYC'
                     WHEN p.[state] IN ('NY', 'NJ', 'CT') THEN 'NY Metro'
                     WHEN p.country = 'USA' THEN 'Domestic'
                     ELSE 'Unknown' END AS varchar(30)) AS region,
           p.patron_type, p.email_opt_in, p.source_systems, p.first_seen_date,
           CONVERT(varchar(64), HASHBYTES('SHA2_256',
                   CONCAT_WS('|', p.address_line1, p.city, p.[state], p.postal_code, p.patron_type)), 2) AS scd_hash
    FROM [lh_silver].[core].[patron] AS p;

    -- 2) Overwrite contact details on the current row. No history is needed for these.
    UPDATE d SET first_name = s.first_name, last_name = s.last_name, full_name = s.full_name, email = s.email,
                 phone = s.phone, email_opt_in = s.email_opt_in, source_systems = s.source_systems
    FROM dim.patron AS d JOIN etl.stg_patron AS s ON d.patron_id = s.patron_id
    WHERE d.is_current = 1
      AND (ISNULL(d.email, '') <> ISNULL(s.email, '') OR ISNULL(d.phone, '') <> ISNULL(s.phone, '')
           OR ISNULL(d.full_name, '') <> ISNULL(s.full_name, '') OR ISNULL(d.source_systems, '') <> ISNULL(s.source_systems, '')
           OR ISNULL(CAST(d.email_opt_in AS int), -1) <> ISNULL(CAST(s.email_opt_in AS int), -1));
    SET @upd = @@ROWCOUNT;

    -- 3) If the address or patron type changed, close the current row.
    UPDATE d SET valid_to = @now, is_current = 0
    FROM dim.patron AS d JOIN etl.stg_patron AS s ON d.patron_id = s.patron_id
    WHERE d.is_current = 1 AND d.scd_hash <> s.scd_hash;
    SET @exp = @@ROWCOUNT;

    -- 4) Add a current row for new patrons and for patrons closed in step 3.
    --    New patrons start in 1900 so their older orders and gifts still link to them.
    SELECT @max = ISNULL(MAX(patron_key), 0) FROM dim.patron WHERE patron_key > 0;
    INSERT INTO dim.patron
    SELECT @max + ROW_NUMBER() OVER (ORDER BY s.patron_id),
           s.patron_id, s.first_name, s.last_name, s.full_name, s.email, s.phone, s.address_line1, s.city, s.[state],
           s.postal_code, s.country, s.region, s.patron_type, s.email_opt_in, s.source_systems, s.first_seen_date, s.scd_hash,
           CASE WHEN h.patron_id IS NULL THEN CAST('1900-01-01' AS datetime2(6)) ELSE @now END,
           CAST('9999-12-31' AS datetime2(6)), 1
    FROM etl.stg_patron AS s
    LEFT JOIN (SELECT DISTINCT patron_id FROM dim.patron) AS h ON h.patron_id = s.patron_id
    WHERE NOT EXISTS (SELECT 1 FROM dim.patron AS d WHERE d.patron_id = s.patron_id AND d.is_current = 1);
    SET @ins = @@ROWCOUNT;

    IF NOT EXISTS (SELECT 1 FROM dim.patron WHERE patron_key = -1)
        INSERT INTO dim.patron (patron_key, patron_id, full_name, region, valid_from, valid_to, is_current)
        VALUES (-1, 'N/A', 'Unknown patron', 'Unknown', '1900-01-01', '9999-12-31', 1);

    -- EXEC only accepts variables or literals, so build the note first.
    DECLARE @note varchar(4000) = CONCAT(@exp, ' version(s) expired (SCD2)');
    EXEC etl.usp_log @run_id, 'etl.usp_load_dim_patron', 'dim.patron', @ins, @upd, 0, 'Succeeded', @note, @started;
END;

GO