"""Gaussian model-X/TSKI research harness; never an automatic causal gate.

TSKI Algorithm 1: Chi, Fan, Ing, Lv, arXiv:2112.09851v3.
Uses a swap-equivariant ridge coefficient difference, not the paper's Lasso
power theorem. Rowwise Gaussian knockoffs are exact under the declared IID
Gaussian law; thinning dependent rows does not itself prove valid e-values.
"""

from __future__ import annotations

import numpy as np

from .contracts import digest, finite, integer


def gaussian_knockoffs(x, covariance, *, mean=None, seed=0):
    x = np.asarray(x, dtype=float)
    cov = np.asarray(covariance, dtype=float)
    if (
        x.ndim != 2
        or not np.isfinite(x).all()
        or cov.shape != (x.shape[1], x.shape[1])
        or not np.isfinite(cov).all()
        or not np.allclose(cov, cov.T)
    ):
        raise ValueError("finite matrix and symmetric covariance required")
    eigen = np.linalg.eigvalsh(cov)
    if eigen[0] <= 1e-8:
        raise ValueError("strictly positive definite known covariance required")
    p = x.shape[1]
    mu = np.zeros(p) if mean is None else np.asarray(mean, dtype=float)
    if mu.shape != (p,) or not np.isfinite(mu).all():
        raise ValueError("known finite mean required")
    s = np.eye(p) * min(1.0, 2 * eigen[0]) * 0.95
    a = np.eye(p) - np.linalg.solve(cov, s)
    conditional = 2 * s - s @ np.linalg.solve(cov, s)
    noise = np.random.default_rng(seed).normal(size=x.shape)
    knock = mu + (x - mu) @ a + noise @ np.linalg.cholesky(conditional).T
    joint = np.block([[cov, cov - s], [cov - s, cov]])
    swap_errors = []
    for j in range(p):
        perm = np.arange(2 * p)
        perm[j], perm[p + j] = perm[p + j], perm[j]
        swap_errors.append(float(np.max(np.abs(joint - joint[np.ix_(perm, perm)]))))
    return knock, {
        "S": s.tolist(),
        "conditional_covariance": conditional.tolist(),
        "row_exchangeability_max_error": max(swap_errors),
        "min_joint_eigenvalue": float(np.linalg.eigvalsh(joint)[0]),
        "response_not_used": True,
        "A": a.tolist(),
    }


def coefficient_difference(x, knock, y, *, ridge=1.0):
    x = np.asarray(x, dtype=float)
    knock = np.asarray(knock, dtype=float)
    y = np.asarray(y, dtype=float)
    if (
        x.shape != knock.shape
        or y.shape != (len(x),)
        or not np.isfinite(y).all()
        or finite(ridge, "ridge") <= 0
    ):
        raise ValueError("aligned observations and positive symmetric ridge required")
    z = np.column_stack((x, knock))
    z = z - z.mean(axis=0)
    z = z / np.maximum(z.std(axis=0), 1e-12)
    beta = np.linalg.solve(z.T @ z + ridge * np.eye(z.shape[1]), z.T @ (y - y.mean()))
    p = x.shape[1]
    return np.abs(beta[:p]) - np.abs(beta[p:])


def knockoff_evalues(w, *, threshold_level):
    w = np.asarray(w, dtype=float)
    if (
        w.ndim != 1
        or not np.isfinite(w).all()
        or not 0 < finite(threshold_level, "threshold_level") < 1
    ):
        raise ValueError("finite W and threshold in (0,1) required")
    threshold = None
    for t in sorted(set(np.abs(w[w != 0]))):
        if (1 + sum(w <= -t)) / max(1, sum(w >= t)) <= threshold_level:
            threshold = float(t)
            break
    e = (
        np.zeros(len(w))
        if threshold is None
        else len(w) * (w >= threshold) / (1 + sum(w <= -threshold))
    )
    return e, threshold


def e_bh(values, *, alpha):
    values = np.asarray(values, dtype=float)
    if (
        values.ndim != 1
        or not np.isfinite(values).all()
        or np.any(values < 0)
        or not 0 < finite(alpha, "alpha") < 1
    ):
        raise ValueError("nonnegative finite e-values and alpha required")
    order = np.argsort(-values, kind="stable")
    k = 0
    p = len(values)
    for rank, index in enumerate(order, 1):
        if values[index] >= p / (alpha * rank):
            k = rank
    return sorted(order[:k].tolist())


