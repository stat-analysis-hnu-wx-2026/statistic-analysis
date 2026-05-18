import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import FactorAnalysis
import io


def analyze(options):
    if not isinstance(options, dict):
        options = options.to_py()

    data_path = options.get('data_path')
    if not data_path:
        return {"error": "请先在左侧上传数据文件"}

    try:
        df = pd.read_csv(data_path)
    except Exception as e:
        return {"error": f"读取数据失败: {e}"}

    first_col = df.columns[0]
    if df[first_col].dtype == 'object':
        sample_labels = df[first_col].tolist()
        df_numeric = df.drop(columns=[first_col])
    else:
        sample_labels = [f"S{i+1}" for i in range(len(df))]
        df_numeric = df.copy()

    df_numeric = df_numeric.select_dtypes(include=[np.number]).dropna()
    if df_numeric.shape[1] < 3:
        return {"error": f"数值变量仅 {df_numeric.shape[1]} 个，至少需要 3 个"}

    n_samples, n_features = df_numeric.shape
    feature_names = df_numeric.columns.tolist()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_numeric.values)

    corr = np.corrcoef(X_scaled, rowvar=False)
    eig_vals = np.linalg.eigvalsh(corr)[::-1]

    n_factors = int(np.sum(eig_vals > 1))
    max_factors = min(n_features, n_samples - 1)
    if n_factors < 1:
        n_factors = min(2, max_factors)
    elif n_factors > max_factors:
        n_factors = max_factors

    svgs = []

    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(range(1, n_features + 1), eig_vals, 'bo-', markersize=6, linewidth=2)
    ax1.axhline(y=1, color='r', linestyle='--', alpha=0.7, label='特征值=1')
    ax1.set_xlabel('因子序号', fontsize=11)
    ax1.set_ylabel('特征值', fontsize=11)
    ax1.set_title('碎石图 (Scree Plot)', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.3, linestyle='--')
    ax1.set_xticks(range(1, n_features + 1))
    fig1.tight_layout()
    buf = io.BytesIO()
    fig1.savefig(buf, format='svg')
    plt.close(fig1)
    svgs.append(buf.getvalue().decode())

    fa = FactorAnalysis(n_components=n_factors, random_state=42, rotation='varimax')
    fa.fit(X_scaled)
    loadings = fa.components_.T
    scores = fa.transform(X_scaled)

    communality = np.sum(loadings**2, axis=1)

    variance = np.sum(loadings**2, axis=0)
    total_var = np.sum(variance)
    if total_var > 0:
        proportion_var = variance / total_var
    else:
        proportion_var = np.ones(n_factors) / n_factors
    cumulative_var = np.cumsum(proportion_var)

    factor_names = [f'Factor {i+1}' for i in range(n_factors)]

    fig2, ax2 = plt.subplots(figsize=(8, max(4, n_features * 0.35)))
    im = ax2.imshow(loadings, aspect='auto', cmap='coolwarm', vmin=-1, vmax=1)
    ax2.set_xticks(range(n_factors))
    ax2.set_xticklabels(factor_names, fontsize=10)
    ax2.set_yticks(range(n_features))
    ax2.set_yticklabels(feature_names, fontsize=10)
    ax2.set_title('旋转后因子载荷热图', fontsize=13, fontweight='bold')
    for i in range(n_features):
        for j in range(n_factors):
            val = loadings[i, j]
            c = 'white' if abs(val) > 0.5 else 'black'
            ax2.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=8, color=c)
    fig2.colorbar(im, ax=ax2, shrink=0.8)
    fig2.tight_layout()
    buf = io.BytesIO()
    fig2.savefig(buf, format='svg')
    plt.close(fig2)
    svgs.append(buf.getvalue().decode())

    if n_factors >= 2:
        fig3, ax3 = plt.subplots(figsize=(8, 6))
        ax3.scatter(scores[:, 0], scores[:, 1], c='steelblue', s=60, alpha=0.7, edgecolors='#1e3b5c')
        for i, lbl in enumerate(sample_labels[:len(scores)]):
            ax3.annotate(lbl, (scores[i, 0], scores[i, 1]),
                        textcoords="offset points", xytext=(5, 5), fontsize=7, alpha=0.8)
        ax3.axhline(y=0, color='grey', linestyle='--', alpha=0.5)
        ax3.axvline(x=0, color='grey', linestyle='--', alpha=0.5)
        ax3.set_xlabel('Factor 1', fontsize=11)
        ax3.set_ylabel('Factor 2', fontsize=11)
        ax3.set_title('前两个因子得分图（旋转后）', fontsize=13, fontweight='bold')
        ax3.grid(alpha=0.3, linestyle='--')
        fig3.tight_layout()
        buf = io.BytesIO()
        fig3.savefig(buf, format='svg')
        plt.close(fig3)
        svgs.append(buf.getvalue().decode())

    loadings_header = ['变量'] + factor_names + ['共同度']
    loadings_rows = []
    for i, vn in enumerate(feature_names):
        row = [vn] + [f'{loadings[i, j]:.4f}' for j in range(n_factors)] + [f'{communality[i]:.4f}']
        loadings_rows.append(row)

    var_header = ['因子', '方差', '贡献率', '累积贡献率']
    var_rows = []
    for j in range(n_factors):
        var_rows.append([
            f'Factor {j+1}',
            f'{variance[j]:.4f}',
            f'{proportion_var[j]:.1%}',
            f'{cumulative_var[j]:.1%}'
        ])

    scores_header = ['样本'] + [f'F{j+1}' for j in range(n_factors)]
    scores_rows = []
    for i in range(min(10, n_samples)):
        row = [sample_labels[i]] + [f'{scores[i, j]:.4f}' for j in range(n_factors)]
        scores_rows.append(row)

    return {
        "svgs": svgs,
        "metrics": {
            "提取因子数": n_factors,
            "变量数": n_features,
            "样本数": n_samples,
            "累积贡献率": f"{cumulative_var[-1]:.1%}"
        },
        "tables": [
            {"header": loadings_header, "rows": loadings_rows},
            {"header": var_header, "rows": var_rows},
            {"header": scores_header, "rows": scores_rows},
        ],
    }
