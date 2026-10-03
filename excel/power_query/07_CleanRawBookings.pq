// Query name: CleanRawBookingsPreview   (reads the RAW extract; the raw file is never modified)
// Demonstrates the row-level cleaning steps in Power Query: remove exact duplicates, trim and upper-case station codes, parse ISO and DD-MM-YYYY dates,
// parse currency text, and map status aliases. Rejecting unrecoverable booking families and recomputing totals from passengers are done in the Python cleaner
// (python/src/clean_data.py) and practised in the Excel exercises workbook. Not executed in the build environment: see excel/SETUP_INSTRUCTIONS.md.
let
    Source = Csv.Document(File.Contents(RawFolder & "bookings.csv"), [Delimiter = ",", Columns = 13, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    AllText = Table.TransformColumnTypes(Promoted, List.Transform(Table.ColumnNames(Promoted), each {_, type text})),
    NoDuplicates = Table.Distinct(AllText),
    Stations = Table.TransformColumns(NoDuplicates, {{"boarding_station_code", each Text.Upper(Text.Trim(_)), type text}, {"destination_station_code", each Text.Upper(Text.Trim(_)), type text}}),
    ParseDate = (t as nullable text) as nullable date =>
        let s = Text.Trim(if t = null then "" else t),
            iso = try Date.FromText(s, [Format = "yyyy-MM-dd", Culture = "en-US"]) otherwise null,
            dmy = try Date.FromText(s, [Format = "dd-MM-yyyy", Culture = "en-US"]) otherwise null
        in if iso <> null then iso else dmy,
    ParseFare = (t as nullable text) as nullable number =>
        let s = Text.Remove(Text.Replace(Text.Upper(Text.Trim(if t = null then "" else t)), "RS.", ""), {"₹", ",", " "})
        in try Number.FromText(s, "en-US") otherwise null,
    MapStatus = (t as nullable text) as nullable text =>
        let k = Text.Lower(Text.Trim(if t = null then "" else t)), m = Table.SelectRows(StatusLookup, each [variant] = k)
        in if Table.IsEmpty(m) then null else m{0}[status],
    WithDate = Table.AddColumn(Stations, "journey_date_clean", each ParseDate([journey_date]), type nullable date),
    WithFare = Table.AddColumn(WithDate, "total_fare_parsed", each ParseFare([total_fare]), type nullable number),
    WithStatus = Table.AddColumn(WithFare, "booking_status_clean", each MapStatus([booking_status]), type nullable text),
    FlagDate = Table.AddColumn(WithStatus, "issue_journey_date", each if [journey_date_clean] = null then "impossible or unreadable" else if Text.Length(Text.Trim([journey_date])) = 10 and Text.At(Text.Trim([journey_date]), 2) = "-" then "DD-MM-YYYY fixed" else null, type nullable text),
    FlagFare = Table.AddColumn(FlagDate, "issue_total_fare", each if Text.Trim([total_fare]) = "" then "missing" else if [total_fare_parsed] = null then "unreadable" else if [total_fare_parsed] <= 0 then "not positive" else null, type nullable text),
    FlagStatus = Table.AddColumn(FlagFare, "issue_status", each if [booking_status_clean] = null then "invalid" else if [booking_status_clean] <> [booking_status] then "alias mapped" else null, type nullable text)
in
    FlagStatus
