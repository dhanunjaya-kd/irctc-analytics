// Query name: fnLoadCsv   (function). Loads one CSV from DataFolder with the first row as headers. Columns arrive as text and are typed by each query.
(FileName as text) as table =>
let
    Source = Csv.Document(File.Contents(DataFolder & FileName), [Delimiter = ",", Columns = null, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Promoted