def run_knockoff_research(
    *,
    x,
    y,
    feature_ids,
    covariance,
    known_mean=None,
    temporal_rho=0.0,
    distribution_known=False,
    distribution_ref=None,
    subsample_gap=0,
    alpha=0.1,
    threshold_level=0.1,
    seed=0,
):
    if type(distribution_known) is not bool:
        raise ValueError("distribution_known must be an explicit boolean")
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if (
        x.ndim != 2
        or not 20 <= len(x) <= 5000
        or not 2 <= x.shape[1] <= 100
        or y.shape != (len(x),)
        or not np.isfinite(y).all()
    ):
        raise ValueError("bounded aligned research matrix required")
    if len(feature_ids) != x.shape[1] or len(set(feature_ids)) != len(feature_ids):
        raise ValueError("unique feature identifiers required")
    gap = integer(subsample_gap, "subsample_gap")
    rho = finite(temporal_rho, "rho")
    if not 0 <= gap <= 20 or abs(rho) >= 1:
        raise ValueError("bounded stationary AR coefficient and thinning gap required")
    knock, construction = gaussian_knockoffs(x, covariance, mean=known_mean, seed=seed)
    w = coefficient_difference(x, knock, y)
    flip = []
    for j in range(x.shape[1]):
        xx = x.copy()
        kk = knock.copy()
        xx[:, j], kk[:, j] = knock[:, j], x[:, j]
        actual = coefficient_difference(xx, kk, y)
        expected = w.copy()
        expected[j] *= -1
        flip.append(float(np.max(np.abs(actual - expected))))
    # Analytic full-matrix swap diagnosis for the declared separable AR law.
    cov = np.asarray(covariance)
    a = np.asarray(construction["A"])
    c = np.asarray(construction["conditional_covariance"])
    probe_n = 4
    r = rho ** np.abs(np.arange(probe_n)[:, None] - np.arange(probe_n)[None, :])
    original = np.kron(r, cov)
    cross = np.kron(r, cov @ a)
    other = np.kron(r, a.T @ cov @ a) + np.kron(np.eye(probe_n), c)
    joint = np.block([[original, cross], [cross.T, other]])
    p = x.shape[1]
    np_ = probe_n * p
    full_swap = []
    for j in range(p):
        perm = np.arange(2 * np_)
        left = np.arange(probe_n) * p + j
        right = left + np_
        perm[left], perm[right] = right, left
        full_swap.append(float(np.max(np.abs(joint - joint[np.ix_(perm, perm)]))))
    folds = []
    for offset in range(gap + 1):
        indices = np.arange(offset, len(x), gap + 1)
        if len(indices) < 20:
            raise ValueError("insufficient rows per thinning fold")
        ww = coefficient_difference(x[indices], knock[indices], y[indices])
        ev, threshold = knockoff_evalues(ww, threshold_level=threshold_level)
        folds.append(
            {
                "offset": offset,
                "rows": indices.tolist(),
                "W": ww.tolist(),
                "evalues": ev.tolist(),
                "threshold": threshold,
            }
        )
    averaged = np.mean([f["evalues"] for f in folds], axis=0)
    selected = e_bh(averaged, alpha=alpha)
    discrepancy = float(
        np.max(np.abs(np.cov(x, rowvar=False) - cov)) / max(np.max(np.abs(cov)), 1e-12)
    )
    conditional_eligible = bool(
        distribution_known
        and distribution_ref
        and abs(rho) < 1e-12
        and max(flip) < 1e-7
        and discrepancy < 0.5
    )
    report = {
        "schema": "knockoff-research/1",
        "feature_ids": feature_ids,
        "null": "Y independent of X_j conditional on remaining X at registered row target",
        "construction": construction,
        "flip_sign_max_error": max(flip),
        "full_temporal_swap_error": max(full_swap),
        "marginal_covariance_discrepancy": discrepancy,
        "rho_after_thinning": rho ** (gap + 1),
        "folds": folds,
        "averaged_evalues": averaged.tolist(),
        "research_selected": [feature_ids[j] for j in selected],
        "eligible_under_declared_iid_gaussian_model": conditional_eligible,
        "formal_selection_allowed": False,
        "causal_eligible": False,
        "qualification": "conditional IID Gaussian experiment"
        if conditional_eligible
        else "diagnostic_only_unverified_joint_model_or_dependence",
        "unverified_conditions": []
        if conditional_eligible
        else [
            "joint law accuracy/KL",
            "beta-mixing and subsampling rate",
            "finite-sample dependence error",
        ],
        "power_theorem": "Lasso-specific theorem not claimed for ridge statistic",
        "distribution_ref": distribution_ref,
        "seed": seed,
        "alpha": alpha,
        "source": "https://arxiv.org/html/2112.09851v3",
    }
    report["digest"] = digest(report)
    return report
