# 扩展线性
import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, Lasso, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def _options_to_dict(options):
    if options is not None and not isinstance(options, dict):
        to_py = getattr(options, "to_py", None)
        if callable(to_py):
            return to_py()
    return options or {}


def _fig_to_svg(fig):
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")


def _make_model(model_type, alpha, l1_ratio):
    if model_type == "ridge":
        return Ridge(alpha=alpha)
    if model_type == "lasso":
        return Lasso(alpha=alpha, max_iter=10000)
    if model_type == "elasticnet":
        return ElasticNet(alpha=alpha, l1_ratio=l1_ratio, max_iter=10000)
    raise ValueError("模型类型必须是 ridge、lasso 或 elasticnet")


def _coerce_float(value, default):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception:
        return default


def analyze(options):
    options = _options_to_dict(options)

    data_path = options.get("data_path")
    if not data_path:
        return {"error": "请先在左侧上传数据文件"}

    model_type = str(options.get("model_type", "ridge")).strip().lower()
    target_col = str(options.get("target_col") or "").strip()
    alpha = max(_coerce_float(options.get("alpha"), 1.0), 0.000001)
    l1_ratio = min(max(_coerce_float(options.get("l1_ratio"), 0.5), 0.0), 1.0)
    test_size = min(max(_coerce_float(options.get("test_size"), 0.25), 0.1), 0.5)

    try:
        df = pd.read_csv(data_path)
    except Exception as e:
        return {"error": f"读取数据失败: {e}"}

    numeric_df = df.select_dtypes(include=[np.number]).dropna(axis=0)
    if numeric_df.shape[1] < 2:
        return {"error": "至少需要 2 个数值列：一个因变量和至少一个自变量"}
    if numeric_df.shape[0] < 5:
        return {"error": "有效样本数太少，至少需要 5 行完整数值数据"}

    if not target_col:
        target_col = numeric_df.columns[-1]
    if target_col not in numeric_df.columns:
        return {"error": f"因变量列不存在或不是数值列: {target_col}"}

    y = numeric_df[target_col].to_numpy(dtype=float)
    x_df = numeric_df.drop(columns=[target_col])
    feature_names = x_df.columns.tolist()
    x = x_df.to_numpy(dtype=float)

    if len(feature_names) < 1:
        return {"error": "至少需要 1 个数值自变量"}

    try:
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=test_size, random_state=42
        )
    except Exception as e:
        return {"error": f"划分训练集和测试集失败: {e}"}

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    x_test_scaled = scaler.transform(x_test)

    try:
        model = _make_model(model_type, alpha, l1_ratio)
        model.fit(x_train_scaled, y_train)
    except Exception as e:
        return {"error": f"模型训练失败: {e}"}

    y_pred = model.predict(x_test_scaled)
    residuals = y_test - y_pred

    r2 = r2_score(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))

    svgs = []

    fig1, ax1 = plt.subplots(figsize=(7, 5))
    ax1.scatter(y_test, y_pred, color="steelblue", edgecolors="#1e3b5c", alpha=0.75)
    min_val = min(float(np.min(y_test)), float(np.min(y_pred)))
    max_val = max(float(np.max(y_test)), float(np.max(y_pred)))
    ax1.plot([min_val, max_val], [min_val, max_val], "--", color="crimson", linewidth=1.5)
    ax1.set_title("真实值 vs 预测值")
    ax1.set_xlabel("真实值")
    ax1.set_ylabel("预测值")
    ax1.grid(alpha=0.25, linestyle="--")
    svgs.append(_fig_to_svg(fig1))

    fig2, ax2 = plt.subplots(figsize=(7, 5))
    ax2.scatter(y_pred, residuals, color="darkorange", edgecolors="#7a4b00", alpha=0.75)
    ax2.axhline(0, linestyle="--", color="crimson", linewidth=1.5)
    ax2.set_title("残差诊断图")
    ax2.set_xlabel("预测值")
    ax2.set_ylabel("残差")
    ax2.grid(alpha=0.25, linestyle="--")
    svgs.append(_fig_to_svg(fig2))

    coef_rows = [
        [name, f"{coef:.6f}"]
        for name, coef in zip(feature_names, model.coef_)
    ]
    coef_rows.sort(key=lambda row: abs(float(row[1])), reverse=True)

    metric_rows = [
        ["模型", model_type],
        ["因变量", target_col],
        ["训练样本数", str(len(y_train))],
        ["测试样本数", str(len(y_test))],
        ["R²", f"{r2:.4f}"],
        ["RMSE", f"{rmse:.4f}"],
        ["MAE", f"{mae:.4f}"],
        ["alpha", f"{alpha:.4f}"],
        ["l1_ratio", f"{l1_ratio:.4f}" if model_type == "elasticnet" else "N/A"],
    ]

    print(f"模型: {model_type}")
    print(f"因变量: {target_col}")
    print(f"自变量数量: {len(feature_names)}")
    print(f"有效样本数: {len(numeric_df)}")

    return {
        "svgs": svgs,
        "metrics": {
            "样本数": len(numeric_df),
            "变量数": len(feature_names),
            "R²": f"{r2:.4f}",
            "RMSE": f"{rmse:.4f}",
        },
        "tables": [
            {"header": ["变量", "标准化系数"], "rows": coef_rows},
            {"header": ["指标", "值"], "rows": metric_rows},
        ],
    }
