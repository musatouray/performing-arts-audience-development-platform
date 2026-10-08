CREATE   PROCEDURE etl.usp_set_watermark @object_name varchar(128), @value datetime2(6)
AS
BEGIN
    DELETE FROM etl.watermark WHERE object_name = @object_name;
    INSERT INTO etl.watermark VALUES (@object_name, @value, SYSUTCDATETIME());
END;

GO