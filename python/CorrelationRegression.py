import io
import re
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as st


EPS = 1e-12


def _to_py_dict(options):
    if options is None:
        return {}
    if isinstance(options, dict):
        return options
    to_py = getattr(options, "to_py", None)
    if callable(to_py):
        return to_py()
    return dict(options)


def _split_columns(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,，、;；\s]+", text) if part.strip()]


def _fmt_float(value, digits: int = 4) -> str:
    try:
        v = float(value)
    except Exception:
        return "-"
    if not np.isfinite(v):
        if np.isposinf(v):
            return "inf"
        if np.isneginf(v):
            return "-inf"
        return "-"
    return f"{v:.{digits}f}"


def _fmt_p(value) -> str:
    try:
        v = float(value)
    except Exception:
        return "-"
    if not np.isfinite(v):
        return "-"
    if v < 0.001:
        return "<0.001"
    return f"{v:.4f}"


def _stars(p_value: float) -> str:
    if not np.isfinite(p_value):
        return "-"
    if p_value <= 0.001:
        return "***"
    if p_value <= 0.01:
        return "**"
    if p_value <= 0.05:
        return "*"
    return ""


def _fig_to_svg(fig) -> str:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")


def _read_selected_data(data_path: str, y_col: str, x_cols: List[str]) -> Tuple[pd.DataFrame, List[str], int]:
    try:
        df = pd.read_csv(data_path)
    except Exception as exc:
        raise ValueError(f"读取数据失败: {exc}")

    df = df.rename(columns=lambda c: str(c).strip())
    y_col = str(y_col).strip()
    x_cols = [str(c).strip() for c in x_cols]
    selected = [y_col] + x_cols

    missing = [c for c in selected if c not in df.columns]
    if missing:
        raise ValueError(f"数据中找不到列: {', '.join(missing)}")

    numeric = pd.DataFrame(index=df.index)
    bad_cols = []
    for col in selected:
        numeric[col] = pd.to_numeric(df[col], errors="coerce")
        if numeric[col].notna().sum() == 0:
            bad_cols.append(col)
    if bad_cols:
        raise ValueError(f"以下列无法转换为数值: {', '.join(bad_cols)}")

    before = len(numeric)
    numeric = numeric.dropna(axis=0, how="any")
    dropped = before - len(numeric)
    if len(numeric) < 3:
        raise ValueError("有效样本数不足，至少需要 3 行完整数值数据。")

    constant_cols = [col for col in selected if numeric[col].max() - numeric[col].min() <= EPS]
    if constant_cols:
        raise ValueError(f"以下列为常量列，无法进行相关或回归分析: {', '.join(constant_cols)}")

    return numeric, selected, dropped


def _correlation_table(data: pd.DataFrame, cols: List[str]) -> Dict[str, object]:
    rows = []
    header = ["变量"] + cols
    for i, row_col in enumerate(cols):
        row = [row_col]
        for j, col in enumerate(cols):
            if i == j:
                row.append("------")
            elif i > j:
                r, _ = st.pearsonr(data[row_col], data[col])
                row.append(_fmt_float(r, 4))
            else:
                _, p_value = st.pearsonr(data[row_col], data[col])
                star = _stars(p_value)
                row.append(star if star else _fmt_p(p_value))
        rows.append(row)
    return {"header": header, "rows": rows}


def _plot_correlation_heatmap(data: pd.DataFrame, cols: List[str]) -> str:
    corr = data[cols].corr().to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(7.5, 6))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right")
    ax.set_yticklabels(cols)
    ax.set_title("Pearson 相关系数矩阵")
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center", fontsize=9, color="#1f2d3d")
    return _fig_to_svg(fig)


