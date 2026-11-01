# Phase 5: Exploratory data analysis summary

> **Synthetic data, sampled simulation.** 768 simulated train runs (32 per month) compared with 19,708 scheduled runs in the modelled schedule (3.9%). These results describe this dataset only: they are not IRCTC or Indian Railways network-wide figures, and nothing here is a forecast. Months are compared with per-run and capacity-normalised measures because raw monthly totals reflect the sampling design. Associations are not causes.

**Dataset analysed (full cleaned data):** 201,182 bookings, 405,200 passengers, 30,562 bookings with a cancellation, 2,285 simulated train-class runs, 768 simulated runs, 24 months (2024-09 to 2026-08).

## A. Booking demand

### Monthly demand (per simulated run)

| journey_month | total_bookings | total_passengers | simulated_runs | bookings_per_run | passengers_per_run | bookings_growth | bookings_per_run_growth |
|---|---|---|---|---|---|---|---|
| 2024-09 | 5,944 | 12,159 | 32 | 185.8 | 380.0 |  |  |
| 2024-10 | 7,727 | 15,448 | 32 | 241.5 | 482.8 | 30.0% | 30.0% |
| 2024-11 | 7,934 | 16,023 | 32 | 247.9 | 500.7 | 2.7% | 2.7% |
| 2024-12 | 7,457 | 14,941 | 32 | 233.0 | 466.9 | -6.0% | -6.0% |
| 2025-01 | 7,939 | 16,225 | 32 | 248.1 | 507.0 | 6.5% | 6.5% |
| 2025-02 | 7,165 | 14,255 | 32 | 223.9 | 445.5 | -9.7% | -9.7% |
| 2025-03 | 9,243 | 18,628 | 32 | 288.8 | 582.1 | 29.0% | 29.0% |
| 2025-04 | 9,150 | 18,515 | 32 | 285.9 | 578.6 | -1.0% | -1.0% |
| 2025-05 | 10,856 | 21,782 | 32 | 339.2 | 680.7 | 18.6% | 18.6% |
| 2025-06 | 8,073 | 16,270 | 32 | 252.3 | 508.4 | -25.6% | -25.6% |
| 2025-07 | 7,382 | 15,103 | 32 | 230.7 | 472.0 | -8.6% | -8.6% |
| 2025-08 | 7,166 | 14,583 | 32 | 223.9 | 455.7 | -2.9% | -2.9% |
| 2025-09 | 7,510 | 15,173 | 32 | 234.7 | 474.2 | 4.8% | 4.8% |
| 2025-10 | 8,400 | 16,925 | 32 | 262.5 | 528.9 | 11.9% | 11.9% |
| 2025-11 | 8,177 | 16,554 | 32 | 255.5 | 517.3 | -2.7% | -2.7% |
| 2025-12 | 8,636 | 17,321 | 32 | 269.9 | 541.3 | 5.6% | 5.6% |
| 2026-01 | 8,149 | 16,292 | 32 | 254.7 | 509.1 | -5.6% | -5.6% |
| 2026-02 | 8,288 | 16,768 | 32 | 259.0 | 524.0 | 1.7% | 1.7% |
| 2026-03 | 9,361 | 18,669 | 32 | 292.5 | 583.4 | 12.9% | 12.9% |
| 2026-04 | 9,986 | 20,130 | 32 | 312.1 | 629.1 | 6.7% | 6.7% |
| 2026-05 | 11,501 | 23,001 | 32 | 359.4 | 718.8 | 15.2% | 15.2% |
| 2026-06 | 8,963 | 17,914 | 32 | 280.1 | 559.8 | -22.1% | -22.1% |
| 2026-07 | 7,932 | 15,908 | 32 | 247.9 | 497.1 | -11.5% | -11.5% |
| 2026-08 | 8,243 | 16,613 | 32 | 257.6 | 519.2 | 3.9% | 3.9% |

**Observed:** bookings per simulated run range from 185.8 (2024-09) to 359.4 (2026-05). Raw monthly totals are shown only for completeness: with a fixed 32 runs per month they mostly reflect which trains were sampled.

