-- Education reach, for grant and board reports. Counts only, no student details.
CREATE   VIEW rpt.vw_education_impact AS
SELECT d.fiscal_year, pr.program_type, pr.program_name, sc.borough,
       CAST(ISNULL(sc.is_title_i, 0) AS bit) AS is_title_i_school,
       COUNT(*)                          AS sessions,
       SUM(e.participants)               AS participant_touchpoints,
       SUM(e.teaching_artist_hours)      AS teaching_artist_hours,
       COUNT(DISTINCT e.school_key)      AS schools_served
FROM fact.education_sessions AS e
JOIN dim.[date]   AS d  ON d.date_key = e.session_date_key
JOIN dim.program  AS pr ON pr.program_key = e.program_key
JOIN dim.school   AS sc ON sc.school_key = e.school_key
GROUP BY d.fiscal_year, pr.program_type, pr.program_name, sc.borough, CAST(ISNULL(sc.is_title_i, 0) AS bit);

GO