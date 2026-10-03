"""Read-only Phase 3 review audit helpers (no workbook or data file is modified). Sections are run from the review session; output goes to reports/phase3_work/."""
import html, os, re, sys, zipfile, pathlib
import xml.etree.ElementTree as ET
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOOKS = {"MAIN": ROOT / "excel/IRCTC_Booking_Analytics_Workbook.xlsx", "PIVOT": ROOT / "excel/IRCTC_KPI_Pivot_Dashboard.xlsx", "EXERCISES": ROOT / "excel/IRCTC_Data_Cleaning_Exercises.xlsx",
         "GS_KPI": ROOT / "google_sheets/KPI_Tracker_Template.xlsx", "GS_CANCEL": ROOT / "google_sheets/Cancellation_Refund_Tracker_Template.xlsx", "GS_OCC": ROOT / "google_sheets/Occupancy_Waitlist_Tracker_Template.xlsx"}
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
POST2007 = {"IFS", "SWITCH", "MAXIFS", "MINIFS", "CONCAT", "TEXTJOIN", "XLOOKUP", "XMATCH", "FILTER", "SORT", "SORTBY", "UNIQUE", "SEQUENCE", "LET", "LAMBDA", "RANDARRAY", "IFNA", "DAYS", "XOR", "ISOWEEKNUM", "STDEV.S", "FORECAST.LINEAR"}