### Weekday and weekend

| weekday | runs | bookings_per_run | passengers_per_run | occupancy |
|---|---|---|---|---|
| Monday | 158 | 278.7 | 557.3 | 0.757 |
| Tuesday | 137 | 222.8 | 452.5 | 0.653 |
| Wednesday | 134 | 260.6 | 525.8 | 0.687 |
| Thursday | 63 | 274.7 | 553.7 | 0.772 |
| Friday | 96 | 310.6 | 623.6 | 0.845 |
| Saturday | 97 | 233.5 | 471.4 | 0.698 |
| Sunday | 83 | 264.1 | 532.8 | 0.805 |

| day_type | runs | passengers_per_run | occupancy |
|---|---|---|---|
| Weekday (Mon-Fri) | 588 | 536.1 | 0.732 |
| Weekend (Sat-Sun) | 180 | 499.7 | 0.746 |

**Observed:** weekend-day runs average 499.7 passengers per run against 536.1 on weekdays (occupancy 74.6% vs 73.2%); see test S-01 for whether the gap is distinguishable from zero.

### Status mix

| booking_status | bookings | share |
|---|---|---|
| Confirmed | 146,020 | 72.6% |
| RAC | 11,169 | 5.6% |
| Waitlisted | 12,749 | 6.3% |
| Cancelled | 26,619 | 13.2% |
| Mixed | 4,625 | 2.3% |

| status | initial | final | initial_share | final_share |
|---|---|---|---|---|
| Confirmed | 340,054 | 301,671 | 83.9% | 74.4% |
| RAC | 28,270 | 23,349 | 7.0% | 5.8% |
| Waitlisted | 36,876 | 24,200 | 9.1% | 6.0% |
| Cancelled | 0 | 55,980 | 0.0% | 13.8% |

**Observed:** 72.6% of bookings finished fully Confirmed, 13.2% fully Cancelled and 2.3% Mixed. By passenger, 74.4% finished Confirmed, 5.8% RAC, 6.0% Waitlisted and 13.8% Cancelled; 9.1% were waitlisted when booking.

## B. Passenger behaviour

### Cancellation, waitlist and RAC by class (passenger-based)

| travel_class | passengers | cancellation_rate | cancel_ci_low | cancel_ci_high | initial_wl_share | wl_clearance_rate | uncleared_share_of_wl_demand |
|---|---|---|---|---|---|---|---|
| 1A | 641 | 8.1% | 6.2% | 10.5% | 5.1% | 18.2% | 78.8% |
| 2A | 23,137 | 10.7% | 10.3% | 11.1% | 6.7% | 12.8% | 74.8% |
| 3A | 122,748 | 12.9% | 12.7% | 13.1% | 9.7% | 19.8% | 67.0% |
| SL | 154,096 | 14.6% | 14.4% | 14.8% | 9.6% | 20.4% | 63.4% |
| CC | 4,239 | 12.5% | 11.5% | 13.5% | 1.0% | 25.6% | 53.5% |
| 2S | 100,339 | 14.5% | 14.3% | 14.7% | 8.4% | 17.6% | 65.8% |

**Observed:** the passenger cancellation rate is 13.8% overall, from 8.1% (1A) to 14.6% (SL). Of 36,876 passengers waitlisted at booking, 19.2% cleared to Confirmed or RAC and 24,200 were refunded by the System as uncleared.

### Cancellation by lead time and age band

| lead_bucket | passengers | cancellation_rate | cancel_ci_low | cancel_ci_high |
|---|---|---|---|---|
| 0-3 days | 48,009 | 9.5% | 9.2% | 9.8% |
| 4-14 days | 98,830 | 10.7% | 10.5% | 10.9% |
| 15-30 days | 101,073 | 12.5% | 12.3% | 12.7% |
| 31-60 days | 104,916 | 15.7% | 15.5% | 15.9% |
| 61-120 days | 52,372 | 22.4% | 22.1% | 22.8% |

