"""Shared catalogue of the controlled data-quality issues.

Used by the injector (inject_quality_issues.py), the cleaner (clean_data.py) and the report writer so that the
issue names, cleaning rules and outcomes are defined exactly once.

outcome:  corrected = record kept, value repaired by a documented rule
          retained  = record kept, value left NULL / 'Unknown' (repairing it would mean inventing data)
          rejected  = record removed (duplicate copy, orphan, or unrecoverable booking family)
family:   True when a rejection removes the whole booking family (booking + passengers + cancellation events)
"""

CATALOG = {
    # ---- duplicates
    "dup_booking_rows": dict(table="bookings", title="Duplicate booking rows", outcome="rejected", family=False,
        issue="Exact re-ingested copies of a booking row (same booking_id)",
        rule="Keep the first occurrence per booking_id; remove the extra copies"),
    "dup_passenger_rows": dict(table="booking_passengers", title="Duplicate passenger rows", outcome="rejected", family=False,
        issue="Exact re-ingested copies of a passenger row (same passenger_id)",
        rule="Keep the first occurrence per passenger_id; remove the extra copies"),
    "dup_cancellation_rows": dict(table="cancellations", title="Duplicate cancellation rows", outcome="rejected", family=False,
        issue="Exact re-ingested copies of a cancellation event (same cancellation_id)",
        rule="Keep the first occurrence per cancellation_id; remove the extra copies"),
    # ---- missing / invalid values
    "missing_total_fare": dict(table="bookings", title="Missing booking total fare", outcome="corrected", family=False,
        issue="total_fare is blank",
        rule="Recompute as SUM(passenger fare_amount) for the booking (BR-03)"),
    "total_fare_currency_format": dict(table="bookings", title="Fare stored with currency symbol", outcome="corrected", family=False,
        issue="total_fare stored as text such as '\u20b91,250.00' or 'Rs. 1250'",
        rule="Strip symbols and separators, parse, and verify it equals the passenger fare sum"),
    "total_fare_invalid": dict(table="bookings", title="Invalid booking total fare", outcome="corrected", family=False,
        issue="total_fare is negative, zero, non-numeric or does not equal the passenger fare sum",
        rule="Replace with SUM(passenger fare_amount) when all passenger fares are valid"),
    "negative_passenger_fare": dict(table="booking_passengers", title="Invalid passenger fare", outcome="corrected", family=False,
        issue="A passenger fare_amount is negative or non-numeric",
        rule="Reconstruct as booking total_fare minus the other passengers' fares; accept only if positive"),
    "missing_route_id": dict(table="bookings", title="Missing route reference", outcome="corrected", family=False,
        issue="route_id is blank",
        rule="Derive from trains.route_id for the booking's train"),
    "num_passengers_invalid": dict(table="bookings", title="Invalid passenger count", outcome="corrected", family=False,
        issue="num_passengers blank, non-numeric, or different from the number of passenger rows",
        rule="Set to the number of passenger rows for the booking (BR-03)"),
    "missing_age_band": dict(table="booking_passengers", title="Missing age band", outcome="retained", family=False,
        issue="age_band is blank",
        rule="Set to 'Unknown'; no age is imputed. Age band is not used by any KPI"),
    # ---- station identifiers
    "station_code_format": dict(table="bookings", title="Inconsistent station code format", outcome="corrected", family=False,
        issue="boarding/destination station code in lower case or padded with spaces",
        rule="Trim, upper-case, and map to station_id"),
    "station_code_unknown": dict(table="bookings", title="Unknown station code", outcome="corrected", family=False,
        issue="station code not present in the station master (e.g. 'XXX', '000', 'N/A')",
        rule="Derive boarding/destination station from the booking's route (BR-06)"),
    # ---- dates
    "missing_booking_ts": dict(table="bookings", title="Missing booking timestamp", outcome="rejected", family=True,
        issue="booking_ts is blank",
        rule="Cannot be recovered without inventing a value; reject the booking family"),
    "journey_date_format": dict(table="bookings", title="Journey date in DD-MM-YYYY format", outcome="corrected", family=False,
        issue="journey_date written as DD-MM-YYYY instead of ISO YYYY-MM-DD",
        rule="Parse the unambiguous DD-MM-YYYY pattern and store as ISO date"),
    "journey_date_impossible": dict(table="bookings", title="Impossible journey date", outcome="rejected", family=True,
        issue="journey_date is not a real calendar date (e.g. 30 February, month 13)",
        rule="Cannot be recovered; reject the booking family"),
    "booking_after_journey": dict(table="bookings", title="Booking after journey date", outcome="rejected", family=True,
        issue="booking_ts is later than the journey date",
        rule="Booking must precede travel (BR-04); the true value is unknown, so reject the booking family"),
    "cancellation_before_booking": dict(table="cancellations", title="Cancellation before booking", outcome="rejected", family=True,
        issue="cancellation_ts is earlier than the booking timestamp",
        rule="Violates BR-12; the true value is unknown, so reject the booking family"),
    # ---- statuses
    "booking_status_alias": dict(table="bookings", title="Booking status alias", outcome="corrected", family=False,
        issue="booking_status written as an alias (CNF, WL, CAN, 'confirmed ' ...)",
        rule="Map the alias to the canonical status; verified against the passenger roll-up (BR-02)"),
    "booking_status_invalid": dict(table="bookings", title="Invalid booking status", outcome="corrected", family=False,
        issue="booking_status blank or unrecognised (UNKNOWN, ?, TBD ...)",
        rule="Recompute from the passengers' final_status roll-up (BR-02)"),
    "passenger_status_alias": dict(table="booking_passengers", title="Passenger status alias", outcome="corrected", family=False,
        issue="initial_status or final_status written as an alias",
        rule="Map the alias to the canonical status"),
    "passenger_final_status_invalid": dict(table="booking_passengers", title="Invalid passenger final status", outcome="corrected", family=False,
        issue="final_status unrecognised",
        rule="Derive from the linked cancellation event: Passenger event -> Cancelled, System event -> Waitlisted (BR-10)"),
    "passenger_initial_status_invalid": dict(table="booking_passengers", title="Invalid passenger initial status", outcome="rejected", family=True,
        issue="initial_status unrecognised",
        rule="The status at booking time cannot be derived; reject the booking family"),
    # ---- referential integrity
    "orphan_cancellation_rows": dict(table="cancellations", title="Cancellation without a valid booking", outcome="rejected", family=False,
        issue="cancellation row whose booking_id does not exist in bookings",
        rule="Reject the cancellation row (no valid booking reference)"),
    "orphan_passenger_rows": dict(table="booking_passengers", title="Passenger without a valid booking", outcome="rejected", family=False,
        issue="passenger row whose booking_id does not exist in bookings",
        rule="Reject the passenger row"),
    "refund_exceeds_fare": dict(table="cancellations", title="Refund exceeds original fare", outcome="corrected", family=False,
        issue="refund_amount is greater than original_fare_amount",
        rule="Recompute refund_amount = original_fare_amount - cancellation_charge (BR-11)"),
    # ---- capacity
    "capacity_total_mismatch": dict(table="seat_capacity", title="Capacity total inconsistent", outcome="corrected", family=False,
        issue="total_seats does not equal coaches_attached x seats_per_coach",
        rule="Set total_seats = coaches_attached x seats_per_coach (BR-09)"),
    "capacity_seats_per_coach_invalid": dict(table="seat_capacity", title="Seats per coach off class standard", outcome="corrected", family=False,
        issue="seats_per_coach differs from the standard for the travel class",
        rule="Restore the class-standard seats_per_coach (total_seats already equals coaches x standard)"),
    "capacity_conflicting_duplicate": dict(table="seat_capacity", title="Conflicting duplicate capacity record", outcome="rejected", family=False,
        issue="second capacity row for the same train, date and class with different, inconsistent values",
        rule="Keep the internally consistent row; reject the inconsistent one"),
    # ---- operations
    "missing_arrival_delay": dict(table="train_operations", title="Missing arrival delay", outcome="retained", family=False,
        issue="arrival_delay_min is blank",
        rule="Retain the run with NULL delay; excluded from delay KPIs, never imputed"),
    "delay_out_of_range": dict(table="train_operations", title="Arrival delay out of range", outcome="retained", family=False,
        issue="arrival_delay_min outside the sanity range -60..1440 minutes",
        rule="Set to NULL and retain the run; excluded from delay KPIs"),
}