def sheet_files(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = []
    for s in wb.find(f"{M}sheets"):
        t = rels[s.get(f"{R}id")]
        out.append((s.get("name"), "xl/" + t.lstrip("/").replace("xl/", "", 1) if not t.startswith("/") else t.lstrip("/")))
    return wb, out


def static_audit():
    lines, allfuncs = [], Counter()
    for key, path in BOOKS.items():
        z = ET.ElementTree  # noqa
        zf = zipfile.ZipFile(path)
        bad_parts = []
        for n in zf.namelist():
            if n.endswith((".xml", ".rels")):
                try:
                    ET.fromstring(zf.read(n))
                except ET.ParseError as e:
                    bad_parts.append((n, str(e)))
        wb, sheets = sheet_files(zf)
        names = [s for s, _ in sheets]
        calc = wb.find(f"{M}calcPr")
        dn = wb.find(f"{M}definedNames")
        funcs, nform, maxlen, maxdepth, badref, errlit, shared = Counter(), 0, 0, 0, [], 0, 0
        dv = cf = merges = 0
        for name, part in sheets:
            xml = zf.read(part).decode("utf-8", errors="ignore")
            dv += xml.count("<dataValidation "); cf += xml.count("<conditionalFormatting"); merges += xml.count("<mergeCell ")
            for m in re.finditer(r"<f([^>]*)>(.*?)</f>", xml, flags=re.S):
                f = html.unescape(m.group(2)); nform += 1
                if 't="shared"' in m.group(1):
                    shared += 1
                maxlen = max(maxlen, len(f))
                g = re.sub(r'"[^"]*"', '""', f)
                d = cur = 0
                for ch in g:
                    cur += ch == "("; d = max(d, cur); cur -= ch == ")"
                maxdepth = max(maxdepth, d)
                funcs.update(re.findall(r"\b([A-Z][A-Z0-9\.]{1,})\(", g))
                for a, b in re.findall(r"(?:'([^']+)'|\b([A-Za-z_][A-Za-z0-9_\.]*))!", g):
                    if (a or b) not in names:
                        badref.append((name, a or b))
                errlit += "#REF!" in f
            nform += len(re.findall(r'<f [^>]*t="shared"[^>]*/>', xml))
        allfuncs.update(funcs)
        parts = zf.namelist()
        lines.append(f"[{key}] {path.relative_to(ROOT)}  {path.stat().st_size/1024:.0f} KB | zip ok={zf.testzip() is None} | XML parts well-formed={not bad_parts} {bad_parts[:2]}")
        lines.append(f"     sheets({len(names)}): {', '.join(names)}")
        lines.append(f"     formulas={nform} (shared-formula refs={shared}) maxlen={maxlen} maxnest={maxdepth} | #REF! literals={errlit} | refs to missing sheets={sorted(set(badref))[:5]} | definedNames={0 if dn is None else len(list(dn))}")
        lines.append(f"     data validations={dv} conditional formats={cf} merged ranges={merges} charts={sum(n.startswith('xl/charts/chart') for n in parts)} drawings={sum(n.startswith('xl/drawings/drawing') for n in parts)} pivot tables={sum(bool(re.match(r'xl/pivotTables/pivotTable\d+.xml$', n)) for n in parts)} pivot caches={sum(n.startswith('xl/pivotCache/pivotCacheDefinition') for n in parts)}")
        lines.append(f"     calcPr={dict(calc.attrib) if calc is not None else None}")
        post = sorted(f for f in funcs if f in POST2007)
        lines.append(f"     distinct functions ({len(funcs)}): {', '.join(sorted(funcs))}")
        lines.append(f"     functions newer than Excel 2007 (need _xlfn prefix / not portable): {post or 'none'}")
    lib = (ROOT / "excel/FORMULA_LIBRARY.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"\b([A-Z][A-Z0-9\.]{2,})\(", lib))
    lines.append("\nFORMULA_LIBRARY.md: functions documented but not used in any workbook: " + str(sorted(f for f in documented if f not in allfuncs and f not in {"XLOOKUP", "FILTER", "UNIQUE", "SORT", "LET", "LAMBDA"})))
    lines.append("FORMULA_LIBRARY.md: functions used in workbooks but not named in the library: " + str(sorted(f for f in allfuncs if f not in documented)))
    return lines


def pivot_audit():
    zf = zipfile.ZipFile(BOOKS["PIVOT"]); lines = []
    wb, sheets = sheet_files(zf); names = dict(sheets)
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))}
    caches = {}
    pcs = wb.find(f"{M}pivotCaches")
    for pc in (pcs if pcs is not None else []):
        caches[pc.get("cacheId")] = "xl/" + rels[pc.get(f"{R}id")].lstrip("/").replace("xl/", "", 1)
    lines.append(f"workbook.xml pivotCaches: {len(caches)} -> {sorted(caches)}")
    for cid, part in sorted(caches.items()):
        d = ET.fromstring(zf.read(part)); ws = d.find(f"{M}cacheSource").find(f"{M}worksheetSource")
        ref, sh = ws.get("ref"), ws.get("sheet")
        nf = len(d.find(f"{M}cacheFields")); rec_part = part.replace("Definition", "Records")
        rc = ET.fromstring(zf.read(rec_part)).get("count")
        lines.append(f"  cache {cid}: source sheet={sh!r} ref={ref} (sheet exists={sh in names}) cacheFields={nf} records={rc} refreshOnLoad={d.get('refreshOnLoad')}")
    for n in sorted(x for x in zf.namelist() if re.match(r"xl/pivotTables/pivotTable\d+\.xml$", x)):
        p = ET.fromstring(zf.read(n)); loc = p.find(f"{M}location")
        lines.append(f"  {n.split('/')[-1]}: name={p.get('name')} cacheId={p.get('cacheId')} (cache declared={p.get('cacheId') in caches}) location={loc.get('ref')} dataFields={len(p.find(f'{M}dataFields')) if p.find(f'{M}dataFields') is not None else 0} dataOnRows={p.get('dataOnRows')}")
    return lines


