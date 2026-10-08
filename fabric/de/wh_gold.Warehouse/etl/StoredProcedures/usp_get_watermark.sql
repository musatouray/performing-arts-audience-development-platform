CREATE   PROCEDURE etl.usp_get_watermark @object_name varchar(128), @value datetime2(6) OUTPUT
AS
BEGIN
    SELECT @value = MAX(last_value) FROM etl.watermark WHERE object_name = @object_name;
    SET @value = COALESCE(@value, CAST('1900-01-01' AS datetime2(6)));
END;

GO