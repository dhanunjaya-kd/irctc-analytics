"""Run the whole Phase 2 pipeline: generate -> inject -> clean -> validate -> report -> sample.

    python python/src/pipeline.py

Deterministic: the same seed reproduces every file byte for byte.
"""
import sys
import time

import numpy as np
import pandas as pd

import build_reports as br
import clean_data as cl
import config as cfg
import generate_synthetic_data as gen
import inject_quality_issues as inj
import validate_data as val


def build_sample(T, n_runs=20, seed=cfg.SEED):
    """A small, referentially complete sample: all reference tables + every record of `n_runs` train runs."""
    rng = np.random.default_rng(seed)
    ops = T["train_operations"]
    pick = ops.iloc[np.sort(rng.choice(len(ops), size=n_runs, replace=False))]
    keys = set(zip(pick["train_id"], pick["run_date"]))
    S = {k: T[k] for k in ("stations", "routes", "trains", "train_stops", "calendar")}
    S["train_operations"] = pick
    cap = T["seat_capacity"]
    S["seat_capacity"] = cap[[(t, d) in keys for t, d in zip(cap["train_id"], cap["journey_date"])]]
    bk = T["bookings"]
    S["bookings"] = bk[[(t, d) in keys for t, d in zip(bk["train_id"], bk["journey_date"])]]
    ids = set(S["bookings"]["booking_id"])
    S["booking_passengers"] = T["booking_passengers"][T["booking_passengers"]["booking_id"].isin(ids)]
    S["cancellations"] = T["cancellations"][T["cancellations"]["booking_id"].isin(ids)]
    return S


def main():
    t0 = time.time()
    step = lambda msg: print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    step("1/6 generating clean synthetic truth")
    truth = gen.generate(verbose=False)
    gen.write_tables(truth, cfg.INTERIM_DIR)

    step("2/6 injecting controlled quality issues -> raw extract")
    raw, log = inj.make_raw(truth)
    inj.write_raw(raw, log)
    before = cl.file_checksums(cfg.RAW_DIR)

    step("3/6 cleaning (detection reads raw text only)")
    cleaned, res = cl.clean(raw_dir=cfg.RAW_DIR)
    cl.write_clean(cleaned)
    if cl.file_checksums(cfg.RAW_DIR) != before:
        sys.exit("ERROR: raw files were modified during cleaning")

    step("4/6 validating the cleaned data")
    T = cl.read_clean()
    results = val.run_checks(T)
    print(val.format_results(results))

    step("5/6 writing data-quality outputs, dataset profile and sample")
    br.write_dq_outputs(res, log, results)
    profile = br.dataset_profile(T)
    br.write_dq_report(res, log, results, cfg.ROOT / "docs" / "data_quality_report.md", profile)
    src_doc = cfg.ROOT / "docs" / "data_sources.md"
    if src_doc.exists():
        br.inject_profile_into(src_doc, profile)
    S = build_sample(T)
    cfg.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in S.items():
        df.to_csv(cfg.SAMPLE_DIR / f"{name}.csv", index=False)

    step("6/6 done")
    failed = [r["check"] for r in results if not r["passed"]]
    if failed:
        sys.exit(f"validation failed: {failed}")


if __name__ == "__main__":
    main()
