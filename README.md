# StatCore — 多元统计分析

基于 **Pyodide**（Python → WebAssembly）在浏览器本地运行的统计分析工具。

- **纯静态部署** — 最终产物是单个 HTML 文件，可托管于任何静态服务
- **离线计算** — 首次加载后，所有操作在本地 Wasm 中执行，不需后端服务器
- **无服务器架构** — 浏览器即运行时，Python 代码在 Pyodide 沙箱内运行

---
## 一：架构总览

```
┌─ 浏览器 JS ────────────────────────────────────────────────────────┐
│                                                                   │
│  html/modules/xxx.html          js/bridge.js                      │
│  ┌──────────────────────┐      ┌─────────────────────┐            │
│  │ data-param="alpha"   │ ──→  │ collectParams() →   │            │
│  │ data-param="k"       │      │ {alpha: 0.5, k: 3}  │            │
│  │                      │      │                     │            │
│  │ class="btn-run"      │ ──→  │ captureStdout(      │            │
│  │ data-module="Xxx"    │      │   "Xxx","analyze",  │            │
│  │ data-func="analyze"  │      │   {alpha:0.5,k:3}   │            │
│  │                      │      │ )                   │            │
│  │ .chart-container     │      │                     │            │
│  │ .metric-value        │ ←──  │ renderModuleResult()│            │
│  │ .simple-table        │      │                     │            │
│  │ .py-output           │      │                     │            │
│  └──────────────────────┘      └──────────┬──────────┘            │
│                                           │                       │
│                              pyodide.globals.get("Xxx").analyze() │
│                                           │                       │
│  ┌─ WASM / Pyodide ──────────────────────────────────────┐        │
│  │                                                       │        │
│  │  python/Xxx.py                                        │        │
│  │                                                       │        │
│  │  def analyze(options):                                │        │
│  │      # 1. 读虚拟文件系统                                │        │
│  │      meta = json.load(open("/home/pyodide/upload_meta"))│       │
│  │      df = pd.read_csv(meta["sheets"][0]["path"])       │        │
│  │                                                        │        │
│  │      # 2. 取参数                                        │        │
│  │      alpha = options.get("alpha", 0.5)                 │        │
│  │      k = options.get("k", 3)                           │        │
│  │                                                        │        │
│  │      # 3. 计算 + 绘图                                   │        │
│  │      buf = io.BytesIO()                                │        │
│  │      fig.savefig(buf, format="svg")                    │        │
│  │      svg_str = buf.getvalue().decode()                 │        │
│  │                                                        │        │
│  │      # 4. 返回结构化结果                                 │        │
│  │      return {                                          │        │
│  │          "svgs": [svg_str],                            │        │
│  │          "metrics": {"n": n, "k": k},                  │        │
│  │          "table": [["a","1"],["b","2"]],               │        │
│  │          "tables": [{"header":..., "rows":...}]        │        │
│  │      }                                                 │        │
│  │                                                        │        │
│  └────────────────────────────────────────────────────────┘        │
│                                           │                        │
│                              result.toJs()  (Python dict → JS)     │
│                                           ▼                        │
│  renderModuleResult(scope, out)                                    │
│  ├── .py-output.textContent     ← out.lines (print 捕获)            │
│  ├── .chart-container.innerHTML ← out.result.svgs[]                │
│  ├── .metric-value.textContent  ← Object.values(out.result.metrics)│
│  ├── .simple-table (按 DOM 顺序) ← out.result.tables[].rows[]       │
│  └── .simple-table              ← out.result.tables[].rows[]       │
│                                                                    │
│  DOM 更新，用户看到结果                                               │
└────────────────────────────────────────────────────────────────────┘
```

**核心数据流**：

1. 用户上传文件 → JS 写入原始 CSV 到 VFS，自动调用 `DataClean.auto_clean()` 生成清洗版
2. `_currentDataPath`（清洗后）和 `_currentRawDataPath`（原始）存入 JS 全局
3. 用户点击「运行分析」→ JS 收集 `[data-param]` 参数，自动注入 `data_path`
4. JS 通过 `pyodide.globals.get("Module").funcName(params)` 调用 Python
5. 参数自动从 JS 对象转为 Python dict（Pyodide JsProxy 机制）
6. Python 直接从 `params.data_path` 读取 CSV 文件，无需再读元数据 JSON
7. Python 执行分析，matplotlib 生成 SVG，返回 dict
8. JS 根据返回值的键名，将结果填充到 HTML 对应位置

