// Query name: Bookings   (one row per booking; SYNTHETIC data)
// Adds journey_month, lead_days and lead_bucket. booking_status is the roll-up of passenger final statuses (Mixed = passengers differ).
let
    Source = fnLoadCsv("bookings.csv"),
    Typed = Table.TransformColumnTypes(Source, {{"booking_id", Int64.Type}, {"booking_reference", type text}, {"train_id", Int64.Type}, {"journey_date", type date},
        {"route_id", Int64.Type}, {"boarding_station_id", Int64.Type}, {"destination_station_id", Int64.Type}, {"travel_class", type text}, {"booking_ts", type datetime},
        {"num_passengers", Int64.Type}, {"booking_status", type text}, {"total_fare", type number}, {"data_origin", type text}}, "en-US"),
    WithMonth = Table.AddColumn(Typed, "journey_month", each Date.ToText([journey_date], "yyyy-MM"), type text),
    WithLead = Table.AddColumn(WithMonth, "lead_days", each Duration.Days([journey_date] - Date.From([booking_ts])), Int64.Type),
    WithBucket = Table.AddColumn(WithLead, "lead_bucket", each
        if [lead_days] <= 3 then "0-3 days" else if [lead_days] <= 14 then "4-14 days" else if [lead_days] <= 30 then "15-30 days"
        else if [lead_days] <= 60 then "31-60 days" else "61-120 days", type text)
in
    WithBucket
