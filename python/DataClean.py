import os
import re
from typing import Union

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler


# 数据清洗
def _clean_series_numeric(series: pd.Series) -> pd.Series:
    """
    向量化清洗单个 Series 中的数值格式：
    - 货币符号（$€¥£₹等）
    - 百分号（转除以100）
    - 千位分隔符（逗号、空格）
    - 全角数字、全角负号/小数点
    - 括号负数 -> 负号
    """
    # 先尝试直接转为数值
    numeric = pd.to_numeric(series, errors='coerce', downcast='float')
    
    # 未被转换成功的索引
    failed_mask = numeric.isna() & series.notna()
    if not failed_mask.any():
        return numeric
    
    # 对失败的条目进行字符串清理
    failed_vals = series[failed_mask].astype(str).str.strip()
    
    # 1. 全角负号和小数点映射
    fullwidth_map = str.maketrans('－．', '-.')
    failed_vals = failed_vals.str.translate(fullwidth_map)
    
    # 2. 全角数字转半角
    fullwidth_digits = str.maketrans('０１２３４５６７８９', '0123456789')
    failed_vals = failed_vals.str.translate(fullwidth_digits)
    
    # 3. 移除货币符号
    currency_pattern = r'[$€¥£₹]'
    failed_vals = failed_vals.str.replace(currency_pattern, '', regex=True)
    
    # 4. 处理括号负数： (123.45) -> -123.45
    failed_vals = failed_vals.str.replace(r'^\((.*)\)$', r'-\1', regex=True)
    
    # 5. 移除百分号并除以100
    pct_mask = failed_vals.str.contains(r'%', na=False)
    failed_vals = failed_vals.str.replace(r'%', '', regex=True)
    
    # 6. 移除千位分隔符（逗号）和空格（只移除数字内部的空格，保守处理）
    failed_vals = failed_vals.str.replace(',', '', regex=False)
    failed_vals = failed_vals.str.replace(' ', '', regex=False)
    
    # 第二次转数值
    cleaned_numeric = pd.to_numeric(failed_vals, errors='coerce', downcast='float')
    
    # 百分比除以100
    if pct_mask.any():
        # pct_mask 索引对应原始 failed_mask 内的子集，需要对齐
        # 在 cleaned_numeric 上，根据原始的带%标记来调整
        pct_mask_full = failed_mask.copy()
        pct_mask_full[failed_mask] = pct_mask
        numeric.loc[pct_mask_full] = cleaned_numeric.loc[pct_mask] / 100.0
    else:
        numeric.loc[failed_mask] = cleaned_numeric
    
    return numeric


def clean_dataframe(
    df: pd.DataFrame,
    name_col_index: Union[int, str] = 0,
    missing_strategy: str = "mean",
    standardize: bool = True
) -> pd.DataFrame:
    """
    清洗数据框中的数值列，保留一列标识列（如名称）。
 
    参数:
        df: 原始 DataFrame
        name_col_index: 标识列的索引（整数位置）或列名
        missing_strategy: 缺失值处理策略，'drop' 或 sklearn SimpleImputer 支持的策略
        standardize: 是否标准化

    返回: clean_df
    """
    # 标识列处理
    if isinstance(name_col_index, str):
        name_col = name_col_index
        name_data = df[[name_col]]
        numeric_cols = [c for c in df.columns if c != name_col]
    else:
        name_col = df.columns[name_col_index]
        name_data = df[[name_col]]
        numeric_cols = [c for i, c in enumerate(df.columns) if i != name_col_index]

    # 向量化转换数值列
    numeric_df = pd.DataFrame(index=df.index)
    for col in numeric_cols:
        numeric_df[col] = _clean_series_numeric(df[col])

    # 缺失值处理
    if missing_strategy == "drop":
        numeric_df = numeric_df.dropna()
        name_data = name_data.loc[numeric_df.index]
    else:
        imputer = SimpleImputer(strategy=missing_strategy)
        numeric_array = imputer.fit_transform(numeric_df)
        numeric_df = pd.DataFrame(numeric_array, columns=numeric_df.columns, index=numeric_df.index)
   
    # 删除填充后残留的空缺值
    nan_rows_before = numeric_df.isna().any(axis=1).sum()
    if nan_rows_before > 0:
        numeric_df = numeric_df.dropna()
        name_data = name_data.loc[numeric_df.index]
        print(f"警告：填充后仍有 {nan_rows_before} 行包含 NaN，已删除。")

    # 标准化
    if standardize:
        scaler = StandardScaler()
        numeric_array = scaler.fit_transform(numeric_df)
        numeric_df = pd.DataFrame(numeric_array, columns=numeric_df.columns, index=numeric_df.index)
        result = pd.concat([name_data, numeric_df], axis=1)
    else:
        result = pd.concat([name_data, numeric_df], axis=1)

    return result


