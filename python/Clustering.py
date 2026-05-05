import io
import json
import os
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score


UPLOAD_NAME_PATH = "/home/pyodide/upload_name.txt"
UPLOAD_META_PATH = "/home/pyodide/upload_meta.json"
DATA_DIR = "/home/pyodide"
HIERARCHICAL_METHODS = ["single", "complete", "average", "centroid", "median", "ward"]


def _read_numeric_data(sheet_name=None) -> Tuple[pd.DataFrame, np.ndarray]:
    df = _load_uploaded_dataframe(sheet_name=sheet_name)
    num_df = df.select_dtypes(include=[np.number]).dropna(axis=0)
    if num_df.empty:
        raise ValueError("未检测到可用于聚类的数值列，请上传包含数值列的 CSV/Excel。")
    return df, num_df.to_numpy(dtype=float)


def _get_upload_meta() -> Tuple[str, str]:
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


def _load_uploaded_dataframe(sheet_name=None) -> pd.DataFrame:
    path, ext = _get_upload_meta()

    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python")
        except Exception:
            continue

    raise ValueError("CSV 解析失败，请检查编码/分隔符，或改存为 UTF-8 CSV 后重试。")


def _standardize(x: np.ndarray) -> np.ndarray:
    mean = x.mean(axis=0, keepdims=True)
    std = x.std(axis=0, keepdims=True)
    std[std == 0] = 1.0
    return (x - mean) / std


def _pca2(x: np.ndarray) -> np.ndarray:
    x0 = x - x.mean(axis=0, keepdims=True)
    cov = np.cov(x0, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    pc = eigvecs[:, order[:2]]
    return x0 @ pc


def _svg_scatter(points2d: np.ndarray, labels: np.ndarray, title: str) -> str:
    fig, ax = plt.subplots(figsize=(8, 5))
    unique = np.unique(labels)
    for k in unique:
        idx = labels == k
        ax.scatter(points2d[idx, 0], points2d[idx, 1], s=36, alpha=0.85, label=f"Cluster {int(k)}")
    ax.set_title(title)
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.2)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")


def _svg_dendrogram(z: np.ndarray, title: str) -> str:
    fig, ax = plt.subplots(figsize=(9, 5))
    dendrogram(z, ax=ax, leaf_rotation=0, leaf_font_size=10)
    ax.set_title(title)
    ax.set_xlabel("Samples")
    ax.set_ylabel("Distance")
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")


def _safe_metrics(x: np.ndarray, labels: np.ndarray) -> Dict[str, str]:
    unique = np.unique(labels)
    if unique.size < 2:
        return {
            "silhouette": "N/A",
            "ch": "N/A",
            "db": "N/A",
            "inertia": "N/A",
        }
    sil = silhouette_score(x, labels)
    ch = calinski_harabasz_score(x, labels)
    db = davies_bouldin_score(x, labels)
    return {
        "silhouette": f"{sil:.4f}",
        "ch": f"{ch:.2f}",
        "db": f"{db:.4f}",
        "inertia": "N/A",
    }


def _kmeans_fit(
    x_std: np.ndarray,
    n_clusters: int = 3,
    init: str = "k-means++",
    max_iter: int = 300,
    algorithm: str = "lloyd",
    random_state: int = 42,
):
    model = KMeans(
        n_clusters=n_clusters,
        init=init,
        max_iter=max_iter,
        algorithm=algorithm,
        random_state=random_state,
        n_init=10,
    )
    labels = model.fit_predict(x_std)
    centers = model.cluster_centers_
    return model, labels, centers


def _cluster_table_from_centers(labels: np.ndarray, centers: np.ndarray) -> Tuple[List[str], List[List[str]]]:
    header = ["簇", "样本数"] + [f"中心{i + 1}" for i in range(centers.shape[1])]
    rows: List[List[str]] = []
    for cid in range(centers.shape[0]):
        count = int(np.sum(labels == cid))
        row = [str(cid + 1), str(count)] + [f"{v:.4f}" for v in centers[cid]]
        rows.append(row)
    return header, rows