def label_audit():
    import openpyxl
    lines = []
    for key, path in BOOKS.items():
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        row = []
        for ws in wb:
            txt = " ".join(str(c) for r in ws.iter_rows(min_row=1, max_row=8, values_only=True) for c in r if c is not None)
            header = [str(c) for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True), []) if c is not None]
            syn = bool(re.search(r"synthetic", txt, re.I)); samp = bool(re.search(r"19,708|sampled simulation|sample \(", txt, re.I))
            row.append((ws.title, syn, samp, "data_origin" in " ".join(header)))
        lines.append(f"[{key}] sheet: synthetic-label / sampling-label / data_origin-column (first 8 rows)")
        lines += [f"     {n:<28} synthetic={s!s:<5} sampling={m!s:<5} data_origin_col={o}" for n, s, m, o in row]
        ch = []
        zf = zipfile.ZipFile(path)
        for n in sorted(zf.namelist()):
            if re.match(r"xl/charts/chart\d+\.xml$", n):
                t = " ".join(re.findall(r"<a:t>([^<]*)</a:t>", zf.read(n).decode("utf-8", errors="ignore")))
                ch.append((n.split("/")[-1], t[:95], bool(re.search(r"synthetic|sampl", t, re.I))))
        if ch:
            lines.append(f"     chart titles: " + " | ".join(f"{a}: '{b}' label={c}" for a, b, c in ch))
    return lines


def docs_audit():
    lines = []
    for f in sorted([*(ROOT / "docs").glob("*.md"), ROOT / "README.md", *(ROOT / "excel").glob("*.md"), *(ROOT / "google_sheets").glob("*.md")]):
        t = f.read_text(encoding="utf-8")
        lines.append(f"{str(f.relative_to(ROOT)):<38} '19,708'={t.count('19,708'):>2}  'sampled'={len(re.findall('sampled', t, re.I)):>2}  'synthetic'={len(re.findall('synthetic', t, re.I)):>2}  'network-wide'={len(re.findall('network-wide', t, re.I)):>2}")
    return lines


def coverage_audit():
    import openpyxl
    lines, src = [], ""
    for f in [*(ROOT / "python/src").glob("build_*.py"), *(ROOT / "excel/power_query").glob("*.pq")]:
        src += f.read_text(encoding="utf-8")
    for csv in sorted(p.name for p in (ROOT / "data/processed/derived").glob("*.csv")) + sorted("excel sample: " + p.name for p in (ROOT / "data/sample/excel").glob("*.csv")):
        nm = csv.split(": ")[-1]
        lines.append(f"  {csv:<55} referenced by a workbook builder or M script: {nm in src}")
    wb = openpyxl.load_workbook(BOOKS["MAIN"], read_only=True, data_only=True)
    kw = ["route", "train", "weekday", "season", "holiday", "travel class|class", "lead", "month", "refund", "delay|on-time", "occupancy", "waitlist|waiting"]
    lines.append("  keyword presence in the four analysis sheets of the main workbook (headers/labels):")
    for sh in ("Dashboard", "Monthly_Aggregates", "Cancellation_Refund", "Occupancy_Demand"):
        ws = wb[sh]
        txt = " ".join(str(c).lower() for r in ws.iter_rows(min_row=1, max_row=80, values_only=True) for c in r if isinstance(c, str))
        lines.append(f"     {sh:<22} " + " ".join(f"{k.split('|')[0]}={'Y' if re.search(k, txt) else '-'}" for k in kw))
    return lines


# ============================================================ LibreOffice audit (open, recalculate, cached-vs-fresh, cross-workbook KPI consistency)
def _snapshot(doc):
    snap = {}
    for i in range(doc.Sheets.Count):
        sh = doc.Sheets.getByIndex(i)
        cur = sh.createCursor(); cur.gotoEndOfUsedArea(False)
        snap[sh.Name] = sh.getCellRangeByPosition(0, 0, cur.RangeAddress.EndColumn, cur.RangeAddress.EndRow).DataArray
    return snap


def _diff(a, b):
    n, ex = 0, []
    for sh in a:
        for r, (ra, rb) in enumerate(zip(a[sh], b[sh])):
            for c, (x, y) in enumerate(zip(ra, rb)):
                same = (abs(x - y) <= 1e-9 * max(1.0, abs(y))) if isinstance(x, float) and isinstance(y, float) else (x == y)
                if not same:
                    n += 1
                    if len(ex) < 4:
                        ex.append((sh, r + 1, c + 1, x, y))
    return n, ex


