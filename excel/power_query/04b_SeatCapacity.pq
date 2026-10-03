// Query name: SeatCapacity   (one row per simulated train-class run; capacity is SIMULATED)
let
    Source = fnLoadCsv("seat_capacity.csv"),
    Typed = Table.TransformColumnTypes(Source, {{"capacity_id", Int64.Type}, {"train_id", Int64.Type}, {"journey_date", type date}, {"travel_class", type text},
        {"coaches_attached", Int64.Type}, {"seats_per_coach", Int64.Type}, {"total_seats", Int64.Type}, {"rac_berths", Int64.Type}, {"wl_limit", Int64.Type}, {"data_origin", type text}}, "en-US"),
    WithMonth = Table.AddColumn(Typed, "journey_month", each Date.ToText([journey_date], "yyyy-MM"), type text)
in
    WithMonth
