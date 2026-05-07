import io
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score


HIERARCHICAL_METHODS = ["single", "complete", "average", "centroid", "median", "ward"]


def _read_numeric_data(data_path: str) -> Tuple[pd.DataFrame, np.ndarray]:
    df = pd.read_csv(data_path)
    num_df = df.select_dtypes(include=[np.number]).dropna(axis=0)
    if num_df.empty:
        raise ValueError("未检测到可用于聚类的数值列，请上传包含数值列的 CSV/Excel。")
    return df, num_df.to_numpy(dtype=float)


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


def analyze(options=None) -> Dict[str, object]:
    if options is not None and not isinstance(options, dict):
        to_py = getattr(options, "to_py", None)
        if callable(to_py):
            options = to_py()

    algorithm = "kmeans"
    n_clusters = 3
    init = "k-means++"
    max_iter = 300
    loss = "lloyd"
    plot_type = "scatter"
    data_path = None

    if isinstance(options, dict):
        algorithm = str(options.get("algorithm", algorithm)).strip().lower()
        n_clusters = int(options.get("n_clusters", n_clusters))
        init = options.get("init", init)
        max_iter = int(options.get("max_iter", max_iter))
        loss = str(options.get("loss", "lloyd")).strip().lower()
        plot_type = str(options.get("plot_type", "scatter")).strip().lower()
        data_path = options.get("data_path")

    if not data_path:
        return {"error": "请先在左侧上传数据文件"}

    dataset_list = _prepare_datasets(data_path)
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

    summary_header = ["sheet", "轮廓系数", "CH 指数", "DB 指数", "簇内平方和"]
    return {
        "svg": svgs[0] if svgs else "",
        "svgs": svgs,
        "metrics": metrics_first,
        "tables": [
            {"header": detail_header or ["sheet", "信息"], "rows": detail_rows or [["-", "无结果"]]},
            {"header": summary_header, "rows": summary_rows},
        ],
    }


def _prepare_datasets(data_path: str) -> List[Tuple[str, np.ndarray]]:
    df = pd.read_csv(data_path)
    num_df = df.select_dtypes(include=[np.number]).dropna(axis=0)
    if num_df.empty:
        raise ValueError("未检测到可用于聚类的数值列。")
    return [("data", num_df.to_numpy(dtype=float))]


def hierarchical(method: str = "ward", n_clusters: int = 3, data_path: str = None) -> Dict[str, object]:
    if not data_path:
        return {"error": "请先上传数据文件"}
    method = method.lower().strip()
    if method not in HIERARCHICAL_METHODS:
        raise ValueError(f"method 必须为 {HIERARCHICAL_METHODS} 之一")
    _, x = _read_numeric_data(data_path)
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
        "tables": [{"header": header, "rows": rows}],
    }


def analyze_all_methods(n_clusters: int = 3, data_path: str = None) -> Dict[str, object]:
    if not data_path:
        return {"error": "请先上传数据文件"}
    _, x = _read_numeric_data(data_path)
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
        "tables": [{"header": ["方法", "轮廓系数", "CH 指数", "DB 指数", "簇内平方和"], "rows": results}],
    }