| age_band | passengers | cancellation_rate |
|---|---|---|
| Child | 20,558 | 13.4% |
| Adult | 322,862 | 13.8% |
| Senior | 60,770 | 13.8% |
| Unknown | 1,010 | 12.1% |

### Booking shape: party size, partial cancellation, mixed status

| passengers_in_booking | bookings | share |
|---|---|---|
| 1 | 93,734 | 46.6% |
| 2 | 56,059 | 27.9% |
| 3 | 21,904 | 10.9% |
| 4 | 19,631 | 9.8% |
| 5 | 4,012 | 2.0% |
| 6 | 5,842 | 2.9% |

| item | bookings |
|---|---|
| bookings with at least one cancelled passenger | 30,562 |
| of which every passenger cancelled (fully cancelled) | 26,619 |
| of which partially cancelled | 3,943 |
| bookings with 2+ passengers | 107,448 |
| mixed-status bookings | 4,625 |

| multi | bookings | mixed | mixed_share |
|---|---|---|---|
| 1 | 93,734 | 0 | 0.0% |
| 2 | 56,059 | 2,270 | 4.0% |
| 3 | 21,904 | 965 | 4.4% |
| 4 | 19,631 | 905 | 4.6% |
| 5 | 4,012 | 197 | 4.9% |
| 6 | 5,842 | 288 | 4.9% |

**Observed:** 3,943 bookings were partially cancelled; mixed-status bookings (4,625) can only occur with two or more passengers, where they are 4.3% of such bookings.

## C. Operations

### Class performance (capacity utilisation and demand per available seat)

| travel_class | class_runs | seats | passengers | occupancy | confirmed_occupancy | waitlist_pressure | demand_per_seat | occ_ci_low | occ_ci_high |
|---|---|---|---|---|---|---|---|---|---|
| 1A | 29 | 768 | 641 | 0.733 | 0.733 | 0.034 | 0.835 | 0.657 | 0.799 |
| 2A | 351 | 25,760 | 23,137 | 0.727 | 0.697 | 0.045 | 0.898 | 0.702 | 0.750 |
| 3A | 734 | 122,368 | 122,748 | 0.768 | 0.728 | 0.065 | 1.003 | 0.752 | 0.784 |
| SL | 720 | 154,368 | 154,096 | 0.752 | 0.714 | 0.061 | 0.998 | 0.736 | 0.768 |
| CC | 34 | 7,020 | 4,239 | 0.525 | 0.525 | 0.003 | 0.604 | 0.458 | 0.593 |
| 2S | 417 | 116,100 | 100,339 | 0.691 | 0.691 | 0.048 | 0.864 | 0.668 | 0.713 |

**Observed:** seat occupancy is 73.5% overall (Confirmed 70.8% + RAC 2.7% of seat supply); waitlist pressure is 5.7%. `demand_per_seat` (all requested passengers per seat, 0.95) is an exploratory measure, not an approved KPI.

### Class-run occupancy distribution

| measure | value |
|---|---|
| class-runs | 2,285.000 |
| mean occupancy | 0.736 |
| median occupancy | 0.761 |
| 5th percentile | 0.326 |
| 25th percentile | 0.542 |
| 75th percentile | 0.986 |
| 95th percentile | 1.000 |
| share of class-runs below 50% occupancy | 0.200 |
| share of class-runs at or above 95% | 0.312 |
| share of class-runs with any uncleared waitlist | 0.257 |

**Observed:** the median class-run is 76.1% occupied; 31.2% of class-runs are at or above 95% and 20.0% are below 50%.

### Train level (every train has 9 to 20 simulated runs)

Highest occupancy:

