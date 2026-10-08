CREATE TABLE [fact].[education_sessions] (
    [enrollment_id]         VARCHAR (20)   NOT NULL,
    [program_key]           INT            NOT NULL,
    [school_key]            INT            NOT NULL,
    [session_date_key]      INT            NOT NULL,
    [participants]          INT            NOT NULL,
    [teaching_artist_hours] DECIMAL (6, 1) NULL,
    [loaded_at]             DATETIME2 (6)  NOT NULL
);


GO