# Status aliases: variant (after strip + lower-case) -> canonical status. Used by the cleaner; the injector draws from
# the VARIANTS lists so every injected alias is a documented, mappable value.
CANONICAL_STATUS = ["Confirmed", "RAC", "Waitlisted", "Cancelled"]
STATUS_VARIANTS = {
    "Confirmed": ["CNF", "cnf", "Conf", "confirmed", "CONFIRMED "],
    "RAC": ["rac", "RAC ", "Rac"],
    "Waitlisted": ["WL", "wl", "Waitlist", "waitlisted", "Wait-listed"],
    "Cancelled": ["CAN", "Canceled", "cancelled", "CANCELLED "],
    "Mixed": ["MIXED", "mixed"],
}
STATUS_LOOKUP = {}
for canon, variants in STATUS_VARIANTS.items():
    STATUS_LOOKUP[canon.lower()] = canon
    for v in variants:
        STATUS_LOOKUP[v.strip().lower()] = canon
STATUS_GARBAGE = ["UNKNOWN", "?", "TBD", "N/A", "##", ""]     # not mappable
PASSENGER_STATUS_GARBAGE = ["??", "UNKNOWN", "#N/A", "TBD"]

# station-code garbage used by the injector
UNKNOWN_STATION_CODES = ["XXX", "000", "N/A", "UNK"]

ORDER = list(CATALOG.keys())