def lo_audit():
    sys.path.insert(0, str(ROOT / "python/src"))
    import lo_bridge as lb
    lines, S = [], {}
    with lb.office(timeout=180) as desktop:
        for key, path in BOOKS.items():
            doc = lb.load(desktop, path)
            opened = doc is not None
            before = _snapshot(doc)
            doc.calculateAll()
            after = _snapshot(doc)
            errs = lb.error_cells(doc)
            n, ex = _diff(before, after)
            nform = sum(doc.Sheets.getByIndex(i).queryContentCells(16).RangeAddresses.__len__() for i in range(doc.Sheets.Count))
            lines.append(f"[{key}] opened in LibreOffice={opened} | sheets={doc.Sheets.Count} | formula-error cells after recalculation={sum(v for v in errs.values() if v > 0)} {[k for k, v in errs.items() if v != 0]}")
            lines.append(f"     stored (cached) values vs fresh recalculation: {n} differing cells {ex}")
            S[key] = after
            doc.close(True)
    # ---------------- cross-workbook KPI consistency (values read after recalculation)
    def row_of(sheet, label, col=0, start=0):
        for i, r in enumerate(sheet[start:], start=start):
            if r[col] == label:
                return r
    main_kpi = {r[0]: r[1] for r in S["MAIN"]["KPI_Calc"][4:40]}
    piv = {r[0]: r[1] for r in S["PIVOT"]["Dashboard"][4:20] if r[0]}
    pairs = [("Total passengers", "total_passengers"), ("Total bookings", "total_bookings"), ("Fully confirmed bookings (every passenger Confirmed)", "confirmed_bookings"),
             ("Mixed-status bookings (reported separately)", "mixed_bookings"), ("Cancellation rate (passenger-based)", "passenger_cancellation_rate"), ("Waiting-list demand (initially waitlisted passengers)", "wl_demand"),
             ("Waitlist clearance rate", "wl_clearance_rate"), ("Uncleared waitlist passengers", "wl_uncleared"), ("Seat occupancy %", "occupancy"), ("Waitlist pressure % (not part of occupancy)", "waitlist_pressure"),
             ("Gross booking value (INR)", "gross_value"), ("Refund amount (INR)", "refund_total"), ("Net booking value (INR)", "net_value"), ("Average fare per passenger (INR)", "avg_fare_per_passenger")]
    bad = [(a, piv.get(a), main_kpi.get(b)) for a, b in pairs if not (isinstance(piv.get(a), float) and abs(piv[a] - main_kpi[b]) <= 1e-9 * max(1, abs(main_kpi[b])))]
    lines.append(f"\nCROSS-CHECK main KPI_Calc (sample) vs pivot dashboard cards: {len(pairs) - len(bad)} of {len(pairs)} KPIs identical {bad}")
    hdr = [str(c).replace(" (formula)", "") for c in S["MAIN"]["Monthly_Aggregates"][4]]
    col = {h: i for i, h in enumerate(hdr)}
    mon = S["MAIN"]["Monthly_Aggregates"][5:29]; tot = S["MAIN"]["Monthly_Aggregates"][29]
    tr = S["GS_KPI"]["KPI_Tracker"][4:28]
    mp = [("bookings_per_run", 1), ("passengers_per_run", 2), ("passenger_cancellation_rate", 3), ("booking_cancellation_rate", 4), ("wl_clearance_rate", 8), ("waitlist_pressure", 9), ("occupancy", 10), ("net_value", 13), ("avg_fare_per_passenger", 14), ("otp", 15), ("avg_delay", 16)]
    nb = 0
    for i in range(24):
        for k, c in mp:
            x, y = mon[i][col[k]], tr[i][c]
            nb += not (isinstance(x, float) and isinstance(y, float) and abs(x - y) <= 1e-9 * max(1, abs(y)))
    lines.append(f"CROSS-CHECK main Monthly_Aggregates vs Google KPI tracker: {24 * len(mp)} cells compared, {nb} differing")
    ca = S["GS_CANCEL"]["Analysis"][4:28]; nb = 0
    for i in range(24):
        for k, c in (("passenger_cancellation_rate", 1), ("booking_cancellation_rate", 2), ("refund_total", 3), ("net_value", 4)):
            x, y = mon[i][col[k]], ca[i][c]
            nb += not (abs(x - y) <= 1e-9 * max(1, abs(y)))
    lines.append(f"CROSS-CHECK main Monthly_Aggregates vs Google cancellation tracker: {24 * 4} cells compared, {nb} differing")
    allc = next(r for r in S["GS_OCC"]["By_Class"][4:12] if r[0] == "All classes")
    lines.append(f"CROSS-CHECK full-dataset occupancy: main Monthly total row={tot[col['occupancy']]:.10f} | Google occupancy tracker 'All classes'={allc[4]:.10f} | identical={abs(tot[col['occupancy']] - allc[4]) < 1e-12}")
    import pandas as pd
    ref = pd.read_csv(ROOT / "reports/kpi_reference_values.csv").set_index("kpi_key")["value"]
    chk = [(k, tot[col[k]], ref[k]) for k in ("total_bookings", "total_passengers", "gross_value", "occupancy", "passenger_cancellation_rate", "wl_clearance_rate", "otp", "avg_delay", "bookings_per_run")]
    lines.append("CROSS-CHECK main Monthly total row vs reports/kpi_reference_values.csv: " + ("all identical" if all(abs(a - b) <= 1e-9 * max(1, abs(b)) for _, a, b in chk) else str([c for c in chk if abs(c[1] - c[2]) > 1e-9 * max(1, abs(c[2]))])))
    return lines