---

## 二：项目结构

```
.
├── run_localhost.py       # 启动一个localhost服务器
├── build.py               # 构建脚本
├── requirements.txt       # Python 构建依赖
├── modules.json           # 存放导航栏与python文件加载顺序
├── .gitignore
├── README.md
│
├── html/
│   ├── index.html         # 模板（含 <!--BUILD_*--> 占位符）
│   └── modules/           # 功能模块的 HTML 片段
│       ├── clustering.html
│       ├── visualization.html
│       ├── test.html
│       └── ...
│
├── css/
│   └── style.css          # 全部样式
│
├── js/
│   ├── boot.js            # Pyodide 初始化 + 加载进度
│   ├── navigation.js      # 模块切换导航
│   └── bridge.js          # 文件上传 + Python↔JS 通信桥
│
├── python/                # Python 源码
│   ├── test.py            # Pyodide 功能测试
│   ├── Clustering.py      # 聚类分析
│   ├── Pca.py             # 主成分分析
│   ├── Factor.py          # 因子分析
│   ├── Correspondence.py  # 对应分析
│   ├── CorrelationRegression.py  # 相关与回归
│   ├── CanonicalCorrelation.py   # 典型相关
│   ├── ExtendedLinear.py  # 扩展线性
│   ├── Evaluation.py      # 统计评价
│   └── Visualization.py   # 可视化
│
├── doc/                   # 文档（预留）
│
└── build/                 # 构建产物（运行 build.py 后生成）
	├── index.inline.html  # 全内联版本，你可以点击它来预览效果
    ├── index.html
    ├── css/style.css
    └── js/*.js
```

注意：