def _fit_ols(y: np.ndarray, x: np.ndarray, x_names: List[str], alpha: float) -> Dict[str, object]:
    y = np.asarray(y, dtype=float).reshape(-1)
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)

    n = y.shape[0]
    p = x.shape[1]
    k = p + 1
    df_resid = n - k
    if p < 1:
        raise ValueError("至少需要 1 个自变量。")
    if df_resid <= 0:
        raise ValueError(f"有效样本数不足：n={n}，模型参数数={k}，无法进行显著性检验。")

    design = np.column_stack([np.ones(n), x])
    rank = np.linalg.matrix_rank(design)
    if rank < k:
        raise ValueError("自变量之间存在完全共线性，无法估计完整回归模型。")

    xtx = design.T @ design
    xtx_inv = np.linalg.inv(xtx)
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    fitted = design @ beta
    resid = y - fitted

    y_bar = y.mean()
    sse = float(np.sum(resid ** 2))
    sst = float(np.sum((y - y_bar) ** 2))
    ssr = float(np.sum((fitted - y_bar) ** 2))
    mse = sse / df_resid
    rmse = float(np.sqrt(max(mse, 0.0)))
    r2 = 1.0 - sse / sst if sst > EPS else np.nan
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / df_resid if np.isfinite(r2) else np.nan

    cov = mse * xtx_inv
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t_values = beta / se
    p_values = np.array([2 * st.t.sf(abs(t), df_resid) if np.isfinite(t) else 0.0 for t in t_values])
    t_crit = st.t.ppf(1 - alpha / 2, df_resid)
    ci_low = beta - t_crit * se
    ci_high = beta + t_crit * se

    if p > 0 and mse > EPS:
        f_value = (ssr / p) / mse
        f_p = st.f.sf(f_value, p, df_resid)
    elif p > 0 and sse <= EPS:
        f_value = np.inf
        f_p = 0.0
    else:
        f_value = np.nan
        f_p = np.nan

    sigma2 = max(sse / n, EPS)
    aic = n * np.log(sigma2) + 2 * k
    bic = n * np.log(sigma2) + np.log(n) * k
    leverage = np.sum((design @ xtx_inv) * design, axis=1)
    denom = np.sqrt(np.maximum(mse * (1 - leverage), EPS))
    std_resid = resid / denom
    condition_number = float(np.linalg.cond(design))

    return {
        "n": n,
        "p": p,
        "k": k,
        "df_model": p,
        "df_resid": df_resid,
        "x_names": x_names,
        "beta": beta,
        "se": se,
        "t": t_values,
        "p_values": p_values,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "fitted": fitted,
        "resid": resid,
        "std_resid": std_resid,
        "sse": sse,
        "ssr": ssr,
        "sst": sst,
        "mse": mse,
        "rmse": rmse,
        "r2": r2,
        "adj_r2": adj_r2,
        "multiple_r": float(np.sqrt(max(r2, 0.0))) if np.isfinite(r2) else np.nan,
        "f": f_value,
        "f_p": f_p,
        "aic": float(aic),
        "bic": float(bic),
        "condition_number": condition_number,
    }


def _coefficient_table(model: Dict[str, object], alpha: float) -> Dict[str, object]:
    names = ["Intercept"] + list(model["x_names"])
    rows = []
    for i, name in enumerate(names):
        rows.append([
            name,
            _fmt_float(model["beta"][i], 4),
            _fmt_float(model["se"][i], 4),
            _fmt_float(model["t"][i], 4),
            _fmt_p(model["p_values"][i]),
            _fmt_float(model["ci_low"][i], 4),
            _fmt_float(model["ci_high"][i], 4),
        ])
    ci_label = f"{int(round((1 - alpha) * 100))}% CI"
    return {"header": ["项", "估计值", "标准误", "t", "p", f"{ci_label} 下限", f"{ci_label} 上限"], "rows": rows}


def _summary_table(model: Dict[str, object], y_col: str) -> Dict[str, object]:
    rows = [
        ["因变量", y_col],
        ["有效样本数", str(model["n"])],
        ["自变量数", str(model["p"])],
        ["残差自由度", str(model["df_resid"])],
        ["R²", _fmt_float(model["r2"], 4)],
        ["调整 R²", _fmt_float(model["adj_r2"], 4)],
        ["复相关 R", _fmt_float(model["multiple_r"], 4)],
        ["F 统计量", _fmt_float(model["f"], 4)],
        ["F 检验 p 值", _fmt_p(model["f_p"])],
        ["RMSE", _fmt_float(model["rmse"], 4)],
        ["SSE", _fmt_float(model["sse"], 4)],
        ["AIC", _fmt_float(model["aic"], 4)],
        ["BIC", _fmt_float(model["bic"], 4)],
        ["条件数", _fmt_float(model["condition_number"], 2)],
    ]
    return {"header": ["指标", "值"], "rows": rows}


