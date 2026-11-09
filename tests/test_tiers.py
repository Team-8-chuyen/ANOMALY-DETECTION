from copy import deepcopy
from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from itd.data.ldap import FEATURES, join_groups, load_monthly_groups
from itd.scoring.tiers import TierConfig, fit_baselines, init_history, score_days


def row(user, day, value=2, role="A", department="D"):
    return {"user_id": user, "date": day, "role": role, "department": department,
            **{name: str(value) for name in FEATURES}}


def training():
    return [row(user, day) for day in ("2020-01-30", "2020-01-31") for user in ("U1", "U2")]


@pytest.mark.parametrize("group_key", ["department", "role"])
def test_hand_calculation_weights_and_constant_features(group_key):
    config = TierConfig(group_key)
    train = training()
    baselines = fit_baselines(train, config)
    history = init_history(train, date(2020, 2, 1), config)
    original_history = deepcopy(history)
    original_mean = baselines["global"]["mean"].copy()
    results, state = score_days([row("U1", "2020-02-01", 4)], baselines, history, config)
    result = results[0]
    assert result["n_history"] == 2 and result["n_group_users"] == 2
    assert result["w_personal"] == pytest.approx(2 / 9)
    assert result["w_group"] == pytest.approx(14 / 45)
    assert result["w_global"] == pytest.approx(7 / 15)
    assert sum(result[key] for key in ("w_personal", "w_group", "w_global")) == pytest.approx(1)
    assert result["s_global"] == result["s_group"] == result["s_personal"] == pytest.approx(2)
    assert result["score"] == pytest.approx(2)
    assert history == original_history and state != history
    np.testing.assert_array_equal(baselines["global"]["mean"], original_mean)


def test_one_sided_score():
    cfg = TierConfig("role")
    base = fit_baselines(training(), cfg)
    hist = init_history(training(), date(2020, 2, 1), cfg)
    results, _ = score_days([row("U1", "2020-02-01", 1)], base, hist, cfg)
    assert results[0]["score"] == 0


def test_cold_start_missing_group_and_single_user_group():
    cfg = TierConfig("role")
    train = training() + [row("SOLO", "2020-01-31", role="S")]
    base = fit_baselines(train, cfg)
    hist = init_history(train, date(2020, 2, 1), cfg)
    results, _ = score_days([row("NEW", "2020-02-01", 5),
                            row("SOLO", "2020-02-01", 5, role="S"),
                            row("MISSING", "2020-02-01", 5, role="UNKNOWN"),
                            row("UNSEEN", "2020-02-01", 5, role="UNSEEN")], base, hist, cfg)
    for r in results:
        assert r["w_personal"] == 0
        if r["user_id"] == "NEW":
            assert r["w_group"] == pytest.approx(0.4)
        else:
            assert r["w_global"] == 1
            assert r["s_group"] is None and r["s_personal"] is None
        assert np.isfinite(r["score"])


def test_window_boundary_and_gap():
    cfg = TierConfig("role")
    train = [row("U1", "2020-01-01", 100), row("U1", "2020-01-02", 2), row("U1", "2020-01-31", 2)]
    base = fit_baselines(train, cfg)
    hist = init_history(train, date(2020, 2, 1), cfg)
    results, _ = score_days([row("U1", "2020-02-01", 4), row("U1", "2020-04-01", 4)], base, hist, cfg)
    assert results[0]["n_history"] == 2
    assert results[0]["s_personal"] == 2
    assert results[1]["n_history"] == 0
    assert results[1]["w_personal"] == 0