def analyze(
    options=None,
    algorithm: str = "kmeans",
    n_clusters: int = 3,
    init: str = "k-means++",
    max_iter: int = 300,
) -> Dict[str, object]:
    """前端默认入口：支持 KMeans 与系统聚类。

    优先兼容 README 推荐的 analyze(options: dict) 形式。
    """
    if options is not None and not isinstance(options, dict):
        to_py = getattr(options, "to_py", None)
        if callable(to_py):
            options = to_py()

    if isinstance(options, dict):
        algorithm = options.get("algorithm", algorithm)
        n_clusters = options.get("n_clusters", n_clusters)
        init = options.get("init", init)
        max_iter = options.get("max_iter", max_iter)
        loss = str(options.get("loss", "lloyd")).strip().lower()
        plot_type = str(options.get("plot_type", "scatter")).strip().lower()
    else:
        loss = "lloyd"
        plot_type = "scatter"

    sheet_selector = ""
    if isinstance(options, dict):
        sheet_selector = str(options.get("sheet_selector", "")).strip()

    dataset_list = _prepare_datasets(sheet_selector)
    n_clusters = max(2, int(n_clusters))
    max_iter = max(10, int(max_iter))
    algorithm = str(algorithm).strip().lower()
    if algorithm == "kmeans":
        plot_type = "scatter"

    svgs: List[str] = []
    summary_rows: List[List[str]] = []
    metrics_first: Dict[str, str] = {"silhouette": "--", "ch": "--", "db": "--", "inertia": "--"}
    detail_header: List[str] = []
    detail_rows: List[List[str]] = []
    kmeans_rows_raw: List[Tuple[str, int, int, List[float]]] = []
    kmeans_max_dim = 0

    for idx, (sheet_label, x) in enumerate(dataset_list):
        x_std = _standardize(x)
        x2 = _pca2(x_std)

        if algorithm == "kmeans":
            km_algo = loss if loss in {"lloyd", "elkan"} else "lloyd"
            model, labels, centers = _kmeans_fit(
                x_std,
                n_clusters=n_clusters,
                init=init,
                max_iter=max_iter,
                algorithm=km_algo,
            )
            metrics = _safe_metrics(x_std, labels)
            metrics["inertia"] = f"{model.inertia_:.4f}"
            svgs.append(_svg_scatter(x2, labels + 1, f"{sheet_label} - KMeans Clustering (K={n_clusters})"))
            summary_rows.append([sheet_label, metrics["silhouette"], metrics["ch"], metrics["db"], metrics["inertia"]])
            if idx == 0:
                metrics_first = metrics
            kmeans_max_dim = max(kmeans_max_dim, centers.shape[1])
            for cid in range(centers.shape[0]):
                count = int(np.sum(labels == cid))
                kmeans_rows_raw.append((sheet_label, cid + 1, count, [float(v) for v in centers[cid]]))
            continue

        if algorithm == "hierarchical":
            method = loss if loss in HIERARCHICAL_METHODS else "ward"
            z = linkage(x_std, method=method)
            labels = fcluster(z, t=n_clusters, criterion="maxclust")
            metrics = _safe_metrics(x_std, labels)
            if plot_type == "dendrogram":
                svgs.append(_svg_dendrogram(z, f"{sheet_label} - Dendrogram ({method})"))
            else:
                svgs.append(_svg_scatter(x2, labels, f"{sheet_label} - Hierarchical Clustering ({method}) (K={n_clusters})"))
            summary_rows.append([sheet_label, metrics["silhouette"], metrics["ch"], metrics["db"], "N/A"])
            counts = [int(np.sum(labels == k)) for k in sorted(np.unique(labels))]
            rows = [[method, str(i + 1), str(c)] for i, c in enumerate(counts)]
            if idx == 0:
                metrics_first = metrics
                detail_header = ["sheet", "方法", "簇编号", "样本数"]
            detail_rows.extend([[sheet_label] + r for r in rows])
            continue

        raise ValueError(f"未知算法: {algorithm}")

    if algorithm == "kmeans":
        detail_header = ["sheet", "簇", "样本数"] + [f"中心{i + 1}" for i in range(kmeans_max_dim)]
        for sheet_label, cluster_id, sample_count, center_vals in kmeans_rows_raw:
            center_strs = [f"{v:.4f}" for v in center_vals]
            if len(center_strs) < kmeans_max_dim:
                center_strs.extend([""] * (kmeans_max_dim - len(center_strs)))
            detail_rows.append([sheet_label, str(cluster_id), str(sample_count)] + center_strs)

    return {
        "svg": svgs[0] if svgs else "",
        "svgs": svgs,
        "metrics": metrics_first,
        "table_header": detail_header or ["sheet", "信息"],
        "table": detail_rows or [["-", "无结果"]],
        "summary_header": ["sheet", "轮廓系数", "CH 指数", "DB 指数", "簇内平方和"],
        "summary_table": summary_rows,
    }


