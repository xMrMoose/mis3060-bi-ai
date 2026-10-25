# 02_clean.py
# HW4 Part C: clean the Wildcat Capital warehouse extract.
# Author: Jonah Karst
# Generated: 2026-10-25
#
# Implements decision_log.md, one decision at a time, in the logged order:
#   1. quarantine                    (D-01, D-07)  rows that will not be in the output
#   2. lossless format conversions   (D-05, D-11, D-12)
#   3. verifiable value repairs      (D-02, D-04, D-06)
#   4. fill                          (D-03)
#   5. flags                         (D-08, D-13, D-14)
#   6. row-count proof: raw = clean + quarantined, for every table
# Quarantine runs first so quarantine files hold untouched raw rows and every
# logged value change applies to a row that is in the clean output.
#
# After each step the script prints rows affected and a before/after check,
# then checks the after-state AND that the rows changed equal the count in the
# decision log (EXPECTED). If a fix does not do what the log claims, it stops
# (explicit raise, so the checks also run under python -O).
#
# Values are kept as text end to end (dtype=str, keep_default_na=False), so a
# value no step touches is written back byte-for-byte. Raw files are never
# modified (checked by hash at start and end). Nothing is written until every
# table has passed validation.
#
# Usage:  python hw04/scripts/02_clean.py
#
# Outputs:
#   hw04/data/clean/<same 8 file names>.csv
#   hw04/data/audit/cleaning_log.csv
#   hw04/data/audit/value_changes.csv
#   hw04/data/audit/quarantine_*.csv

import hashlib
from decimal import Decimal
from pathlib import Path

import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = HW_DIR / "data" / "dirty"
CLEAN_DIR = HW_DIR / "data" / "clean"
AUDIT_DIR = HW_DIR / "data" / "audit"

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]
PKS = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
       "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
       "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

# Rows each decision changes in the clean output, from decision_log.md. The
# script stops if a step changes a different number of rows than the log says.
EXPECTED = {
    "D-01": 25, "D-07": 200,
    "D-05": 197_044, "D-11": 300, "D-12a": 135, "D-12b": 756,
    "D-02": 77, "D-04": 6, "D-06": 835,
    "D-03": 75,
    "D-08": 2_410, "D-13a": 420, "D-13b": 386, "D-14": 1_475,
}

STATE_CODES = {"Pennsylvania": "PA", "Florida": "FL", "New York": "NY", "New Jersey": "NJ",
               "California": "CA", "Illinois": "IL", "Texas": "TX"}
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}
RISK_PROFILES = {"Conservative", "Moderately Conservative", "Balanced",
                 "Moderately Aggressive", "Aggressive"}
CERTIFICATIONS = {"CFA", "CFP", "CFP, CFA", "CFP, CIMA"}
SECURITY_TXN_TYPES = {"Buy", "Sell", "Dividend"}
AUM_FLOOR = 1000.0
RETURN_BOUNDS = (-0.9, 1.0)

cleaning_log = []
value_changes = []
quarantined = {}  # table -> {set name: quarantined DataFrame}


class CleaningError(Exception):
    """A fix did not do what the decision log claims."""


def check(condition, message):
    if not condition:
        raise CleaningError(message)


def log(line=""):
    print(line)


def num(series):
    """Strict text -> float; blanks become NaN."""
    return pd.to_numeric(series.where(series != ""), errors="coerce")


def plain_decimal(text):
    """Exact text rewrite of a number without scientific notation ('-1.9e-05' -> '-0.000019')."""
    return format(Decimal(text), "f")


def step(decision, table, issue, action, rows, note=""):
    """Print, record in cleaning_log, and check the count matches the decision log."""
    log(f"  rows affected: {rows:,}")
    cleaning_log.append({"decision_id": decision, "table": table, "issue": issue,
                         "action": action, "rows_affected": int(rows), "note": note})
    expected = EXPECTED.get(decision)
    check(expected is None or rows == expected,
          f"{decision}: changed {rows} rows, decision log claims {expected}")


def record_changes(table, df, mask, column, old, new):
    """Append one value_changes row per changed cell."""
    key = PKS[table]
    value_changes.append(pd.DataFrame({
        "table": table, "key_column": key, "key": df.loc[mask, key].values,
        "column": column, "old_value": old[mask].values, "new_value": new[mask].values,
    }))


