-- Donor retention by fiscal year: donors who gave again / donors last year.
CREATE   VIEW rpt.vw_donor_retention AS
SELECT fiscal_year,
       SUM(CASE WHEN donor_status = 'Retained' THEN 1 ELSE 0 END)                        AS retained_donors,
       SUM(CASE WHEN donor_status IN ('Retained', 'LYBUNT') THEN 1 ELSE 0 END)           AS donors_last_year,
       SUM(CASE WHEN donor_status = 'LYBUNT' THEN 1 ELSE 0 END)                          AS lybunt_donors,
       SUM(CASE WHEN donor_status = 'LYBUNT' THEN amount_last_year ELSE 0 END)           AS lybunt_revenue_at_risk,
       CAST(SUM(CASE WHEN donor_status = 'Retained' THEN 1 ELSE 0 END) AS decimal(12,4))
         / NULLIF(SUM(CASE WHEN donor_status IN ('Retained', 'LYBUNT') THEN 1 ELSE 0 END), 0) AS donor_retention_rate
FROM rpt.vw_donor_status_by_fy
GROUP BY fiscal_year;

GO