def _prepare_datasets(sheet_selector: str) -> List[Tuple[str, np.ndarray]]:
    if not os.path.exists(UPLOAD_META_PATH):
        _, x = _read_numeric_data()
        return [("sheet1", x)]
    try:
        meta = json.loads(open(UPLOAD_META_PATH, "r", encoding="utf-8").read())
    except Exception as e:
        raise ValueError(f"上传元信息读取失败: {e}") from e
    sheets = meta.get("sheets", [])
    if not sheets:
        _, x = _read_numeric_data()
        return [("sheet1", x)]
    names = [s.get("name", f"sheet{s.get('index', i+1)}") for i, s in enumerate(sheets)]

    if not sheet_selector:
        chosen_idx = [0]
    else:
        chosen_idx = []
        for token in sheet_selector.split(","):
            t = token.strip()
            if not t:
                continue
            i = int(t)
            if i < 1 or i > len(sheets):
                raise ValueError(f"sheet 序号越界: {i}，有效范围 1~{len(names)}")
            chosen_idx.append(i - 1)
        if not chosen_idx:
            chosen_idx = [0]

    datasets: List[Tuple[str, np.ndarray]] = []
    for i in chosen_idx:
        s = sheets[i]
        sname = s.get("name", f"sheet{s.get('index', i+1)}")
        path = s.get("path")
        if not path:
            raise ValueError(f"sheet '{sname}' 缺少 path 信息。")
        df = None
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
            try:
                df = pd.read_csv(path, encoding=enc, sep=None, engine="python")
                break
            except Exception:
                continue
        if df is None:
            raise ValueError(f"sheet '{sname}' CSV 解析失败。")
        num_df = df.select_dtypes(include=[np.number]).dropna(axis=0)
        if num_df.empty:
            raise ValueError(f"sheet '{sname}' 未检测到可用于聚类的数值列。")
        datasets.append((sname, num_df.to_numpy(dtype=float)))
    return datasets


def hierarchical(method: str = "ward", n_clusters: int = 3) -> Dict[str, object]:
    """系统聚类：single/complete/average/centroid/median/ward。"""
    method = method.lower().strip()
    if method not in HIERARCHICAL_METHODS:
        raise ValueError(f"method 必须为 {HIERARCHICAL_METHODS} 之一")
    _, x = _read_numeric_data()
    x_std = _standardize(x)
    x2 = _pca2(x_std)
    z = linkage(x_std, method=method)
    labels = fcluster(z, t=n_clusters, criterion="maxclust")
    metrics = _safe_metrics(x_std, labels)
    counts = [int(np.sum(labels == k)) for k in sorted(np.unique(labels))]
    header = ["方法", "簇编号", "样本数"]
    rows = [[method, str(i + 1), str(c)] for i, c in enumerate(counts)]
    return {
        "svg": _svg_scatter(x2, labels, f"系统聚类({method}) 结果 (K={n_clusters})"),
        "metrics": metrics,
        "table_header": header,
        "table": rows,
    }


def analyze_all_methods(n_clusters: int = 3) -> Dict[str, object]:
    """汇总 notebook 中全部聚类方法的指标。"""
    _, x = _read_numeric_data()
    x_std = _standardize(x)

    results: List[List[str]] = []
    for method in HIERARCHICAL_METHODS:
        z = linkage(x_std, method=method)
        labels = fcluster(z, t=n_clusters, criterion="maxclust")
        m = _safe_metrics(x_std, labels)
        results.append([method, m["silhouette"], m["ch"], m["db"], "N/A"])

    km, labels, _ = _kmeans_fit(x_std, n_clusters=n_clusters)
    m = _safe_metrics(x_std, labels)
    results.append(["kmeans", m["silhouette"], m["ch"], m["db"], f"{km.inertia_:.4f}"])

    return {
        "table_header": ["方法", "轮廓系数", "CH 指数", "DB 指数", "簇内平方和"],
        "table": results,
    }