| train_number | train_name | runs | passengers_per_run | occupancy | occ_ci_low | occ_ci_high | otp |
|---|---|---|---|---|---|---|---|
| S1015 | Lucknow–Mumbai Express 2 | 15 | 1,063.6 | 0.976 | 0.959 | 0.990 | 80.0% |
| S1051 | Vijayawada–Patna Express | 17 | 780.6 | 0.942 | 0.900 | 0.970 | 64.7% |
| S1046 | Kolkata–Hyderabad Superfast 2 | 15 | 680.9 | 0.941 | 0.919 | 0.963 | 93.3% |
| S1045 | Hyderabad–Kolkata Superfast 2 | 18 | 817.6 | 0.940 | 0.909 | 0.968 | 66.7% |
| S1014 | Mumbai–Lucknow Premium 1 | 11 | 420.5 | 0.938 | 0.897 | 0.972 | 70.0% |
| S1044 | Kolkata–Hyderabad Express 1 | 14 | 937.4 | 0.933 | 0.892 | 0.974 | 78.6% |
| S1032 | Bengaluru–Mumbai Express 2 | 14 | 933.4 | 0.922 | 0.856 | 0.974 | 78.6% |
| S1024 | Ahmedabad–Varanasi Express | 19 | 584.3 | 0.922 | 0.885 | 0.964 | 83.3% |

Lowest occupancy:

| train_number | train_name | runs | passengers_per_run | occupancy | occ_ci_low | occ_ci_high | otp |
|---|---|---|---|---|---|---|---|
| S1038 | Madurai–Madgaon Superfast | 17 | 325.4 | 0.519 | 0.456 | 0.581 | 87.5% |
| S1010 | Bhopal–Jaipur Express | 15 | 348.5 | 0.508 | 0.447 | 0.587 | 80.0% |
| S1041 | Bhopal–Guwahati Express | 13 | 397.5 | 0.488 | 0.411 | 0.585 | 83.3% |
| S1049 | Coimbatore–Ranchi Express | 15 | 275.7 | 0.384 | 0.335 | 0.457 | 84.6% |
| S1017 | Chandigarh–Visakhapatnam Express | 10 | 254.6 | 0.356 | 0.295 | 0.432 | 90.0% |

### Route level and train type

| route_name | runs | trains | passengers_per_run | occupancy | otp |
|---|---|---|---|---|---|
| Bengaluru to Mumbai | 30 | 2 | 896.8 | 0.910 | 73.3% |
| Hyderabad to Kolkata | 31 | 2 | 881.7 | 0.922 | 67.7% |
| Kolkata to Hyderabad | 29 | 2 | 804.7 | 0.937 | 86.2% |
| Vijayawada to Patna | 17 | 1 | 780.6 | 0.942 | 64.7% |
| Bengaluru to Jodhpur | 13 | 1 | 757.7 | 0.797 | 92.3% |
| Mumbai to Bengaluru | 30 | 2 | 746.0 | 0.843 | 83.3% |
| Delhi to Madurai | 30 | 2 | 686.8 | 0.829 | 85.2% |
| Visakhapatnam to Chandigarh | 15 | 1 | 667.9 | 0.724 | 80.0% |

| train_type | runs | passengers_per_run | occupancy | otp | avg_delay |
|---|---|---|---|---|---|
| Premium | 29 | 312.1 | 0.894 | 85.7% | 12.1 |
| Superfast | 179 | 502.2 | 0.691 | 81.5% | 14.0 |
| Express | 560 | 546.9 | 0.745 | 72.1% | 21.0 |

**Observed:** highest-occupancy train S1015 (97.6%, 15 runs) and lowest S1017 (35.6%, 10 runs). Train-level intervals are wide because each train has only 9 to 20 simulated runs; rankings are indicative, not definitive.

## D. Financial analysis (INR; booking value, not revenue or profit)

