import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from sklearn.decomposition import PCA as SKPCA
import io


def pca(options):

    if not isinstance(options, dict):
        options = options.to_py()
    n_components = options.get('n_components') or None
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
        sample_labels = [f"sample{i+1}" for i in range(len(df))]
        df_numeric = df.copy()

    df_numeric = df_numeric.select_dtypes(include=[np.number])
    constant_cols = df_numeric.columns[df_numeric.std() < 1e-10].tolist()
    if constant_cols:
        df_numeric = df_numeric.drop(columns=constant_cols)

    feature_names = df_numeric.columns.tolist()
    n_samples, n_features = df_numeric.shape

    if n_features < 2:
        return {"error": f"数值变量仅 {n_features} 个，至少需要 2 个"}

    from sklearn.preprocessing import StandardScaler
    X_scaled = StandardScaler().fit_transform(df_numeric.values)

    

    max_pc = min(n_samples, n_features)
    if n_components is None:
        n_components = min(max_pc, 6)
    else:
        n_components = int(min(n_components, max_pc))

    pca_full = SKPCA()
    pca_full.fit(X_scaled)

    pca_model = SKPCA(n_components=n_components)
    scores = pca_model.fit_transform(X_scaled)
    loadings = pca_model.components_.T
    explained_var = pca_model.explained_variance_ratio_
    cum_var = np.cumsum(explained_var)

    pc_names = [f'PC{i+1}' for i in range(n_components)]

    svgs = []

    # 图1: 方差解释比例柱状图
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    colors1 = plt.cm.Blues(np.linspace(0.4, 0.9, n_components))
    bars = ax1.bar(pc_names, explained_var, color=colors1, edgecolor='#1e3b5c', linewidth=1.2)
    for b, v in zip(bars, explained_var):
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01,
                 f'{v:.1%}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax1.set_ylabel('Proportion of variance explained', fontsize=11)
    ax1.set_title('Explained variance ratio for each principal component', fontsize=13, fontweight='bold')
    ax1.set_ylim(0, max(explained_var) * 1.25)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    fig1.tight_layout()
    buf = io.BytesIO()
    fig1.savefig(buf, format='svg')
    plt.close(fig1)
    svgs.append(buf.getvalue().decode())

    # 图2: 累积方差折线图
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    cum_var_full = np.cumsum(pca_full.explained_variance_ratio_)
    pc_range = range(1, len(cum_var_full) + 1)
    ax2.plot(pc_range, cum_var_full, 'o--', color='lightgray', markersize=5,
             linewidth=1.5, label='All PCs')
    ax2.plot(range(1, n_components + 1), cum_var, 'o-', color='darkorange',
             markersize=8, linewidth=2.5, label='Selected PCs', zorder=5)
    for th, clr, lbl in [(0.8, 'green', '80%'), (0.9, 'red', '90%'), (0.95, 'purple', '95%')]:
        ax2.axhline(y=th, color=clr, linestyle='--', alpha=0.6, linewidth=1)
        ax2.text(max_pc + 0.3, th, lbl, color=clr, fontsize=9, va='center')
    ax2.set_xlabel('Number of PCs', fontsize=11)
    ax2.set_ylabel('Cumulative explained variance ratio', fontsize=11)
    ax2.set_title('Cumulative explained variance ratio', fontsize=13, fontweight='bold')
    ax2.set_xticks(range(1, max_pc + 1))
    ax2.set_xlim(0.5, max_pc + 1.2)
    ax2.set_ylim(0, 1.05)
    ax2.legend(loc='lower right', fontsize=9)
    ax2.grid(alpha=0.3, linestyle='--')
    fig2.tight_layout()
    buf = io.BytesIO()
    fig2.savefig(buf, format='svg')
    plt.close(fig2)
    svgs.append(buf.getvalue().decode())

    # 图3: 得分散点图
    fig3, ax3 = plt.subplots(figsize=(7, 6))
    if n_components >= 2:
        ax3.scatter(scores[:, 0], scores[:, 1], c='steelblue', edgecolors='#1e3b5c',
                    s=70, alpha=0.75, zorder=3)
        # for i, lbl in enumerate(sample_labels):
        #     ax3.annotate(lbl, (scores[i, 0], scores[i, 1]),
        #                  textcoords="offset points", xytext=(5, 5),
        #                  fontsize=7, alpha=0.85)
        ax3.set_xlabel(f'PC1 ({explained_var[0]:.1%})', fontsize=11)
        ax3.set_ylabel(f'PC2 ({explained_var[1]:.1%})', fontsize=11)
        ax3.set_title('PCA score ', fontsize=13, fontweight='bold')
    else:
        ax3.text(0.5, 0.5, 'Only one PC', transform=ax3.transAxes,
                 ha='center', va='center', fontsize=14, color='gray')
    ax3.axhline(y=0, color='grey', linestyle='--', alpha=0.5, zorder=1)
    ax3.axvline(x=0, color='grey', linestyle='--', alpha=0.5, zorder=1)
    ax3.grid(alpha=0.3, linestyle='--', zorder=0)
    fig3.tight_layout()
    buf = io.BytesIO()
    fig3.savefig(buf, format='svg')
    plt.close(fig3)
    svgs.append(buf.getvalue().decode())

    # 图4: 双标图
    fig4, ax4 = plt.subplots(figsize=(8, 7))
    if n_components >= 2:
        ax4.scatter(scores[:, 0], scores[:, 1], c='steelblue', edgecolors='#1e3b5c',
                    s=50, alpha=0.6, label='samples', zorder=3)
        scale = (np.max(np.abs(scores[:, :2])) * 0.9 /
                 max(np.max(np.abs(loadings[:, :2])), 1e-10))
        for i, vn in enumerate(feature_names):
            ax4.arrow(0, 0, loadings[i, 0] * scale, loadings[i, 1] * scale,
                      head_width=scale * 0.08, head_length=scale * 0.12,
                      fc='crimson', ec='darkred', alpha=0.85, linewidth=1.5, zorder=4)
            ax4.text(loadings[i, 0] * scale * 1.15, loadings[i, 1] * scale * 1.15,
                     vn, color='darkred', fontsize=9, fontweight='bold',
                     ha='center', va='center')
        ax4.set_xlabel(f'PC1 ({explained_var[0]:.1%})', fontsize=11)
        ax4.set_ylabel(f'PC2 ({explained_var[1]:.1%})', fontsize=11)
        ax4.set_title('PCA biplot', fontsize=13, fontweight='bold')
        ax4.legend(loc='upper right', fontsize=9)
    else:
        ax4.text(0.5, 0.5, 'Unable to draw biplot', transform=ax4.transAxes,
                 ha='center', va='center', fontsize=14, color='gray')
    ax4.axhline(y=0, color='grey', linestyle='--', alpha=0.4, zorder=1)
    ax4.axvline(x=0, color='grey', linestyle='--', alpha=0.4, zorder=1)
    ax4.grid(alpha=0.3, linestyle='--', zorder=0)
    fig4.tight_layout()
    buf = io.BytesIO()
    fig4.savefig(buf, format='svg')
    plt.close(fig4)
    svgs.append(buf.getvalue().decode())

    # 载荷矩阵
    table = []
    for i, vn in enumerate(feature_names):
        row = [vn] + [f'{loadings[i, j]:.4f}' for j in range(n_components)]
        table.append(row)
    table_header = ['variable'] + pc_names

    # 得分矩阵
    scores_table = []
    for i, lbl in enumerate(sample_labels):
        row = [lbl] + [f'{scores[i, j]:.4f}' for j in range(n_components)]
        scores_table.append(row)
    scores_header = ['sample'] + pc_names

    return {
        "svgs": svgs,
        "metrics": {
            "samples num": n_samples,
            "variable num": n_features,
            "PC num": n_components,
            "Cumulative variance": f"{cum_var[-1]:.1%}"
        },
        "tables": [
            {"header": table_header, "rows": table},
            {"header": scores_header, "rows": scores_table},
        ],
    }
