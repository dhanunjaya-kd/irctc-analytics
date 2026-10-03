"""Shared helpers for building the Phase 3 workbooks with xlsxwriter.

Two-pass build: pass 1 writes formulas with no cached values; LibreOffice (UNO) then performs a REAL recalculation;
pass 2 rebuilds the file with those recalculated values stored as the cached results. The stored values therefore come from an
independent calculation engine, and the Python reference (kpi.py) is compared against them in the tests.
"""
import datetime as dt
import pathlib

import openpyxl
import xlsxwriter
from openpyxl.utils.datetime import to_excel

import lo_bridge as lb

SYNTHETIC_BANNER = ("SYNTHETIC DATA. Sampled simulation: 768 simulated train runs, compared with 19,708 scheduled runs in the modelled schedule (3.9%). "
                    "Not a representative full railway schedule and not IRCTC or Indian Railways network-wide metrics.")
SAMPLE_LABEL = ("Analytical sample: balanced by journey month (2 of the 32 simulated runs in each month) and run-complete (every booking, passenger and cancellation of each sampled run). "
                "It is not balanced by travel class, train type or weekday, has no Premium train runs and no 1A class-runs, and its results should not be generalised to the full dataset.")
PER_RUN_NOTE = ("Monthly totals reflect the sampling design (32 simulated runs per month). Use per-run and capacity-normalised measures "
                "(bookings per run, occupancy, waitlist pressure, cancellation rate) for comparisons and trends.")


class Book:
    def __init__(self, path, cache=None):
        self.wb = xlsxwriter.Workbook(str(path), {"nan_inf_to_errors": True})
        self.cache = cache or {}
        self._f = {}

    def f(self, **kw):
        k = tuple(sorted(kw.items()))
        if k not in self._f:
            base = {"font_name": "Calibri", "font_size": 10, "valign": "vcenter"}
            base.update(kw)
            self._f[k] = self.wb.add_format(base)
        return self._f[k]

    def formula(self, ws, r, c, formula, fmt=None):
        v = self.cache.get((ws.get_name(), r, c), 0)
        if isinstance(v, (dt.datetime, dt.date)):
            v = to_excel(v)
        ws.write_formula(r, c, formula, fmt, v)

    def close(self):
        self.wb.close()

    # ---- common formats
    @property
    def title(self):
        return self.f(bold=True, font_size=16, font_color="#1F3864")

    @property
    def hdr(self):
        return self.f(bold=True, bg_color="#1F3864", font_color="#FFFFFF", border=1, text_wrap=True, align="center")

    @property
    def warn(self):
        return self.f(bold=True, font_color="#9C0006", bg_color="#FFC7CE", text_wrap=True, border=1)

    @property
    def note(self):
        return self.f(italic=True, font_color="#595959", text_wrap=True)


def side_label(b, ws, row, col, text):
    """One-line, non-wrapping synthetic/sampling label placed beside a data table (does not shift any data row)."""
    ws.write_string(row, col, text, b.f(bold=True, font_color="#9C0006", bg_color="#FFC7CE"))


def read_cache(path):
    """Map (sheet, row0, col0) -> recalculated value for every formula cell in `path`."""
    wf = openpyxl.load_workbook(path, data_only=False, read_only=True)
    wv = openpyxl.load_workbook(path, data_only=True, read_only=True)
    cache = {}
    for name in wf.sheetnames:
        for rf, rv in zip(wf[name].iter_rows(), wv[name].iter_rows()):
            for cf, cv in zip(rf, rv):
                v = getattr(cf, "value", None)
                if isinstance(v, str) and v.startswith("="):
                    val = cv.value
                    cache[(name, cf.row - 1, cf.column - 1)] = "" if val is None else val
    wf.close(); wv.close()
    return cache


def two_pass(build_fn, final_path, work_dir):
    work_dir = pathlib.Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)
    p1, rc = work_dir / (pathlib.Path(final_path).stem + "_pass1.xlsx"), work_dir / (pathlib.Path(final_path).stem + "_recalc.xlsx")
    b = Book(p1); build_fn(b); b.close()
    lb.recalc_copy(p1, rc)
    cache = read_cache(rc)
    b = Book(final_path, cache); build_fn(b); b.close()
    return cache


def recalculated_values(xlsx_path, work_dir):
    """Force a real recalculation of an existing xlsx and return {sheet: openpyxl worksheet (data_only)} plus the workbook."""
    work_dir = pathlib.Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)
    rc = work_dir / (pathlib.Path(xlsx_path).stem + "_verify.xlsx")
    lb.recalc_copy(xlsx_path, rc)
    return openpyxl.load_workbook(rc, data_only=True)
