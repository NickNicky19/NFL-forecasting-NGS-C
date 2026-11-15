"""CPU-only, output-preserving inference for trusted C M3 native JSON models.

Training requires the separately pinned XGBoostLSS/Torch environment. This adapter
requires only XGBoost CPU, NumPy and SciPy. It never imports that training wrapper,
loads pickle, refits, supplies outcome labels, changes a side/ranking policy, or
establishes current roster/source admission from historical feature arrays.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.special import expit
import xgboost as xgb

SCHEMA = "C-M3-XGBoostLSS-safe-json-v1"
EXPECTED_PARAMETERS = {
    "max_depth": 3, "eta": .05, "min_child_weight": 30,
    "lambda": 10., "seed": 1703, "nthread": 1,
    "tree_method": "hist", "verbosity": 0,
}
SUPPORTED_QUERY_ROLES = frozenset(("WR", "TE"))


class NativeInference:
    """Restore one hash-bound trusted model; enforce its exact feature schema.

    Missing/nonfinite numeric values follow the trained median + missing-mask
    representation. Absent/reordered/new columns raise, rather than silently
    changing that representation. Supplied roles must be WR/TE. With roles=None,
    inference is explicitly role-unchecked and confers no product admission.
    ``last_query_contract`` reports that distinction without adding fake model
    parameters or guessing a player's eligibility.
    """

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.suffix != ".json":
            raise ValueError("Only trusted native M3 JSON model paths are supported")
        recipe_path = path.with_suffix(".recipe.json")
        recipe = json.loads(recipe_path.read_text())
        if recipe.get("schema") != SCHEMA or recipe.get("kind") not in ("nb", "student_t"):
            raise ValueError("Unexpected M3 recipe/schema/kind")
        if recipe.get("parameters") != EXPECTED_PARAMETERS or recipe.get("rounds") != 32:
            raise ValueError("Unexpected registered M3 fitting contract")
        if recipe.get("xgboost_version") != "3.1.2" or xgb.__version__ != "3.1.2":
            raise ValueError("Pinned xgboost-cpu 3.1.2 is required for this adapter")
        model_bytes = path.read_bytes()
        if len(model_bytes) > 33554432:
            raise ValueError("Native model size exceeds bounded restoration contract")
        if hashlib.sha256(model_bytes).hexdigest() != recipe.get("model_SHA256"):
            raise ValueError("Native model hash differs from its immutable recipe")
        obj = cls()
        obj.kind = recipe["kind"]
        obj.feature_names = list(recipe["feature_names"])
        obj.design_names = list(recipe["design_names"])
        obj.medians = np.asarray(recipe["training_medians"], dtype=float)
        obj.start_values = np.asarray(recipe["start_values"], dtype=float)
        d, p = len(obj.feature_names), 2 if obj.kind == "nb" else 3
        if (len(set(obj.feature_names)) != d or obj.medians.shape != (d,) or
                obj.start_values.shape != (p,) or not np.isfinite(obj.medians).all() or
                not np.isfinite(obj.start_values).all()):
            raise ValueError("Invalid primitive M3 feature/imputation/start state")
        if obj.design_names != (["v%d" % i for i in range(d)] +
                                ["missing%d" % i for i in range(d)]):
            raise ValueError("Unexpected trained median/missing feature design")
        obj.booster = xgb.Booster(params={"nthread": 1, "device": "cpu"})
        obj.booster.load_model(str(path))
        if obj.booster.num_features() != 2 * d:
            raise ValueError("Native model and primitive feature schema disagree")
        obj.model_SHA256 = recipe["model_SHA256"]
        obj.recipe_SHA256 = hashlib.sha256(recipe_path.read_bytes()).hexdigest()
        obj.last_query_contract = None
        return obj

    def predict_params(self, x, feature_names, roles=None):
        if list(feature_names) != self.feature_names:
            raise ValueError("M3 feature order/schema mismatch; unknown columns are unsupported")
        if hasattr(x, "columns") and list(x.columns) != self.feature_names:
            raise ValueError("Data-frame columns disagree with the declared feature order")
        x = np.asarray(x, dtype=float)
        if x.ndim != 2 or x.shape[1] != len(self.feature_names):
            raise ValueError("M3 feature dimensions mismatch; missing columns are unsupported")
        if roles is not None:
            roles = np.asarray(roles)
            if roles.ndim != 1 or len(roles) != len(x):
                raise ValueError("One explicit role per query row is required")
            if any(str(r) not in SUPPORTED_QUERY_ROLES for r in roles):
                raise ValueError("Unsupported/unknown role: M3 primary queries require WR or TE")
        self.last_query_contract = {
            "rows": len(x), "missing_value_count": int((~np.isfinite(x)).sum()),
            "missing_policy": "Eligible-training median plus registered missingness mask",
            "feature_schema_checked": True, "roles_checked": roles is not None,
            "role_admission": "WR_TE_ONLY" if roles is not None else "NOT_CHECKED",
            "outcomes_required": False, "current_source_admission_established": False,
        }
        keys = ("total_count", "probs") if self.kind == "nb" else ("df", "loc", "scale")
        if len(x) == 0:
            return {k: np.empty(0, dtype=float) for k in keys}
        missing = ~np.isfinite(x)
        design = np.column_stack((np.where(missing, self.medians, x), missing)).astype(float)
        dm = xgb.DMatrix(design, feature_names=self.design_names, nthread=1)
        dm.set_base_margin((np.ones((len(x), 1)) * self.start_values).flatten())
        raw = np.asarray(self.booster.predict(dm, output_margin=True),
                         dtype=np.float64).reshape(-1, len(keys))
        if not np.isfinite(raw).all():
            raise FloatingPointError("Nonfinite native M3 distribution margins")
        if self.kind == "nb":
            out = {"total_count": np.exp(raw[:, 0]) + 1e-6,
                   "probs": np.clip(expit(raw[:, 1]) + 1e-6, .001, .999)}
            valid = np.all(out["total_count"] > 0) and np.all((out["probs"] > 0) & (out["probs"] < 1))
        else:
            out = {"df": np.exp(raw[:, 0]) + 1e-6 + 2., "loc": raw[:, 1],
                   "scale": np.exp(raw[:, 2]) + 1e-6}
            valid = np.all(out["df"] > 2) and np.all(out["scale"] > 0)
        if not valid or not all(np.isfinite(v).all() for v in out.values()):
            raise FloatingPointError("Invalid native M3 parameter support")
        return out


def load(path):
    return NativeInference.load(path)