def _nested_model_table(data: pd.DataFrame, y_col: str, x_cols: List[str], alpha: float) -> Dict[str, object]:
    y = data[y_col].to_numpy(dtype=float)
    rows = []
    for i in range(1, len(x_cols) + 1):
        names = x_cols[:i]
        try:
            model = _fit_ols(y, data[names].to_numpy(dtype=float), names, alpha)
            rows.append([
                f"M{i}",
                " + ".join(names),
                _fmt_float(model["r2"], 4),
                _fmt_float(model["adj_r2"], 4),
                _fmt_float(model["f"], 4),
                _fmt_p(model["f_p"]),
                _fmt_float(model["aic"], 2),
                _fmt_float(model["bic"], 2),
            ])
        except Exception as exc:
            rows.append([f"M{i}", " + ".join(names), "-", "-", "-", str(exc), "-", "-"])
    return {"header": ["模型", "自变量", "R²", "调整 R²", "F", "p", "AIC", "BIC"], "rows": rows}


def _residual_table(data: pd.DataFrame, y_col: str, model: Dict[str, object]) -> Dict[str, object]:
    rows = []
    limit = min(12, model["n"])
    for i in range(limit):
        rows.append([
            str(data.index[i]),
            _fmt_float(data[y_col].iloc[i], 4),
            _fmt_float(model["fitted"][i], 4),
            _fmt_float(model["resid"][i], 4),
            _fmt_float(model["std_resid"][i], 4),
        ])
    return {"header": ["序号", "实际值", "拟合值", "残差", "标准化残差"], "rows": rows}


