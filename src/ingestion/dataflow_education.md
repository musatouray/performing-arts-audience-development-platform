# Dataflow Gen2: df_education_sharepoint (SharePoint → lh_bronze)

Reads the education team's Excel workbooks from SharePoint and writes three Bronze tables. The team keeps working in Excel the way they always have; the Dataflow does the clean-up in Power Query, which the education analyst can read and change.

## Before you start

Upload `data/education_sharepoint/` to a SharePoint document library, keeping the layout:

```
Documents/
  Education/
    Program Reference.xlsx        sheets: Programs, Schools
    Sessions/
      Sessions 2023-09.xlsx       one workbook per month, sheet: Sessions
      ...
```

After each incremental generator run, upload the changed month's workbook again (replace the file).

## Build it

1. `hh-dataplatform-dev` › **New item › Dataflow Gen2**. Name it `df_education_sharepoint`. Keep **Git integration** ticked so it's saved with the workspace.
2. **Home › Manage parameters › New:** `SiteUrl` (Text) = your site, for example `https://contoso.sharepoint.com/sites/Education`.
3. **Get data › Blank query**, then **Advanced editor**, and paste each query below. Name each query as shown.
4. Right-click `EducationFiles` and untick **Enable staging**. It's a helper and isn't written anywhere.
5. For `programs`, `schools` and `enrollments`: **Add data destination › Lakehouse** › `lh_bronze`, table with the same name (it lands in schema `dbo`). Set the update method to **Replace**.
   - Dataflow Gen2 doesn't offer a schema choice for a lakehouse destination yet, so the tables land in `dbo`. `config/sources.yaml` already says `bronze_schema: dbo` for education, so Silver knows where to look.
6. **Save & run.** The first run asks you to sign in to SharePoint. Use the account that owns the site.

### EducationFiles (helper)

```powerquery
let
    Files = SharePoint.Files(SiteUrl, [ApiVersion = 15]),
    Education = Table.SelectRows(Files, each Text.Contains([Folder Path], "/Education/") and [Extension] = ".xlsx")
in
    Education
```

### programs

```powerquery
let
    Workbook = Table.SelectRows(EducationFiles, each [Name] = "Program Reference.xlsx"){0}[Content],
    Sheet = Excel.Workbook(Workbook, true){[Item = "Programs", Kind = "Sheet"]}[Data],
    Renamed = Table.RenameColumns(Sheet, {
        {"Program ID", "program_id"}, {"Program Name", "program_name"},
        {"Program Type", "program_type"}, {"Audience", "audience"}}),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"program_id", type text}, {"program_name", type text}, {"program_type", type text}, {"audience", type text}}),
    Stamped = Table.AddColumn(Typed, "_ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Stamped
```

### schools

```powerquery
let
    Workbook = Table.SelectRows(EducationFiles, each [Name] = "Program Reference.xlsx"){0}[Content],
    Sheet = Excel.Workbook(Workbook, true){[Item = "Schools", Kind = "Sheet"]}[Data],
    Renamed = Table.RenameColumns(Sheet, {
        {"School ID", "school_id"}, {"School Name", "school_name"}, {"Borough", "borough"}, {"Title I", "is_title_i"}}),
    // The sheet says Yes or No; Bronze stores true or false.
    TitleI = Table.TransformColumns(Renamed, {{"is_title_i", each _ = "Yes", type logical}}),
    Typed = Table.TransformColumnTypes(TitleI, {
        {"school_id", type text}, {"school_name", type text}, {"borough", type text}}),
    Stamped = Table.AddColumn(Typed, "_ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Stamped
```

### enrollments

```powerquery
let
    Months = Table.SelectRows(EducationFiles, each Text.Contains([Folder Path], "/Sessions/")),
    WithData = Table.AddColumn(Months, "Data", each Excel.Workbook([Content], true){[Item = "Sessions", Kind = "Sheet"]}[Data]),
    Kept = Table.SelectColumns(WithData, {"Name", "Data"}),
    Expanded = Table.ExpandTableColumn(Kept, "Data",
        {"Enrollment ID", "Program ID", "School ID", "Session Date", "Participants", "Teaching Artist Hours"},
        {"enrollment_id", "program_id", "school_id", "session_date", "participants", "teaching_artist_hours"}),
    // People leave empty rows at the bottom of spreadsheets.
    NoBlanks = Table.SelectRows(Expanded, each [enrollment_id] <> null),
    Typed = Table.TransformColumnTypes(NoBlanks, {
        {"enrollment_id", type text}, {"program_id", type text}, {"school_id", type text},
        {"session_date", type date}, {"participants", Int64.Type}, {"teaching_artist_hours", type number}}),
    Renamed = Table.RenameColumns(Typed, {{"Name", "_source_file"}}),
    Stamped = Table.AddColumn(Renamed, "_ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Stamped
```

## Check it

- `lh_bronze` › Tables › `dbo` has `programs` (10 rows), `schools` (150) and `enrollments` (about 3,000).
- Run `nb_20_silver_transform`: the education tables reach Silver, and sessions with 0 participants end up in `dq.quarantine`.

## Why these choices

| Choice | Why |
|---|---|
| Dataflow Gen2, not a notebook | A few thousand rows, and the rules (renames, Yes/No) belong to the business. A notebook would make IT the bottleneck for a spreadsheet. |
| **Replace** each run | The whole source is a few thousand rows, so reloading it is cheap and always correct. Silver only writes rows whose content changed. |
| One workbook per month | Keeps each file small and matches how the team works. The Dataflow combines them, so a new month needs no change. |
| `_source_file` column | When a number looks wrong, you can tell the team which workbook it came from. |
