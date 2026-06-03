import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json

def analyze(options):
    """综合分析主函数 - 支持层次分析法和综合分析法"""
    if not isinstance(options, dict):
        options = options.to_py()
    
    data_path = options.get('data_path')
    method_type = options.get('method_type', 'ahp')  # 'ahp' 或 'comprehensive'
    
    if not data_path:
        return {"error": "请先在左侧上传数据文件"}
    
    try:
        df = pd.read_csv(data_path)
    except Exception as e:
        return {"error": f"读取数据失败: {e}"}
    
    if df.empty:
        return {"error": "数据文件为空"}
    
    # 获取数值列
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) < 2:
        return {"error": "数据需要至少2个数值型指标列"}
    
    # 获取用户选择的指标（逗号分隔字符串 → 列表）
    selected_indicators = options.get('indicators', None)
    if selected_indicators and isinstance(selected_indicators, str):
        selected_indicators = [c.strip() for c in selected_indicators.split(',') if c.strip()]
    if selected_indicators and isinstance(selected_indicators, list) and len(selected_indicators) > 0:
        available_cols = [col for col in selected_indicators if col in numeric_cols]
        # 只要用户明确指定了指标，就只使用匹配到的列（至少 1 列即可生效）
        if len(available_cols) >= 1:
            numeric_cols = available_cols
            if len(numeric_cols) < 2:
                return {"error": f"指标匹配后不足 2 个数值列（匹配到: {numeric_cols}）"}
    
    if method_type == 'ahp':
        return run_ahp(df, numeric_cols, options)
    else:
        return run_comprehensive(df, numeric_cols, options)


def run_ahp(df, numeric_cols, options):
    """层次分析法"""
    # 判断矩阵获取优先级：多矩阵(judgement_matrices) > 单矩阵(judgement_matrix) > 自动权重
    weights = None

    # 1. 尝试获取多判断矩阵（来自网格矩阵UI）
    judgement_matrices_str = options.get('judgement_matrices', '')
    if judgement_matrices_str:
        try:
            matrices = json.loads(judgement_matrices_str)
            if isinstance(matrices, list) and len(matrices) > 0:
                # 过滤空矩阵
                valid_matrices = [m for m in matrices if len(m) == len(numeric_cols)]
                if len(valid_matrices) >= 1:
                    agg_matrix = aggregate_matrices(valid_matrices)
                    weights = calculate_ahp_weights(agg_matrix)
        except:
            pass

    # 2. 尝试获取单判断矩阵（向后兼容）
    if weights is None:
        judgement_matrix_str = options.get('judgement_matrix', '')
        if judgement_matrix_str:
            try:
                judgement_matrix = json.loads(judgement_matrix_str)
                if len(judgement_matrix) == len(numeric_cols):
                    weights = calculate_ahp_weights(judgement_matrix)
            except:
                pass
    
    # 3. 自动计算权重（默认）
    if weights is None:
        weights = calculate_auto_weights(df, numeric_cols)
    
    # 标准化并计算得分
    normalized = normalize_minmax(df[numeric_cols].values)
    scores = np.dot(normalized, weights)
    sorted_indices = np.argsort(scores)[::-1]
    
    # 结果表格
    results_table = []
    for i, idx in enumerate(sorted_indices[:20]):
        results_table.append([
            i + 1,
            str(df.iloc[idx, 0]) if df.shape[1] > 0 else f"样本{idx+1}",
            f"{scores[idx]:.4f}"
        ])
    
    table_header = ["排名", "名称/ID", "综合得分"]
    weights_table = [[col, f"{weights[i]:.4f}"] for i, col in enumerate(numeric_cols)]
    
    # 创建可视化
    svgs = []
    bar_svg = create_score_bar_chart(scores[sorted_indices[:10]], results_table[:10])
    if bar_svg:
        svgs.append(bar_svg)
    
    return {
        "svgs": svgs,
        "tables": [
            {"header": table_header, "rows": results_table},
            {"header": ["指标名称", "权重"], "rows": weights_table}
        ],
        "metrics": {
            "样本数": len(df),
            "指标数": len(numeric_cols),
            "方法": "AHP",
            "最高分": f"{scores.max():.4f}",
            "最低分": f"{scores.min():.4f}",
            "平均分": f"{scores.mean():.4f}"
        }
    }