def kpi_definition_audit():
    sys.path.insert(0, str(ROOT / "python/src"))
    import build_excel_workbook as bw
    doc = (ROOT / "docs/KPI_definitions.md").read_text(encoding="utf-8")
    blocks = dict((m.group(1).strip(), m.group(2)) for m in re.finditer(r"^### \d+\. ([^\n]+)\n(.*?)(?=^### |^## |\Z)", doc, flags=re.M | re.S))
    mapping = [("Total Bookings", "total_bookings"), ("Total Passengers", "total_passengers"), ("Confirmed Booking Count", "confirmed_bookings"), ("Cancelled Booking Count", "cancelled_bookings"),
               ("Cancellation Rate", "passenger_cancellation_rate"), ("Gross Booking Value", "gross_value"), ("Refund Amount", "refund_total"), ("Net Booking Value", "net_value"), ("Average Fare", "avg_fare_per_passenger"),
               ("Seat Occupancy %", "occupancy"), ("Waiting-List Demand", "wl_demand"), ("On-Time Performance %", "otp"), ("Average Delay", "avg_delay"), ("Monthly Booking Growth", None), ("Route-Level Demand", None)]
    lines = []
    for name, key in mapping:
        b = blocks[name]
        den = re.search(r"\*\*(?:Denominator|Numerator):\*\*[^\n]*\n?(?:- \*\*Denominator:\*\*[^\n]*)?", b)
        dline = re.search(r"- \*\*Denominator:\*\*\s*([^\n]+)", b)
        lines.append(f"{name:<26} doc denominator: {(dline.group(1)[:95] if dline else '(none: count/value KPI)'):<97} | workbook ({key}): {bw.KPI_DEFS[key][1] if key else 'not in Excel workbook (see report)'}")
    return lines




