-- Rows are added by 61_security_users.local.sql.

CREATE FUNCTION sec.fn_gift_access(@is_anonymous bit)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
    SELECT 1 AS allowed
    WHERE @is_anonymous = 0
       OR EXISTS (SELECT 1 FROM sec.privileged_users WHERE user_principal_name = USER_NAME());

GO