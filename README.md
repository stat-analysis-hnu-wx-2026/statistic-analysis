# StatCore — 多元统计分析

基于 **Pyodide**（Python → WebAssembly）在浏览器本地运行的全部统计分析工具。

---

## 为什么选择 Pyodide？

本项目所有 Python 代码通过 Pyodide 在浏览器的 WebAssembly 沙箱中执行，**不需要任何后端服务器**。

- **纯静态部署** — 最终产物是 `.html + .css + .js`，可托管于 Cloudflare Pages、GitHub Pages、Netlify 等任意静态服务，部署成本几乎为零
- **离线计算** — 除首次加载需要联网下载 Pyodide 运行时，后续所有操作在本地 Wasm 中执行

### 网络说明

首次加载时浏览器会从 CDN 下载 Pyodide 运行时 + numpy + matplotlib（合计约 13 MB）。国内网络环境下可能因 CDN 波动导致加载缓慢或超时。如遇加载失败：

1. 等待片刻后刷新页面重试
2. 切换网络环境（如移动热点 → 有线 / 反之）

---

## 项目结构

```
.
├── build.py               # 构建脚本
├── requirements.txt       # Python 构建依赖
├── .gitignore
├── README.md
│
├── html/
│   ├── index.html         # 模板（含 <!--BUILD_*--> 占位符）
│   └── modules/           # 功能模块的 HTML 片段（10 个）
│       ├── clustering.html
│       ├── visualization.html
│       ├── test.html
│       └── ...
│
├── css/
│   └── style.css          # 全部样式（单文件，约 680 行）
│
├── js/
│   ├── boot.js            # Pyodide 初始化 + 加载进度
│   ├── navigation.js      # 模块切换导航
│   └── bridge.js          # 文件上传 + Python↔JS 通信桥
│
├── python/                # Python 源码（11 个文件）
│   ├── test.py            # Pyodide 功能测试
│   ├── File.py            # 文件上传处理
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
    ├── index.html
    ├── css/style.css
    └── js/*.js
```

---

## 构建流程

### 安装依赖

```bash
pip install -r requirements.txt
```

### 执行构建

```bash
python build.py
```

### 本地运行（localhost）

Pyodide 需要通过 HTTP 访问，不能直接双击 `html` 文件。

推荐一键命令：

```bash
python run_localhost.py
```

默认会先构建，再在 `http://127.0.0.1:8000` 启动服务。

常用参数：

```bash
# 仅构建，不启动服务
python run_localhost.py --build-only

# 指定端口
python run_localhost.py --port 5173

# 跳过构建，直接服务 build/
python run_localhost.py --skip-build
```

### 构建做了什么

`build.py` 读取模板 `html/index.html`，通过字符串替换完成拼装：

| 模板占位符 | 替换为 |
|---|---|
| `<!--BUILD_PYTHON-->` | 所有 `python/*.py`，内联为 `<script type="text/python-src" data-module="...">` 标签 |
| `<!--BUILD_MODULES-->` | 所有 `html/modules/*.html`，内联为 `<script>window.MODULE_HTML = { "模块名": \`...\` }</script>` |

随后将 `css/` 和 `js/` 复制到 `build/` 目录。

### 部署

将 `build/` 目录下所有文件上传到静态服务器即可。

---

## Python ↔ JavaScript 通信

### 文件上传

```javascript
// bridge.js — 用户拖拽/选择文件后
pyodide.FS.writeFile('/home/pyodide/data.csv', content)
```

```python
# python/File.py — Python 侧读取
import pandas as pd
df = pd.read_csv('/home/pyodide/data.csv')

# 或原生文件操作
with open('/home/pyodide/data.csv') as f:
    for line in f:
        ...
```

### 参数传递

前端通过 `bridge.js` 的 `captureStdout()` 调用 Python 函数：

```javascript
// bridge.js
function captureStdout(moduleName, funcName, params = {}) {
    const mod = pyodide.globals.get(moduleName)
    const fn = mod[funcName]
    // params 的值被展开为位置参数传入
    Promise.resolve(fn(...Object.values(params)))
        .then(result => result.toJs({ dict_converter: Object.fromEntries }))
}
```

当前机制：`captureStdout('Mod', 'func', { a: 1, b: 2 })` → Python 侧 `func(1, 2)`。

**推荐写法** — Python 函数接收一个 dict 参数，便于扩展：

```python
# python/Clustering.py
def analyze(options):
    k = options.get('k', 3)
    algorithm = options.get('algorithm', 'k-means++')
    max_iter = options.get('max_iter', 300)
    data = pd.read_csv('/home/pyodide/data.csv')
    ...
```

```javascript
// 前端调用
captureStdout('Clustering', 'analyze', {
    k: 5,
    algorithm: 'k-means++',
    max_iter: 500
})
```

### 返回值约定

Python 函数应返回 dict，经 `toJs({ dict_converter: Object.fromEntries })` 转换为 JS 对象后，`bridge.js` 按以下键名渲染：

| 键 | 类型 | 用途 |
|---|---|---|
| `svg` | string | matplotlib 生成的 SVG 图表，直接设为 `.chart-container` 的 innerHTML |
| `metrics` | object | 指标数值，按顺序填入 `.metric-value` 元素 |
| `table` | string[][] | 表格数据，每行一个数组，渲染到 `.simple-table tbody` |
| `table_header` | string[] | 表头，渲染到 `.simple-table thead tr` |
| 其他 | — | 暂不处理 |

---

## 如何添加新模块

1. 在 `python/` 下新建 `.py` 文件，实现统计方法（函数返回 dict）
2. 在 `html/modules/` 下新建 `.html` 文件，编写 UI 布局（最外层为 `<div class="module-content" id="xxx">`）
3. 在 `html/index.html` 的 `<nav class="nav-menu">` 中添加按钮：`<button class="nav-item" data-module="xxx">`
4. 运行 `python build.py`

---

## 调试

推荐流程：

```
在 Python 函数中添加 print() → python build.py → 刷新浏览器
→ 查看模块内的 Python 输出框
→ (可选) F12 → 控制台查看详细 JS 日志
```

常见问题：

- **`resultKeys: Array(0)`** — `toJs()` 遗漏了 `{ dict_converter: Object.fromEntries }` 参数
- **`Module "xxx" not found`** — 运行 `build.py` 了吗？
- **加载失败 / 进度条卡住** — CDN 网络问题，刷新重试或更换网络

---

## 依赖

| 依赖 | 用途 | 类型 |
|---|---|---|
| [Pyodide](https://pyodide.org/) v0.25.0 | 浏览器端 Python 运行时 | CDN 自动加载 |
| Pygments | 构建时 Python 代码语法高亮（Monokai 主题） | `pip install pygments` |
| numpy | 数值计算（通过 Pyodide 加载） | CDN 自动加载 |
| matplotlib | 数据可视化（通过 Pyodide 加载） | CDN 自动加载 |