def quarantine(table, set_name, df, mask, reason, extra=None):
    """Move rows out of a table into a named quarantine set; nothing is dropped silently."""
    q = df.loc[mask].copy()
    q.insert(0, "quarantine_reason", reason)
    if extra is not None:
        for col, values in extra.items():
            q[col] = values
    quarantined.setdefault(table, {})[set_name] = q
    return df.loc[~mask].copy()


def relabel(t, table, column, decision, issue, action, mask, label, allowed, note):
    """Replace masked values with a label; check the column ends up inside the allowed set."""
    df = t[table]
    old = df[column].copy()
    new = old.where(~mask, label)
    log(f"  before: {mask.sum()} values to relabel {old[mask].value_counts().to_dict()}")
    check(new.isin(allowed | {label}).all(),
          f"{table}.{column} has values outside the allowed set: {set(new) - allowed - {label}}")
    check((new[~mask] == old[~mask]).all(), f"{table}.{column}: unmasked values changed")
    record_changes(table, df, mask, column, old, new)
    df[column] = new
    log(f"  after:  every value in allowed set; {label!r} = {(new == label).sum()}")
    step(decision, table, issue, action, mask.sum(), note)


def header(decision, title):
    log()
    log(f"[{decision}] {title}")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Load ─────────────────────────────────────────────────────────────────────

def load():
    raw = {t: pd.read_csv(RAW_DIR / f"{t}.csv", dtype=str, keep_default_na=False) for t in TABLES}
    log("=" * 70)
    log("HW4 PART C - CLEANING")
    log("=" * 70)
    for t, df in raw.items():
        log(f"  {t:<26} {len(df):>9,} raw rows")
    return raw


# ── 1. Quarantine ────────────────────────────────────────────────────────────

FACTS = ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]


def d01_duplicate_clients(t):
    header("D-01", "dim_client: quarantine near-duplicate clients")
    cl = t["dim_client"]
    other = [c for c in cl.columns if c not in ("client_id", "last_name")]
    # Same client on every attribute except key and last name; keep the lowest id
    ids = cl["client_id"].astype(int)
    first_id = ids.groupby([cl[c] for c in other]).transform("min")
    mask = ids != first_id
    log(f"  before: {len(cl):,} clients; near-duplicate copies = {mask.sum()}")
    referenced = set().union(*(t[f]["client_id"] for f in FACTS))
    check(not set(cl.loc[mask, "client_id"]) & referenced,
          "a duplicate client has fact rows; quarantine would orphan them")
    t["dim_client"] = quarantine("dim_client", "dim_client_duplicates", cl, mask,
                                 "D-01 near-duplicate client",
                                 {"duplicate_of_client_id": first_id[mask].astype(str).values})
    after = t["dim_client"]
    # Independent: each kept original is the one the copy points to, and no copy survives
    kept_ids = set(after["client_id"])
    check(set(first_id[mask].astype(str)) <= kept_ids, "a duplicate's original was not kept")
    check(not after.duplicated(other).any(), "near-duplicates remain")
    log(f"  after:  {len(after):,} clients; near-duplicates remaining = 0; "
        f"fact rows referencing quarantined ids = 0")
    step("D-01", "dim_client", "client entered twice with altered last name", "quarantine",
         mask.sum(), "Kept lowest client_id (complete name, owns all activity)")


def d07_orphan_transactions(t):
    header("D-07", "fact_transactions: quarantine rows whose client_id is not in dim_client")
    tx = t["fact_transactions"]
    raw_total = num(tx["amount"]).sum()
    mask = ~tx["client_id"].isin(set(t["dim_client"]["client_id"]))
    amount = num(tx.loc[mask, "amount"]).sum()
    log(f"  before: orphan rows = {mask.sum()} ({tx.loc[mask, 'client_id'].nunique()} distinct ids), "
        f"amount ${amount:,.2f}")
    t["fact_transactions"] = quarantine("fact_transactions", "fact_transactions_orphan_client",
                                        tx, mask, "D-07 client_id not in dim_client")
    after = t["fact_transactions"]
    # Independent: every remaining row joins, and the dollars reconcile across clean + quarantine
    q_total = num(quarantined["fact_transactions"]["fact_transactions_orphan_client"]["amount"]).sum()
    check(after["client_id"].isin(set(t["dim_client"]["client_id"])).all(), "orphans remain")
    check(abs(num(after["amount"]).sum() + q_total - raw_total) < 0.01, "amount does not reconcile")
    log(f"  after:  orphan rows = 0; clean ${num(after['amount']).sum():,.2f} + quarantined "
        f"${q_total:,.2f} = raw ${raw_total:,.2f}")
    step("D-07", "fact_transactions", "orphan client_id", "quarantine", mask.sum(),
         f"Amount ${amount:,.2f}; not recreated as placeholder clients")


