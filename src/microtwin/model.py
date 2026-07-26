"""Pure-Python deterministic ridge regression and held-out validation."""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

from src.microtwin.config import MicroTwinSettings
from src.microtwin.dataset import Record
from src.planning.provenance import planning_fingerprint


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    augmented = [matrix[i][:] + [vector[i]] for i in range(n)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        if abs(divisor) < 1e-12:
            divisor = 1e-12
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                a - factor * b for a, b in zip(augmented[row], augmented[column], strict=True)
            ]
    return [row[-1] for row in augmented]


@dataclass(frozen=True)
class RidgeModel:
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    target: str

    def predict(self, features: tuple[float, ...]) -> float:
        standardized = tuple(
            (value - mean) / scale
            for value, mean, scale in zip(features, self.means, self.scales, strict=True)
        )
        return self.intercept + sum(
            coef * value for coef, value in zip(self.coefficients, standardized, strict=True)
        )

    def payload(self) -> dict[str, object]:
        return {
            "model_family": "deterministic_ridge_arx",
            "target": self.target,
            "feature_names": self.feature_names,
            "means": self.means,
            "scales": self.scales,
            "coefficients": self.coefficients,
            "intercept": self.intercept,
            "schema_version": 1,
        }


def fit(records: tuple[Record, ...], settings: MicroTwinSettings, target: str) -> RidgeModel:
    columns = list(zip(*(record.features for record in records), strict=True))
    means = tuple(statistics.fmean(column) for column in columns)
    scales = tuple(max(statistics.pstdev(column), 1e-9) for column in columns)
    x = [
        [(value - means[i]) / scales[i] for i, value in enumerate(record.features)]
        for record in records
    ]
    y = [
        record.temperature_target if target == "temperature_c" else record.demand_target
        for record in records
    ]
    intercept = statistics.fmean(y)
    centered = [value - intercept for value in y]
    count = len(settings.feature_order)
    gram = [
        [
            sum(row[i] * row[j] for row in x) + (settings.ridge_alpha if i == j else 0.0)
            for j in range(count)
        ]
        for i in range(count)
    ]
    rhs = [
        sum(row[i] * value for row, value in zip(x, centered, strict=True)) for i in range(count)
    ]
    return RidgeModel(
        settings.feature_order, means, scales, tuple(_solve(gram, rhs)), intercept, target
    )


def metrics(model: RidgeModel, records: tuple[Record, ...], target: str) -> dict[str, float]:
    actual = [
        r.temperature_target if target == "temperature_c" else r.demand_target for r in records
    ]
    predicted = [model.predict(r.features) for r in records]
    demand_index = model.feature_names.index("previous_hvac_j")
    persistence = [
        r.features[0] if target == "temperature_c" else r.features[demand_index] for r in records
    ]
    errors = [p - a for p, a in zip(predicted, actual, strict=True)]
    baseline = [p - a for p, a in zip(persistence, actual, strict=True)]
    mae = statistics.fmean(abs(e) for e in errors)
    rmse = math.sqrt(statistics.fmean(e * e for e in errors))
    baseline_mae = statistics.fmean(abs(e) for e in baseline)
    baseline_rmse = math.sqrt(statistics.fmean(e * e for e in baseline))
    mean_actual = statistics.fmean(actual)
    denominator = sum((value - mean_actual) ** 2 for value in actual)
    return {
        "mae": mae,
        "rmse": rmse,
        "median_absolute_error": statistics.median(abs(e) for e in errors),
        "maximum_absolute_error": max(abs(e) for e in errors),
        "r2": 1 - sum(e * e for e in errors) / denominator if denominator else 0.0,
        "persistence_mae": baseline_mae,
        "persistence_rmse": baseline_rmse,
        "mae_improvement_fraction": (baseline_mae - mae) / baseline_mae if baseline_mae else 0.0,
        "residual_p05": sorted(errors)[int(len(errors) * 0.05)],
        "residual_p95": sorted(errors)[int(len(errors) * 0.95)],
        "residual_median": statistics.median(errors),
    }


