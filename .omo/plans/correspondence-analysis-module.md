# 对应分析模块实现计划

## 1. 概述

对应分析（Correspondence Analysis, CA）用于分析两个分类变量之间的关联性，将列联表的 row profile 和 column profile 投影到同一低维空间进行可视化。这是当前唯一未实现的分析模块。

**引用模式**: PCA（降维+可视化）、Factor（SVD分解+载荷表）

---

## 2. Python 端 (`python/Correspondence.py`)

### 2.1 `get_columns(options)` - 获取列名列表

- 读取 `data_path`
- 返回 `{columns: [...]}`（所有列名，用于 UI 下拉框）

### 2.2 `analyze(options)` - 主分析函数

**输入参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `data_path` | str | CSV 路径 |
| `row_var` | str | 行变量列名（分类） |
| `col_var` | str | 列变量列名（分类） |
| `n_dims` | int | 显示维度数（默认 2，最大 min(n_rows, n_cols)-1） |

**算法流程**:
1. 读 CSV → `df`
2. 从 `df[[row_var, col_var]]` 构造列联表（`pd.crosstab`）
3. 计算：
   - 总频数 N = sum(F)
   - 概率矩阵 P = F / N
   - 行质量（行和）r = P 的行和
   - 列质量（列和）c = P 的列和
   - 行 chi² 距离行向量（用于 cos² 计算）
   - 标准化残差矩阵 S = D_r^(-½)(P - rcᵀ)D_c^(-½)
   - SVD: S = U Σ Vᵀ
   - 奇异值 σ_k, 惯性 λ_k = σ_k²
   - 行标准坐标 Φ = D_r^(-½)U
   - 列标准坐标 Γ = D_c^(-½)V
   - 行主坐标 F = ΦΣ（= D_r^(-½)UΣ）
   - 列主坐标 G = ΓΣ（= D_c^(-½)VΣ）
   - 对称图坐标（α=0.5）：行 = ΦΣ^(½), 列 = ΓΣ^(½)
   - 贡献度：行贡献 col_to_dim_k = r_i·F_ik²/λ_k, 列同理
   - 质量（cos²）：行 cos²_ik = F_ik² / (行 i 到 centroid 的 chi² 距离²)

**输出图表 (SVGs)**:
| 图号 | 名称 | 说明 |
|------|------|------|
| 1 | 对称图 (Symmetric Map) | Dim1 × Dim2 散点图，行列点用不同颜色/形状，标注标签 |
| 2 | 惯性碎石图 (Scree Plot) | 各维度的惯性柱状图 + 累积折线 |
| 3 | 行贡献柱状图 | Top N 行对 Dim1+Dim2 的贡献 |
| 4 | 列贡献柱状图 | Top N 列对 Dim1+Dim2 的贡献 |

**输出指标 (metrics)**:
| 指标 | 说明 |
|------|------|
| 行类别数 | row_var 的唯一值个数 |
| 列类别数 | col_var 的唯一值个数 |
| 总惯性 | sum(λ_k) |
| 前2维解释率 | (λ₁+λ₂)/sum(λ) |

**输出表格**:
| 表号 | 名称 | 列 |
|------|------|----|
| 1 | 惯性分解表 | 维度, 奇异值, 惯性, 解释率%, 累积% |
| 2 | 行坐标表 | 类别, Dim1, Dim2, 贡献(Dim1), 贡献(Dim2), cos²(Dim1), cos²(Dim2) |
| 3 | 列坐标表 | 类别, Dim1, Dim2, 贡献(Dim1), 贡献(Dim2), cos²(Dim1), cos²(Dim2) |
| 4 | 列联表 | 行变量×列变量的频数表 |

**返回结构** (与 PCA/Factor 相同的模式):
```python
{
    "svgs": [svg1, svg2, svg3, svg4],
    "metrics": {"行类别数": n, "列类别数": m, "总惯性": val, "前2维解释率": pct},
    "tables": [
        {"header": [...], "rows": [...]},
        ...
    ]
}
```

---

## 3. HTML 端 (`html/modules/correspondence.html`)

替换现有的 redirect-placeholder 为完整模块 UI，结构匹配 PCA/Factor 模板。

