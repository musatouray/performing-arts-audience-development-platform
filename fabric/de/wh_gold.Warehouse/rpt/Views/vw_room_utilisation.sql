-- Hall and room use by month: hours booked by type, and share of the available hours
-- (14 bookable hours a day, 9am to 11pm).
CREATE   VIEW rpt.vw_room_utilisation AS
SELECT r.room_name, r.room_type, d.fiscal_year, d.calendar_year, d.month_num, d.month_name,
       SUM(CASE WHEN e.event_type = 'Concert'   THEN b.hours_booked ELSE 0 END) AS concert_hours,
       SUM(CASE WHEN e.event_type = 'Rental'    THEN b.hours_booked ELSE 0 END) AS rental_hours,
       SUM(CASE WHEN e.event_type = 'Rehearsal' THEN b.hours_booked ELSE 0 END) AS rehearsal_hours,
       SUM(b.hours_booked) AS hours_booked,
       14.0 * DAY(EOMONTH(MIN(d.[date]))) AS hours_available,
       CAST(SUM(b.hours_booked) / (14.0 * DAY(EOMONTH(MIN(d.[date])))) AS decimal(6,3)) AS utilisation,
       SUM(CASE WHEN e.event_type = 'Rental' THEN b.rental_fee ELSE 0 END) AS rental_revenue
FROM fact.venue_booking AS b
JOIN dim.event AS e ON e.event_key = b.event_key
JOIN dim.room  AS r ON r.room_key = b.room_key
JOIN dim.[date] AS d ON d.date_key = b.booking_date_key
WHERE e.[status] <> 'Cancelled' AND b.hours_booked > 0
GROUP BY r.room_name, r.room_type, d.fiscal_year, d.calendar_year, d.month_num, d.month_name;

GO