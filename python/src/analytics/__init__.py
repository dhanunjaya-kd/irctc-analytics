"""Phase 5 analytics layer (Python): loading, validation, cleaning, KPIs, EDA, statistics, visualisation, insights.

Everything here describes a SYNTHETIC dataset produced by a SAMPLED simulation (768 simulated train runs, compared with 19,708 scheduled
runs in the modelled schedule). Results are not IRCTC or Indian Railways network-wide metrics, and nothing here forecasts.

The package is separate from python/src/kpi.py (the Phase 3 reference implementation) on purpose: the Phase 5 KPIs are computed independently
from the cleaned base tables and then reconciled against the reference values, instead of comparing a module with itself.
"""
import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:            # makes the existing project utilities (config.py) importable from notebooks and scripts
    sys.path.insert(0, str(_SRC))

SYNTHETIC_NOTE = ("Synthetic data, sampled simulation (768 simulated runs of 19,708 scheduled). "
                  "Not IRCTC or Indian Railways network-wide data; no forecasts.")