- **如果你不想了解具体机制**，那么请直接看[[#四：如何编写一个模块]]和[[#构建]]
- 如果你把代码放错位置了，比如把html代码放到了python目录下，**那么是不会有任何效果的**
- 除非你想要引入多线程等特性，否则不必操心服务器等事宜

___
## 三：文件上传与虚拟文件系统

Pyodide 在 WASM 内存中模拟了一个文件系统（Emscripten FS）。上传文件的流程：

### 上传流程

```javascript
// JS 侧（bridge.js）
// 1. 将用户选择的 sheet 转为 CSV 写入 VFS
const rawPath = `/home/pyodide/${baseName}.${sheetName}.csv`
pyodide.FS.writeFile(rawPath, csvContent)

// 2. 自动调用清洗
const cleanedPath = `/home/pyodide/${baseName}.${sheetName}.cleaned.csv`
pyodide.globals.get('DataClean').auto_clean(rawPath, cleanedPath)

// 3. 路径存入 JS 全局，供后续模块调用
window._currentDataPath = cleanedPath     // 清洗后数据
window._currentRawDataPath = rawPath      // 原始数据
```

```python
# Python 侧 — 直接从参数读取路径，不再读 JSON
def analyze(options):
    data_path = options.get('data_path')   # JS 自动注入
    df = pd.read_csv(data_path)           # 直接使用
```

不再使用 `upload_meta.json` 和 `upload_name.txt`。CSV 路径格式为 `/home/pyodide/{原始文件名}.{sheet名}.csv`。

---

## 四：如何编写一个模块

添加一个新模块只需三步：**写 Python、写 HTML、注册**。不需要碰 CSS 或 JS（除非你觉得默认样式不好看，想要自定义css）。

### 步骤 1：编写 Python 分析函数

在 `python/` 下新建 `.py` 文件，导出一个**接收 dict 参数、返回 dict 结果**的函数。

**约定**：
- 函数签名：`def 函数名(options: dict) -> dict`
- 数据读取：通过 `options.get('data_path')` 获取路径（JS 自动注入，直接 `pd.read_csv()`）
- 参数读取：`options.get("参数名", 默认值)`
- 图表输出：matplotlib 导出为 SVG 字符串
- 异常处理：失败时返回 `{"error": "错误信息"}`

```python
# python/MyModule.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io


def analyze(options):
    if not isinstance(options, dict):
        options = options.to_py()
    threshold = options.get('threshold', 0.5)
    data_path = options.get('data_path')

    if not data_path:
        return {"error": "请先在左侧上传数据文件"}

    try:
        df = pd.read_csv(data_path)
    except Exception as e:
        return {"error": f"读取数据失败: {e}"}

    # --- 分析逻辑 ---
    # ... 你的计算 ...

    # --- 绘图 ---
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(...)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='svg')
    plt.close(fig)
    svg_str = buf.getvalue().decode()

    # --- 返回结构化结果 ---
    return {
        "svgs": [svg_str],
        "metrics": {
            "样本数": n_samples,
            "变量数": n_features,
        },
        "tables": [
            {"header": ["变量", "得分"], "rows": [["A", 1.23], ["B", 4.56]]},
        ],
    }
```

### 步骤 2：编写模块 HTML 模板

在 `html/modules/` 下新建 `.html` 文件（不过目前课程作业要求的html模板都已经建立好了，除非有特殊需要，不然是不需要新建的）。

**结构要求**：
- 最外层：`<div class="module-content" id="模块ID">`
- 参数控件：使用 `data-param="参数名"` 属性（自动收集）
- 运行按钮：`class="btn-run"` + `data-module="Python模块名"` + `data-func="Python函数名"`
- 结果容器使用约定的 class 名称（见下文）

```html
<!-- html/modules/mymodule.html -->
<div class="module-content" id="mymodule">
  <div class="page-header">
    <div class="header-left">
      <h1>我的模块</h1>
      <div class="breadcrumb"><i class="fas fa-folder-open"></i> 分类 / 子分类</div>
    </div>
    <div class="header-actions">
      <button class="btn-primary btn-run" data-module="MyModule" data-func="analyze">
        <i class="fas fa-play"></i> 运行分析
      </button>
    </div>
  </div>

  <!-- 参数卡片：所有带 data-param 的元素会被自动收集 -->
  <div class="param-card">
    <div class="param-title"><i class="fas fa-sliders-h"></i> 参数配置</div>
    <div class="param-grid">
      <div class="param-field">
        <label>阈值</label>
        <input class="fake-select-control" data-param="threshold" type="number" min="0" max="1" step="0.1" value="0.5">
      </div>
      <div class="param-field">
        <label>方法</label>
        <select class="fake-select-control" data-param="method">
          <option value="a" selected>方法 A</option>
          <option value="b">方法 B</option>
        </select>
      </div>
    </div>
  </div>

  <!-- 图表区域 -->
  <div class="chart-card">
    <div class="chart-header">
      <h3><i class="fas fa-chart-bar"></i> 结果图</h3>
    </div>
    <div class="chart-container" style="min-height:240px;display:flex;align-items:center;justify-content:center;color:#7a8c9d;">
      点击「运行分析」后显示图形
    </div>
    <pre class="py-output" style="margin:12px 8px 0;padding:10px 12px;background:#f6f9fc;border:1px solid #e2eaf2;border-radius:8px;color:#3e5468;font-size:12px;white-space:pre-wrap;">等待运行...</pre>
  </div>

  <!-- 指标行 -->
  <div class="metrics-row">
    <div class="metric-item">
      <div class="metric-label"><i class="fas fa-hashtag"></i> 样本数</div>
      <div class="metric-value">--</div>
    </div>
    <div class="metric-item">
      <div class="metric-label"><i class="fas fa-list"></i> 变量数</div>
      <div class="metric-value">--</div>
    </div>
  </div>

  <!-- 表格 -->
  <div class="table-preview">
    <div class="preview-header">
      <span><i class="fas fa-table"></i> 结果表</span>
    </div>
    <table class="simple-table">
      <thead><tr><th>变量</th><th>值</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
</div>
```

### 步骤 3：注册模块

在 `modules.json` 中添加导航项和 Python 加载顺序：

```json
{
  "nav": [
    {"type": "button", "module": "mymodule", "icon": "fas fa-cog", "label": "我的模块"},
  ],
  "python_order": [
    "MyModule",
  ]
}
```

运行 `python build.py` 即可。

同样的，大部分需要使用的模块已经注册好了，除非有新的需要，一般不用修改这里

---

### 完整示例

以主成分分析模块为例：

编写python代码（可以直接问ai），**放在python目录下**。大部分必须的模块已经创建好了。如果一定要新建，参考前文的新建方法。

```python
# 该文件位于python/Pca.py
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


	# ......部分处理过程省略......
	
	# svgs用于储存matplotlib绘制的图片
    svgs = []

    # 图1: 方差解释比例柱状图
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    
	# ......绘图部分省略.......
	
    buf = io.BytesIO()
    fig1.savefig(buf, format='svg')
    plt.close(fig1)
    # 将绘制的图片放到svgs中
    svgs.append(buf.getvalue().decode())

    # 图2: 累积方差折线图
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    
	# ......绘图部分省略......
    buf = io.BytesIO()
    
    fig2.savefig(buf, format='svg')
    plt.close(fig2)
    # 将绘制的图片放入svgs中
    svgs.append(buf.getvalue().decode())

    # 图3: 得分散点图
	# ......绘图部分省略...... 

    # 图4: 双标图
    # ......绘图部分省略...... 
    
    # 载荷矩阵
    # table用于接受多个表格。这些表格在python中表现为嵌套列表
    table = []
    pc_names = [f'PC{i+1}' for i in range(n_components)]
    for i, vn in enumerate(feature_names):
        row = [vn] + [f'{loadings[i, j]:.4f}' for j in range(n_components)]
        table.append(row)
    # 构建表头。在这里，表头形如:
    # variable    PC1    PC2    PC3    ......
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

```

编写html（可以直接问ai），**放在html/modules目录下**。大部分必须的模块已经创建好了。如果一定要新建，参考前文的新建方法。


```html
%% 该文件位于html/modules/pca.html
在遵循上述规范要求的前提下，是不需要额外编写js代码的。css代码也不用编写——除非你觉得默认样式不好看。%%
<div class="module-content" id="pca">
  <div class="page-header">
    <div class="header-left">
      <h1>主成分分析 · PCA</h1>
      <div class="breadcrumb"><i class="fas fa-folder-open"></i> 降维 / PCA / 方差解释</div>
    </div>
    <div class="header-actions">
      <button class="btn-primary btn-run" data-module="Pca" data-func="pca" disabled>
        <i class="fas fa-play"></i> 运行分析
      </button>
    </div>
  </div>

  <div class="param-card">
    <div class="param-title"><i class="fas fa-sliders-h" style="color:#2a5c8a;"></i> 分析参数</div>
    <div class="param-grid">
      <div class="param-field">
        <label>主成分个数</label>
        <input type="number" data-param="n_components" min="2" max="20" placeholder="自动"
               style="background:#f9fbfd;border:1px solid #d6e0ea;border-radius:40px;padding:10px 18px;font-size:14px;width:140px;text-align:center;">
      </div>
    </div>
    <p style="color:#738fa0; margin-top:10px; font-size:12px;">留空自动选择（最多 6 个）。请先在左侧上传数据文件。</p>
  </div>

  <div class="metrics-row">
    <div class="metric-item">
      <div class="metric-label"><i class="fas fa-hashtag"></i> 样本数</div>
      <div class="metric-value">--</div>
    </div>
    <div class="metric-item">
      <div class="metric-label"><i class="fas fa-list"></i> 变量数</div>
      <div class="metric-value">--</div>
    </div>
    <div class="metric-item">
      <div class="metric-label"><i class="fas fa-cubes"></i> 主成分数</div>
      <div class="metric-value">--</div>
    </div>
    <div class="metric-item">
      <div class="metric-label"><i class="fas fa-chart-pie"></i> 累积方差</div>
      <div class="metric-value">--</div>
    </div>
  </div>

  <div class="chart-card">
    <div class="chart-header">
      <h3><i class="fas fa-chart-bar" style="margin-right:8px; color:#1e4b6e;"></i>方差解释 + 降维可视化</h3>
    </div>
    <div class="chart-container" style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
    </div>
  </div>

  <div class="table-preview">
    <div class="preview-header">
      <span><i class="fas fa-table"></i> 载荷矩阵</span>
      <span class="badge">变量在各主成分上的权重</span>
    </div>
    <table class="simple-table">
      <thead><tr><th>变量</th><th>PC1</th><th>PC2</th><th>PC3</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="table-preview">
    <div class="preview-header">
      <span><i class="fas fa-table"></i> 样本得分</span>
      <span class="badge">各样本的主成分得分</span>
    </div>
    <table class="simple-table">
      <thead><tr><th>样本</th><th>PC1</th><th>PC2</th><th>PC3</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
</div>

```

___
## 五：参数收集机制

`bridge.js` 的 `collectParams(container)` 函数自动扫描模块容器内的所有 `[data-param]` 元素：

```javascript
function collectParams(container) {
  const params = {}
  container.querySelectorAll('[data-param]').forEach(el => {
    const key = el.dataset.param
    if (el.type === 'number') {
      const v = el.value.trim()
      params[key] = v === '' ? null : Number(v)    // number → 数字
    } else {
      params[key] = el.value                        // 其他 → 字符串
    }
  })
  return params
}
```

| HTML 元素 | `data-param` 值 | 收集到的 JS 类型 |
|-----------|----------------|-----------------|
| `<input type="number" data-param="k" value="3">` | `k` | `number` (3) |
| `<select data-param="method">` | `method` | `string` ("kmeans") |
| `<input type="text" data-param="name" value="abc">` | `name` | `string` ("abc") |

收集后的 JS 对象 `{k: 3, method: "kmeans"}` 通过 Pyodide 自动转为 Python dict，传入你的函数。

---

## 六：Python 返回值与渲染映射

`renderModuleResult()` 根据返回值的 key 名，将数据填充到 HTML 的对应位置。

### 返回值的键与 DOM 映射

| 返回键       | 类型       | 渲染目标                              | 说明                                                    |
| --------- | -------- | --------------------------------- | ----------------------------------------------------- |
| `error`   | string   | `.py-output` + `.chart-container` | 显示错误信息，渲染终止                                           |
| `svgs`    | string[] | `.chart-container`                | 多个 SVG 从上到下排列                                         |
| `svg`     | string   | `.chart-container`                | 单个 SVG（`svgs` 优先）                                     |
| `metrics` | object   | `.metric-value` 元素                | 按 `Object.values()` 顺序填充                              |
| `tables`  | object[] | `.simple-table` 元素                | 按 DOM 顺序填充，每一项 `{header: string[], rows: string[][]}` |

### 典型返回值示例

```python
# 成功返回（多数据）
return {
    "svgs": ["<svg>...</svg>", "<svg>...</svg>"],
    # 指标，有多个指标时，返回顺序需要与html中，metric-value摆放的顺序保持一致
    # 目前指标的键是用不到的，因此其命名只要方便就好
    "metrics": {"A": 10, "B": 20, "C": 30},
    # 表格。有多个表格时，返回顺序需要与html中，simple-table摆放的顺序一致
    "tables": [
        {"header": ["变量", "得分"], "rows": [["x", "1.0"], ["y", "2.0"]]},
        {"header": ["样本", "得分"], "rows": [["s1", "0.5"], ["s2", "0.8"]]},
    ],
}

# 成功返回（单表）
return {
    "tables": [{"header": ["统计指标", "值"], "rows": ...}],
}

# 返回错误
return {"error": "数据包含非数值列，请检查上传文件"}
```

### SVG 图表的生成规范

```python
import io
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(8, 4))
# ... 绘图 ...
fig.tight_layout()
buf = io.BytesIO()
fig.savefig(buf, format='svg')
plt.close(fig)
svg_str = buf.getvalue().decode()  # ← 这是字符串，不是文件
```

**关键**：
- matplotlib 导出为 **SVG 字符串**（不是 PNG 文件，不是 base64）
- 返回的 SVG 字符串被直接 `.innerHTML` 到 DOM 中
- 每个 `plt.close(fig)` 释放内存（WASM 内存有限）
- 想生成多张图就 append 多个 SVG 到 `svgs[]`

---

## 七：print 输出与错误处理

### print 捕获

JS 在调用 Python 函数前执行 `pyodide.setStdout({ batched: s => lines.push(s) })`，将 Python 的 `print()` 输出逐行捕获到 `lines[]` 数组中。

函数返回后，`lines.join('\n')` 显示在模块的 `<pre class="py-output">` 中。

```python
print("开始 PCA 计算...")
print(f"数据形状: {df.shape}")
# 这些文字将出现在界面上的 .py-output 区域
```

### 错误处理

```python
# Python 侧返回 error 键
try:
    df = pd.read_csv(csv_path)
except Exception as e:
    return {"error": f"读取数据失败: {e}"}
```

`bridge.js` 检测到 `out.result.error` 后：
1. 将错误信息写入 `.py-output`
2. 在 `.chart-container` 中显示红色错误信息
3. 终止后续渲染

```javascript
if (out.result.error) {
    outputPre.textContent = '错误: ' + out.result.error
    chartBox.innerHTML = `<div style="color:#c0392b;">${out.result.error}</div>`
    return  // 不继续渲染其他内容
}
```

---

## 八：模块开发工作流

```bash
# 1. 在 python/ 下新建 .py 文件
# 2. 在 html/modules/ 下新建 .html 文件
# 3. 在 modules.json 中注册

# 4. 构建
python build.py

# 5. 启动本地服务器测试
python run_localhost.py

# 6. 调试循环
#    - 修改 .py → python build.py → 刷新浏览器 → 查看 .py-output
#    - 修改 .html → python build.py → 刷新浏览器
#    - 修改 .css/.js → 无需构建，直接刷新浏览器
```

**调试提示**：Python 代码中添加 `print()` 是主要的调试手段，输出会显示在模块的 `.py-output` 区域。F12 控制台可查看 JS 错误日志。

---

## 九：构建与部署

### 构建

安装python依赖，然后运行`build.py`

```bash
pip install -r requirements.txt
python build.py
```

构建产物在 `build/` 目录：
- `index.html` — 标准版本（引用外部 CSS/JS）
- `index.inline.html` — 单文件版本（CSS/JS 全部内联）

### 构建过程

`build.py` 对 `html/index.html` 模板做三次字符串替换：

| 占位符 | 替换为 |
|--------|--------|
| `<!--BUILD_PYTHON-->` | `<script type="text/python-src" data-module="...">` 标签，每个 `.py` 文件一个 |
| `<!--BUILD_MODULES-->` | `window.MODULE_HTML = { "模块名": "HTML内容" }` |
| `<!--BUILD_NAV-->` | 导航按钮列表（从 `modules.json` 生成） |

随后可选内联本地 CSS/JS 文件到 HTML 中，生成 `index.inline.html`。

### 本地服务器

```bash
# 一键构建 + 启动
python run_localhost.py

# 仅构建
python run_localhost.py --build-only

# 指定端口
python run_localhost.py --port 5173
```

大部分情况下，双击`build/index.inline.html`或者`build/index.html`可以正常运行。如果遇到无法运行的情况，可以尝试启动服务器，并使用浏览器打开对应端口。默认情况下，需要把[http://127.0.0.1:8000]()输入到浏览器中。如果你指定了端口，比如5173，那么就打开[http://127.0.0.1:5173]()

如果遇到卡顿，迟迟加载不出来，可以考虑刷新/等一会/更换网络。

### 部署

将 `build/index.inline.html` 部署到任意静态服务器，即可工作，无需其他资源。该部分已经由前端组完成了。点击[StatCore - 多元统计分析](https://statistic-analysis.netlify.app/)可查看效果。

---

## 十：依赖

| 依赖                                      | 用途                | 类型           |
| --------------------------------------- | ----------------- | ------------ |
| [Pyodide](https://pyodide.org/) v0.25.0 | 浏览器端 Python 运行时   | CDN 自动加载     |
| [SheetJS](https://sheetjs.com/) (xlsx)  | 浏览器端 Excel 解析     | CDN 自动加载     |
| Pygments                                | 构建时 Python 代码语法高亮 | pip 安装（可选）   |
| numpy                                   | 数值计算              | Pyodide 自动加载 |
| matplotlib                              | 数据可视化             | Pyodide 自动加载 |
| pandas                                  | 数据处理              | Pyodide 自动加载 |
| scipy                                   | 科学计算              | Pyodide 自动加载 |
| scikit                                  | 机器学习              | Pyodide 自动加载 |
# 最后

编写模块后，可以在浏览器上跑一跑，确认效果与自己的预期相同。如果想要方便地提交代码/接收更新，请前往github，确认自己有一个github账号，且电脑安装了git，了解基本用法。然后，运行

```bash
git clone https://github.com/stat-analysis-hnu-wx-2026/statistic-analysis
```

为了推送更新，可以加入`stat-analysis-hnu-wx-2026`这个临时组织。

如果不想使用git，请确认效果无误后，将两份文件：python代码，html代码（可以空着，不过实际上拿着代码要求ai写出对应的html，把这份文件也甩给ai，ai就可以给出很好的效果）打包发送给前端组。如果你修改了更多的文件，那么把那些文件一并打包，并注明修改了第几行到第几行。
