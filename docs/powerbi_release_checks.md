# Power BI release preparation checks

These checks read local source and CSV files; they do not run Power BI or DAX.

| Check | Result |
|---|---|
| Model tables / relationships / measures | 17 / 17 / 70 |
| Report pages / visual containers | 6 / 85 |
| Referenced CSV files present, headers checked | 15 |
| CSV counts matching imported row-count reference | 11 / 11 |
| KPI reference rows | 31 |
| Project-to-report and report-to-model paths | Matched |

The original report/model/data bytes are preserved. Caches, old report copies,
diagnostic projects, unrelated Python changes and Tableau files are not in the
staging manifest. Desktop refresh, interactions and fresh-clone execution are
separate checks; see phase6_powerbi.md.
