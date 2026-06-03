import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io


def get_columns(options):
    if not isinstance(options, dict):
        options = options.to_py()
    data_path = options.get('data_path')
    if not data_path:
        return {"error": "请先在左侧上传数据文件"}
    try:
        df = pd.read_csv(data_path)
    except Exception as e:
        return {"error": f"读取数据失败: {e}"}
    return {"columns": df.columns.tolist()}


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

    row_var = options.get('row_var')
    col_var = options.get('col_var')

    if row_var not in df.columns:
        return {"error": f"列名不存在: {row_var}"}
    if col_var not in df.columns:
        return {"error": f"列名不存在: {col_var}"}
    if row_var == col_var:
        return {"error": "行列变量不能相同"}

    ct = pd.crosstab(df[row_var], df[col_var])
    n_rows, n_cols = ct.shape

    if n_rows < 2 or n_cols < 2:
        return {"error": f"列联表太小：{n_rows}行×{n_cols}列，至少需要2×2"}

    row_labels = ct.index.tolist()
    col_labels = ct.columns.tolist()

    F = ct.values.astype(float)
    N = F.sum()
    P = F / N

    r = P.sum(axis=1)
    c = P.sum(axis=0)

    Dr_inv_sqrt = np.diag(1.0 / np.sqrt(r + 1e-15))
    Dc_inv_sqrt = np.diag(1.0 / np.sqrt(c + 1e-15))

    S = Dr_inv_sqrt @ (P - np.outer(r, c)) @ Dc_inv_sqrt

    U, s, Vt = np.linalg.svd(S, full_matrices=False)

    tol = 1e-10
    valid = s > tol
    s = s[valid]
    U = U[:, valid]
    Vt = Vt[valid, :]

    max_dims = min(len(s), n_rows - 1, n_cols - 1)
    n_dims_raw = options.get('n_dims', None)
    n_dims = n_dims_raw if (n_dims_raw and n_dims_raw > 0) else 2
    n_dims = min(n_dims, max_dims)
    if n_dims < 1:
        n_dims = 1

    s_k = s[:n_dims]
    U_k = U[:, :n_dims]
    Vt_k = Vt[:n_dims, :]

    inertia = s_k ** 2
    total_inertia = np.sum(s ** 2)
    explained_ratio = inertia / (total_inertia + 1e-15)
    cum_ratio = np.cumsum(explained_ratio)

    phi = Dr_inv_sqrt @ U_k
    gamma = Dc_inv_sqrt @ Vt_k.T

    row_principal = phi * s_k[np.newaxis, :]
    col_principal = gamma * s_k[np.newaxis, :]

    row_sym = phi * np.sqrt(s_k[np.newaxis, :])
    col_sym = gamma * np.sqrt(s_k[np.newaxis, :])

    row_contrib = np.zeros((n_rows, n_dims))
    col_contrib = np.zeros((n_cols, n_dims))
    for k in range(n_dims):
        row_contrib[:, k] = r * row_principal[:, k] ** 2 / (inertia[k] + 1e-15)
        col_contrib[:, k] = c * col_principal[:, k] ** 2 / (inertia[k] + 1e-15)

    row_cos2 = np.zeros((n_rows, n_dims))
    col_cos2 = np.zeros((n_cols, n_dims))
    for i in range(n_rows):
        denom = np.sum(row_principal[i, :] ** 2) + 1e-15
        row_cos2[i, :] = row_principal[i, :] ** 2 / denom
    for j in range(n_cols):
        denom = np.sum(col_principal[j, :] ** 2) + 1e-15
        col_cos2[j, :] = col_principal[j, :] ** 2 / denom

    svgs = []

    # Chart 1: Symmetric Map
    fig1, ax1 = plt.subplots(figsize=(8, 7))
    if n_dims >= 2:
        ax1.scatter(row_sym[:, 0], row_sym[:, 1], c='steelblue', edgecolors='#1e3b5c',
                    s=80, zorder=3, label='Rows')
        ax1.scatter(col_sym[:, 0], col_sym[:, 1], c='crimson', edgecolors='darkred',
                    s=80, marker='s', zorder=3, label='Columns')
        for i, lbl in enumerate(row_labels):
            ax1.annotate(lbl, (row_sym[i, 0], row_sym[i, 1]),
                         textcoords="offset points", xytext=(5, 5), fontsize=8)
        for j, lbl in enumerate(col_labels):
            ax1.annotate(lbl, (col_sym[j, 0], col_sym[j, 1]),
                         textcoords="offset points", xytext=(5, 5), fontsize=8)
        ax1.set_xlabel(f'Dimension 1 ({explained_ratio[0]:.1%})', fontsize=11)
        ax1.set_ylabel(f'Dimension 2 ({explained_ratio[1]:.1%})', fontsize=11)
    else:
        ax1.text(0.5, 0.5, 'Only one dimension available', transform=ax1.transAxes,
                 ha='center', va='center', fontsize=14, color='gray')
        ax1.set_xlabel(f'Dimension 1 ({explained_ratio[0]:.1%})', fontsize=11)
        ax1.set_ylabel('Dimension 2', fontsize=11)

    ax1.axhline(y=0, color='grey', linestyle='--', alpha=0.5, zorder=1)
    ax1.axvline(x=0, color='grey', linestyle='--', alpha=0.5, zorder=1)
    ax1.set_title('Correspondence Analysis - Symmetric Map', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.3, linestyle='--', zorder=0)
    fig1.tight_layout()
    buf = io.BytesIO()
    fig1.savefig(buf, format='svg')
    plt.close(fig1)
    svgs.append(buf.getvalue().decode())

    # Chart 2: Scree Plot
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    all_inertia = s ** 2
    n_all = len(s)
    dims = range(1, n_all + 1)
    bar_colors = plt.cm.Blues(np.linspace(0.4, 0.9, n_all))
    bars = ax2.bar(dims, all_inertia, color=bar_colors, edgecolor='#1e3b5c', linewidth=1.2)
    for b, v in zip(bars, all_inertia):
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.001,
                 f'{v:.4f}', ha='center', va='bottom', fontsize=8)

    ax3 = ax2.twinx()
    cum_prop = np.cumsum(all_inertia) / (total_inertia + 1e-15)
    ax3.plot(dims, cum_prop, 'ro-', markersize=6, linewidth=2, label='Cumulative proportion')
    ax3.axhline(y=0.8, color='green', linestyle='--', alpha=0.6, linewidth=1)
    ax3.axhline(y=0.9, color='red', linestyle='--', alpha=0.6, linewidth=1)

    ax2.set_xlabel('Dimension', fontsize=11)
    ax2.set_ylabel('Inertia', fontsize=11)
    ax3.set_ylabel('Cumulative proportion', fontsize=11)
    ax2.set_title('Inertia and Cumulative Proportion', fontsize=13, fontweight='bold')
    ax2.set_xticks(dims)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    fig2.tight_layout()
    buf = io.BytesIO()
    fig2.savefig(buf, format='svg')
    plt.close(fig2)
    svgs.append(buf.getvalue().decode())

    # Chart 3: Row Contributions
    dim_label = '+'.join([f'Dim{d + 1}' for d in range(n_dims)])
    top_n_rows = min(15, n_rows)
    row_total_contrib = np.sum(row_contrib, axis=1)
    top_idx_rows = np.argsort(row_total_contrib)[-top_n_rows:][::-1]

    fig3, ax4 = plt.subplots(figsize=(8, max(4, top_n_rows * 0.35)))
    ax4.barh(range(top_n_rows), row_total_contrib[top_idx_rows],
             color='steelblue', edgecolor='#1e3b5c')
    ax4.set_yticks(range(top_n_rows))
    ax4.set_yticklabels([row_labels[i] for i in top_idx_rows], fontsize=9)
    ax4.invert_yaxis()
    ax4.set_xlabel(f'Total contribution ({dim_label})', fontsize=11)
    ax4.set_title('Row contributions to dimensions', fontsize=13, fontweight='bold')
    ax4.grid(axis='x', alpha=0.3, linestyle='--')
    fig3.tight_layout()
    buf = io.BytesIO()
    fig3.savefig(buf, format='svg')
    plt.close(fig3)
    svgs.append(buf.getvalue().decode())

    # Chart 4: Column Contributions
    top_n_cols = min(15, n_cols)
    col_total_contrib = np.sum(col_contrib, axis=1)
    top_idx_cols = np.argsort(col_total_contrib)[-top_n_cols:][::-1]

    fig4, ax5 = plt.subplots(figsize=(8, max(4, top_n_cols * 0.35)))
    ax5.barh(range(top_n_cols), col_total_contrib[top_idx_cols],
             color='crimson', edgecolor='darkred')
    ax5.set_yticks(range(top_n_cols))
    ax5.set_yticklabels([col_labels[j] for j in top_idx_cols], fontsize=9)
    ax5.invert_yaxis()
    ax5.set_xlabel(f'Total contribution ({dim_label})', fontsize=11)
    ax5.set_title('Column contributions to dimensions', fontsize=13, fontweight='bold')
    ax5.grid(axis='x', alpha=0.3, linestyle='--')
    fig4.tight_layout()
    buf = io.BytesIO()
    fig4.savefig(buf, format='svg')
    plt.close(fig4)
    svgs.append(buf.getvalue().decode())

    # --- Tables ---
    # Table 1: Inertia table
    inertia_header = ['维度', '奇异值', '惯性', '解释率', '累积率']
    inertia_rows = []
    for k in range(n_dims):
        inertia_rows.append([
            f'Dim {k + 1}',
            f'{s_k[k]:.4f}',
            f'{inertia[k]:.4f}',
            f'{explained_ratio[k]:.1%}',
            f'{cum_ratio[k]:.1%}'
        ])

    # Table 2: Row coordinates
    row_header = ['类别', 'Dim1', 'Dim2', '贡献(Dim1)', '贡献(Dim2)',
                  "Cos\u00b2(Dim1)", "Cos\u00b2(Dim2)"]
    row_rows = []
    for i in range(n_rows):
        row = [row_labels[i]]
        # Dim1, Dim2
        for d in range(2):
            if d < n_dims:
                row.append(f'{row_principal[i, d]:.4f}')
            else:
                row.append('0.0000')
        # 贡献(Dim1), 贡献(Dim2)
        for d in range(2):
            if d < n_dims:
                row.append(f'{row_contrib[i, d] * 100:.2f}%')
            else:
                row.append('0.00%')
        # Cos²(Dim1), Cos²(Dim2)
        for d in range(2):
            if d < n_dims:
                row.append(f'{row_cos2[i, d]:.4f}')
            else:
                row.append('0.0000')
        row_rows.append(row)

    # Table 3: Column coordinates
    col_header = ['类别', 'Dim1', 'Dim2', '贡献(Dim1)', '贡献(Dim2)',
                  "Cos\u00b2(Dim1)", "Cos\u00b2(Dim2)"]
    col_rows = []
    for j in range(n_cols):
        row = [col_labels[j]]
        for d in range(2):
            if d < n_dims:
                row.append(f'{col_principal[j, d]:.4f}')
            else:
                row.append('0.0000')
        for d in range(2):
            if d < n_dims:
                row.append(f'{col_contrib[j, d] * 100:.2f}%')
            else:
                row.append('0.00%')
        for d in range(2):
            if d < n_dims:
                row.append(f'{col_cos2[j, d]:.4f}')
            else:
                row.append('0.0000')
        col_rows.append(row)

    # Table 4: Contingency table
    ct_header = [row_var] + col_labels
    ct_rows = []
    for i in range(n_rows):
        row = [row_labels[i]] + [f'{int(F[i, j])}' for j in range(n_cols)]
        ct_rows.append(row)

    # Metrics
    pct = f'{(sum(explained_ratio) if n_dims >= 2 else explained_ratio[0]):.1%}'

    return {
        "svgs": svgs,
        "metrics": {
            "行类别数": n_rows,
            "列类别数": n_cols,
            "总惯性": f'{total_inertia:.4f}',
            "前2维解释率": pct
        },
        "tables": [
            {"header": inertia_header, "rows": inertia_rows},
            {"header": row_header, "rows": row_rows},
            {"header": col_header, "rows": col_rows},
            {"header": ct_header, "rows": ct_rows}
        ]
    }