# ── 2. Lossless format conversions ───────────────────────────────────────────

def d05_security_id(t):
    header("D-05", "fact_transactions.security_id: '45.0' -> '45'")
    tx = t["fact_transactions"]
    dim_keys = set(t["dim_security"]["security_id"])
    sid = tx["security_id"]
    mask = sid.str.endswith(".0")
    # Only whole-number floats may be converted; anything else would be truncated
    check(sid[sid != ""].str.fullmatch(r"\d+\.0").all(), "non-integer security_id found")
    before = sid[sid != ""].isin(dim_keys).mean()
    new = sid.str.replace(r"\.0$", "", regex=True)
    record_changes("fact_transactions", tx, mask, "security_id", sid, new)
    tx["security_id"] = new
    after = new[new != ""].isin(dim_keys).mean()
    log(f"  before: {before:.1%} of non-blank keys join to dim_security | after: {after:.1%}")
    check(after == 1.0, "security_id still does not join 100%")
    check((new == "").sum() == (sid == "").sum(), "blank security_ids changed")
    step("D-05", "fact_transactions", "security_id stored as float text", "convert",
         mask.sum(), "Stripped trailing '.0'; RI to dim_security now 100%")


def alpha_gap(snap):
    return (num(snap["return_ytd"]) - num(snap["benchmark_return_ytd"])
            - num(snap["active_alpha_ytd"])).abs()


def d11_percent_returns(t):
    header("D-11", "fact_portfolio_snapshot.return_ytd: '9.28%' -> 0.0928")
    snap = t["fact_portfolio_snapshot"]
    old = snap["return_ytd"].copy()
    mask = old.str.endswith("%")
    log(f"  before: {mask.sum()} percent strings; unparseable returns = {num(old).isna().sum()}")
    new = old.copy()
    new[mask] = [format(Decimal(v.rstrip("%").strip()) / 100, "f") for v in old[mask]]
    snap["return_ytd"] = new
    # Verify the unit against two other columns: return - benchmark = alpha
    gap = alpha_gap(snap)
    passing = (gap[mask] <= 1e-4).sum()
    log(f"  after: unparseable = {num(new).isna().sum()}; converted rows passing alpha identity "
        f"= {passing} of {mask.sum()}")
    check(num(new).notna().all(), "return_ytd still has unparseable values")
    check(passing == mask.sum(), "a converted return does not reconcile to alpha")
    record_changes("fact_portfolio_snapshot", snap, mask, "return_ytd", old, new)
    step("D-11", "fact_portfolio_snapshot", "return_ytd stored as percent string", "convert",
         mask.sum(), "Stripped % and divided by 100; verified by return - benchmark = alpha")


def d12_scientific(t):
    header("D-12", "fact_portfolio_snapshot: scientific notation -> plain decimal")
    snap = t["fact_portfolio_snapshot"]
    for col, decision in [("return_ytd", "D-12a"), ("active_alpha_ytd", "D-12b")]:
        old = snap[col].copy()
        mask = old.str.contains(r"[eE]", regex=True)
        new = old.copy()
        new[mask] = old[mask].map(plain_decimal)
        example = f", e.g. {old[mask].iloc[0]} -> {new[mask].iloc[0]}" if mask.any() else ""
        log(f"  {col}: before {mask.sum()} values in e-notation{example}")
        check(not new.str.contains(r"[eE]", regex=True).any(), f"{col} still has e-notation")
        check((num(new) == num(old)).all(), f"{col} numeric value changed")
        snap[col] = new
        record_changes("fact_portfolio_snapshot", snap, mask, col, old, new)
        step(decision, "fact_portfolio_snapshot", f"{col} in scientific notation", "standardize",
             mask.sum(), "Text rewritten exactly via Decimal; numeric value unchanged")
    check(not (alpha_gap(snap) > 1e-4).any() and alpha_gap(snap).notna().all(),
          "alpha identity broken after D-12")
    log(f"  after: alpha identity holds on all {len(snap):,} snapshot rows")


