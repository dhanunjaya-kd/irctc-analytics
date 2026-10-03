// Query name: MonthlyKpis   (executive view: one row per journey month; same definitions as docs/KPI_definitions.md)
// Expected result on the cleaned data: 24 rows, total_bookings sums to 201,182 and total_passengers to 405,200 (see reports/kpi_reference_values.csv).
// Only 32 runs per month are simulated (768 of 19,708 scheduled runs), so compare months with the per-run and normalised columns, not raw totals.
let
    SafeSum = (l as list) as number => List.Sum(List.Combine({{0}, l})),
    BkG = Table.Group(Bookings, {"journey_month"}, {
        {"total_bookings", each Table.RowCount(_), Int64.Type},
        {"confirmed_bookings", each List.Count(List.Select([booking_status], each _ = "Confirmed")), Int64.Type},
        {"mixed_bookings", each List.Count(List.Select([booking_status], each _ = "Mixed")), Int64.Type},
        {"cancelled_bookings", each List.Count(List.Select([booking_status], each _ = "Cancelled")), Int64.Type},
        {"gross_value", each SafeSum([total_fare]), type number}}),
    PsG = Table.Group(PassengersFact, {"journey_month"}, {
        {"total_passengers", each Table.RowCount(_), Int64.Type}, {"cancelled_passengers", each SafeSum([is_cancelled]), Int64.Type},
        {"wl_demand", each SafeSum([is_initial_wl]), Int64.Type}, {"wl_cleared", each SafeSum([is_cleared_wl]), Int64.Type},
        {"wl_uncleared", each SafeSum([is_uncleared_wl]), Int64.Type}, {"booked_seats", each SafeSum([seat_equivalent]), type number}}),
    EvJoin = Table.ExpandTableColumn(Table.NestedJoin(Cancellations, {"booking_id"}, Bookings, {"booking_id"}, "b", JoinKind.Inner), "b", {"journey_month"}),
    EvG = Table.Group(EvJoin, {"journey_month"}, {
        {"refund_passenger", each SafeSum(Table.SelectRows(_, each [cancellation_type] = "Passenger")[refund_amount]), type number},
        {"refund_system", each SafeSum(Table.SelectRows(_, each [cancellation_type] = "System")[refund_amount]), type number},
        {"retained_charges", each SafeSum([cancellation_charge]), type number}}),
    CapG = Table.Group(SeatCapacity, {"journey_month"}, {{"class_runs", each Table.RowCount(_), Int64.Type}, {"seat_supply", each SafeSum([total_seats]), Int64.Type}}),
    OpsG = Table.Group(TrainOperations, {"journey_month"}, {
        {"simulated_runs", each Table.RowCount(_), Int64.Type},
        {"runs_with_delay", each List.Count(List.RemoveNulls([arrival_delay_min])), Int64.Type},
        {"on_time_runs", each List.Count(List.Select(List.RemoveNulls([arrival_delay_min]), each _ <= 15)), Int64.Type},
        {"delay_sum_pos", each SafeSum(List.Transform(List.RemoveNulls([arrival_delay_min]), each if _ > 0 then _ else 0)), type number}}),
    J1 = Table.ExpandTableColumn(Table.NestedJoin(BkG, {"journey_month"}, PsG, {"journey_month"}, "x", JoinKind.Inner), "x", List.RemoveItems(Table.ColumnNames(PsG), {"journey_month"})),
    J2 = Table.ExpandTableColumn(Table.NestedJoin(J1, {"journey_month"}, EvG, {"journey_month"}, "x", JoinKind.LeftOuter), "x", List.RemoveItems(Table.ColumnNames(EvG), {"journey_month"})),
    J3 = Table.ExpandTableColumn(Table.NestedJoin(J2, {"journey_month"}, CapG, {"journey_month"}, "x", JoinKind.Inner), "x", List.RemoveItems(Table.ColumnNames(CapG), {"journey_month"})),
    J4 = Table.ExpandTableColumn(Table.NestedJoin(J3, {"journey_month"}, OpsG, {"journey_month"}, "x", JoinKind.Inner), "x", List.RemoveItems(Table.ColumnNames(OpsG), {"journey_month"})),
    Sorted = Table.Sort(J4, {{"journey_month", Order.Ascending}}),
    Ratio = (n as nullable number, d as nullable number) as nullable number => if d = null or d = 0 then null else n / d,
    K1 = Table.AddColumn(Sorted, "passenger_cancellation_rate", each Ratio([cancelled_passengers], [total_passengers]), type nullable number),
    K2 = Table.AddColumn(K1, "booking_cancellation_rate", each Ratio([cancelled_bookings], [total_bookings]), type nullable number),
    K3 = Table.AddColumn(K2, "refund_total", each [refund_passenger] + [refund_system], type number),
    K4 = Table.AddColumn(K3, "net_value", each [gross_value] - [refund_total], type number),
    K5 = Table.AddColumn(K4, "wl_clearance_rate", each Ratio([wl_cleared], [wl_demand]), type nullable number),
    K6 = Table.AddColumn(K5, "occupancy", each Ratio([booked_seats], [seat_supply]), type nullable number),
    K7 = Table.AddColumn(K6, "waitlist_pressure", each Ratio([wl_uncleared], [seat_supply]), type nullable number),
    K8 = Table.AddColumn(K7, "bookings_per_run", each Ratio([total_bookings], [simulated_runs]), type nullable number),
    K9 = Table.AddColumn(K8, "otp", each Ratio([on_time_runs], [runs_with_delay]), type nullable number),
    K10 = Table.AddColumn(K9, "avg_delay", each Ratio([delay_sum_pos], [runs_with_delay]), type nullable number)
in
    K10
