"""Causal three-tier statistical scoring (SPEC-002 §4)."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from itertools import groupby

import numpy as np

from itd.data.ldap import FEATURES


@dataclass(frozen=True)
class TierConfig:
    group_key: str
    window_days: int = 30
    scale_floor: float = 1.0
    k_P: float = 7.0
    k_G: float = 3.0
    min_personal_days: int = 2
    min_group_users: int = 2

    def __post_init__(self):
        if self.group_key not in {"role", "department"}:
            raise ValueError("invalid group_key")
        for name in ("scale_floor", "k_P", "k_G"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        for name, minimum in (("window_days", 1), ("min_personal_days", 2), ("min_group_users", 2)):
            value = getattr(self, name)
            if type(value) is not int or value < minimum:
                raise ValueError(f"invalid {name}")


def _records(rows: list[dict]) -> list[tuple]:
    if not rows:
        raise ValueError("rows must not be empty")
    records, seen = [], set()
    for row in rows:
        user = row["user_id"].strip()
        day = date.fromisoformat(row["date"])
        if not user or day.isoformat() != row["date"] or (user, day) in seen:
            raise ValueError("empty user, invalid date or duplicate user-day")
        seen.add((user, day))
        values = np.array([float(row[name]) for name in FEATURES], dtype=float)
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError("features must be finite and non-negative")
        records.append((day, user, values, row))
    return sorted(records, key=lambda record: (record[0], record[1]))


def _stats(values) -> dict:
    matrix = np.asarray(values, dtype=float)
    with np.errstate(over="raise", invalid="raise"):
        try:
            return {"mean": matrix.mean(axis=0), "std": matrix.std(axis=0), "n_samples": len(matrix)}
        except FloatingPointError as error:
            raise ValueError("baseline statistics overflow") from error


def fit_baselines(train_rows: list[dict], config: TierConfig) -> dict:
    records = _records(train_rows)
    groups = {}
    for _, user, values, row in records:
        group = row.get(config.group_key, "UNKNOWN").strip() or "UNKNOWN"
        if group != "UNKNOWN":
            entry = groups.setdefault(group, {"values": [], "users": set()})
            entry["values"].append(values)
            entry["users"].add(user)
    return {
        "global": _stats([record[2] for record in records]),
        "groups": {name: {**_stats(entry["values"]), "n_users": len(entry["users"])}
                   for name, entry in sorted(groups.items())},
        "group_key": config.group_key, "train_start": records[0][0].isoformat(),
        "train_end": records[-1][0].isoformat(), "config": asdict(config),
    }


def init_history(train_rows: list[dict], first_day: date, config: TierConfig) -> dict:
    records = _records(train_rows)
    if records[-1][0] >= first_day:
        raise ValueError("history train rows must precede scoring")
    users = {}
    for day, user, values, _ in records:
        if day >= first_day - timedelta(days=config.window_days):
            users.setdefault(user, []).append((day.isoformat(), values.tolist()))
    return {"last_date": records[-1][0].isoformat(), "users": users}


def _validate_history(history: dict, first_day: date) -> None:
    last = date.fromisoformat(history["last_date"]) if history["last_date"] else None
    if last is not None and last.isoformat() != history["last_date"]:
        raise ValueError("history last_date must use YYYY-MM-DD")
    if last is not None and last >= first_day:
        raise ValueError("scoring must start after history last_date")
    for entries in history["users"].values():
        previous = None
        for raw_day, raw_values in entries:
            day = date.fromisoformat(raw_day)
            if day.isoformat() != raw_day:
                raise ValueError("history dates must use YYYY-MM-DD")
            values = np.asarray(raw_values, dtype=float)
            if (last is None or day > last or day >= first_day
                    or (previous is not None and day <= previous)):
                raise ValueError("history contains duplicate, unordered or future records")
            if values.shape != (len(FEATURES),) or not np.isfinite(values).all() or (values < 0).any():
                raise ValueError("invalid history values")
            previous = day


def _score(values: np.ndarray, baseline: dict, floor: float) -> float:
    # SPEC-002 §4.2: one-sided deviations, equal feature contributions.
    with np.errstate(over="raise", invalid="raise"):
        try:
            result = float(np.maximum(0, (values - baseline["mean"]) /
                                      np.maximum(baseline["std"], floor)).mean())
        except FloatingPointError as error:
            raise ValueError("anomaly score overflow") from error
    if not np.isfinite(result):
        raise ValueError("anomaly score is not finite")
    return result


def score_days(rows: list[dict], baselines: dict, history: dict, config: TierConfig) -> tuple[list[dict], dict]:
    records = _records(rows)
    if baselines["config"] != asdict(config):
        raise ValueError("baseline/config mismatch")
    if records[0][0] <= date.fromisoformat(baselines["train_end"]):
        raise ValueError("score dates must follow train")
    _validate_history(history, records[0][0])
    state, output = deepcopy(history), []
    for day, daily_records in groupby(records, key=lambda record: record[0]):
        daily = list(daily_records)
        cutoff = (day - timedelta(days=config.window_days)).isoformat()
        state["users"] = {user: [item for item in entries if item[0] >= cutoff]
                          for user, entries in state["users"].items()}
        state["users"] = {user: entries for user, entries in state["users"].items() if entries}
        for _, user, values, row in daily:
            past = state["users"].get(user, [])
            n = len(past)
            group = row.get(config.group_key, "UNKNOWN").strip() or "UNKNOWN"
            group_baseline = baselines["groups"].get(group)
            m = group_baseline["n_users"] if group_baseline else 0
            # SPEC-002 §4.3: n counts days, m counts distinct employees.
            w_p = n / (n + config.k_P) if n >= config.min_personal_days else 0.0
            r_g = m / (m + config.k_G) if m >= config.min_group_users else 0.0
            w_g = (1.0 - w_p) * r_g
            w_o = 1.0 - w_p - w_g
            s_o = _score(values, baselines["global"], config.scale_floor)
            s_p = _score(values, _stats([item[1] for item in past]), config.scale_floor) if w_p else None
            s_g = _score(values, group_baseline, config.scale_floor) if w_g else None
            score = w_o * s_o + (w_p * s_p if w_p else 0) + (w_g * s_g if w_g else 0)
            output.append({"user_id": row["user_id"], "date": day.isoformat(),
                           "group_key": config.group_key, "group_value": group,
                           "n_history": n, "n_group_users": m, "s_global": s_o,
                           "s_group": s_g, "s_personal": s_p, "w_global": w_o,
                           "w_group": w_g, "w_personal": w_p, "score": score})
        # SPEC-002 §4.4: no row from t enters history before all t scores exist.
        for _, user, values, _ in daily:
            state["users"].setdefault(user, []).append((day.isoformat(), values.tolist()))
        state["last_date"] = day.isoformat()
    return output, state
