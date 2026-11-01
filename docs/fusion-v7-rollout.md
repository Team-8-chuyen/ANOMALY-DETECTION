# Framework v7 fusion rollout

`framework.v7` is a research candidate derived from `framework.v6`. It changes
only the calibrated Feature/Sequence fusion contract:

```text
weighted_mean.v1:
risk = 0.5 * q_feature + 0.5 * q_sequence

noisy_or.v1:
risk = 1 - (1 - q_feature) * (1 - q_sequence)
```

The risk is an anomaly index, not a probability that the user is malicious.

## Missing branches

- Feature and Sequence available: apply the configured method.
- One branch available: risk equals that branch percentile.
- Both missing: `NO_SCORE`, no alert.

## Threshold rule

The v6 numeric threshold must never be reused for v7. Select a new threshold
from Validation using the unchanged label-free `0.995` empirical quantile, then
freeze it before Test.

## Isolated experiment

From `machine_learning`:

```powershell
python -m cli.run_experiment `
  --framework-config ../backend/config/framework.v7.json `
  --artifact-dir ../data/artifacts/experiment_v3 `
  --evaluation-dir ../data/evaluation/experiment_v3 `
  --epochs 20 `
  --batch-size 4 `
  --device auto
```

The separate directories prevent v7 from overwriting the reproducible v5/v6
artifacts.

## Required comparison

Compare v6 and v7 using:

- AUPRC;
- Recall at the locked threshold;
- Recall@Top-K/day;
- precision and F1;
- false positives per user-day;
- scenario-wise recall;
- no-score rate;
- percentage of scored rows with risk exactly `1.0`.

A high exact-`1.0` rate indicates empirical-CDF saturation. In that case, do
not promote v7; introduce a separately versioned smoothed ECDF contract first.

## Production activation

Do not point `FRAMEWORK_CONFIG_PATH` to v7 until:

1. Validation threshold is selected without labels.
2. Test is run once with the frozen threshold.
3. Recall improvement and false-positive budget are approved.
4. Severity bands are reviewed for the v7 risk scale.
5. The v7 checkpoint, references, config checksum and threshold release are
   stored together.

Rollback consists of restoring the previous framework config path, checkpoint,
reference artifact and corresponding locked threshold as one atomic release.
