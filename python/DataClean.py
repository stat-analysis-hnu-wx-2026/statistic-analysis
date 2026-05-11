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