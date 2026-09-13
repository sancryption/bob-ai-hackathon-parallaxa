import csv
from collections import Counter, defaultdict

rows = list(csv.DictReader(open("tests/fixtures/faers_demo.csv", encoding="utf-8")))
total = len(rows)
drug_event = Counter((r["drugname"], r["event_term"]) for r in rows)
print(f"Total rows (incl dupes): {total}")
print()
print("Top 10 drug-event pairs:")
for (d, e), n in drug_event.most_common(10):
    print(f"  {d:12s}  {e:20s}  {n}")
print()
by_case = defaultdict(set)
for r in rows:
    by_case[r["caseid"]].add(r["caseversion"])
multi = {k: v for k, v in by_case.items() if len(v) > 1}
print(f"Cases with multiple versions: {len(multi)}")
for c, vs in list(multi.items())[:3]:
    print(f"  caseid={c}  versions={sorted(vs)}")
print()
aliases = [r for r in rows if r["event_term"] in ("severe headache", "headache")]
print(f"Alias rows (headache variants): {len(aliases)}")
drugs_seen = set(r["drugname"] for r in rows)
print(f"Distinct drugs: {sorted(drugs_seen)}")