def run_comprehensive(df, numeric_cols, options):
    """综合分析法"""
    method = options.get('method', 'topsis')
    
    # 权重优先级：AHP 判断矩阵 → 标准差法 → 等权重法
    weights = None
    judgement_matrices_str = options.get('judgement_matrices', '')
    if judgement_matrices_str:
        try:
            matrices = json.loads(judgement_matrices_str)
            if isinstance(matrices, list) and len(matrices) > 0:
                valid_matrices = [m for m in matrices if len(m) == len(numeric_cols)]
                if len(valid_matrices) >= 1:
                    agg_matrix = aggregate_matrices(valid_matrices)
                    weights = calculate_ahp_weights(agg_matrix)
        except:
            pass
    
    if weights is None:
        data = df[numeric_cols].values
        stds = data.std(axis=0)
        if stds.sum() > 0:
            weights = stds / (stds.sum() + 1e-10)
        else:
            weights = np.ones(len(numeric_cols)) / len(numeric_cols)
    
    # 标准化
    normalized = normalize_minmax(df[numeric_cols].values)
    
    # 计算得分
    if method == 'topsis':
        scores = topsis(normalized, weights)
    elif method == 'gray_relational':
        scores = gray_relational(normalized, weights)
    else:
        scores = np.dot(normalized, weights)
    
    sorted_indices = np.argsort(scores)[::-1]
    
    # 结果表格
    results_table = []
    for i, idx in enumerate(sorted_indices[:20]):
        results_table.append([
            i + 1,
            str(df.iloc[idx, 0]) if df.shape[1] > 0 else f"样本{idx+1}",
            f"{scores[idx]:.4f}"
        ])
    
    weights_table = [[col, f"{weights[i]:.4f}"] for i, col in enumerate(numeric_cols)]
    
    # 可视化
    svgs = []
    radar_svg = create_radar_chart(normalized[sorted_indices[:8]], numeric_cols, scores[sorted_indices[:8]])
    if radar_svg:
        svgs.append(radar_svg)
    
    dist_svg = create_score_distribution(scores)
    if dist_svg:
        svgs.append(dist_svg)
    
    method_names = {'topsis': 'TOPSIS', 'weighted_sum': '加权和法', 'gray_relational': '灰色关联'}
    
    return {
        "svgs": svgs,
        "tables": [
            {"header": ["排名", "名称/ID", "综合得分"], "rows": results_table},
            {"header": ["指标名称", "权重"], "rows": weights_table}
        ],
        "metrics": {
            "样本数": len(df),
            "指标数": len(numeric_cols),
            "分析方法": method_names.get(method, method),
            "最高分": f"{scores.max():.4f}",
            "最低分": f"{scores.min():.4f}",
            "平均分": f"{scores.mean():.4f}"
        }
    }


def normalize_minmax(data):
    """Min-Max标准化"""
    min_vals = data.min(axis=0)
    max_vals = data.max(axis=0)
    ranges = max_vals - min_vals
    ranges[ranges == 0] = 1
    return (data - min_vals) / ranges


def calculate_auto_weights(df, numeric_cols):
    """自动计算权重（标准差法）"""
    data = df[numeric_cols].values
    data_norm = (data - data.min(axis=0)) / (data.max(axis=0) - data.min(axis=0) + 1e-10)
    stds = data_norm.std(axis=0)
    weights = stds / (stds.sum() + 1e-10)
    return weights


def aggregate_matrices(matrices_list):
    """多判断矩阵逐元素几何平均法聚合

    将多个专家的判断矩阵进行逐元素几何平均，得到聚合判断矩阵。

    Args:
        matrices_list: list of 2D lists/arrays, 每个元素是一个 N×N 判断矩阵

    Returns:
        np.array: 聚合后的判断矩阵
    """
    if not matrices_list or len(matrices_list) == 0:
        return None
    # 转换为 numpy 数组，shape = (k, n, n)
    matrices_arr = np.array([np.array(m) for m in matrices_list])
    # 逐元素相乘
    product = np.prod(matrices_arr, axis=0)
    # 几何平均
    k = len(matrices_list)
    geom_mean = product ** (1.0 / k)
    return geom_mean