def _plot_simple_fit(data: pd.DataFrame, y_col: str, x_col: str, alpha: float) -> str:
    x = data[[x_col]].to_numpy(dtype=float)
    y = data[y_col].to_numpy(dtype=float)
    model = _fit_ols(y, x, [x_col], alpha)
    order = np.argsort(x[:, 0])

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(x[:, 0], y, s=42, alpha=0.78, color="#2a5c8a", edgecolors="#16364f")
    ax.plot(x[order, 0], model["fitted"][order], color="#c0392b", linewidth=2.2)
    ax.set_title(f"一元线性回归: {y_col} ~ {x_col}")
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.grid(alpha=0.25)
    equation = f"{y_col} = {model['beta'][0]:.4f} + {model['beta'][1]:.4f} * {x_col}"
    ax.text(0.02, 0.96, equation, transform=ax.transAxes, va="top", fontsize=9,
            bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#d6e0ea", "alpha": 0.9})
    return _fig_to_svg(fig)


def _plot_diagnostics(y: np.ndarray, model: Dict[str, object], y_col: str) -> str:
    fitted = model["fitted"]
    resid = model["resid"]
    std_resid = model["std_resid"]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    ax = axes[0]
    ax.scatter(fitted, y, s=38, alpha=0.78, color="#2a5c8a", edgecolors="#16364f")
    low = min(float(np.min(fitted)), float(np.min(y)))
    high = max(float(np.max(fitted)), float(np.max(y)))
    ax.plot([low, high], [low, high], color="#c0392b", linestyle="--", linewidth=1.6)
    ax.set_title("实际值 vs 拟合值")
    ax.set_xlabel("拟合值")
    ax.set_ylabel(y_col)
    ax.grid(alpha=0.25)

    ax = axes[1]
    ax.scatter(fitted, std_resid, s=38, alpha=0.78, color="#3d7a57", edgecolors="#214d34")
    ax.axhline(0, color="#c0392b", linestyle="--", linewidth=1.5)
    ax.axhline(2, color="#8a9aaa", linestyle=":", linewidth=1.0)
    ax.axhline(-2, color="#8a9aaa", linestyle=":", linewidth=1.0)
    ax.set_title("标准化残差 vs 拟合值")
    ax.set_xlabel("拟合值")
    ax.set_ylabel("标准化残差")
    ax.grid(alpha=0.25)
    return _fig_to_svg(fig)


def _plot_qq(model: Dict[str, object]) -> str:
    fig, ax = plt.subplots(figsize=(6.8, 5))
    st.probplot(model["std_resid"], dist="norm", plot=ax)
    ax.set_title("残差 Q-Q 图")
    ax.grid(alpha=0.25)
    return _fig_to_svg(fig)


def _placeholder_table(header: List[str], message: str) -> Dict[str, object]:
    return {"header": header, "rows": [[message] + ["-"] * (len(header) - 1)]}


def analyze(options=None) -> Dict[str, object]:
    try:
        opts = _to_py_dict(options)
        data_path = opts.get("data_path")
        if not data_path:
            return {"error": "请先在左侧上传数据文件。"}

        analysis_type = str(opts.get("analysis_type", "all")).strip().lower()
        if analysis_type not in {"all", "correlation", "simple", "multiple"}:
            analysis_type = "all"

        y_col = str(opts.get("y_col", "")).strip()
        x_cols = _split_columns(opts.get("x_cols"))
        alpha = float(opts.get("alpha") or 0.05)
        if not (0 < alpha < 1):
            alpha = 0.05

        if not y_col:
            return {"error": "请填写因变量 Y 的列名。"}
        if not x_cols:
            return {"error": "请填写至少 1 个自变量 X 的列名。"}

        # 去重并避免把 Y 同时作为 X。
        x_cols = list(dict.fromkeys(x_cols))
        x_cols = [c for c in x_cols if c != y_col]
        if not x_cols:
            return {"error": "自变量不能与因变量完全相同。"}

        data, selected_cols, dropped = _read_selected_data(data_path, y_col, x_cols)
        y = data[y_col].to_numpy(dtype=float)
        regression_cols = x_cols[:1] if analysis_type == "simple" else x_cols
        run_regression = analysis_type in {"all", "simple", "multiple"}

        svgs = [_plot_correlation_heatmap(data, selected_cols)]
        tables = [
            _correlation_table(data, selected_cols),
            _placeholder_table(["项", "估计值", "标准误", "t", "p", "CI 下限", "CI 上限"], "未运行回归模型"),
            _placeholder_table(["指标", "值"], "未运行回归模型"),
            _placeholder_table(["模型", "自变量", "R²", "调整 R²", "F", "p", "AIC", "BIC"], "未运行回归模型"),
            _placeholder_table(["序号", "实际值", "拟合值", "残差", "标准化残差"], "未运行回归模型"),
        ]
        metrics = {
            "n": str(len(data)),
            "p": str(len(regression_cols) if run_regression else len(x_cols)),
            "R": "--",
            "R2": "--",
            "adj_R2": "--",
            "RMSE": "--",
        }

        print(f"读取数据完成：有效样本 {len(data)} 行，选中变量 {', '.join(selected_cols)}。")
        if dropped:
            print(f"已删除包含缺失值或非数值转换失败的记录 {dropped} 行。")
        print("相关矩阵：下三角为 Pearson r，上三角为显著性标记（* p<=0.05，** p<=0.01，*** p<=0.001）。")

        if run_regression:
            x = data[regression_cols].to_numpy(dtype=float)
            model = _fit_ols(y, x, regression_cols, alpha)
            tables[1] = _coefficient_table(model, alpha)
            tables[2] = _summary_table(model, y_col)
            tables[3] = _nested_model_table(data, y_col, regression_cols, alpha)
            tables[4] = _residual_table(data, y_col, model)
            metrics = {
                "n": str(model["n"]),
                "p": str(model["p"]),
                "R": _fmt_float(model["multiple_r"], 4),
                "R2": _fmt_float(model["r2"], 4),
                "adj_R2": _fmt_float(model["adj_r2"], 4),
                "RMSE": _fmt_float(model["rmse"], 4),
            }
            if analysis_type in {"all", "simple"}:
                svgs.append(_plot_simple_fit(data, y_col, x_cols[0], alpha))
            elif len(regression_cols) == 1:
                svgs.append(_plot_simple_fit(data, y_col, regression_cols[0], alpha))
            svgs.append(_plot_diagnostics(y, model, y_col))
            svgs.append(_plot_qq(model))
            print(f"OLS 模型：{y_col} ~ {' + '.join(regression_cols)}")
            print(f"R^2={model['r2']:.4f}, 调整R^2={model['adj_r2']:.4f}, F检验p={_fmt_p(model['f_p'])}, RMSE={model['rmse']:.4f}")

        return {
            "svgs": svgs,
            "metrics": metrics,
            "tables": tables,
        }
    except Exception as exc:
        return {"error": str(exc)}