# ── 3. Verifiable value repairs ──────────────────────────────────────────────

def d02_states(t):
    header("D-02", "dim_client.state: full names -> USPS codes")
    cl = t["dim_client"]
    mask = ~cl["state"].isin(US_STATES)
    unmapped = set(cl.loc[mask, "state"]) - set(STATE_CODES)
    check(not unmapped, f"no code for {unmapped}; refusing to guess")
    old = cl["state"].copy()
    new = old.replace(STATE_CODES)
    log(f"  before: {mask.sum()} non-code values {old[mask].value_counts().to_dict()}")
    check(new.isin(US_STATES).all(), "state still has non-code values")
    # Independent: each name maps to the code that already holds that state's other clients
    check(all(STATE_CODES[name] in set(old) for name in set(old[mask])), "mapped to an unused code")
    record_changes("dim_client", cl, mask, "state", old, new)
    cl["state"] = new
    log(f"  after:  0 non-code values; PA clients {(old == 'PA').sum()} -> {(new == 'PA').sum()}")
    step("D-02", "dim_client", "state spelled out", "standardize", mask.sum(),
         "Explicit 7-entry name->USPS map")


def d04_certifications(t):
    header("D-04", "dim_advisor.certifications: 'None' -> 'No Certification'")
    adv = t["dim_advisor"]
    relabel(t, "dim_advisor", "certifications", "D-04",
            "null-like token 'None' means no certification", "standardize",
            adv["certifications"] == "None", "No Certification", CERTIFICATIONS,
            "Keeps meaning; avoids parse-to-null in BI tools")


def recon_failing(tx):
    """Security rows where shares x price != amount; NaN (unparseable) counts as failing."""
    is_sec = tx["txn_type"].isin(SECURITY_TXN_TYPES)
    gap = (num(tx["shares"]) * num(tx["price"]) - num(tx["amount"])).abs()
    return is_sec & ~(gap <= 0.01)


def d06_negative_shares(t):
    header("D-06", "fact_transactions.shares: negative Buy shares -> absolute value")
    tx = t["fact_transactions"]
    old = tx["shares"].copy()
    mask = old.str.startswith("-")
    check(set(tx.loc[mask, "txn_type"]) == {"Buy"}, "negative shares outside Buy")
    # Verify before repairing: the flipped sign must reconcile shares x price = amount
    flipped = old.str.lstrip("-")
    gap_if_flipped = (num(flipped) * num(tx["price"]) - num(tx["amount"])).abs()
    check((gap_if_flipped[mask] <= 0.01).all(), "flipping the sign does not reconcile")
    log(f"  before: negative shares = {mask.sum()}; rows failing shares x price = amount "
        f"= {recon_failing(tx).sum()}")
    record_changes("fact_transactions", tx, mask, "shares", old, flipped)
    tx["shares"] = flipped
    failing = recon_failing(tx).sum()
    log(f"  after:  negative shares = {(num(tx['shares']) < 0).sum()}; rows failing = {failing}")
    check(failing == 0 and (num(tx["shares"]) < 0).sum() == 0, "D-06 reconciliation failed")
    step("D-06", "fact_transactions", "negative shares on Buy", "convert", mask.sum(),
         "abs(shares); every security row reconciles to amount within $0.01")


# ── 4. Fill ──────────────────────────────────────────────────────────────────

def d03_risk_profile(t):
    header("D-03", "dim_client.risk_profile: blank -> 'Unknown'")
    cl = t["dim_client"]
    relabel(t, "dim_client", "risk_profile", "D-03", "blank risk_profile", "fill",
            cl["risk_profile"] == "", "Unknown", RISK_PROFILES,
            "Explicit label, not an inferred profile")


# ── 5. Flags ─────────────────────────────────────────────────────────────────