def rollout_metrics(model: RidgeModel, records: tuple[Record, ...]) -> dict[str, float]:
    result: dict[str, float] = {}
    for horizon in (3, 6, 12):
        errors: list[float] = []
        sample_step = max(1, len(records) // 300)
        for start in range(0, len(records) - horizon, sample_step):
            predicted = records[start].features[0]
            prior = predicted - records[start].features[1]
            for offset in range(horizon):
                features = list(records[start + offset].features)
                features[0], features[1] = predicted, predicted - prior
                prior, predicted = predicted, model.predict(tuple(features))
            errors.append(predicted - records[start + horizon - 1].temperature_target)
        result[f"rollout_{horizon}_mae_c"] = statistics.fmean(abs(e) for e in errors)
        result[f"rollout_{horizon}_bias_c"] = statistics.fmean(errors)
    return result


def train_artifacts(
    settings: MicroTwinSettings,
    train: tuple[Record, ...],
    validation: tuple[Record, ...],
    test: tuple[Record, ...],
    split_fingerprint: str,
) -> dict[str, object]:
    thermal = fit(train, settings, "temperature_c")
    demand = fit(train, settings, "hvac_electricity_j_per_zone_timestep")
    thermal_metrics = metrics(thermal, test, "temperature_c")
    thermal_metrics.update(rollout_metrics(thermal, test))
    demand_metrics = metrics(demand, test, "demand")
    qualified = thermal_metrics["mae_improvement_fraction"] >= settings.minimum_improvement
    demand_qualified = demand_metrics["mae_improvement_fraction"] >= 0
    semantic = planning_fingerprint(
        {
            "thermal": thermal.payload(),
            "demand": demand.payload(),
            "split": split_fingerprint,
            "qualification": qualified,
        }
    )
    settings.model_directory.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "thermal_model.json": thermal.payload(),
        "demand_model.json": demand.payload(),
        "thermal_feature_schema.json": {
            "schema_version": 1,
            "feature_order": settings.feature_order,
            "causal_alignment": "features_t_to_target_t_plus_1",
            "prohibited_feature_count": 0,
            "training_minimums": [
                min(record.features[i] for record in train)
                for i in range(len(settings.feature_order))
            ],
            "training_maximums": [
                max(record.features[i] for record in train)
                for i in range(len(settings.feature_order))
            ],
        },
        "thermal_validation_report.json": {
            **thermal_metrics,
            "qualification_status": "QUALIFIED" if qualified else "NOT_QUALIFIED",
            "test_rows": len(test),
        },
        "demand_validation_report.json": {
            **demand_metrics,
            "qualification_status": "QUALIFIED" if demand_qualified else "UNAVAILABLE",
            "units": "J per zone timestep; whole-HVAC proxy, not SPACE3-1 attribution",
        },
        "split_manifest.json": {
            "chronological": True,
            "train_rows": len(train),
            "validation_rows": len(validation),
            "test_rows": len(test),
            "train_start": train[0].timestamp,
            "train_end": train[-1].timestamp,
            "validation_start": validation[0].timestamp,
            "validation_end": validation[-1].timestamp,
            "test_start": test[0].timestamp,
            "test_end": test[-1].timestamp,
            "split_fingerprint": split_fingerprint,
        },
        "training_data_fingerprint.json": {
            "fingerprint": planning_fingerprint(
                [(r.sequence, r.features, r.temperature_target, r.demand_target) for r in train]
            ),
            "prohibited_feature_count": 0,
        },
        "model_manifest.json": {
            "schema_version": 1,
            "model_id": semantic,
            "semantic_fingerprint": semantic,
            "thermal_qualification": qualified,
            "demand_qualification": demand_qualified,
            "source_run": settings.source_run,
            "environment_id": settings.environment_id,
            "safe_serialization": "JSON",
            "limitations": [
                "offline EnergyPlus surrogate",
                "not safety authority",
                "no verified savings",
            ],
        },
    }
    for name, payload in artifacts.items():
        (settings.model_directory / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return artifacts


def load_model(path: Path) -> RidgeModel:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RidgeModel(
        tuple(raw["feature_names"]),
        tuple(raw["means"]),
        tuple(raw["scales"]),
        tuple(raw["coefficients"]),
        float(raw["intercept"]),
        str(raw["target"]),
    )
