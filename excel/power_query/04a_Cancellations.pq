// Query name: Cancellations   (one row per refund EVENT: Passenger cancellation or System auto-refund of an uncleared waitlist)
let
    Source = fnLoadCsv("cancellations.csv"),
    Typed = Table.TransformColumnTypes(Source, {{"cancellation_id", Int64.Type}, {"booking_id", Int64.Type}, {"cancellation_ts", type datetime}, {"cancellation_type", type text},
        {"status_at_cancellation", type text}, {"cancelled_passengers", Int64.Type}, {"original_fare_amount", type number}, {"cancellation_charge", type number},
        {"refund_amount", type number}, {"data_origin", type text}}, "en-US")
in
    Typed
