import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from io import BytesIO
import json
# from __DataClean import clean_data


def _read_data():
    try:
        with open('/home/pyodide/upload_meta.json') as f:
            meta = json.load(f)
    except Exception:
        raise ValueError("请先在左侧上传数据文件")
    path = meta['sheets'][0]['path']
    print(f'[Evaluation] 读取: {path}')
    df = pd.read_csv(path)
    df = clean_data(df)
    print(f'[Evaluation] 数据形状: {df.shape}')
    return df


def _ensure_dict(obj):
    if obj is not None and not isinstance(obj, dict):
        obj = obj.to_py()
    return obj or {}


def descriptive(options):
    options = _ensure_dict(options)
    print(f'[描述性统计] 参数: column={options.get("column", "全部")}')
    try:
        df = _read_data()
        column = options.get('column') or None

        if column and column in df.columns:
            data = df[column].dropna()
            if len(data) == 0:
                return {"error": f"列 '{column}' 没有有效数据"}
            s = _calc_stats(data)
            print(f'[描述性统计] {column}: 均值={s["mean"]}, 标准差={s["std"]}, 样本量={s["n"]}')
            return {
                "table": [
                    ['样本量', s['n']],
                    ['均值', s['mean']],
                    ['中位数', s['median']],
                    ['标准差', s['std']],
                    ['方差', s['var']],
                    ['最小值', s['min']],
                    ['最大值', s['max']],
                    ['偏度', s['skew']],
                    ['峰度', s['kurtosis']],
                ],
                "table_header": ['统计指标', column],
                "metrics": {"样本量": s['n'], "均值": s['mean'], "中位数": s['median'], "标准差": s['std']},
            }

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return {"error": "数据中没有数值类型的列"}

        results = []
        for col in numeric_cols:
            data = df[col].dropna()
            if len(data) > 0:
                results.append({"name": col, **_calc_stats(data)})

        metric_names = ['样本量', '均值', '中位数', '标准差', '最小值', '最大值']
        table_header = ['统计指标'] + [r['name'] for r in results]
        table = []
        for m in metric_names:
            row = [m]
            for r in results:
                val = r.get(m, '-')
                if isinstance(val, float):
                    val = round(val, 4)
                row.append(val)
            table.append(row)

        print(f'[描述性统计] 完成: {len(results)} 个数值变量')
        return {
            "table": table,
            "table_header": table_header,
            "metrics": {"样本量": len(df), "均值": len(numeric_cols), "中位数": "", "标准差": ""},
        }
    except Exception as e:
        return {"error": f"描述性统计失败: {e}"}


def _calc_stats(data):
    return {
        "n": len(data),
        "mean": round(data.mean(), 4),
        "median": round(data.median(), 4),
        "std": round(data.std(), 4),
        "var": round(data.var(), 4),
        "min": round(data.min(), 4),
        "max": round(data.max(), 4),
        "skew": round(data.skew(), 4),
        "kurtosis": round(data.kurtosis(), 4),
    }


def normality(options):
    options = _ensure_dict(options)
    print(f'[正态性检验] 参数: column={options.get("column", "全部")}, alpha={options.get("alpha", 0.05)}')
    try:
        df = _read_data()
        column = options.get('column') or None
        alpha = float(options.get('alpha', 0.05))

        if not column:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if not numeric_cols:
                return {"error": "数据中没有数值类型的列"}
            results = []
            for col in numeric_cols:
                data = df[col].dropna()
                if len(data) >= 3:
                    stat, p = stats.shapiro(data)
                    results.append({
                        "name": col, "n": len(data),
                        "statistic": round(stat, 4), "p_value": round(p, 4),
                        "is_normal": "是" if p >= alpha else "否",
                    })
            table = [[r['name'], r['n'], r['statistic'], r['p_value'], r['is_normal']] for r in results]
            print(f'[正态性检验] 完成: {len(results)} 个变量')
            return {
                "table": table,
                "table_header": ['变量名', '样本量', 'W统计量', 'p值', '正态分布'],
                "metrics": {"W统计量": len(results), "p值": alpha, "正态性": f"{len(results)}个变量", "显著性水平": alpha},
            }

        if column not in df.columns:
            return {"error": f"列 '{column}' 不存在"}

        data = df[column].dropna()
        if len(data) < 3:
            return {"error": "样本量不足（需要至少3个）"}

        stat, p = stats.shapiro(data)
        is_normal = p >= alpha
        svg = _generate_qq_plot(data, column)
        print(f'[正态性检验] {column}: W={stat:.4f}, p={p:.4f}, {"服从" if is_normal else "不服从"}正态分布')
        return {
            "table": [
                ['Shapiro-Wilk检验', round(stat, 4), round(p, 4),
                 f"{'服从正态分布' if is_normal else '不服从正态分布'} (α={alpha})"],
            ],
            "table_header": ['检验项目', '统计量', 'p值', '结论'],
            "svg": svg,
            "metrics": {"W统计量": round(stat, 4), "p值": round(p, 4), "正态性": "服从" if is_normal else "不服从", "显著性水平": alpha},
        }
    except Exception as e:
        return {"error": f"正态性检验失败: {e}"}


