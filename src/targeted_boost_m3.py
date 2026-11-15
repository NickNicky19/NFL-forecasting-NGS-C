"""Pinned, safe-JSON XGBoostLSS wrappers for the bounded C M3 experiment.

This module never samples forecasts, loads pickle, chooses settings from test
outcomes, or changes the existing empirical-law controls.  A Student-t fit uses
the package's continuous-density NLL; integer-bin probabilities are a separate
declared inference operation, not a claim of discrete-likelihood training.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch
import xgboost as xgb
from xgboostlss.model import XGBoostLSS
from xgboostlss.distributions.NegativeBinomial import NegativeBinomial
from xgboostlss.distributions.StudentT import StudentT

from laws_v2 import design, medians

ROUND_COUNT = 32
PARAMETERS = {
    "max_depth": 3, "eta": .05, "min_child_weight": 30,
    "lambda": 10., "seed": 1703, "nthread": 1,
    "tree_method": "hist", "verbosity": 0,
}
SCHEMA = "C-M3-XGBoostLSS-safe-json-v1"


def distribution(kind, stabilization="L2"):
    if kind in ("rec", "count", "nb"):
        return NegativeBinomial(stabilization=stabilization,
            response_fn_total_count="exp", response_fn_probs="sigmoid",
            loss_fn="nll", initialize=False)
    if kind in ("rec_yd", "yards", "student_t"):
        return StudentT(stabilization=stabilization, response_fn="exp",
                        loss_fn="nll", initialize=False)
    raise ValueError("Unsupported registered M3 distribution")


def start_values(y, kind):
    """Eligible-training-only moment initialization; no iterative optimizer."""
    y = np.asarray(y, dtype=float)
    if y.ndim != 1 or not len(y) or not np.isfinite(y).all():
        raise ValueError("Finite nonempty training labels required")
    mean, variance = float(y.mean()), float(y.var())
    if kind in ("rec", "count", "nb"):
        if np.any(y < 0) or np.any(y != np.floor(y)):
            raise ValueError("Receptions require nonnegative integer labels")
        mu = max(.05, mean)
        r = float(np.clip(mu * mu / max(variance - mu, .01), .05, 10000.))
        # Package exp_fn adds 1e-6; sigmoid adds 1e-6 then clamps to [.001,.999].
        p = float(np.clip(mu / (r + mu), .001001, .998999))
        inverse_p = p - 1e-6
        return [math.log(r - 1e-6), math.log(inverse_p / (1 - inverse_p))]
    if kind in ("rec_yd", "yards", "student_t"):
        scale = max(.05, math.sqrt(variance * 3. / 5.))
        return [math.log(3. - 1e-6), mean, math.log(scale - 1e-6)]
    raise ValueError("Unsupported registered M3 distribution")


class DistributionBoost:
    """A complete fixed-settings booster with training-only imputation.

    ``predict_params`` returns a dict of one-dimensional parameter arrays in
    native distribution names.  Feature names, if supplied, must match exactly.
    ``save(path.json)`` writes native XGBoost JSON plus ``path.recipe.json``.
    """

    def __init__(self, kind):
        self.kind = "nb" if kind in ("rec", "count", "nb") else "student_t"
        self.dist = distribution(kind)

    def _matrix(self, x, feature_names=None):
        x = np.asarray(x, dtype=float)
        if x.ndim != 2 or x.shape[1] != len(self.feature_names):
            raise ValueError("M3 feature dimension mismatch")
        if feature_names is not None and list(feature_names) != self.feature_names:
            raise ValueError("M3 feature order mismatch")
        return xgb.DMatrix(design(x, self.medians), feature_names=self.design_names,
                           nthread=1)

    def fit(self, x, y, feature_names=None):
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        if x.ndim != 2 or len(x) != len(y) or not len(x):
            raise ValueError("Aligned nonempty training matrix/labels required")
        self.feature_names = (list(feature_names) if feature_names is not None
                              else ["f%d" % i for i in range(x.shape[1])])
        if len(self.feature_names) != x.shape[1] or len(set(self.feature_names)) != x.shape[1]:
            raise ValueError("Unique feature names required")
        # Use safe native names independent of user-facing schema punctuation.
        self.design_names = (["v%d" % i for i in range(x.shape[1])] +
                             ["missing%d" % i for i in range(x.shape[1])])
        self.medians = medians(x)
        self.start_values = start_values(y, self.kind)
        self.model = XGBoostLSS(self.dist)
        self.model.start_values = self.start_values
        data = self._matrix(x, self.feature_names)
        data.set_label(y)
        self.evals_result = {}
        # XGBoostLSS mutates params with its num_target/base_score contract.
        self.model.train(dict(PARAMETERS), data, num_boost_round=ROUND_COUNT,
                         verbose_eval=False)
        self.booster = self.model.booster
        self.training_rows = len(y)
        return self

    def predict_params(self, x, feature_names=None):
        data = self._matrix(x, feature_names)
        if not data.num_row():
            return {k: np.empty(0, dtype=float) for k in self.dist.param_dict}
        # Mirror the released library's base margin and response functions in
        # float64.  Native Torch float32 sigmoid can differ by one ULP between
        # a one-row and a vector call even when booster margins are identical.
        # This is deterministic numeric adaptation, not a changed trained law.
        from scipy.special import expit
        data.set_base_margin((np.ones((data.num_row(), 1)) *
                              np.asarray(self.start_values)).flatten())
        raw = np.asarray(self.booster.predict(data, output_margin=True),
                         dtype=np.float64).reshape(-1, self.dist.n_dist_param)
        if not np.isfinite(raw).all():
            raise FloatingPointError("Nonfinite M3 raw distribution margins")
        if self.kind == "nb":
            out = {"total_count": np.exp(raw[:, 0]) + 1e-6,
                   "probs": np.clip(expit(raw[:, 1]) + 1e-6, .001, .999)}
        else:
            out = {"df": np.exp(raw[:, 0]) + 1e-6 + 2., "loc": raw[:, 1],
                   "scale": np.exp(raw[:, 2]) + 1e-6}
        if not all(np.isfinite(v).all() for v in out.values()):
            raise FloatingPointError("Nonfinite M3 distribution parameters")
        if self.kind == "nb":
            if np.any(out["total_count"] <= 0) or np.any(out["probs"] <= 0) or np.any(out["probs"] >= 1):
                raise FloatingPointError("Invalid negative-binomial parameters")
        elif np.any(out["df"] <= 2) or np.any(out["scale"] <= 0):
            raise FloatingPointError("Student-t variance/support contract failed")
        return out

    def feature_usage(self):
        return {k: float(v) for k, v in self.booster.get_score(importance_type="weight").items()}

    def save(self, path):
        path = Path(path)
        if path.suffix != ".json":
            raise ValueError("M3 model export must be native JSON")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.booster.save_model(str(path))
        sidecar = {
            "schema": SCHEMA, "kind": self.kind,
            "feature_names": self.feature_names, "design_names": self.design_names,
            "training_medians": self.medians.tolist(), "start_values": self.start_values,
            "training_rows": self.training_rows, "parameters": PARAMETERS,
            "rounds": ROUND_COUNT, "xgboost_version": xgb.__version__,
            "torch_version": torch.__version__, "xgboostlss_version": "0.6.1",
            "model_SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "loss": "continuous_density_nll" if self.kind == "student_t" else "count_nll",
            "serialization": "native XGBoost JSON plus primitive JSON sidecar; no pickle",
        }
        recipe = path.with_suffix(".recipe.json")
        recipe.write_text(json.dumps(sidecar, sort_keys=True, indent=2, allow_nan=False) + "\n")
        return {"model": str(path), "recipe": str(recipe), "model_SHA256": sidecar["model_SHA256"]}

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.suffix != ".json":
            raise ValueError("Only native JSON models are supported")
        recipe = json.loads(path.with_suffix(".recipe.json").read_text())
        if recipe["schema"] != SCHEMA or recipe["parameters"] != PARAMETERS or recipe["rounds"] != ROUND_COUNT:
            raise ValueError("Unexpected M3 recipe contract")
        if hashlib.sha256(path.read_bytes()).hexdigest() != recipe["model_SHA256"]:
            raise ValueError("M3 model hash mismatch")
        obj = cls(recipe["kind"])
        obj.feature_names, obj.design_names = recipe["feature_names"], recipe["design_names"]
        obj.medians = np.asarray(recipe["training_medians"], dtype=float)
        obj.start_values, obj.training_rows = recipe["start_values"], recipe["training_rows"]
        if not np.isfinite(obj.medians).all() or not np.isfinite(obj.start_values).all():
            raise ValueError("Nonfinite M3 primitive state")
        obj.booster = xgb.Booster(params={"nthread": 1})
        obj.booster.load_model(str(path))
        return obj


def fit(x, y, kind, feature_names=None):
    return DistributionBoost(kind).fit(x, y, feature_names)


def load(path):
    return DistributionBoost.load(path)