def calculate_ahp_weights(matrix):
    """AHP几何平均法计算权重"""
    matrix = np.array(matrix)
    n = len(matrix)
    product = np.prod(matrix, axis=1)
    geometric_mean = product ** (1/n)
    weights = geometric_mean / geometric_mean.sum()
    # 简单一致性检查
    lambda_max = np.sum(np.dot(matrix, weights) / weights) / n
    ci = (lambda_max - n) / (n - 1) if n > 1 else 0
    cr = ci / 0.9 if n == 3 else (ci / 1.12 if n == 4 else ci / 1.24 if n == 5 else ci)
    return weights


def topsis(data, weights):
    """TOPSIS方法"""
    weighted = data * weights
    ideal_best = weighted.max(axis=0)
    ideal_worst = weighted.min(axis=0)
    dist_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    dist_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))
    return dist_worst / (dist_best + dist_worst + 1e-10)


def gray_relational(data, weights):
    """灰色关联分析"""
    reference = data.max(axis=0)
    diff = np.abs(data - reference)
    min_diff = diff.min(axis=0)
    max_diff = diff.max(axis=0)
    rho = 0.5
    rel_coef = (min_diff + rho * max_diff) / (diff + rho * max_diff + 1e-10)
    return np.dot(rel_coef, weights)


def create_score_bar_chart(scores, labels):
    """创建得分条形图"""
    try:
        fig, ax = plt.subplots(figsize=(10, 5))
        ranks = range(1, len(scores) + 1)
        colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(scores)))
        bars = ax.bar(ranks, scores, color=colors, edgecolor='white', linewidth=0.5)
        ax.set_xlabel('Rank', fontsize=11)
        ax.set_ylabel('Comprehensive Score', fontsize=11)
        ax.set_title('Top 10 Samples Ranking', fontsize=13, fontweight='bold')
        ax.set_xticks(ranks)
        ax.set_ylim(0, 1.05)
        for bar, score in zip(bars, scores):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                   f'{score:.3f}', ha='center', va='bottom', fontsize=9)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='svg')
        plt.close(fig)
        return buf.getvalue().decode()
    except:
        return None


def create_radar_chart(data, labels, scores):
    """创建雷达图"""
    if len(data) == 0:
        return None
    try:
        fig, ax = plt.subplots(figsize=(9, 7), subplot_kw={'projection': 'polar'})
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        angles += angles[:1]
        colors = plt.cm.Set3(np.linspace(0, 1, min(len(data), 8)))
        for i in range(min(len(data), 8)):
            values = data[i].tolist()
            values += values[:1]
            ax.plot(angles, values, 'o-', linewidth=1.5, color=colors[i],
                   label=f'#{i+1} (Score: {scores[i]:.3f})')
            ax.fill(angles, values, alpha=0.1, color=colors[i])
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, size=8)
        ax.set_ylim(0, 1)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=8)
        ax.set_title('Top 8 Samples - Radar Chart', size=12, pad=20)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='svg', bbox_inches='tight')
        plt.close(fig)
        return buf.getvalue().decode()
    except:
        return None


def create_score_distribution(scores):
    """创建得分分布图"""
    try:
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        axes[0].hist(scores, bins=15, edgecolor='black', alpha=0.7, color='steelblue')
        axes[0].set_xlabel('Score')
        axes[0].set_ylabel('Frequency')
        axes[0].set_title('Score Distribution')
        axes[0].axvline(scores.mean(), color='red', linestyle='--', label=f'Mean: {scores.mean():.3f}')
        axes[0].legend()
        sorted_scores = np.sort(scores)[::-1]
        axes[1].plot(range(1, len(sorted_scores) + 1), sorted_scores,
                    'o-', color='steelblue', linewidth=1.5, markersize=3)
        axes[1].set_xlabel('Rank')
        axes[1].set_ylabel('Score')
        axes[1].set_title('Score Rank Curve')
        axes[1].grid(True, alpha=0.3)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='svg')
        plt.close(fig)
        return buf.getvalue().decode()
    except:
        return None