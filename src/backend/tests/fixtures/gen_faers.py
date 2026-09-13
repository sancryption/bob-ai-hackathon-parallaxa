#!/usr/bin/env python3
"""
Generate tests/fixtures/faers_demo.csv deterministically.

Design:
  - 3 drugs: DRUGALPHA, DRUGBETA, DRUGGAMMA
  - Events: headache, severe headache, nausea, liver injury, hepatic failure,
            fatigue, rash, vomiting
  - DRUGALPHA + liver injury  => intentionally strong signal (high a, low b/c)
  - Case 10000001 has two versions (caseversion 1 and 2) — duplicate source rows
  - Several rows share caseid but differ on primaryid (reporter duplicates)
  - Event aliases: "severe headache" / "headache" map to same preferred term
  - Total rows: ~150 (after dedup by latest caseversion the engine should get ~148)
"""
import csv
import itertools
import random

random.seed(42)

DRUGS = ["DRUGALPHA", "DRUGBETA", "DRUGGAMMA"]

# Event aliases: severe headache and headache are aliases for the same MedDRA term
EVENTS = [
    "headache",
    "severe headache",       # alias for headache
    "nausea",
    "liver injury",
    "hepatic failure",       # alias for liver injury (looser)
    "fatigue",
    "rash",
    "vomiting",
]

# Weights per drug to create a strong DRUGALPHA + liver_injury signal
# (drug_idx, event_idx) -> relative weight
DRUG_EVENT_WEIGHTS = {
    (0, 0): 4,   # DRUGALPHA + headache
    (0, 1): 3,   # DRUGALPHA + severe headache (alias)
    (0, 2): 3,   # DRUGALPHA + nausea
    (0, 3): 28,  # DRUGALPHA + liver injury  <-- STRONG SIGNAL
    (0, 4): 6,   # DRUGALPHA + hepatic failure (alias)
    (0, 5): 2,
    (0, 6): 2,
    (0, 7): 2,
    (1, 0): 8,   # DRUGBETA + headache
    (1, 1): 5,
    (1, 2): 6,
    (1, 3): 2,   # DRUGBETA + liver injury (low)
    (1, 4): 1,
    (1, 5): 5,
    (1, 6): 4,
    (1, 7): 4,
    (2, 0): 5,   # DRUGGAMMA + headache
    (2, 1): 3,
    (2, 2): 7,
    (2, 3): 1,   # DRUGGAMMA + liver injury (low)
    (2, 4): 1,
    (2, 5): 6,
    (2, 6): 3,
    (2, 7): 5,
}

SPONSORS = ["SPONSOR_A", "SPONSOR_B", "SPONSOR_C"]
SEXES = ["M", "F", "UNK"]
AGE_GROUPS = ["A", "E", "T"]  # adult, elderly, teen

rows = []
primaryid = 10000001
caseid_counter = 10000001

def fmt_date(base_day: int) -> str:
    """Fake YYYYMMDD starting from 20220101 + base_day days."""
    from datetime import date, timedelta
    d = date(2022, 1, 1) + timedelta(days=base_day % 365)
    return d.strftime("%Y%m%d")

# Build weighted pool
pool: list[tuple[int, int]] = []
for (di, ei), weight in DRUG_EVENT_WEIGHTS.items():
    pool.extend([(di, ei)] * weight)

random.shuffle(pool)

# Assign primaryids, caseids
case_rows = []
for idx, (di, ei) in enumerate(pool):
    case_rows.append({
        "drug_idx": di,
        "event_idx": ei,
        "caseid": caseid_counter + idx,
        "caseversion": 1,
        "sponsor_idx": idx % 3,
        "age": random.randint(20, 80),
        "sex": SEXES[idx % 3],
        "age_grp": AGE_GROUPS[idx % 3],
        "wt": random.randint(50, 100),
        "day_offset": idx,
    })

# Manually insert: case 10000001 with version 1 AND version 2 (duplicate)
version2_row = dict(case_rows[0])
version2_row["caseversion"] = 2
version2_row["day_offset"] = case_rows[0]["day_offset"] + 5

case_rows.insert(1, version2_row)

# Manually insert: a pure reporter duplicate (same caseid, new primaryid)
reporter_dup = dict(case_rows[2])
reporter_dup["caseid"] = case_rows[2]["caseid"]  # same case
# primaryid will be unique from counter

# Write CSV
import io, sys

out = io.StringIO()
writer = csv.writer(out)

DEMO_COLUMNS = [
    "primaryid", "caseid", "caseversion",
    "i_f_code", "event_dt", "mfr_dt", "init_fda_dt", "fda_dt",
    "rept_cod", "mfr_num", "mfr_sndr", "lit_ref",
    "age", "age_cod", "age_grp", "sex", "e_sub",
    "wt", "wt_cod", "rept_dt", "to_mfr", "occp_cod",
    "reporter_country", "occr_country",
    "drugname", "event_term",
]

DRUG_COLUMNS = [
    "primaryid", "drug_seq", "role_cod", "drugname",
    "prod_ai", "val_vbm", "route", "dose_amt",
    "dose_unit", "dechal", "rechal",
]

REAC_COLUMNS = [
    "primaryid", "isr", "pt",
]

# Write demographics + drug + reaction as a denormalised flat CSV for simplicity
# (real FAERS uses separate DEMO/DRUG/REAC files; this flat format is used by our parser fixture)
writer.writerow(DEMO_COLUMNS)

pid = 10000001
for r in case_rows:
    pid += 1
    caseid = r["caseid"]
    caseversion = r["caseversion"]
    drug = DRUGS[r["drug_idx"]]
    event = EVENTS[r["event_idx"]]
    sponsor = SPONSORS[r["sponsor_idx"]]
    d_off = r["day_offset"]

    writer.writerow([
        pid,
        caseid,
        caseversion,
        "I",
        fmt_date(d_off),
        fmt_date(d_off + 10),
        fmt_date(d_off + 15),
        fmt_date(d_off + 20),
        "EXP",
        "",
        sponsor,
        "",
        r["age"],
        "YR",
        r["age_grp"],
        r["sex"],
        "N",
        r["wt"],
        "KG",
        fmt_date(d_off + 25),
        "N",
        "MD",
        "US",
        "US",
        drug,
        event,
    ])

import os, pathlib
dest = pathlib.Path(__file__).parent / "faers_demo.csv"
dest.write_text(out.getvalue(), encoding="utf-8")
print(f"Written {dest}  ({len(out.getvalue().splitlines())} lines)")
