// Query name: Passengers   (one row per passenger; status is tracked per passenger)
let
    Source = fnLoadCsv("booking_passengers.csv"),
    Typed = Table.TransformColumnTypes(Source, {{"passenger_id", Int64.Type}, {"booking_id", Int64.Type}, {"passenger_seq", Int64.Type}, {"age_band", type text},
        {"fare_amount", type number}, {"initial_status", type text}, {"final_status", type text}, {"cancellation_id", Int64.Type}, {"data_origin", type text}}, "en-US"),
    Flags = Table.AddColumn(Typed, "passengers", each 1, Int64.Type),
    Cancelled = Table.AddColumn(Flags, "is_cancelled", each if [final_status] = "Cancelled" then 1 else 0, Int64.Type),
    InitialWL = Table.AddColumn(Cancelled, "is_initial_wl", each if [initial_status] = "Waitlisted" then 1 else 0, Int64.Type),
    ClearedWL = Table.AddColumn(InitialWL, "is_cleared_wl", each if [initial_status] = "Waitlisted" and ([final_status] = "Confirmed" or [final_status] = "RAC") then 1 else 0, Int64.Type),
    UnclearedWL = Table.AddColumn(ClearedWL, "is_uncleared_wl", each if [final_status] = "Waitlisted" then 1 else 0, Int64.Type),
    SeatEq = Table.AddColumn(UnclearedWL, "seat_equivalent", each if [final_status] = "Confirmed" then 1 else if [final_status] = "RAC" then RacWeight else 0, type number)
in
    SeatEq
