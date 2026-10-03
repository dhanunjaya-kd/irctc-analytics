// Query name: PassengersFact   (passengers joined to their booking's month, class, route and lead bucket; aggregate BEFORE joining to capacity)
let
    Joined = Table.NestedJoin(Passengers, {"booking_id"}, Bookings, {"booking_id"}, "b", JoinKind.Inner),
    Expanded = Table.ExpandTableColumn(Joined, "b", {"train_id", "journey_date", "journey_month", "travel_class", "route_id", "lead_bucket"})
in
    Expanded
