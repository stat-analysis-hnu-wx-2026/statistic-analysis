import io
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler


# 数据清洗

def clean_to_numeric(x) -> Union[float, np.nan]:
    """将单个值转为数字：处理货币符号、百分号、逗号、全角数字等"""
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float)):
        return x
    s = str(x).strip()
    s = re.sub(r'[$€¥%]', '', s)           # 移除货币符号和百分号
    s = s.replace(',', '').replace(' ', '') # 移除千位分隔符和空格
    s = s.translate(str.maketrans('０１２３４５６７８９', '0123456789'))  # 全角转半角
    try:
        return pd.to_numeric(s)
    except Exception:
        return np.nan


def clean_dataframe(
    df: pd.DataFrame,
    name_col_index: Union[int, str] = 0,
    missing_strategy: str = "mean",
    standardize = True
) -> pd.DataFrame :
    """
    清洗数据框中的数值列，保留一列标识列（如名称）。

    参数:
        df: 原始 DataFrame
        name_col_index: 标识列的索引（整数位置）或列名
        missing_strategy: 缺失值处理策略，'drop' 或 sklearn SimpleImputer 支持的策略
        standardize: 是否标准化

    返回:   clean_df
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

    # 转换数值列
    numeric_df = df[numeric_cols].applymap(clean_to_numeric)

    # 缺失值处理
    if missing_strategy == "drop":
        numeric_df = numeric_df.dropna()
        name_data = name_data.loc[numeric_df.index]
    else:
        imputer = SimpleImputer(strategy=missing_strategy)
        numeric_array = imputer.fit_transform(numeric_df)
        numeric_df = pd.DataFrame(numeric_array, columns=numeric_df.columns, index=numeric_df.index)

    # 标准化
    if standardize:
        scaler = StandardScaler()
        numeric_array = scaler.fit_transform(numeric_df)
        numeric_df = pd.DataFrame(numeric_array, columns=numeric_df.columns, index=numeric_df.index)
        result = pd.concat([name_data, numeric_df], axis=1)
    else:
        result = pd.concat([name_data, numeric_df], axis=1)

    return result


# ----------------------------------------------------------------------
# 文件上传 & 多 sheet 加载（原 Clustering.py 中的逻辑）
# ----------------------------------------------------------------------

UPLOAD_NAME_PATH = "/home/pyodide/upload_name.txt"
UPLOAD_META_PATH = "/home/pyodide/upload_meta.json"
DATA_DIR = "/home/pyodide"


def get_upload_meta() -> Tuple[str, str]:
    """返回 (数据文件路径, 扩展名)"""
    if os.path.exists(UPLOAD_META_PATH):
        try:
            meta = json.loads(open(UPLOAD_META_PATH, "r", encoding="utf-8").read())
            sheets = meta.get("sheets", [])
            if sheets:
                return sheets[0]["path"], "csv"
        except Exception:
            pass

    if os.path.exists(UPLOAD_NAME_PATH):
        with open(UPLOAD_NAME_PATH, "r", encoding="utf-8") as f:
            original_name = f.read().strip()
        ext = (original_name.split(".")[-1] if "." in original_name else "csv").lower()
        path = os.path.join(DATA_DIR, f"data.{ext}")
    else:
        path = os.path.join(DATA_DIR, "data.csv")
        ext = "csv"

    if not os.path.exists(path):
        raise ValueError("未检测到上传文件，请先上传 CSV/Excel 文件。")
    return path, ext


def load_dataframe_from_upload(sheet_name: Optional[str] = None) -> pd.DataFrame:
    """从上传路径加载 DataFrame（CSV，自动检测编码与分隔符）"""
    path, _ = get_upload_meta()
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python")
        except Exception:
            continue
    raise ValueError("CSV 解析失败，请检查编码/分隔符，或改存为 UTF-8 CSV 后重试。")


def load_numeric_data(sheet_name: Optional[str] = None) -> pd.DataFrame:
    """
    从上传文件加载数值数据。
    """
    df = load_dataframe_from_upload(sheet_name=sheet_name)
    num_df = clean_dataframe(df)
    if num_df.empty:
        raise ValueError("未检测到可用于聚类的数值列，请上传包含数值列的 CSV/Excel。")
    return num_df


def load_multi_sheets(
    sheet_selector: str = "",
    name_col_index: Union[int, str] = 0,
    missing_strategy: str = "mean",
    standardize: bool = True,
) -> List[Tuple[str, pd.DataFrame]]:
    """
    根据 sheet_selector 加载多个 sheet 的数据，并对每个 sheet 应用统一的清洗流程。

    参数:
        sheet_selector: 逗号分隔的 sheet 序号（从1开始），例如 "1,3"。为空时只加载第一个 sheet。
        name_col_index: 标识列的索引（整数位置）或列名，将保留此列不参与数值转换。
        missing_strategy: 缺失值处理策略，'drop' 或 sklearn SimpleImputer 支持的策略。
        standardize: 是否对数值列进行标准化。

    返回:
        List[Tuple[str, pd.DataFrame]]，每个元素为 (sheet名称, 清洗后的DataFrame)。

    异常:
        ValueError: 当元数据缺失、sheet序号越界、文件读取失败或无可用于聚类的数值列时抛出。
    """
    if not os.path.exists(UPLOAD_META_PATH):
        # 没有元数据时回退到单 sheet 行为（兼容旧上传）
        df = load_numeric_data()  # 使用默认清洗参数
        return [("sheet1", df)]

    try:
        with open(UPLOAD_META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        raise ValueError(f"上传元信息读取失败: {e}") from e

    sheets = meta.get("sheets", [])
    if not sheets:
        # meta 存在但无 sheets 信息，仍回退到单 sheet
        df = load_numeric_data()
        return [("sheet1", df)]

    # 解析 sheet 选择器
    if not sheet_selector:
        chosen_indices = [0]
    else:
        chosen_indices = []
        for token in sheet_selector.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                idx = int(token) - 1  # 转换为 0‑based
            except ValueError:
                raise ValueError(f"无效的 sheet 序号: '{token}'，应为整数")
            if idx < 0 or idx >= len(sheets):
                raise ValueError(f"sheet 序号越界: {idx+1}，有效范围 1~{len(sheets)}")
            chosen_indices.append(idx)
        if not chosen_indices:
            chosen_indices = [0]

    results: List[Tuple[str, pd.DataFrame]] = []
    for idx in chosen_indices:
        sheet_info = sheets[idx]
        sheet_name = sheet_info.get("name", f"sheet{sheet_info.get('index', idx+1)}")
        sheet_path = sheet_info.get("path")
        if not sheet_path:
            raise ValueError(f"sheet '{sheet_name}' 缺少 path 信息")

        # 读取 CSV（尝试多种编码与自动分隔符）
        df_raw = None
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
            try:
                df_raw = pd.read_csv(sheet_path, encoding=enc, sep=None, engine="python")
                break
            except Exception:
                continue
        if df_raw is None:
            raise ValueError(f"sheet '{sheet_name}' CSV 解析失败，请检查编码/分隔符")

        # 应用与 load_numeric_data 完全一致的清洗流程
        try:
            cleaned_df = clean_dataframe(
                df_raw,
                name_col_index=name_col_index,
                missing_strategy=missing_strategy,
                standardize=standardize,
            )
        except Exception as e:
            raise ValueError(f"sheet '{sheet_name}' 数据清洗失败: {e}") from e

        if cleaned_df.empty:
            raise ValueError(f"sheet '{sheet_name}' 清洗后无有效数据，可能缺少数值列或全部为缺失值")

        results.append((sheet_name, cleaned_df))

    return results