[DefaultOutputDestinationSettings = [DestinationDefinition = [Kind = "Reference", QueryName = "DefaultDestination", IsNewTarget = true], UpdateMethod = [Kind = "Replace"], DestinationTypeSettings = [Kind = "Table"]], StagingDefinition = [Kind = "FastCopy"]]
section Section1;
shared SiteUrl = "https://amigomusa.sharepoint.com/sites/HarmoniaHallEducationPrograms" meta [IsParameterQuery = true, IsParameterQueryRequired = false, Type = type text];
shared FolderPath = "Shared%20Documents/Education/Sessions" meta [IsParameterQuery = true, IsParameterQueryRequired = false, Type = type text];
[BindToDefaultDestination = true]
shared enrollments = let
  // Get all files from the site
  Source = SharePoint.Files(SiteUrl, [ApiVersion = 15]),

  // Normalize folder path (decode %20, ensure leading and trailing slash)
  NormalizedFolderPath = Text.Replace(FolderPath, "%20", " "),

  // Filter to target folder and only .xlsx files (apply to the table 'Source')
  FilesInFolder = Table.SelectRows(
    Source,
    each Text.Contains([Folder Path], NormalizedFolderPath) and Text.Lower([Extension]) = ".xlsx"
  ),

  // Keep only the columns we need
  FilesReduced = Table.SelectColumns(FilesInFolder, {"Content", "Name", "Folder Path", "Date modified"}),

  // Buffer the file list
  FilesBuffered = Table.Buffer(FilesReduced),

  // Parse each workbook
  WithWorkbooks = Table.AddColumn(
    FilesBuffered,
    "Workbook",
    each Excel.Workbook(Binary.Buffer([Content]), true),
    type table
  ),

  // Expand workbook sheets
  ExpandedSheets = Table.ExpandTableColumn(WithWorkbooks, "Workbook", {"Name", "Data"}, {"WorkSheetName", "Data"}),

  // Add source file name into each sheet table
  DataWithSource = Table.AddColumn(
    ExpandedSheets,
    "DataWithSource",
    each Table.AddColumn([Data], "source_file", (r) => [Name]),
    type table
  ),

  // Combine all sheet tables
  Combined = Table.Combine(DataWithSource[DataWithSource]),

  // Filter out empty enrollment rows
  FilteredRows = Table.SelectRows(Combined, each ([Enrollment ID] <> null and Text.Trim(Text.From([Enrollment ID])) <> "")),

  // Rename and type conversions
  Renamed = Table.RenameColumns(
    FilteredRows,
    {
      {"Enrollment ID", "enrollment_id"},
      {"Program ID", "program_id"},
      {"School ID", "school_id"},
      {"Session Date", "session_date"},
      {"Participants", "participants"},
      {"Teaching Artist Hours", "teaching_artist_hours"}
    },
    MissingField.Ignore
  ),

  ChangedTypes = Table.TransformColumnTypes(Renamed, {{"session_date", type date}, {"participants", Int64.Type}, {"source_file", type text}}, "en-US"),
  ingestedAt = Table.AddColumn(ChangedTypes, "_ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
  ingestedAt;
[BindToDefaultDestination = true]
shared programs = let
  // Load SharePoint contents
  Source = SharePoint.Contents(SiteUrl, [ApiVersion = 15]),
  Navigation = Source{[Name = "Shared Documents"]}[Content],
  #"Navigation 1" = Navigation{[Name = "Education"]}[Content],
  #"Navigation 2" = #"Navigation 1"{[Name = "Program Reference.xlsx"]}[Content],
  #"Imported Excel workbook" = Excel.Workbook(#"Navigation 2", true, true),
  #"Navigation 3" = #"Imported Excel workbook"{[Item = "Programs", Kind = "Sheet"]}[Data],
  Renamed = Table.RenameColumns(#"Navigation 3", {{"Program ID", "program_id"}, {"Program Name", "program_name"}, {"Program Type", "program_type"}, {"Audience", "audience"}}),
  Typed = Table.TransformColumnTypes(Renamed, {{"program_id", type text}, {"program_name", type text}, {"program_type", type text}, {"audience", type text}}),
  #"Current date and time" = Table.AddColumn(Typed, "_ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)

  
in
  #"Current date and time";
[BindToDefaultDestination = true]
shared schools = let
  // Load SharePoint contents
  Source = SharePoint.Contents(SiteUrl, [ApiVersion = 15]),
  Navigation = Source{[Name = "Shared Documents"]}[Content],
  #"Navigation 1" = Navigation{[Name = "Education"]}[Content],
  #"Navigation 2" = #"Navigation 1"{[Name = "Program Reference.xlsx"]}[Content],
  #"Imported Excel workbook" = Excel.Workbook(#"Navigation 2", true, true),
  #"Navigation 3" = #"Imported Excel workbook"{[Item = "Schools", Kind = "Sheet"]}[Data],
  Renamed = Table.RenameColumns(#"Navigation 3", {{"School ID", "school_id"}, {"School Name", "school_name"}, {"Borough", "borough"}, {"Title I", "is_title_i"}}),
  TitleI = Table.TransformColumns(Renamed, {{"is_title_i", each _ = "Yes", type logical}}),
  Typed = Table.TransformColumnTypes(TitleI, {
        {"school_id", type text}, {"school_name", type text}, {"borough", type text}}),
  Stamped = Table.AddColumn(Typed, "_ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Stamped;
shared DefaultDestination = Lakehouse.Contents([EnableFolding = false]){[workspaceId = "9f9f5fa0-6a89-4f39-987e-240311772371"]}[Data]{[lakehouseId = "e4b5b873-13f4-4335-827c-bf8d757c7554"]}[Data];
