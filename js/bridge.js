// --- file upload ---
function initUpload() {
  const dropZone = document.getElementById('dropZone')
  const fileInput = document.getElementById('fileInput')
  if (!dropZone || !fileInput) return

  dropZone.ondragover = e => { e.preventDefault(); dropZone.classList.add('drag-over') }
  dropZone.ondragleave = () => dropZone.classList.remove('drag-over')
  dropZone.ondrop = e => {
    e.preventDefault()
    dropZone.classList.remove('drag-over')
    const files = e.dataTransfer?.files
    if (files?.length) handleUpload(files[0])
  }
  dropZone.onclick = e => {
    if (e.target.closest('.browse-btn') || e.target.tagName === 'INPUT' || e.target.closest('.btn-clean-data')) return
    fileInput.click()
  }
  fileInput.onchange = e => {
    const files = e.target?.files
    if (files?.length) handleUpload(files[0])
  }
}

function handleUpload(file) {
  if (!pyodide) return
  const sheetSel = document.getElementById('sheetSelector')
  if (sheetSel) sheetSel.style.display = 'none'
  document.getElementById('confirmSheet').onclick = null
  const reader = new FileReader()
  reader.onload = () => {
    const ext = (file.name.split('.').pop() || 'csv').toLowerCase()
    if (ext === 'xlsx' || ext === 'xls') {
      if (!window.XLSX) {
        throw new Error('Excel 解析库加载失败，请刷新后重试。')
      }
      const wb = window.XLSX.read(reader.result, { type: 'array' })
      showSheetSelector(file.name, wb)
    } else {
      const baseName = file.name.replace(/\.[^.]+$/, '')
      const rawPath = `/home/pyodide/${baseName}.csv`
      const bytes = new Uint8Array(reader.result)
      pyodide.FS.writeFile(rawPath, bytes)

      const cleanedPath = `/home/pyodide/${baseName}.cleaned.csv`
      try {
        const dc = pyodide.globals.get('DataClean')
        if (dc && dc.auto_clean) {
          dc.auto_clean(rawPath, cleanedPath)
          window._currentDataPath = cleanedPath
        } else {
          window._currentDataPath = rawPath
        }
      } catch (e) {
        console.warn('Auto-clean failed, using raw data:', e)
        window._currentDataPath = rawPath
      }
      window._currentRawDataPath = rawPath

      showUploadSuccess(file.name, file.size)
    }
  }
  reader.readAsArrayBuffer(file)
}

function showSheetSelector(originalName, wb) {
  const sheetOptions = document.getElementById('sheetOptions')
  sheetOptions.innerHTML = wb.SheetNames.map((name, i) => `
    <label class="sheet-option">
      <input type="radio" name="selectedSheet" value="${i}" ${i === 0 ? 'checked' : ''}>
      ${name}
    </label>
  `).join('')
  const sheetSel = document.getElementById('sheetSelector')
  sheetSel.style.display = 'block'
  window._pendingExcel = { originalName, wb }

  document.getElementById('confirmSheet').onclick = confirmSheetSelection
}

function confirmSheetSelection() {
  const selected = document.querySelector('input[name="selectedSheet"]:checked')
  if (!selected) return
  const idx = parseInt(selected.value)
  const { originalName, wb } = window._pendingExcel
  const sheetName = wb.SheetNames[idx]
  const ws = wb.Sheets[sheetName]
  const csv = window.XLSX.utils.sheet_to_csv(ws)

  const baseName = originalName.replace(/\.[^.]+$/, '')
  const csvFileName = `${baseName}.${sheetName}.csv`
  const rawPath = `/home/pyodide/${csvFileName}`

  pyodide.FS.writeFile(rawPath, csv)

  const cleanedFileName = `${baseName}.${sheetName}.cleaned.csv`
  const cleanedPath = `/home/pyodide/${cleanedFileName}`

  try {
    const dc = pyodide.globals.get('DataClean')
    if (dc && dc.auto_clean) {
      dc.auto_clean(rawPath, cleanedPath)
      window._currentDataPath = cleanedPath
    } else {
      window._currentDataPath = rawPath
    }
  } catch (e) {
    console.warn('Auto-clean failed, using raw data:', e)
    window._currentDataPath = rawPath
  }
  window._currentRawDataPath = rawPath

  document.getElementById('sheetSelector').style.display = 'none'
  delete window._pendingExcel

  showUploadSuccess(originalName, 0)
}