| journey_month | gross_value | refund_total | net_value | gross_per_run | refund_share_of_gross | avg_fare_per_passenger |
|---|---|---|---|---|---|---|
| 2024-09 | 18,403,297 | 2,358,384 | 16,044,913 | 575,103 | 12.8% | 1,513.6 |
| 2024-10 | 24,124,782 | 3,594,946 | 20,529,836 | 753,899 | 14.9% | 1,561.7 |
| 2024-11 | 23,920,040 | 4,190,534 | 19,729,506 | 747,501 | 17.5% | 1,492.9 |
| 2024-12 | 23,795,348 | 3,449,323 | 20,346,025 | 743,605 | 14.5% | 1,592.6 |
| 2025-01 | 23,019,795 | 3,424,009 | 19,595,786 | 719,369 | 14.9% | 1,418.8 |
| 2025-02 | 21,171,056 | 3,110,456 | 18,060,600 | 661,596 | 14.7% | 1,485.2 |
| 2025-03 | 26,983,278 | 4,896,894 | 22,086,384 | 843,227 | 18.1% | 1,448.5 |
| 2025-04 | 28,114,523 | 5,103,114 | 23,011,410 | 878,579 | 18.2% | 1,518.5 |
| 2025-05 | 30,910,281 | 6,528,283 | 24,381,998 | 965,946 | 21.1% | 1,419.1 |
| 2025-06 | 23,448,148 | 3,824,062 | 19,624,086 | 732,755 | 16.3% | 1,441.2 |
| 2025-07 | 21,550,999 | 3,015,415 | 18,535,584 | 673,469 | 14.0% | 1,426.9 |
| 2025-08 | 21,977,558 | 3,126,508 | 18,851,050 | 686,799 | 14.2% | 1,507.1 |
| 2025-09 | 22,210,254 | 3,264,075 | 18,946,179 | 694,070 | 14.7% | 1,463.8 |
| 2025-10 | 27,539,668 | 4,897,438 | 22,642,230 | 860,615 | 17.8% | 1,627.2 |
| 2025-11 | 24,554,554 | 3,971,634 | 20,582,920 | 767,330 | 16.2% | 1,483.3 |
| 2025-12 | 27,326,615 | 4,589,504 | 22,737,111 | 853,957 | 16.8% | 1,577.7 |
| 2026-01 | 25,044,510 | 4,714,106 | 20,330,404 | 782,641 | 18.8% | 1,537.2 |
| 2026-02 | 25,479,874 | 4,366,306 | 21,113,568 | 796,246 | 17.1% | 1,519.6 |
| 2026-03 | 24,742,606 | 4,783,305 | 19,959,301 | 773,206 | 19.3% | 1,325.3 |
| 2026-04 | 31,004,870 | 6,655,124 | 24,349,746 | 968,902 | 21.5% | 1,540.2 |
| 2026-05 | 36,219,176 | 8,653,240 | 27,565,936 | 1,131,849 | 23.9% | 1,574.7 |
| 2026-06 | 29,318,810 | 5,948,604 | 23,370,206 | 916,213 | 20.3% | 1,636.6 |
| 2026-07 | 25,026,611 | 4,315,194 | 20,711,418 | 782,082 | 17.2% | 1,573.2 |
| 2026-08 | 27,080,300 | 4,303,071 | 22,777,229 | 846,259 | 15.9% | 1,630.1 |

| cancellation_type | events | passengers | original | charge | refund | charge_share |
|---|---|---|---|---|---|---|
| Passenger | 30,661 | 55,980 | 80,815,181 | 8,930,744 | 71,884,437 | 11.1% |
| System | 13,262 | 24,200 | 35,925,090 | 726,000 | 35,199,090 | 2.0% |

| travel_class | n | mean | median | std | p5 | p95 |
|---|---|---|---|---|---|---|
| 1A | 641 | 6,672 | 7,338 | 1,294 | 3,669 | 7,338 |
| 2A | 23,137 | 3,467 | 3,309 | 939 | 1,903 | 5,052 |
| 3A | 122,748 | 2,502 | 2,429 | 813 | 1,278 | 4,198 |
| SL | 154,096 | 925 | 906 | 313 | 420 | 1,579 |
| CC | 4,239 | 763 | 833 | 142 | 500 | 833 |
| 2S | 100,339 | 754 | 753 | 292 | 288 | 1,379 |