def d08_flag_after_last_snapshot(t):
    header("D-08", "fact_transactions: flag_after_last_snapshot")
    tx, snap, cl = t["fact_transactions"], t["fact_portfolio_snapshot"], t["dim_client"]
    inactive = set(cl.loc[cl["is_active"] == "False", "client_id"])
    last = pd.to_datetime(snap.groupby("client_id")["snapshot_date"].max())
    month_end = pd.Series((last + pd.offsets.MonthEnd(0)).reindex(tx["client_id"]).values,
                          index=tx.index)
    # No snapshot at all = no evidence the account was ever open: every txn is "after"
    after_last = month_end.isna() | (pd.to_datetime(tx["txn_date"]) > month_end)
    is_inactive = tx["client_id"].isin(inactive)
    flag = is_inactive & after_last
    tx["flag_after_last_snapshot"] = flag.astype(int).astype(str)
    # Cross-check: active clients must never trip the rule (else the flag is not about closure)
    active_hits = (~is_inactive & after_last).sum()
    log(f"  flagged {flag.sum():,} rows from {tx.loc[flag, 'client_id'].nunique()} inactive clients; "
        f"active clients tripping the same rule = {active_hits}")
    check(active_hits == 0, "active clients transact after their last snapshot")
    # Cross-check: fees agree the account closed (no fee after the last snapshot)
    fee = t["fact_fees"]
    fee_last = pd.to_datetime(fee.groupby("client_id")["fee_date"].max())
    check((fee_last <= last.reindex(fee_last.index)).all(), "fees continue after last snapshot")
    step("D-08", "fact_transactions", "inactive client transacts after last snapshot", "flag",
         flag.sum(), "Rows kept; flag_after_last_snapshot = 1")


def d13_flag_aum_floor(t):
    header("D-13", "flag_aum_floor on fact_portfolio_snapshot and fact_fees")
    snap, fee = t["fact_portfolio_snapshot"], t["fact_fees"]
    s_flag = num(snap["aum"]) == AUM_FLOOR
    f_flag = num(fee["aum_basis"]) == AUM_FLOOR
    check((num(snap["aum"]) >= AUM_FLOOR).all(), "AUM below the floor: floor hypothesis is wrong")
    snap["flag_aum_floor"] = s_flag.astype(int).astype(str)
    fee["flag_aum_floor"] = f_flag.astype(int).astype(str)
    # Cross-table, both directions: on every client-month with a fee, the flags must agree
    m = fee[["client_id", "fee_date", "flag_aum_floor"]].merge(
        snap[["client_id", "snapshot_date", "flag_aum_floor"]],
        left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"],
        suffixes=("_fee", "_snap"), how="left")
    disagree = (m["flag_aum_floor_fee"] != m["flag_aum_floor_snap"]).sum()
    log(f"  snapshot rows flagged {s_flag.sum()}, fee rows flagged {f_flag.sum()}; "
        f"fee/snapshot client-months where flags disagree = {disagree}")
    check(disagree == 0, "fee and snapshot floor flags disagree")
    step("D-13a", "fact_portfolio_snapshot", "AUM held at $1,000 floor", "flag", s_flag.sum(),
         "Value kept; flag_aum_floor = 1")
    step("D-13b", "fact_fees", "aum_basis held at $1,000 floor", "flag", f_flag.sum(),
         "Value kept; matches snapshot flag on same client-month")


def d14_flag_return_outlier(t):
    header("D-14", "fact_portfolio_snapshot: flag_return_outlier")
    snap = t["fact_portfolio_snapshot"]
    lo, hi = RETURN_BOUNDS
    r = num(snap["return_ytd"])
    flag = (r < lo) | (r > hi)
    snap["flag_return_outlier"] = flag.astype(int).astype(str)
    # Independent: rebuild the return from benchmark + alpha and apply the same bounds
    rebuilt = num(snap["benchmark_return_ytd"]) + num(snap["active_alpha_ytd"])
    rebuilt_flag = (rebuilt < lo - 1e-4) | (rebuilt > hi + 1e-4)
    borderline = ((rebuilt - lo).abs() <= 1e-4) | ((rebuilt - hi).abs() <= 1e-4)
    mismatch = (flag != rebuilt_flag) & ~borderline
    on_floor_clients = snap.loc[flag, "client_id"].isin(
        set(snap.loc[snap["flag_aum_floor"] == "1", "client_id"])).sum()
    log(f"  flagged {flag.sum():,} rows ({(r > hi).sum()} above +100%, {(r < lo).sum()} below -90%); "
        f"{on_floor_clients} belong to clients that hit the AUM floor")
    log(f"  flag rebuilt from benchmark + alpha disagrees on {mismatch.sum()} rows")
    check(mismatch.sum() == 0, "return flag disagrees with benchmark + alpha")
    step("D-14", "fact_portfolio_snapshot", "return_ytd outside [-90%, +100%]", "flag", flag.sum(),
         "Values kept (alpha identity holds); flag_return_outlier = 1")