function showUploadSuccess(name, size) {
  const cleaned = window._currentDataPath && window._currentDataPath !== window._currentRawDataPath
  document.getElementById('dropZone').innerHTML = `
    <div class="dataset-card">
      <button class="cancel-btn" onclick="resetUpload()"><i class="fas fa-times"></i></button>
      <div class="dataset-title"><i class="fas fa-database"></i> 当前数据集</div>
      <div class="dataset-detail">
        <span><i class="fas fa-file-csv"></i> ${name}</span>
        ${size ? `<span><i class="fas fa-hashtag"></i> ${(size / 1024).toFixed(1)} KB</span>` : ''}
      </div>
      <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap;">
        <span class="badge-success"><i class="far fa-check-circle"></i> 已写入 VFS</span>
        ${cleaned ? '<span class="badge-success" style="background:#e3f0fa;color:#1e4b6e;"><i class="fas fa-broom"></i> 已自动清洗</span>' : ''}
        <button class="btn-clean-data" onclick="openCleanPanel()"><i class="fas fa-sliders-h"></i> 数据清洗</button>
      </div>
    </div>`
}

function resetUpload() {
  document.getElementById('dropZone').innerHTML = `
    <div class="drop-content">
      <div class="drop-icon"><i class="fas fa-cloud-upload-alt"></i></div>
      <div class="drop-text">
        <span class="drop-primary">拖拽文件到此处</span>
        <span class="drop-secondary">或</span>
        <label class="browse-btn">
          浏览文件<input type="file" id="fileInput" accept=".csv,.xlsx,.xls" hidden>
        </label>
      </div>
      <div class="drop-hint">支持 CSV、Excel 文件</div>
    </div>`
  const sheetSel = document.getElementById('sheetSelector')
  if (sheetSel) sheetSel.style.display = 'none'
  delete window._pendingExcel
  delete window._currentDataPath
  delete window._currentRawDataPath
  initUpload()
}

// --- 数据清洗面板 ---

