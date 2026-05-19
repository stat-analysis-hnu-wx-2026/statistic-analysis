# 此处存放 典型相关 代码
# 此处存放典型相关 代码
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import scipy.stats as stats
from sklearn.cross_decomposition import CCA
from sklearn.preprocessing import StandardScaler


def analyze(options):
    """
    典型相关分析 (CCA) 模块 - 完整版
    严格遵循 README.md 规范
    """
    # 1. 处理参数
    if not isinstance(options, dict):
        options = options.to_py()

    # 2. 获取数据路径
    data_path = options.get('data_path')
    if not data_path:
        return {"error": "请先在左侧上传数据文件"}

    # 3. 读取数据
    try:
        df = pd.read_csv(data_path)
    except Exception as e:
        return {"error": f"读取数据失败: {e}"}

    # 4. 自动选择数值列
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) < 2:
        return {"error": "需要至少两列数值型变量才能进行典型相关分析"}

    # 5. 自动分组：前一半列作为 X，后一半列作为 Y
    n = len(numeric_cols) // 2
    X_cols = numeric_cols[:n]
    Y_cols = numeric_cols[n:]

    if len(X_cols) == 0 or len(Y_cols) == 0:
        return {"error": "分组后 X 或 Y 组为空，请检查数据列数"}

    # 6. 样本量校验
    n_samples = len(df)
    n_vars_x = len(X_cols)
    n_vars_y = len(Y_cols)

    if n_samples <= n_vars_x or n_samples <= n_vars_y:
        return {"error": f"样本量 ({n_samples}) 必须大于变量数 (X:{n_vars_x}, Y:{n_vars_y})"}

    # 7. 提取数据并进行标准化（CCA 必须标准化）
    X = df[X_cols].values
    Y = df[Y_cols].values

    scaler = StandardScaler()
    X_std = scaler.fit_transform(X)
    Y_std = scaler.fit_transform(Y)

    # 8. CCA 计算
    n_components = min(n_vars_x, n_vars_y)
    cca = CCA(n_components=n_components)
    cca.fit(X_std, Y_std)

    # 9. 获取典型变量得分
    X_c, Y_c = cca.transform(X_std, Y_std)

    # 10. 计算典型相关系数
    corrs = []
    for i in range(X_c.shape[1]):
        corr = np.corrcoef(X_c[:, i], Y_c[:, i])[0, 1]
        corrs.append(round(corr, 4))

    # 11. 显著性检验 (Bartlett's test)
    chi2_stats = []
    p_values = []
    n = n_samples
    for k in range(n_components):
        # 计算 Wilks' lambda
        lambda_val = np.prod([1 - c ** 2 for c in corrs[k:]])
        # 卡方统计量
        chi2 = -(n - 1 - (n_vars_x + n_vars_y + 1) / 2) * np.log(lambda_val)
        df = (n_vars_x - k) * (n_vars_y - k)
        p_val = 1 - stats.chi2.cdf(chi2, df)
        chi2_stats.append(round(chi2, 4))
        p_values.append(round(p_val, 4))

    # 12. 获取权重系数
    x_weights = cca.x_weights_
    y_weights = cca.y_weights_

    # 13. 计算结构载荷 (correlation between original variables and canonical variates)
    x_loadings = []
    y_loadings = []
    for i in range(n_components):
        x_loadings.append([np.corrcoef(X_std[:, j], X_c[:, i])[0, 1] for j in range(n_vars_x)])
        y_loadings.append([np.corrcoef(Y_std[:, j], Y_c[:, i])[0, 1] for j in range(n_vars_y)])

    # 14. 计算交叉载荷
    x_cross_loadings = []
    y_cross_loadings = []
    for i in range(n_components):
        x_cross_loadings.append([np.corrcoef(X_std[:, j], Y_c[:, i])[0, 1] for j in range(n_vars_x)])
        y_cross_loadings.append([np.corrcoef(Y_std[:, j], X_c[:, i])[0, 1] for j in range(n_vars_y)])

    # 15. 冗余度分析
    redundancy_x = []
    redundancy_y = []
    for i in range(n_components):
        # X 对 Y 的解释能力
        rx = np.mean([l ** 2 for l in x_loadings[i]])
        redundancy_x.append(round(rx * corrs[i] ** 2, 4))
        # Y 对 X 的解释能力
        ry = np.mean([l ** 2 for l in y_loadings[i]])
        redundancy_y.append(round(ry * corrs[i] ** 2, 4))

    # 16. 构建图表
    svgs = []

    # 图1：典型相关系数柱状图
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    bars = ax1.bar(range(1, len(corrs) + 1), corrs, color='steelblue', alpha=0.8)
    ax1.set_xlabel('典型变量对')
    ax1.set_ylabel('典型相关系数')
    ax1.set_title('典型相关分析 - 典型相关系数')
    ax1.set_xticks(range(1, len(corrs) + 1))
    ax1.set_ylim(0, 1.05)
    for bar, corr in zip(bars, corrs):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                 f'{corr:.3f}', ha='center', va='bottom', fontsize=9)
    fig1.tight_layout()
    buf1 = io.BytesIO()
    fig1.savefig(buf1, format='svg')
    plt.close(fig1)
    svgs.append(buf1.getvalue().decode())

    # 图2：载荷热力图（合并 X 和 Y）
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    all_loadings = np.vstack([np.array(x_loadings), np.array(y_loadings)])
    all_labels = [f'X_{i + 1}' for i in range(n_vars_x)] + [f'Y_{i + 1}' for i in range(n_vars_y)]
    im = ax2.imshow(all_loadings, cmap='RdBu_r', aspect='auto', vmin=-1, vmax=1)
    ax2.set_xticks(range(n_components))
    ax2.set_xticklabels([f'PC{i + 1}' for i in range(n_components)])
    ax2.set_yticks(range(len(all_labels)))
    ax2.set_yticklabels(all_labels)
    ax2.set_title('典型变量载荷热力图')
    plt.colorbar(im, ax=ax2)
    fig2.tight_layout()
    buf2 = io.BytesIO()
    fig2.savefig(buf2, format='svg')
    plt.close(fig2)
    svgs.append(buf2.getvalue().decode())

    # 图3：得分散点图（前两对）
    if n_components >= 2:
        fig3, ax3 = plt.subplots(figsize=(6, 6))
        ax3.scatter(X_c[:, 0], X_c[:, 1], alpha=0.6, label='X得分')
        ax3.scatter(Y_c[:, 0], Y_c[:, 1], alpha=0.6, label='Y得分')
        ax3.set_xlabel('第一典型变量')
        ax3.set_ylabel('第二典型变量')
        ax3.set_title('典型变量得分散点图')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        fig3.tight_layout()
        buf3 = io.BytesIO()
        fig3.savefig(buf3, format='svg')
        plt.close(fig3)
        svgs.append(buf3.getvalue().decode())

    # 图4：冗余度条形图
    fig4, ax4 = plt.subplots(figsize=(8, 4))
    x_pos = np.arange(len(redundancy_x))
    width = 0.35
    ax4.bar(x_pos - width / 2, redundancy_x, width, label='X→Y 解释度', color='steelblue')
    ax4.bar(x_pos + width / 2, redundancy_y, width, label='Y→X 解释度', color='coral')
    ax4.set_xlabel('典型变量对')
    ax4.set_ylabel('冗余度')
    ax4.set_title('冗余度分析')
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels([f'第{i + 1}对' for i in range(len(redundancy_x))])
    ax4.legend()
    fig4.tight_layout()
    buf4 = io.BytesIO()
    fig4.savefig(buf4, format='svg')
    plt.close(fig4)
    svgs.append(buf4.getvalue().decode())

    # 图5：权重条形图（X 和 Y）
    fig5, axes = plt.subplots(1, 2, figsize=(12, 4))
    # X 权重
    axes[0].bar(range(len(X_cols)), x_weights[:, 0], color='steelblue')
    axes[0].set_xticks(range(len(X_cols)))
    axes[0].set_xticklabels([f'X{i + 1}' for i in range(len(X_cols))])
    axes[0].set_title('X 组典型权重 (第一对)')
    axes[0].set_ylabel('权重')
    # Y 权重
    axes[1].bar(range(len(Y_cols)), y_weights[:, 0], color='coral')
    axes[1].set_xticks(range(len(Y_cols)))
    axes[1].set_xticklabels([f'Y{i + 1}' for i in range(len(Y_cols))])
    axes[1].set_title('Y 组典型权重 (第一对)')
    axes[1].set_ylabel('权重')
    fig5.tight_layout()
    buf5 = io.BytesIO()
    fig5.savefig(buf5, format='svg')
    plt.close(fig5)
    svgs.append(buf5.getvalue().decode())

    # 17. 构建表格数据
    # 表1：典型相关系数 + 显著性检验
    corr_table = []
    for i in range(n_components):
        corr_table.append([
            f'第{i + 1}对',
            f'{corrs[i]:.4f}',
            f'{chi2_stats[i]:.4f}',
            f'{p_values[i]:.4f}',
            '显著' if p_values[i] < 0.05 else '不显著'
        ])

    # 表2：典型权重
    weight_table_x = []
    for i in range(len(X_cols)):
        row = [f'X{i + 1}'] + [f'{x_weights[i, j]:.4f}' for j in range(n_components)]
        weight_table_x.append(row)

    weight_table_y = []
    for i in range(len(Y_cols)):
        row = [f'Y{i + 1}'] + [f'{y_weights[i, j]:.4f}' for j in range(n_components)]
        weight_table_y.append(row)

    # 表3：结构载荷
    loading_table_x = []
    for i in range(len(X_cols)):
        row = [f'X{i + 1}'] + [f'{x_loadings[j][i]:.4f}' for j in range(n_components)]
        loading_table_x.append(row)

    loading_table_y = []
    for i in range(len(Y_cols)):
        row = [f'Y{i + 1}'] + [f'{y_loadings[j][i]:.4f}' for j in range(n_components)]
        loading_table_y.append(row)

    # 表4：典型变量得分
    score_table = []
    score_header = ['样本'] + [f'PC{i + 1}' for i in range(n_components)]
    for i in range(min(n_samples, 20)):  # 只显示前20个样本
        row = [f'样本{i + 1}'] + [f'{X_c[i, j]:.4f}' for j in range(n_components)]
        score_table.append(row)

    # 18. 自动文字解读（简化版）
    significant_pairs = sum(1 for p in p_values if p < 0.05)
    if significant_pairs == 0:
        interpretation = "未发现显著的典型相关对。建议检查数据质量或增加样本量。"
    elif significant_pairs == 1:
        interpretation = f"发现1对显著的典型相关，相关系数为 {corrs[0]:.4f}。X组与Y组之间存在较强的线性关系。"
    else:
        interpretation = f"发现 {significant_pairs} 对显著的典型相关，最大相关系数为 {max(corrs):.4f}。"

    # 19. 返回结果
    return {
        "svgs": svgs,
        "metrics": {
            "样本量": n_samples,
            "X变量数": n_vars_x,
            "Y变量数": n_vars_y,
            "显著对数": significant_pairs,
            "最大相关系数": max(corrs),
            "解释": interpretation
        },
        "tables": [
            {"header": ["典型变量对", "相关系数", "卡方值", "p值", "显著性"], "rows": corr_table},
            {"header": ["变量"] + [f'PC{i + 1}' for i in range(n_components)], "rows": weight_table_x},
            {"header": ["变量"] + [f'PC{i + 1}' for i in range(n_components)], "rows": weight_table_y},
            {"header": ["变量"] + [f'PC{i + 1}' for i in range(n_components)], "rows": loading_table_x},
            {"header": ["变量"] + [f'PC{i + 1}' for i in range(n_components)], "rows": loading_table_y},
            {"header": score_header, "rows": score_table}
        ]
    }