# ============================================================ additional review sections
def search_audit():
    hits, out = [], []
    def scan(label, text):
        text = text.replace("\\n", "\n")
        for m in re.finditer(r"(?i)(six|\b6\b)[^\n]{0,40}(required|sheets?)|required[^\n]{0,30}sheets?", text):
            hits.append((label, text[max(0, m.start() - 70): m.end() + 90].replace("\n", " ")))
    for f in ROOT.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".txt", ".py", ".pq") and "phase3_work" not in str(f):
            scan(f"project:{f.relative_to(ROOT)}", f.read_text(encoding="utf-8", errors="ignore"))
    for zn in ("irctc-analytics-phase1.zip", "irctc-analytics-phase2-delta.zip"):
        zp = ROOT.parent / zn
        if zp.exists():
            zz = zipfile.ZipFile(zp)
            for n in zz.namelist():
                if n.endswith((".md", ".txt", ".py")):
                    scan(f"{zn}:{n}", zz.read(n).decode("utf-8", errors="ignore"))
    extra = [d for d in os.environ.get("IRCTC_AUDIT_EXTRA_DIRS", "").split(os.pathsep) if d]      # optional extra folders (the original run also searched the build environment's transcript and upload folders)
    for d in extra:
        for f in pathlib.Path(d).rglob("*"):
            if f.is_file():
                scan(f"{d}:{f.name}", f.read_text(encoding="utf-8", errors="ignore"))
    out.append("Places searched: current project text files, Phase 1 ZIP, Phase 2 delta ZIP" + (", " + ", ".join(extra) if extra else "") + " (the original run also searched the build environment's transcript archive and uploads folder; the uploads folder was empty)")
    seen = set()
    for label, sn in hits:
        key = re.sub(r"\W+", " ", sn)[:90]
        if key not in seen:
            seen.add(key); out.append(f"  - {label.split('/')[-1][:60]} | {sn.strip()[:230]}")
    out.append("Result: only the two requirement lines above exist (BRD AC-6 and the project-plan Phase 3 row). No sheet names, order or specification, and no list of 'required functions', appear anywhere.")
    return out


def inventory_audit():
    import hashlib
    z = zipfile.ZipFile(ROOT.parent / "irctc-analytics-phase3-delta.zip"); names = {n.replace("irctc-analytics/", "", 1): n for n in z.namelist()}
    sha = lambda b: hashlib.sha256(b).hexdigest()
    bad = [n for n in names if not (ROOT / n).is_file() or sha((ROOT / n).read_bytes()) != sha(z.read(names[n]))]
    need = ["excel/IRCTC_Booking_Analytics_Workbook.xlsx", "excel/IRCTC_Data_Cleaning_Exercises.xlsx", "excel/IRCTC_KPI_Pivot_Dashboard.xlsx", "excel/FORMULA_LIBRARY.md", "excel/SETUP_INSTRUCTIONS.md",
            "google_sheets/KPI_Tracker_Template.xlsx", "google_sheets/Cancellation_Refund_Tracker_Template.xlsx", "google_sheets/Occupancy_Waitlist_Tracker_Template.xlsx", "google_sheets/SETUP_INSTRUCTIONS.md"] + \
           sorted(f"excel/power_query/{p.name}" for p in (ROOT / "excel/power_query").glob("*.pq"))
    return [f"Phase 3 ZIP entries: {len(names)}; integrity ok: {z.testzip() is None}; entries differing from disk or missing: {bad}",
            f"deliverable files required: {len(need)}; present on disk: {sum((ROOT / n).is_file() for n in need)}; present in ZIP: {sum(n in names for n in need)}; .pq scripts: {len(list((ROOT / 'excel/power_query').glob('*.pq')))}"]