def preview_data(options):
    """快速返回数据预览信息（只读前 1000 行）

    接受参数:
        data_path: CSV 文件路径

    返回:
        columns: 列名列表
        dtypes: {列名: 类型字符串}
        sample: 前 5 行数据（字符串二维数组）
        n_rows: 总行数
        suggested_roles: {列名: "index"|"numeric"|"categorical"}
    """
    if not isinstance(options, dict):
        options = options.to_py()
    data_path = options.get('data_path')
    if not data_path:
        return {"error": "未指定数据路径"}

    import csv

    # 编码检测 + CSV 行数
    columns = None
    n_rows = 0
    detected_enc = None
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            with open(data_path, encoding=enc, newline='') as f:
                reader = csv.reader(f)
                columns = next(reader)
                n_rows = sum(1 for _ in reader)
            detected_enc = enc
            break
        except Exception:
            continue

    if columns is None:
        return {"error": f"无法读取文件: {data_path}"}
    if n_rows == 0:
        return {"error": "空文件"}

    # pandas 读前 1000 行
    df_sample = pd.read_csv(data_path, nrows=min(1000, n_rows + 1), encoding=detected_enc)

    # 前 5 行预览
    sample = []
    for _, row in df_sample.head(5).iterrows():
        sample.append(["" if pd.isna(v) else str(v) for v in row])

    # 类型推断 + 角色建议
    actual_columns = df_sample.columns.tolist()
    dtypes = {}
    suggested_roles = {}
    for i, col in enumerate(actual_columns):
        dtype_str = str(df_sample[col].dtype)
        dtypes[col] = dtype_str
        if i == 0:
            suggested_roles[col] = "index"
        elif pd.api.types.is_numeric_dtype(df_sample[col]):
            suggested_roles[col] = "numeric"
        else:
            suggested_roles[col] = "categorical"

    # 补上 csv reader 发现但 pd.read_csv(nrows) 未发现的列
    for col in columns:
        if col not in dtypes:
            dtypes[col] = "unknown"
            suggested_roles[col] = "categorical" if columns.index(col) > 0 else "index"

    return {
        "columns": columns,
        "dtypes": dtypes,
        "sample": sample,
        "n_rows": n_rows,
        "suggested_roles": suggested_roles,
    }


def manual_clean(options):
    """根据用户指定的列角色清洗数据

    接受参数:
        data_path: 原始 CSV 路径
        index_col: 索引列名（保留原样，不做数值处理）
        numeric_cols: 数值列名列表（清洗 + 均值填补）
        categorical_cols: 分类列名列表（保留原样）

    返回:
        path: 清洗后文件路径
        columns: 总列数
        numeric_columns: 数值列数
        categorical_columns: 分类列数
        rows: 行数
    """
    if not isinstance(options, dict):
        options = options.to_py()

    data_path = options.get('data_path')
    index_col = options.get('index_col', None)
    numeric_cols = options.get('numeric_cols', [])
    categorical_cols = options.get('categorical_cols', [])

    if hasattr(numeric_cols, 'to_py'):
        numeric_cols = numeric_cols.to_py()
    if hasattr(categorical_cols, 'to_py'):
        categorical_cols = categorical_cols.to_py()
    if isinstance(index_col, list):
        index_col = index_col[0] if index_col else None

    if not data_path:
        return {"error": "未指定数据路径"}

    df = _read_csv(data_path)
    if df is None:
        return {"error": f"无法读取文件: {data_path}"}

    # 分离索引列
    index_df = None
    if index_col and index_col in df.columns:
        index_df = df[[index_col]]

    # 数值列清洗
    valid_numeric = [c for c in numeric_cols if c in df.columns]
    numeric_df = pd.DataFrame(index=df.index)
    for col in valid_numeric:
        numeric_df[col] = _clean_series_numeric(df[col])

    # 均值填补（只对有实际数值的列）
    if not numeric_df.empty and numeric_df.shape[1] > 0:
        imputer = SimpleImputer(strategy='mean')
        numeric_array = imputer.fit_transform(numeric_df)
        numeric_df = pd.DataFrame(numeric_array, columns=numeric_df.columns, index=numeric_df.index)

    # 分类列保留原样
    valid_cat = [c for c in categorical_cols if c in df.columns]
    cat_df = df[valid_cat] if valid_cat else pd.DataFrame(index=df.index)

    # 重组
    parts = []
    if index_df is not None:
        parts.append(index_df)
    if not numeric_df.empty:
        parts.append(numeric_df)
    if not cat_df.empty:
        parts.append(cat_df)

    if not parts:
        return {"error": "没有选择任何列。请至少指定一列为「数值」或「分类」。", "path": data_path, "columns": 0, "numeric_columns": 0, "categorical_columns": 0, "rows": len(df)}

    result = pd.concat(parts, axis=1)

    # 写文件
    output_path = data_path.replace('.csv', '.cleaned.csv')
    if output_path == data_path:
        base, ext = os.path.splitext(data_path)
        output_path = f"{base}.cleaned{ext}"

    result.to_csv(output_path, index=False, encoding="utf-8-sig")

    return {
        "path": output_path,
        "columns": len(result.columns),
        "numeric_columns": len(valid_numeric),
        "categorical_columns": len(valid_cat),
        "rows": len(result),
    }


def _read_csv(path):
    """尝试多种编码读取 CSV"""
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python")
        except Exception:
            continue
    return None


def auto_clean(input_path: str, output_path: str = None) -> str:
    """从 input_path 读 CSV，自动清洗后写入 output_path。

    自动检测编码与分隔符，先做类型转换（clean_to_numeric），
    再用均值填补缺失值（不做标准化）。

    返回: output_path
    """
    df = None
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            df = pd.read_csv(input_path, encoding=enc, sep=None, engine="python")
            break
        except Exception:
            continue
    if df is None:
        raise ValueError(f"无法读取文件: {input_path}")

    cleaned = clean_dataframe(df, standardize=False)
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}.cleaned{ext}"
    cleaned.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path