def _generate_qq_plot(data, name):
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        stats.probplot(data, dist="norm", plot=ax)
        ax.set_title(f'Q-Q Plot: {name}', fontsize=14)
        ax.set_xlabel('理论分位数')
        ax.set_ylabel('样本分位数')
        ax.grid(True, alpha=0.3)
        buf = BytesIO()
        fig.savefig(buf, format='svg', bbox_inches='tight')
        plt.close(fig)
        return buf.getvalue().decode('utf-8')
    except Exception as e:
        print(f"Q-Q图生成失败: {e}")
        return None


def anova(options):
    options = _ensure_dict(options)
    print(f'[方差分析] 参数: dependent_var={options.get("dependent_var")}, group_var={options.get("group_var")}')
    try:
        df = _read_data()
        dependent = options.get('dependent_var') or None
        group = options.get('group_var') or None

        if not dependent or not group:
            return {"error": "请指定因变量和分组变量"}
        if dependent not in df.columns:
            return {"error": f"因变量 '{dependent}' 不存在"}
        if group not in df.columns:
            return {"error": f"分组变量 '{group}' 不存在"}

        groups = []
        group_names = []
        for name, gdf in df.groupby(group):
            vals = gdf[dependent].dropna().values
            if len(vals) > 0:
                groups.append(vals)
                group_names.append(str(name))

        if len(groups) < 2:
            return {"error": "分组数量不足（需要至少2组）"}

        f_stat, p_value = stats.f_oneway(*groups)

        table = []
        for i, (name, g) in enumerate(zip(group_names, groups)):
            table.append([name, len(g), round(g.mean(), 4), round(g.std(), 4)])

        # ANOVA 方差分析表
        all_vals = np.concatenate(groups)
        grand_mean = all_vals.mean()
        ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
        ss_within = sum(sum((x - g.mean()) ** 2 for x in g) for g in groups)
        df_between = len(groups) - 1
        df_within = len(all_vals) - len(groups)
        ms_between = ss_between / df_between if df_between > 0 else 0
        ms_within = ss_within / df_within if df_within > 0 else 0

        anova_table = [
            ['组间', round(ss_between, 4), df_between, round(ms_between, 4), round(f_stat, 4), round(p_value, 4)],
            ['组内', round(ss_within, 4), df_within, round(ms_within, 4), '-', '-'],
            ['总计', round(ss_between + ss_within, 4), df_between + df_within, '-', '-', '-'],
        ]
        anova_header = ['来源', 'SS', 'df', 'MS', 'F值', 'p值']

        svg = _generate_boxplot(df, dependent, group)
        is_sig = p_value < 0.05
        print(f'[方差分析] {dependent} ~ {group}: F({df_between},{df_within})={f_stat:.4f}, p={p_value:.4f}, {"显著" if is_sig else "不显著"}')
        return {
            "table": table,
            "table_header": ['组别', '样本量', '均值', '标准差'],
            "anova_table": anova_table,
            "anova_table_header": anova_header,
            "svg": svg,
            "metrics": {"F值": round(f_stat, 4), "p值": round(p_value, 4), "显著性": "显著" if is_sig else "不显著", "组数": len(groups)},
        }
    except Exception as e:
        return {"error": f"方差分析失败: {e}"}


def _generate_boxplot(df, dependent, group):
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        gd = df.groupby(group)[dependent].apply(list).to_dict()
        data = [v for v in gd.values() if len(v) > 0]
        labels = [str(k) for k, v in gd.items() if len(v) > 0]
        bp = ax.boxplot(data, labels=labels, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
        ax.set_title(f'{dependent} ~ {group}', fontsize=14)
        ax.set_xlabel(group, fontsize=12)
        ax.set_ylabel(dependent, fontsize=12)
        ax.grid(True, alpha=0.3)
        buf = BytesIO()
        fig.savefig(buf, format='svg', bbox_inches='tight')
        plt.close(fig)
        return buf.getvalue().decode('utf-8')
    except Exception as e:
        print(f"箱线图生成失败: {e}")
        return None