def sample_audit():
    sys.path.insert(0, str(ROOT / "python/src"))
    import clean_data as cl, kpi
    import pandas as pd
    T = cl.read_clean(); S = kpi.select_sample(T); bk, ps, ev, cap, ops = kpi._prep(T)
    cal = T["calendar"].set_index("calendar_date"); out = []
    sh = lambda s: (s.value_counts(normalize=True) * 100).round(1)
    def cmp(title, a, b):
        d = pd.concat([a.rename("full %"), b.rename("sample %")], axis=1).fillna(0); d["diff pp"] = (d["sample %"] - d["full %"]).round(1)
        out.append(title + "\n" + d.to_string())
    cmp("Class-runs by travel class", sh(cap.travel_class), sh(S["cap"].travel_class)); cmp("Runs by train type", sh(ops.train_type), sh(S["ops"].train_type))
    wd = lambda d: pd.to_datetime(d.astype(str)).dt.day_name(); cmp("Runs by weekday", sh(wd(ops.run_date)), sh(wd(S["ops"].run_date)))
    out.append(f"coverage: trains {S['ops'].train_id.nunique()} of {T['trains'].train_id.nunique()} | routes {S['ops'].route_name.nunique()} of {T['routes'].route_id.nunique()} | 1A class-runs {int((S['cap'].travel_class == '1A').sum())} of {int((cap.travel_class == '1A').sum())} | Premium runs {int((S['ops'].train_type == 'Premium').sum())} of {int((ops.train_type == 'Premium').sum())}")
    sk, fk = kpi.compute_kpis(S["bk"], S["ps"], S["ev"], S["cap"], S["ops"]), kpi.compute_kpis(bk, ps, ev, cap, ops)
    out.append("KPI sample vs full: " + "; ".join(f"{k} {sk[k]:.4f} vs {fk[k]:.4f} ({(sk[k] - fk[k]) / fk[k]:+.1%})" for k in ("occupancy", "passenger_cancellation_rate", "wl_clearance_rate", "avg_fare_per_passenger", "otp")))
    return out


def visual_audit():
    out = []
    z = zipfile.ZipFile(BOOKS["PIVOT"]); d = z.read("xl/drawings/drawing1.xml").decode()
    from xlsxwriter.utility import xl_col_to_name as CL
    for m in re.finditer(r"<xdr:from><xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>.*?<xdr:to><xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>", d, flags=re.S):
        c0, r0, c1, r1 = map(int, m.groups()); out.append(f"PIVOT Dashboard chart anchored {CL(c0)}{r0 + 1}:{CL(c1)}{r1 + 1}; KPI table occupies A4:E20 -> overlap={c0 <= 4 and r0 <= 19}")
    for n in sorted(x for x in z.namelist() if re.match(r"xl/charts/chart\d+\.xml$", x)):
        c = z.read(n).decode(); out.append(f"PIVOT {n}: legend present={'<c:legend>' in c}, series={c.count('<c:ser>')}")
    sys.path.insert(0, str(ROOT / "python/src")); import lo_bridge as lb
    with lb.office() as dsk:
        doc = lb.load(dsk, BOOKS["MAIN"]); doc.calculateAll()
        doc.Sheets.getByName("Dashboard").getCellRangeByName("C5").String = "1A"; doc.calculateAll()
        rows = lb.read_range(doc, "Dashboard", "B9:E23")
        out.append("MAIN Dashboard with class filter = 1A (no 1A class-runs in the sample): " + "; ".join(f"{r[0].split(' (')[0]}={r[1] if r[1] != '' else 'blank'}" for r in rows[:6]) + f" | error cells={sum(v for v in lb.error_cells(doc).values() if v > 0)}")
        doc.close(True)
    return out


if __name__ == "__main__":
    which = sys.argv[1:] or ["static", "pivot", "labels", "docs", "coverage"]
    for w in which:
        print(f"\n===== {w} =====")
        print("\n".join({"static": static_audit, "pivot": pivot_audit, "labels": label_audit, "docs": docs_audit, "coverage": coverage_audit, "lo": lambda: lo_audit(), "kpidefs": lambda: kpi_definition_audit(), "search": search_audit, "inventory": inventory_audit, "sample": sample_audit, "visual": visual_audit}[w]()))