function escAttr(s) { return String(s).replace(/"/g, '&quot;').replace(/</g, '&lt;') }
function escHtml(s) { return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }

function openCleanPanel() {
  if (!window.pyodideReady || !window._currentRawDataPath) {
    alert('请先上传数据文件')
    return
  }

  const panel = document.getElementById('cleanPanel')
  if (!panel) return

  const body = panel.querySelector('.clean-panel-body')
  panel.style.display = 'flex'

  // 重置 body 到原始结构（保留 #cleanPreview / #cleanColumnRoles 等节点）
  body.innerHTML =
    '<div class="clean-panel-info" id="cleanPanelInfo">' +
      '<i class="fas fa-spinner fa-pulse"></i> 加载数据预览...' +
    '</div>' +
    '<div class="clean-panel-section">' +
      '<div class="clean-panel-section-title"><i class="fas fa-table"></i> 数据预览（前5行）</div>' +
      '<div class="clean-preview-wrap" id="cleanPreview"></div>' +
    '</div>' +
    '<div class="clean-panel-section">' +
      '<div class="clean-panel-section-title"><i class="fas fa-tags"></i> 列角色设置</div>' +
      '<p class="param-hint" style="margin:0 0 8px 4px;">为每一列指定角色：数值列会做清洗和缺失填补，索引列和分类列保持原样。</p>' +
      '<div class="clean-column-roles" id="cleanColumnRoles"></div>' +
    '</div>'

  const info = panel.querySelector('#cleanPanelInfo')

  try {
    const mod = pyodide.globals.get('DataClean')
    const fn = mod['preview_data']
    if (!fn) throw new Error('函数 preview_data 不存在')

    pyodide.setStdout({ batched: () => {} })
    const pyResult = fn({ data_path: window._currentRawDataPath })
    const result = pyResult !== undefined ? pyResult.toJs({ dict_converter: Object.fromEntries }) : null

    if (!result || result.error) {
      info.innerHTML = `<i class="fas fa-times-circle" style="color:#c0392b;"></i> 加载失败: ${escHtml(result?.error || '未知错误')}`
      return
    }

    renderCleanPanel(panel, result)
    info.innerHTML = `<i class="fas fa-info-circle"></i> 共 <strong>${result.n_rows}</strong> 行 · <strong>${result.columns?.length || '?'}</strong> 列`
  } catch (e) {
    info.innerHTML = `<i class="fas fa-times-circle" style="color:#c0392b;"></i> 加载失败: ${escHtml(e.message)}`
  }
}

function closeCleanPanel() {
  const panel = document.getElementById('cleanPanel')
  if (panel) panel.style.display = 'none'
}

function renderCleanPanel(panel, data) {
  const body = panel.querySelector('.clean-panel-body')
  const { columns, dtypes, sample, n_rows, suggested_roles } = data

  // 摘要信息
  const info = panel.querySelector('#cleanPanelInfo')
  if (info) {
    info.innerHTML = `<i class="fas fa-info-circle"></i> 共 <strong>${n_rows}</strong> 行 · <strong>${columns.length}</strong> 列 &nbsp;|&nbsp; 当前数据: <strong>${window._currentDataPath?.split('/').pop() || '—'}</strong>`
  }

  // 预览表格
  const previewWrap = document.getElementById('cleanPreview')
  if (previewWrap) {
    let html = '<table><thead><tr>'
    html += columns.map(c => `<th title="${escAttr(c)}">${escHtml(c)}</th>`).join('')
    html += '</tr></thead><tbody>'
    sample.forEach(row => {
      html += '<tr>' + row.map(v => `<td title="${escAttr(v)}">${escHtml(v)}</td>`).join('') + '</tr>'
    })
    html += '</tbody></table>'
    previewWrap.innerHTML = html
  }

  // 列角色设置
  const rolesWrap = document.getElementById('cleanColumnRoles')
  if (!rolesWrap) return

  let html2 = ''
  columns.forEach(col => {
    const dtype = dtypes[col] || '—'
    const suggested = suggested_roles[col] || 'numeric'
    let typeLabel, typeClass
    if (suggested === 'index')      { typeLabel = '索引'; typeClass = 'idx' }
    else if (suggested === 'numeric') { typeLabel = '数值'; typeClass = 'num' }
    else                             { typeLabel = '分类'; typeClass = 'cat' }

    // 示例值（第一个非空值）
    let sampleVal = '—'
    for (const row of sample) {
      const idx = columns.indexOf(col)
      if (idx >= 0 && row[idx] && row[idx] !== '—' && row[idx] !== '') {
        sampleVal = row[idx]
        break
      }
    }

    html2 += `
      <div class="clean-column-role-row" data-col="${escAttr(col)}">
        <span class="col-name" title="${escAttr(col)}">${escHtml(col)}</span>
        <span class="col-type-badge ${typeClass}">${typeLabel}</span>
        <span class="col-sample" title="${escAttr(sampleVal)}">示例: ${escHtml(sampleVal)}</span>
        <div class="role-options">
          <button class="role-btn ${suggested === 'numeric' ? 'active' : ''}" data-role="numeric">数值</button>
          <button class="role-btn ${suggested === 'categorical' ? 'active' : ''}" data-role="categorical">分类</button>
          <button class="role-btn ${suggested === 'index' ? 'active' : ''}" data-role="index">索引</button>
        </div>
      </div>`
  })
  rolesWrap.innerHTML = html2
}

function applyCleaning() {
  const panel = document.getElementById('cleanPanel')
  if (!panel) return

  const btn = document.getElementById('btnApplyClean')
  if (!btn || btn.classList.contains('loading')) return

  // 收集角色分配
  const rows = panel.querySelectorAll('.clean-column-role-row')
  const numeric_cols = []
  const categorical_cols = []
  let index_col = null

  rows.forEach(row => {
    const col = row.dataset.col
    const activeBtn = row.querySelector('.role-btn.active')
    if (!activeBtn) return
    const role = activeBtn.dataset.role
    if (role === 'numeric') numeric_cols.push(col)
    else if (role === 'categorical') categorical_cols.push(col)
    else if (role === 'index') index_col = col
  })

  btn.classList.add('loading')
  btn.innerHTML = '<i class="fas fa-spinner fa-pulse"></i> 清洗中...'

  captureStdout('DataClean', 'manual_clean', {
    data_path: window._currentRawDataPath,
    index_col: index_col,
    numeric_cols: numeric_cols,
    categorical_cols: categorical_cols,
  })
    .then(out => {
      btn.classList.remove('loading')
      btn.innerHTML = '<i class="fas fa-check"></i> 确认清洗'

      if (!out.result || out.result.error) {
        alert('清洗失败: ' + (out?.result?.error || '未知错误'))
        return
      }

      // 更新数据路径
      window._currentDataPath = out.result.path
      updateDatasetCard('manual')
      closeCleanPanel()
    })
    .catch(err => {
      btn.classList.remove('loading')
      btn.innerHTML = '<i class="fas fa-check"></i> 确认清洗'
      alert('清洗失败: ' + err.message)
    })
}

function updateDatasetCard(mode) {
  // 更新 dropZone 中的状态显示
  const badgeContainer = document.querySelector('.dataset-card > div:last-child')
  if (!badgeContainer) return
  // 移除已有的清洗 badge
  const existing = badgeContainer.querySelector('.badge-success[class*="broom"], .badge-success[class*="manual"]')
  if (existing) existing.remove()

  if (mode === 'manual') {
    const badge = document.createElement('span')
    badge.className = 'badge-success'
    badge.style.cssText = 'background:#e8f5e9;color:#2e7d32;'
    badge.innerHTML = '<i class="fas fa-check-circle"></i> 已手动清洗'
    badgeContainer.appendChild(badge)
  }
}

// --- stdout capture ---
function captureStdout(moduleName, funcName, params = {}) {
  return new Promise((resolve, reject) => {
    const lines = []
    pyodide.setStdout({ batched: s => lines.push(s) })
    const mod = pyodide.globals.get(moduleName)
    const fn = mod[funcName]
    // 与 README 推荐方式一致：传单个 options dict，避免参数顺序问题。
    Promise.resolve(fn(params))
      .then(result => {
        pyodide.setStdout({ batched: () => {} })
        resolve({ lines, result: result !== undefined ? result.toJs({ dict_converter: Object.fromEntries }) : null })
      })
      .catch(err => {
        pyodide.setStdout({ batched: () => {} })
        reject(err)
      })
  })
}

// --- result rendering ---
function renderModuleResult(container, out) {
  const outputPre = container.querySelector('.py-output')
  if (outputPre && out.lines.length) {
    outputPre.textContent = out.lines.join('\n')
  }

  if (!out.result) {
    if (outputPre) outputPre.textContent = '运行完成，但未返回可渲染结果。'
    return
  }

  if (out.result.error) {
    if (outputPre) outputPre.textContent = '错误: ' + out.result.error
    const chartBox2 = container.querySelector('.chart-container')
    if (chartBox2) chartBox2.innerHTML = `<div style="color:#c0392b;font-size:13px;">${out.result.error}</div>`
    return
  }

  const chartBox = container.querySelector('.chart-container')
  if (chartBox && out.result.svgs && out.result.svgs.length) {
    chartBox.innerHTML = out.result.svgs.map((svg, i) => `
      <div style="margin-bottom:14px;">
        <div style="font-size:12px;color:#5d7387;margin:0 0 6px 2px;">结果图 ${i + 1}</div>
        ${svg}
      </div>
    `).join('')
    chartBox.querySelectorAll('svg').forEach(svg => { svg.style.maxWidth = '100%' })
  } else if (chartBox && out.result.svg) {
    chartBox.innerHTML = out.result.svg
    const svg = chartBox.querySelector('svg')
    if (svg) svg.style.maxWidth = '100%'
  } else if (chartBox) {
    chartBox.innerHTML = '<div style="color:#c0392b;font-size:13px;">未返回图形（svg）</div>'
  }

  const metrics = container.querySelectorAll('.metric-value')
  if (metrics.length && out.result.metrics) {
    const vals = Object.values(out.result.metrics)
    metrics.forEach((el, i) => { if (i < vals.length) el.textContent = vals[i] })
  }

  const tables = container.querySelectorAll('.simple-table')
  if (tables.length && out.result.tables) {
    tables.forEach((tbl, i) => {
      const data = out.result.tables[i]
      if (!data) return
      const thead = tbl.querySelector('thead tr')
      const tbody = tbl.querySelector('tbody')
      if (thead && data.header) {
        thead.innerHTML = data.header.map(h => `<th>${h}</th>`).join('')
      }
      if (tbody && data.rows) {
        tbody.innerHTML = data.rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')
      }
    })
  }
}

function collectParams(container) {
  // Run pre-collection hooks (e.g., AHP matrix serialization)
  if (typeof beforeCollectParams === 'function') {
    beforeCollectParams(container)
  }
  const params = {}
  container.querySelectorAll('[data-param]').forEach(el => {
    const key = el.dataset.param
    if (el.type === 'radio') {
      if (el.checked) params[key] = el.value
      return
    }
    if (el.multiple) {
      params[key] = Array.from(el.selectedOptions || []).map(opt => opt.value)
      return
    }
    if (el.type === 'number') {
      const v = el.value.trim()
      params[key] = v === '' ? null : Number(v)
    } else {
      params[key] = el.value
    }
  })
  if (window._currentDataPath) params.data_path = window._currentDataPath
  if (window._currentRawDataPath) params.raw_data_path = window._currentRawDataPath
  return params
}

function exportClusteringReport(container) {
  const params = collectParams(container)
  const paramRows = Object.entries(params).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('')
  const metricItems = Array.from(container.querySelectorAll('.metric-item')).map(item => {
    const label = item.querySelector('.metric-label')?.textContent?.trim() || ''
    const value = item.querySelector('.metric-value')?.textContent?.trim() || '--'
    return `<tr><td>${label}</td><td>${value}</td></tr>`
  }).join('')
  const tableHtml = Array.from(container.querySelectorAll('.simple-table')).map(t => t.outerHTML).join('\n') || '<p>No table.</p>'
  const chartHtml = container.querySelector('.chart-container')?.innerHTML || '<p>No chart.</p>'
  const logText = container.querySelector('.py-output')?.textContent || ''
  const now = new Date()
  const stamp = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`

  const report = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Clustering Report</title>
  <style>
    body{font-family:Arial,sans-serif;padding:24px;color:#1f2d3d}
    h1{margin:0 0 6px} h2{margin-top:24px}
    table{border-collapse:collapse;width:100%;margin-top:8px}
    th,td{border:1px solid #d9e2ec;padding:8px;font-size:13px;text-align:left}
    .muted{color:#627d98;font-size:12px}
    pre{background:#f6f9fc;border:1px solid #e2eaf2;border-radius:6px;padding:10px;white-space:pre-wrap}
  </style>
</head>
<body>
  <h1>Clustering Analysis Report</h1>
  <div class="muted">Exported at: ${stamp}</div>
  <h2>Parameters</h2>
  <table><thead><tr><th>Name</th><th>Value</th></tr></thead><tbody>${paramRows}</tbody></table>
  <h2>Metrics</h2>
  <table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>${metricItems}</tbody></table>
  <h2>Chart</h2>
  <div>${chartHtml}</div>
  <h2>Table</h2>
  <div>${tableHtml}</div>
  <h2>Logs</h2>
  <pre>${logText.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
</body>
</html>`

  const blob = new Blob([report], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `clustering-report-${now.getTime()}.html`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function bindExportButtons() {
  document.querySelectorAll('.btn-export:not([data-bound])').forEach(btn => {
    btn.dataset.bound = 'true'
    btn.addEventListener('click', () => {
      const container = btn.closest('.module-content')
      if (!container || container.id !== 'clustering') return
      exportClusteringReport(container)
    })
  })
}

function initClusteringParamControls(container) {
  if (!container || container.id !== 'clustering') return
  const algoSel = container.querySelector('[data-param="algorithm"]')
  const lossSel = container.querySelector('[data-param="loss"]')
  const plotSel = container.querySelector('[data-param="plot_type"]')
  if (!algoSel || !lossSel || !plotSel || lossSel.dataset.bound === 'true') return

  const updateLossOptions = () => {
    if (algoSel.value === 'hierarchical') {
      lossSel.innerHTML = `
        <option value="ward">ward</option>
        <option value="single">single</option>
        <option value="complete">complete</option>
        <option value="average">average</option>
        <option value="centroid">centroid</option>
        <option value="median">median</option>
      `
      lossSel.value = 'ward'
    } else {
      lossSel.innerHTML = `
        <option value="lloyd">lloyd</option>
        <option value="elkan">elkan</option>
      `
      lossSel.value = 'lloyd'
      plotSel.innerHTML = `<option value="scatter" selected>Scatter</option>`
      plotSel.value = 'scatter'
      plotSel.disabled = true
      plotSel.title = 'K-Means only supports scatter plot.'
      return
    }

    plotSel.innerHTML = `
      <option value="scatter">Scatter</option>
      <option value="dendrogram">Dendrogram</option>
    `
    if (plotSel.value !== 'dendrogram') plotSel.value = 'scatter'
    plotSel.disabled = false
    plotSel.title = ''
  }

  algoSel.addEventListener('change', updateLossOptions)
  lossSel.dataset.bound = 'true'
  updateLossOptions()
}

function switchEvalTab(tabId, btn) {
  const container = btn.closest('.module-content')
  container.querySelectorAll('.eval-tab').forEach(b => b.classList.remove('active'))
  btn.classList.add('active')
  container.querySelectorAll('.eval-panel').forEach(p => p.classList.remove('active'))
  const panel = container.querySelector('#panel-' + tabId)
  if (panel) panel.classList.add('active')
}

// --- run button handler (callable multiple times) ---
function bindRunButtons() {
  document.querySelectorAll('.btn-run:not([data-bound])').forEach(btn => {
    btn.dataset.bound = 'true'
    btn.dataset.running = 'false'
    btn.dataset.canceled = 'false'
    btn.addEventListener('click', async () => {
      const mod = btn.dataset.module
      const func = btn.dataset.func
      const container = btn.closest('.module-content')
      const scope = btn.closest('.eval-panel') || container
      const outputPre = scope.querySelector('.py-output')
      initClusteringParamControls(container)

      if (!window.pyodideReady) {
        btn.innerHTML = '<i class="fas fa-spinner fa-pulse"></i> 等待就绪'
        btn.disabled = true
        setTimeout(() => {
          btn.innerHTML = '<i class="fas fa-play"></i> 运行分析'
          btn.disabled = false
        }, 800)
        if (outputPre) outputPre.textContent = 'Pyodide 尚未就绪，请等待左下角状态变为“已就绪”后再运行。'
        return
      }

      if (btn.dataset.running === 'true') {
        btn.dataset.canceled = 'true'
        btn.innerHTML = '<i class="fas fa-spinner fa-pulse"></i> 中断中...'
        btn.disabled = true
        if (outputPre) outputPre.textContent = '已请求中断，本次结果将被忽略。'
        return
      }

      const runId = String(Date.now())
      btn.dataset.runId = runId
      btn.dataset.running = 'true'
      btn.dataset.canceled = 'false'
      btn.disabled = true
      btn.innerHTML = '<i class="fas fa-stop"></i> 中断'
      // 让浏览器先重绘按钮状态，再进入计算逻辑。
      await new Promise(resolve => requestAnimationFrame(resolve))
      setTimeout(() => {
        if (btn.dataset.running === 'true' && btn.dataset.runId === runId) {
          btn.disabled = false
        }
      }, 120)
      if (outputPre) outputPre.textContent = '运行中...'

      try {
        const params = collectParams(scope)
        const out = await captureStdout(mod, func, params)
        if (btn.dataset.canceled !== 'true' && btn.dataset.runId === runId) {
          renderModuleResult(scope, out)
        }
      } catch (e) {
        if (btn.dataset.canceled !== 'true' && btn.dataset.runId === runId) {
          if (outputPre) outputPre.textContent = `错误: ${e.message}`
          const chartBox = scope.querySelector('.chart-container')
          if (chartBox) {
            chartBox.innerHTML = `<div style="color:#c0392b;font-size:13px;">运行失败：${e.message}</div>`
          }
        }
        console.error(e)
      } finally {
        if (btn.dataset.runId === runId) {
          btn.dataset.running = 'false'
          btn.dataset.canceled = 'false'
          btn.innerHTML = '<i class="fas fa-play"></i> 运行分析'
          btn.disabled = false
        }
      }
    })
  })
}

// --- AHP Matrix & Column Loader Functions ---
function beforeCollectParams(container) {
  // Serialize AHP matrices if present
  if (container && container.querySelector('.matrix-container')) {
    serializeMatrices(container)
  }
}

function serializeMatrices(container) {
  const matrixContainer = container.querySelector('.matrix-container')
  if (!matrixContainer) return

  const matrices = []
  matrixContainer.querySelectorAll('.matrix-table-wrapper').forEach(wrapper => {
    const n = parseInt(wrapper.dataset.size)
    if (!n || n < 2) return

    const matrix = []
    for (let i = 0; i < n; i++) {
      matrix[i] = []
      for (let j = 0; j < n; j++) {
        const input = wrapper.querySelector(`input.matrix-cell[data-i="${i}"][data-j="${j}"]`)
        const val = input ? parseFloat(input.value) : null
        matrix[i][j] = (val !== null && !isNaN(val) && val > 0) ? val : 1
      }
    }
    matrices.push(matrix)
  })

  // Hidden input: list of matrices (multi-expert)
  const hidden = container.querySelector('[data-param="judgement_matrices"]')
  if (hidden) hidden.value = matrices.length ? JSON.stringify(matrices) : ''

  // Backward compat: single matrix
  const hiddenOld = container.querySelector('[data-param="judgement_matrix"]')
  if (hiddenOld) hiddenOld.value = matrices.length ? JSON.stringify(matrices[0]) : ''

  // Status
  const status = container.querySelector('.matrix-status')
  if (status) status.textContent = matrices.length ? `${matrices.length} 位专家 · 已同步` : ''

  // Aggregated preview
  updateAggregatedPreview(container, matrices)
}

function updateAggregatedPreview(container, matrices) {
  const aggContainer = container.querySelector('.aggregate-matrix-container')
  const aggTable = container.querySelector('.aggregate-matrix-table')
  if (!aggContainer || !aggTable) return

  if (matrices.length < 2) {
    aggContainer.style.display = 'none'
    return
  }

  const n = matrices[0].length
  const agg = []
  for (let i = 0; i < n; i++) {
    agg[i] = []
    for (let j = 0; j < n; j++) {
      let product = 1
      for (let k = 0; k < matrices.length; k++) product *= matrices[k][i][j]
      agg[i][j] = Math.pow(product, 1 / matrices.length)
    }
  }

  let html = '<table style="border-collapse:collapse;font-size:12px;width:auto;"><tr><td style="padding:4px 6px;border:1px solid #d9e2ec;background:#f6f9fc;"></td>'
  for (let j = 0; j < n; j++) html += `<th style="padding:4px 8px;border:1px solid #d9e2ec;background:#f6f9fc;">C${j + 1}</th>`
  html += '</tr>'
  for (let i = 0; i < n; i++) {
    html += `<tr><th style="padding:4px 8px;border:1px solid #d9e2ec;background:#f6f9fc;">C${i + 1}</th>`
    for (let j = 0; j < n; j++) html += `<td style="padding:4px 8px;border:1px solid #d9e2ec;text-align:center;">${agg[i][j].toFixed(3)}</td>`
    html += '</tr>'
  }
  html += '</table>'
  aggTable.innerHTML = html
  aggContainer.style.display = 'block'
}

function generateMatrixTable(indicators, expertIndex) {
  const names = indicators.split(',').map(s => s.trim()).filter(Boolean)
  if (names.length < 2) return ''

  const n = names.length
  let html = `<div class="matrix-table-wrapper" data-size="${n}" style="margin-bottom:16px;border:1px solid #e2eaf2;border-radius:8px;padding:12px;background:#fff;">`
  html += `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <span style="font-weight:600;font-size:13px;">专家 ${expertIndex}</span>
    ${expertIndex > 1 ? `<button class="btn-remove-expert" type="button" style="padding:2px 8px;font-size:11px;background:none;border:1px solid #e0c0c0;color:#b94a4a;border-radius:4px;cursor:pointer;"><i class="fas fa-times"></i> 移除</button>` : ''}
  </div>`

  html += '<table style="border-collapse:collapse;width:100%;font-size:12px;"><thead><tr><th style="padding:6px 4px;border:1px solid #d9e2ec;background:#f6f9fc;text-align:center;max-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">指标</th>'
  for (let j = 0; j < n; j++) html += `<th style="padding:6px 4px;border:1px solid #d9e2ec;background:#f6f9fc;text-align:center;max-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${names[j]}">${names[j]}</th>`
  html += '</tr></thead><tbody>'

  for (let i = 0; i < n; i++) {
    html += `<tr><th style="padding:6px 4px;border:1px solid #d9e2ec;background:#f6f9fc;text-align:center;max-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${names[i]}">${names[i]}</th>`
    for (let j = 0; j < n; j++) {
      if (i === j) {
        html += `<td style="padding:2px;border:1px solid #d9e2ec;text-align:center;"><input type="text" class="matrix-cell matrix-diagonal" data-i="${i}" data-j="${j}" value="1" readonly style="width:48px;text-align:center;border:none;background:#f0f4f8;padding:4px;border-radius:4px;font-size:12px;cursor:not-allowed;"></td>`
      } else if (i < j) {
        html += `<td style="padding:2px;border:1px solid #d9e2ec;text-align:center;"><input type="number" class="matrix-cell matrix-upper" data-i="${i}" data-j="${j}" min="0.001" max="9" step="any" placeholder="—" style="width:48px;text-align:center;border:1px solid #d6e0ea;padding:4px;border-radius:4px;font-size:12px;"></td>`
      } else {
        html += `<td style="padding:2px;border:1px solid #d9e2ec;text-align:center;"><input type="text" class="matrix-cell matrix-lower" data-i="${i}" data-j="${j}" value="" readonly style="width:48px;text-align:center;border:none;background:#fafbfc;padding:4px;border-radius:4px;font-size:11px;color:#5d7387;"></td>`
      }
    }
    html += '</tr>'
  }
  html += '</tbody></table></div>'
  return html
}

// --- Event Delegation ---

// Matrix reciprocal: upper triangle → auto lower triangle
document.addEventListener('input', function (e) {
  const input = e.target
  if (!input.classList.contains('matrix-upper')) return

  const i = parseInt(input.dataset.i)
  const j = parseInt(input.dataset.j)
  const wrapper = input.closest('.matrix-table-wrapper')
  if (!wrapper || isNaN(i) || isNaN(j)) return

  const val = parseFloat(input.value)
  const lowerInput = wrapper.querySelector(`input.matrix-lower[data-i="${j}"][data-j="${i}"]`)
  if (lowerInput) {
    lowerInput.value = (!isNaN(val) && val > 0) ? (1 / val).toFixed(4) : ''
  }

  // Auto-serialize
  const container = input.closest('.eval-panel') || input.closest('.module-content')
  if (container) serializeMatrices(container)
})

// Button clicks: column loader, matrix generator, add/remove expert
document.addEventListener('click', function (e) {
  const btn = e.target.closest('button')
  if (!btn || btn.disabled) return

  const container = btn.closest('.eval-panel') || btn.closest('.module-content')
  if (!container) return

  // --- Column loader (generic: reads data-module/data-func from button) ---
  if (btn.classList.contains('btn-load-columns')) {
    if (!window.pyodideReady || !window._currentDataPath) {
      alert('请先上传数据文件')
      return
    }
    const modName = btn.dataset.module || 'CanonicalCorrelation'
    const funcName = btn.dataset.func || 'get_columns'
    try {
      const mod = pyodide.globals.get(modName)
      const resultProxy = mod[funcName]({ data_path: window._currentDataPath })
      const result = resultProxy.toJs({ dict_converter: Object.fromEntries })
      if (result.error) { alert(result.error); return }

      const columns = result.columns || []
      const optHtml = columns.map(c => `<option value="${c}">${c}</option>`).join('')
      // Fill all select[data-param] elements that are not disabled/multiple-free
      const selects = container.querySelectorAll('select[data-param]')
      selects.forEach(sel => { sel.innerHTML = optHtml })

      btn.innerHTML = '<i class="fas fa-check"></i> 已加载'
      btn.style.background = '#e8f5e9'
      btn.style.borderColor = '#4caf50'
      btn.style.color = '#2e7d32'
      const status = container.querySelector('.load-status')
      if (status) status.textContent = `${columns.length} 列`
    } catch (err) {
      alert('加载列名失败: ' + err.message)
    }
    return
  }

  // --- Generate matrix (AHP) ---
  if (btn.classList.contains('btn-generate-matrix')) {
    const indicatorsInput = container.querySelector('[data-param="indicators"]')
    if (!indicatorsInput || !indicatorsInput.value.trim()) {
      alert('请先在「评价指标选择」中输入指标名称（逗号分隔）')
      return
    }
    const vals = indicatorsInput.value.trim()
    if (vals.split(',').map(s => s.trim()).filter(Boolean).length < 2) {
      alert('至少需要 2 个指标')
      return
    }

    const matrixContainer = container.querySelector('.matrix-container')
    if (!matrixContainer) return

    matrixContainer.innerHTML = generateMatrixTable(vals, 1)
    matrixContainer.style.display = ''  // 显示矩阵容器

    // 显示标度参考和添加专家按钮
    const scaleRef = container.querySelector('.matrix-scale-ref')
    if (scaleRef) scaleRef.style.display = ''
    const addBtn = container.querySelector('.btn-add-expert')
    if (addBtn) addBtn.style.display = ''

    serializeMatrices(container)
    matrixContainer.querySelector('.matrix-upper')?.focus()
    return
  }

  // --- Add expert (AHP) ---
  if (btn.classList.contains('btn-add-expert')) {
    const matrixContainer = container.querySelector('.matrix-container')
    if (!matrixContainer) return
    if (!matrixContainer.querySelector('.matrix-table-wrapper')) {
      alert('请先点击「生成判断矩阵」')
      return
    }

    const indicatorsInput = container.querySelector('[data-param="indicators"]')
    if (!indicatorsInput || !indicatorsInput.value.trim()) return

    const existing = matrixContainer.querySelectorAll('.matrix-table-wrapper').length
    const wrapper = document.createElement('div')
    wrapper.innerHTML = generateMatrixTable(indicatorsInput.value.trim(), existing + 1)
    matrixContainer.appendChild(wrapper.firstElementChild)
    serializeMatrices(container)
    return
  }

  // --- Remove expert (AHP) ---
  if (btn.classList.contains('btn-remove-expert')) {
    const wrapper = btn.closest('.matrix-table-wrapper')
    if (!wrapper) return
    wrapper.remove()

    // Re-number remaining
    const wrappers = container.querySelectorAll('.matrix-table-wrapper')
    wrappers.forEach((w, idx) => {
      const label = w.querySelector('div > span:first-child')
      if (label) label.textContent = `专家 ${idx + 1}`
    })
    serializeMatrices(container)
    return
  }
})

// --- 清洗面板角色选择 ---
document.addEventListener('click', function (e) {
  const btn = e.target.closest('.role-btn')
  if (!btn || !btn.closest('#cleanPanel')) return
  const row = btn.closest('.clean-column-role-row')
  if (!row) return
  row.querySelectorAll('.role-btn').forEach(b => b.classList.remove('active'))
  btn.classList.add('active')
})

// --- init ---
document.addEventListener('DOMContentLoaded', () => {
  initUpload()
  bindRunButtons()
  bindExportButtons()
  initClusteringParamControls(document.getElementById('clustering'))

  document.addEventListener('pyodideReady', () => {
    window.pyodideReady = true
    document.querySelectorAll('.btn-run').forEach(b => { b.disabled = false })
    const pyStatus = document.querySelector('.py-status') || document.getElementById('pyStatus')
    if (pyStatus) pyStatus.innerHTML = '<i class="fas fa-check-circle" style="color:#2e7d32;"></i> Pyodide 已就绪'
  })
})