def test_future_invariance_day_order_and_split_continuity():
    cfg = TierConfig("role")
    base = fit_baselines(training(), cfg)
    hist = init_history(training(), date(2020, 2, 1), cfg)
    cal = [row("U1", "2020-02-01", 3), row("U2", "2020-02-01", 8)]
    test = [row("U1", "2020-02-02", 7), row("U2", "2020-02-02", 9)]
    all_results, final = score_days(cal + test, base, hist, cfg)
    first, mid = score_days(cal, base, hist, cfg)
    second, final_split = score_days(test, base, mid, cfg)
    assert all_results == first + second and final == final_split
    reordered, _ = score_days(list(reversed(cal + test)), base, hist, cfg)
    assert reordered == all_results
    altered_future, _ = score_days(cal + [row("U1", "2020-02-02", 999999)], base, hist, cfg)
    assert altered_future[:2] == first


@pytest.mark.parametrize("invalid", [
    {"k_P": 0}, {"k_G": float("nan")}, {"scale_floor": float("inf")},
    {"k_P": True}, {"min_personal_days": 1}, {"min_group_users": 1},
    {"window_days": 0}, {"window_days": True}, {"min_group_users": 2.5},
])
def test_bad_config(invalid):
    with pytest.raises(ValueError):
        TierConfig("role", **invalid)


def test_invalid_history_duplicate_rows_and_config_mismatch():
    cfg = TierConfig("role")
    base = fit_baselines(training(), cfg)
    hist = init_history(training(), date(2020, 2, 1), cfg)
    valid = [row("U1", "2020-02-01")]
    for change in ("future", "duplicate", "invalid_shape", "wrong_last", "non_iso", "non_iso_last"):
        broken = deepcopy(hist)
        if change == "future":
            broken["users"]["U1"].append(("2020-02-01", [2] * 6))
        elif change == "duplicate":
            broken["users"]["U1"].append(broken["users"]["U1"][-1])
        elif change == "invalid_shape":
            broken["users"]["U1"][-1] = ("2020-01-31", [2])
        elif change == "non_iso":
            broken["users"]["U1"][0] = ("20200130", [2] * 6)
        elif change == "non_iso_last":
            broken["last_date"] = "20200131"
        else:
            broken["last_date"] = "2020-02-01"
        with pytest.raises(ValueError):
            score_days(valid, base, broken, cfg)
    with pytest.raises(ValueError):
        score_days(valid + valid, base, hist, cfg)
    with pytest.raises(ValueError):
        score_days(valid, base, hist, replace(cfg, group_key="department"))
    with pytest.raises(ValueError):
        init_history(training(), date(2020, 1, 31), cfg)


def test_group_change_preserves_personal_history():
    config = TierConfig("role")
    base = fit_baselines(training(), config)
    hist = init_history(training(), date(2020, 2, 1), config)
    results, _ = score_days([row("U1", "2020-02-01", 4, role="UNSEEN")], base, hist, config)
    assert results[0]["n_history"] == 2
    assert results[0]["w_personal"] == pytest.approx(2 / 9)
    assert results[0]["w_group"] == 0
    assert results[0]["w_global"] == pytest.approx(7 / 9)


def test_group_members_are_distinct_and_metadata_missing_does_not_drop_rows(tmp_path):
    path = tmp_path / "2020-01.csv"
    path.write_text("user_id,role,department\nU1,A,D\nU2,B,\n", encoding="utf-8")
    metadata = {key: load_monthly_groups(tmp_path, key) for key in ("role", "department")}
    raw = [{k: v for k, v in row(user, "2020-01-02").items() if k not in {"role", "department"}}
           for user in ("U1", "U2", "UNKNOWN_USER")]
    joined = join_groups(raw, metadata)
    assert len(joined) == 3
    assert joined[1]["department"] == "UNKNOWN" and joined[1]["role"] == "B"
    assert joined[2]["role_missing"] == joined[2]["department_missing"] == 1
    base = fit_baselines([row("U1", "2020-01-01"), row("U1", "2020-01-02")], TierConfig("role"))
    assert base["groups"]["A"]["n_users"] == 1
    path.write_text("user_id,role\nU1,A\n")
    with pytest.raises(ValueError):
        load_monthly_groups(tmp_path, "department")