# ── 6. Row-count proof and save ──────────────────────────────────────────────

def prove(raw, t):
    """Validate every table before anything is written."""
    log()
    log("ROW-COUNT PROOF: raw = clean + quarantined")
    for name in TABLES:
        sets = quarantined.get(name, {})
        q_rows = sum(len(q) for q in sets.values())
        clean = t[name]
        ok = len(raw[name]) == len(clean) + q_rows
        log(f"  {name:<26} {len(raw[name]):>9,} = {len(clean):>9,} + {q_rows:>4,}  {'OK' if ok else 'FAIL'}")
        check(ok, f"{name}: rows lost or created")
        # Same columns, same order; only new flag_ columns may be appended
        n_raw = raw[name].shape[1]
        check(list(clean.columns[:n_raw]) == list(raw[name].columns), f"{name}: columns changed")
        check(all(c.startswith("flag_") for c in clean.columns[n_raw:]), f"{name}: non-flag column added")
        check(not clean[PKS[name]].duplicated().any(), f"{name}: duplicate primary key")
        # Quarantined rows are untouched raw rows
        pk = PKS[name]
        for set_name, q in sets.items():
            raw_rows = raw[name].set_index(pk).loc[q[pk], raw[name].columns.drop(pk)]
            check(q.set_index(pk)[raw_rows.columns].equals(raw_rows),
                  f"{set_name}: quarantined rows differ from raw")
    # Every logged change belongs to a row that is in the clean output
    changes = pd.concat(value_changes, ignore_index=True)
    for name in changes["table"].unique():
        check(changes.loc[changes["table"] == name, "key"].isin(set(t[name][PKS[name]])).all(),
              f"{name}: value change logged for a row not in the clean output")
    return changes


def save(t, changes):
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        t[name].to_csv(CLEAN_DIR / f"{name}.csv", index=False, lineterminator="\n")
        for set_name, q in quarantined.get(name, {}).items():
            q.to_csv(AUDIT_DIR / f"quarantine_{set_name}.csv", index=False, lineterminator="\n")
    pd.DataFrame(cleaning_log).to_csv(AUDIT_DIR / "cleaning_log.csv", index=False, lineterminator="\n")
    changes.to_csv(AUDIT_DIR / "value_changes.csv", index=False, lineterminator="\n")
    log()
    log(f"Saved 8 clean tables to {CLEAN_DIR.relative_to(HW_DIR)}")
    log(f"Saved cleaning_log.csv ({len(cleaning_log)} steps), value_changes.csv "
        f"({len(changes):,} cell changes), {sum(map(len, quarantined.values()))} quarantine files to "
        f"{AUDIT_DIR.relative_to(HW_DIR)}")


def main():
    hashes = {t: file_hash(RAW_DIR / f"{t}.csv") for t in TABLES}
    raw = load()
    t = {name: df.copy() for name, df in raw.items()}

    d01_duplicate_clients(t)
    d07_orphan_transactions(t)
    d05_security_id(t)
    d11_percent_returns(t)
    d12_scientific(t)
    d02_states(t)
    d04_certifications(t)
    d06_negative_shares(t)
    d03_risk_profile(t)
    d08_flag_after_last_snapshot(t)
    d13_flag_aum_floor(t)
    d14_flag_return_outlier(t)

    changes = prove(raw, t)
    check(all(file_hash(RAW_DIR / f"{n}.csv") == h for n, h in hashes.items()), "raw file modified")
    save(t, changes)
    log("Raw files unchanged (SHA-256 verified).")


if __name__ == "__main__":
    main()
