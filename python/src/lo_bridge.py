"""Thin LibreOffice (UNO) bridge used to (a) force a real recalculation of xlsx files for validation and
(b) create real PivotTables (DataPilot tables) that xlsxwriter/openpyxl cannot create.

LibreOffice does not recalculate xlsx files on load, so plain `soffice --convert-to` returns the cached values
that the writer stored. Loading through UNO and calling calculateAll() forces genuine recalculation.
"""
import os
import signal
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue


def kill_office():
    """Kill any soffice process (no killall/pkill dependency: scan /proc)."""
    me = os.getpid()
    for d in os.listdir("/proc"):
        if d.isdigit() and int(d) != me:
            try:
                comm = open(f"/proc/{d}/comm").read().strip()
                if comm.startswith("soffice"):
                    os.kill(int(d), signal.SIGKILL)
            except Exception:
                pass


def pv(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


@contextmanager
def office(port=2002, timeout=120):
    kill_office()
    time.sleep(1)
    proc = subprocess.Popen(
        ["soffice", "--headless", "--invisible", "--norestore", "--nologo", f"--accept=socket,host=127.0.0.1,port={port};urp;"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        ctx, t0 = None, time.time()
        while ctx is None and time.time() - t0 < timeout:
            try:
                ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
            except Exception:
                time.sleep(1)
        if ctx is None:
            raise RuntimeError("could not connect to LibreOffice within %ss" % timeout)
        yield ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass
        kill_office()


def load(desktop, path):
    return desktop.loadComponentFromURL(Path(path).resolve().as_uri(), "_blank", 0, (pv("Hidden", True),))


def save_xlsx(doc, path):
    doc.storeToURL(Path(path).resolve().as_uri(), (pv("FilterName", "Calc MS Excel 2007 XML"),))


def recalc_copy(src, dst):
    """Load src, force a full recalculation, and save the recalculated result to dst (xlsx)."""
    with office() as desktop:
        doc = load(desktop, src)
        doc.calculateAll()
        save_xlsx(doc, dst)
        doc.close(True)


def error_cells(doc):
    """Count formula cells whose result is an error, per sheet (uses the sheet's formula-result query; no cell-by-cell scan)."""
    FORMULA_RESULT_ERROR = 4
    out = {}
    for i in range(doc.Sheets.Count):
        sh = doc.Sheets.getByIndex(i)
        try:
            n = sum((a.EndRow - a.StartRow + 1) * (a.EndColumn - a.StartColumn + 1) for a in sh.queryFormulaCells(FORMULA_RESULT_ERROR).RangeAddresses)
        except Exception:
            n = -1
        out[sh.Name] = n
    return out


def read_range(doc, sheet, rng):
    return doc.Sheets.getByName(sheet).getCellRangeByName(rng).DataArray
