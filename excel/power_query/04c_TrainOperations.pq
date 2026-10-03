// Query name: TrainOperations   (one row per simulated train run; delays are SIMULATED; arrival_delay_min may be null = missing, never imputed)
let
    Source = fnLoadCsv("train_operations.csv"),
    Typed = Table.TransformColumnTypes(Source, {{"operation_id", Int64.Type}, {"train_id", Int64.Type}, {"run_date", type date}, {"departure_delay_min", Int64.Type},
        {"arrival_delay_min", Int64.Type}, {"data_origin", type text}}, "en-US"),
    WithMonth = Table.AddColumn(Typed, "journey_month", each Date.ToText([run_date], "yyyy-MM"), type text)
in
    WithMonth