**Observed:** gross booking value INR 612,966,953; refunds INR 107,083,527 (17.5% of gross; Passenger events INR 71,884,437, System auto-refunds INR 35,199,090); net booking value INR 505,883,426; retained charges INR 9,656,744. Average fare per passenger INR 1,512.75; the fare distribution is right-skewed (median INR 1,053, 95th percentile INR 3,694, 99th INR 4,482). Fares come from an illustrative synthetic formula (distance, class, age).

## E. Temporal analysis (only the 24 simulated months)

| journey_month | total_bookings | bookings_growth | bookings_per_run | bookings_per_run_growth | occupancy | passenger_cancellation_rate |
|---|---|---|---|---|---|---|
| 2024-09 | 5,944 |  | 185.8 |  | 58.4% | 13.2% |
| 2024-10 | 7,727 | 30.0% | 241.5 | 30.0% | 68.4% | 13.8% |
| 2024-11 | 7,934 | 2.7% | 247.9 | 2.7% | 70.2% | 13.5% |
| 2024-12 | 7,457 | -6.0% | 233.0 | -6.0% | 66.2% | 12.9% |
| 2025-01 | 7,939 | 6.5% | 248.1 | 6.5% | 68.9% | 13.8% |
| 2025-02 | 7,165 | -9.7% | 223.9 | -9.7% | 65.1% | 13.2% |
| 2025-03 | 9,243 | 29.0% | 288.8 | 29.0% | 79.4% | 13.5% |
| 2025-04 | 9,150 | -1.0% | 285.9 | -1.0% | 77.6% | 13.8% |
| 2025-05 | 10,856 | 18.6% | 339.2 | 18.6% | 89.6% | 14.3% |
| 2025-06 | 8,073 | -25.6% | 252.3 | -25.6% | 72.5% | 13.6% |
| 2025-07 | 7,382 | -8.6% | 230.7 | -8.6% | 67.9% | 13.5% |
| 2025-08 | 7,166 | -2.9% | 223.9 | -2.9% | 71.0% | 12.4% |
| 2025-09 | 7,510 | 4.8% | 234.7 | 4.8% | 68.1% | 14.0% |
| 2025-10 | 8,400 | 11.9% | 262.5 | 11.9% | 73.4% | 13.7% |
| 2025-11 | 8,177 | -2.7% | 255.5 | -2.7% | 73.7% | 14.0% |
| 2025-12 | 8,636 | 5.6% | 269.9 | 5.6% | 75.5% | 13.3% |
| 2026-01 | 8,149 | -5.6% | 254.7 | -5.6% | 73.1% | 14.2% |
| 2026-02 | 8,288 | 1.7% | 259.0 | 1.7% | 72.3% | 14.0% |
| 2026-03 | 9,361 | 12.9% | 292.5 | 12.9% | 77.8% | 14.6% |
| 2026-04 | 9,986 | 6.7% | 312.1 | 6.7% | 81.4% | 15.1% |
| 2026-05 | 11,501 | 15.2% | 359.4 | 15.2% | 92.0% | 15.0% |
| 2026-06 | 8,963 | -22.1% | 280.1 | -22.1% | 77.9% | 13.4% |
| 2026-07 | 7,932 | -11.5% | 247.9 | -11.5% | 69.9% | 13.7% |
| 2026-08 | 8,243 | 3.9% | 257.6 | 3.9% | 74.2% | 13.5% |

| season | runs | passengers | passengers_per_run | occupancy | runs_with_delay | otp | avg_delay |
|---|---|---|---|---|---|---|---|
| Monsoon | 256 | 123,723 | 483.3 | 0.700 | 249 | 73.1% | 22.6 |
| Post-Monsoon | 128 | 64,950 | 507.4 | 0.714 | 124 | 79.0% | 11.8 |
| Summer | 192 | 120,725 | 628.8 | 0.829 | 185 | 78.4% | 13.4 |
| Winter | 192 | 95,802 | 499.0 | 0.702 | 187 | 70.6% | 24.6 |