```
┌─ page-header ──────────────────────────────┐
│ 对应分析 · Correspondence Analysis          │
│ 降维 / 对应分析               [▶ 运行分析]  │
└─────────────────────────────────────────────┘
┌─ param-card ────────────────────────────────┐
│ 📊 分析参数                                  │
│ [行变量 ▼]  [列变量 ▼]  [显示维度数]         │
│ 提示：请先在左侧上传数据文件                 │
│ [🔄 加载列名] ← 自动填充分类列下拉框         │
└─────────────────────────────────────────────┘
┌─ metrics-row ───────────────────────────────┐
│ 行类别数  │  列类别数  │  总惯性  │ 前2维解释率 │
│   --      │    --      │   --     │    --       │
└─────────────────────────────────────────────┘
┌─ chart-card ────────────────────────────────┐
│ 对称图 · 碎石图 · 贡献图                    │
│ ┌────────────┐ ┌────────────┐               │
│ │  对称图    │ │  碎石图    │               │
│ │  (grid)    │ │  (grid)    │               │
│ └────────────┘ └────────────┘               │
│ ┌────────────┐ ┌────────────┐               │
│ │ 行贡献图   │ │ 列贡献图   │               │
│ └────────────┘ └────────────┘               │
│ 输出日志...                                  │
└─────────────────────────────────────────────┘
┌─ table-preview ─────────────────────────────┐
│ 惯性分解表                                   │
└─────────────────────────────────────────────┘
┌─ table-preview ─────────────────────────────┐
│ 行坐标（含贡献和cos²）                        │
└─────────────────────────────────────────────┘
┌─ table-preview ─────────────────────────────┐
│ 列坐标（含贡献和cos²）                        │
└─────────────────────────────────────────────┘
┌─ table-preview ─────────────────────────────┐
│ 列联表                                       │
└─────────────────────────────────────────────┘
```

### HTML 布局要点:
- `id="correspondence"`（与 `modules.json` 中 nav 的 module 名匹配）
- 按钮: `data-module="Correspondence" data-func="analyze"`
- 列名加载按钮: 调用 Python `get_columns` → 填充两个分类列下拉框
- 参数收集: `data-param="row_var"`, `data-param="col_var"`, `data-param="n_dims"`
- 图表容器: 2×2 grid（对称图、碎石图、行贡献图、列贡献图）
- 表格: 4 个 `.simple-table`，与渲染顺序匹配

### CSS 需求:
- 无新增 CSS 类，全部复用现有 `.module-content` / `.param-card` / `.chart-card` / `.table-preview` / `.metrics-row` 等样式
- 删除 `.redirect-placeholder` 相关样式（如无共用则忽略）

---

## 4. 修改清单

| 文件 | 操作 |
|------|------|
| `python/Correspondence.py` | 写入完整 CA 实现 (≈180 行) |
| `html/modules/correspondence.html` | 替换占位符为完整模块 UI (≈100 行) |
| `modules.json` | 无需修改（已有 correspondence 条目） |
| `css/` | 无需修改（复用现有样式） |
| `js/bridge.js` | 无需修改（`renderModuleResult` 通用渲染覆盖全部需求） |
| `build.py` | 无需修改（自动扫描 python/ 和 html/modules/） |

---

## 5. 实现顺序

1. **先写 `Correspondence.py`**（算法 + 图表 + 表格）
   - `get_columns()`: 读 CSV 返回列名
   - `analyze()`: 完整 CA 计算
   - 单元测试: 用 iris 等经典数据集验证
2. **再写 `correspondence.html`**（替换 redirect 占位符）
3. **`python build.py`** 构建验证
4. **浏览器手动测试**: 上传数据 → 选择行列变量 → 运行 → 验证图表和表格

---

## 6. 验证标准

- [ ] `lsp_diagnostics` 无错误
- [ ] `python build.py` 成功，`build/index.html` 和 `build/index.inline.html` 生成
- [ ] HTML 中 `modules.json` 导航按钮`data-module="correspondence"` 正确关联
- [ ] 上传 CSV → 点击"加载列名"→ 下拉框填充列名
- [ ] 选择行列分类变量 → 运行 → 对称图/碎石图/贡献图正确渲染
- [ ] 4 张表（惯性、行坐标、列坐标、列联表）正确填充
- [ ] metrics 行显示正确数值
- [ ] 验证边角情况：2×2 列联表、稀疏表、大型表
