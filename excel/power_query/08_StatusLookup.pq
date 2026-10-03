// Query name: StatusLookup   (alias -> canonical status; the same lookup the Python cleaner uses; variants are compared trimmed and in lower case)
let
    Rows = {{"cnf", "Confirmed"}, {"conf", "Confirmed"}, {"confirmed", "Confirmed"}, {"rac", "RAC"}, {"wl", "Waitlisted"}, {"waitlist", "Waitlisted"}, {"waitlisted", "Waitlisted"},
            {"wait-listed", "Waitlisted"}, {"can", "Cancelled"}, {"canceled", "Cancelled"}, {"cancelled", "Cancelled"}, {"mixed", "Mixed"}},
    T = #table(type table [variant = text, status = text], Rows)
in
    T
