// Query name: OccupancyClassRuns   (focused dataset: one row per simulated train-class run; source = data\processed\derived\occupancy_class_runs.csv)
// Occupancy = (confirmed + RAC weight x RAC) / seats on final statuses; waitlisted passengers are NOT in occupancy (see waitlist_pressure).
let
    Source = Csv.Document(File.Contents(Text.Replace(DataFolder, "cleaned", "derived") & "occupancy_class_runs.csv"), [Delimiter = ",", Columns = null, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"run_class_key", type text}, {"travel_class", type text}, {"train_type", type text}, {"route_name", type text}, {"journey_month", type text},
        {"journey_date", type date}, {"total_seats", Int64.Type}, {"bookings", Int64.Type}, {"passengers", Int64.Type}, {"confirmed_pax", Int64.Type}, {"rac_pax", Int64.Type},
        {"wl_final_pax", Int64.Type}, {"cancelled_pax", Int64.Type}, {"initial_wl_pax", Int64.Type}}, "en-US"),
    Booked = Table.AddColumn(Typed, "booked_seats_calc", each [confirmed_pax] + RacWeight * [rac_pax], type number),
    Occ = Table.AddColumn(Booked, "occupancy_calc", each [booked_seats_calc] / [total_seats], type number),
    Band = Table.AddColumn(Occ, "occupancy_band", each if [occupancy_calc] < 0.5 then "Below 50%" else if [occupancy_calc] < 0.75 then "50% to below 75%" else if [occupancy_calc] < 0.95 then "75% to below 95%" else "95% and above", type text)
in
    Band
