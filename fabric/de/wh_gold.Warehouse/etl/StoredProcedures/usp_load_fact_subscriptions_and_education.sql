CREATE   PROCEDURE etl.usp_load_fact_subscriptions_and_education @run_id varchar(64)
AS
BEGIN
    DECLARE @started datetime2(6) = SYSUTCDATETIME(), @n1 int, @n2 int;

    TRUNCATE TABLE fact.subscriptions;
    INSERT INTO fact.subscriptions
    SELECT s.subscription_id,
           ISNULL(p.patron_key, -1),
           ISNULL(CONVERT(int, CONVERT(varchar(8), CAST(s.purchased_at AS date), 112)), -1),
           s.season_id, se.fiscal_year, s.package_name, ISNULL(s.seats, 0), ISNULL(s.package_amount, 0),
           CAST(ISNULL(s.is_renewal, 0) AS bit), SYSUTCDATETIME()
    FROM [lh_silver].[ticketing].[subscriptions] AS s
    JOIN [lh_silver].[ticketing].[seasons]       AS se ON se.season_id = s.season_id
    LEFT JOIN [lh_silver].[core].[patron_xref]   AS x  ON x.source_system = 'ticketing' AND x.source_id = s.customer_id
    LEFT JOIN dim.patron                         AS p  ON p.patron_id = x.patron_id
                                                      AND s.purchased_at >= p.valid_from AND s.purchased_at < p.valid_to;
    SET @n1 = @@ROWCOUNT;

    TRUNCATE TABLE fact.education_sessions;
    INSERT INTO fact.education_sessions
    SELECT e.enrollment_id, ISNULL(pr.program_key, -1), ISNULL(sc.school_key, -1),
           ISNULL(CONVERT(int, CONVERT(varchar(8), e.session_date, 112)), -1),
           ISNULL(e.participants, 0), e.teaching_artist_hours, SYSUTCDATETIME()
    FROM [lh_silver].[education].[enrollments] AS e
    LEFT JOIN dim.program AS pr ON pr.program_id = e.program_id
    LEFT JOIN dim.school  AS sc ON sc.school_id  = e.school_id;
    SET @n2 = @@ROWCOUNT;

    DECLARE @total int = @n1 + @n2;
    EXEC etl.usp_log @run_id, 'etl.usp_load_fact_subscriptions_and_education', 'fact.subscriptions+education_sessions',
         @total, 0, 0, 'Succeeded', NULL, @started;
END;

GO