| period | runs | passengers | passengers_per_run | occupancy |
|---|---|---|---|---|
| Other days | 607 | 302,352 | 498.1 | 0.707 |
| Peak travel period | 161 | 102,848 | 638.8 | 0.842 |

| month_number | runs | passengers | passengers_per_run | occupancy |
|---|---|---|---|---|
| 1 | 64 | 32,517 | 508.1 | 0.709 |
| 2 | 64 | 31,023 | 484.7 | 0.687 |
| 3 | 64 | 37,297 | 582.8 | 0.786 |
| 4 | 64 | 38,645 | 603.8 | 0.794 |
| 5 | 64 | 44,783 | 699.7 | 0.908 |
| 6 | 64 | 34,184 | 534.1 | 0.752 |
| 7 | 64 | 31,011 | 484.5 | 0.689 |
| 8 | 64 | 31,196 | 487.4 | 0.726 |
| 9 | 64 | 27,332 | 427.1 | 0.633 |
| 10 | 64 | 32,373 | 505.8 | 0.708 |
| 11 | 64 | 32,577 | 509.0 | 0.719 |
| 12 | 64 | 32,262 | 504.1 | 0.708 |

**Observed:** month-over-month change in bookings per run ranges from -25.6% to +30.0%. Peak-travel-period runs average 638.8 passengers vs 498.1 on other days (occupancy 84.2% vs 70.7%). With only two observations of each calendar month, seasonal patterns here describe these two simulated years, not a stable seasonal cycle.

## Statistical highlights

Full results (question, metric, method, effect size, interpretation, limitation): `reports/phase5_statistical_results.csv` and notebook 04.

| test_id | metric | result |
|---|---|---|
| S-01 | passengers per simulated run | weekend mean 499.7 vs weekday mean 536.1 passengers/run; difference -36.4 (95% CI -73.4 to +0.6); p = 0.054; Mann-Whitney p = 0.217 |
| S-02 | passengers per simulated run | peak mean 638.8 vs other 498.1 passengers/run; difference +140.7 (95% CI +96.1 to +185.3); p < 0.001 |
| S-03 | run occupancy (booked seat-equivalents / seats) | peak mean 0.846 vs other 0.709; difference +0.137 (95% CI +0.107 to +0.167); p < 0.001 |
| S-04 | booking-based cancellation rate by lead-time bucket | rate rises from 9.3% (0-3 days) to 21.4% (61-120 days); chi-square = 2,448, dof = 4, p < 0.001 |
| S-05 | occupancy of each simulated train-class run | H = 65.3, p < 0.001; epsilon-squared = 0.026 |
| S-06 | arrival delay in minutes | H = 6.8, p = 0.079; epsilon-squared = 0.005 |
| S-07 | on-time performance by season | chi-square = 4.6, dof = 3, p = 0.206; OTP by season: Monsoon 73.1%, Post-Monsoon 79.0%, Summer 78.4%, Winter 70.6% |
| S-08 | bookings per simulated run, by month | slope +2.36 bookings/run per month (95% CI +0.23 to +4.49); R-squared = 0.19; p = 0.032 |
| S-09 | booking fare per passenger vs route distance (km) | rho = 0.48 (95% CI 0.48 to 0.49); p < 0.001 |
| S-10 | passengers per run vs arrival delay (minutes) | rho = 0.02 (95% CI -0.06 to 0.10); p = 0.589 |
| S-11 | share of initially waitlisted passengers who finished Confirmed or RAC | chi-square = 72, dof = 5, p < 0.001; clearance by class: 1A 18.2%, 2A 12.8%, 3A 19.8%, SL 20.4%, CC 25.6%, 2S 17.6% |

## Limitations

* Synthetic, sampled simulation (768 of 19,708 scheduled runs): findings illustrate method and the simulation's built-in behaviour; they say nothing about real passengers or the real network.
* Passengers cluster within bookings and runs; intervals that assume independence (Wilson) are narrower than cluster-aware ones.
* No forecasts are produced; the trend slope in S-08 describes the 24 simulated months only.
