CREATE SECURITY POLICY [sec].[policy_gifts]
    ADD FILTER PREDICATE [sec].[fn_gift_access]([is_anonymous]) ON [fact].[gifts]
    WITH (STATE = ON);


GO