# Excel Formula Library (Phase 3)

Every formula below is used in a workbook that was recalculated with LibreOffice 24.2 and reconciled with the Python reference (`python/src/kpi.py`), unless marked *not verified*. Ranges are shortened for readability. The table shows the main patterns; it is illustrative, not an exhaustive list of every function used (basic functions such as COUNT, COUNTA, IF, MAX, MID, LEFT, LEN and NOT are not itemised).

| Purpose | Formula pattern | Used in |
|---|---|---|
| Count with one condition | `=COUNTIF(Data_Passengers!I:I,"Cancelled")` | KPI_Calc |
| Count with several conditions | `=COUNTIFS(Data_Passengers!H:H,"Waitlisted",Data_Passengers!I:I,"Confirmed")` | KPI_Calc (waitlist cleared) |
| Conditional sum | `=SUMIFS(Data_Cancellations!K:K,Data_Cancellations!F:F,"System")` | Refunds by event type |
| Class filter with an "All" option | `=IF(C5="All","*",C5)` then `COUNTIFS(class_range,$C$6)` | Dashboard |
| Safe ratio (NULL when the denominator is 0) | `=IF(E7=0,"",I7/E7)` | Every rate |
| Ratio of sums for totals | totals row repeats the ratio formula on summed numerators and denominators (never AVERAGE of rates) | Monthly_Aggregates |
| Passenger-based cancellation rate | `=cancelled_passengers/total_passengers` | KPI 5 |
| Booking-based companion | `=cancelled_bookings/total_bookings` | KPI 5 companion |
| Waitlist clearance rate | `=(COUNTIFS(init,"Waitlisted",final,"Confirmed")+COUNTIFS(init,"Waitlisted",final,"RAC"))/COUNTIF(init,"Waitlisted")` | KPI 11 |
| Seat equivalents | `=IF(I2="Confirmed",1,IF(I2="RAC",Parameters!$B$2,0))` | Data_Passengers |
| Occupancy | `=(confirmed+RAC_weight*RAC)/total_seats` | Data_ClassRuns, Occupancy_Demand |
| Waitlist pressure (not occupancy) | `=uncleared_waitlist/total_seats` | Occupancy_Demand |
| Lead time in days | `=D2-INT(G2)` | Data_Bookings |
| Lead bucket lookup | `=LOOKUP(M2,Parameters!$A$10:$A$14,Parameters!$B$10:$B$14)` | Data_Bookings |
| Month text from a date | `=TEXT(D2,"yyyy-mm")` | Data_Bookings |
| Delay flags with missing values | `=IF(ISNUMBER(I2),IF(I2<=Parameters!$B$3,1,0),"")` | Data_Runs |
| On-time performance | `=SUM(on_time)/SUM(has_delay)` | KPI 12 |
| Count rows where two ranges disagree | `=SUMPRODUCT(--(range_a<>range_b))=0` | Validation checks |
| Month-on-month growth | `=D7/D6-1` | Monthly_Aggregates |
| Tolerance test | `=IF(ABS(B5-C5)<=E5,"PASS","FAIL")` | KPI_Calc |
| Expanding-range duplicate flag | `=IF(COUNTIF($A$2:A2,A2)>1,1,0)` | Cleaning exercises |
| Parse ISO and DD-MM-YYYY text dates | `MID`/`LEFT`/`RIGHT` with `VALUE`, then `DATE` | Cleaning exercises |
| Reject impossible dates | `=AND(MONTH(DATE(y,m,d))=m,DAY(DATE(y,m,d))=d)` | Cleaning exercises |
| Parse currency text | `=VALUE(SUBSTITUTE(SUBSTITUTE(UPPER(L2),"RS.",""),",",""))` wrapped in `IFERROR` | Cleaning exercises |
| Lookup without wildcards | `=IF(SUMPRODUCT(--(keys=LOWER(TRIM(x))))=0,"",INDEX(vals,SUMPRODUCT((keys=LOWER(TRIM(x)))*(ROW(keys)-1))))` | Status aliases (avoids `?` and `*` acting as wildcards in `MATCH`) |
| INDEX/MATCH join | `=INDEX(Work_Bookings!$M:$M,MATCH(B2,Work_Bookings!$A:$A,0))` | Cancellation vs booking time |
| Composite key | `=B2&"\|"&C2&"\|"&D2` | Capacity duplicates |

## Not used, and why

| Function | Reason |
|---|---|
| `XLOOKUP` | Returns `#NAME?` in LibreOffice 24.2, so it cannot be verified here. *Not verified.* Equivalent to the INDEX/MATCH pattern above; practise it in Excel 365 as an extension |
| `FILTER`, `UNIQUE`, `SORT`, `LET`, `LAMBDA` | Dynamic-array and LAMBDA functions are not available in the verification engine. The workbooks rely on classic functions that also work in Google Sheets |
