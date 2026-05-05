// --- file upload ---
function initUpload() {
  const dropZone = document.getElementById('dropZone')
  const fileInput = document.getElementById('fileInput')
  if (!dropZone || !fileInput) return

  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over') })
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'))

  dropZone.addEventListener('drop', e => {
    e.preventDefault()
    dropZone.classList.remove('drag-over')
    const files = e.dataTransfer?.files
    if (files?.length) handleUpload(files[0])
  })

  dropZone.addEventListener('click', e => {
    if (e.target.tagName !== 'INPUT') fileInput.click()
  })

  fileInput.addEventListener('change', e => {
    const files = e.target?.files
    if (files?.length) handleUpload(files[0])
  })
}

function handleUpload(file) {
  if (!pyodide) return
  const reader = new FileReader()
  reader.onload = () => {
    const ext = (file.name.split('.').pop() || 'csv').toLowerCase()
    if (ext === 'xlsx' || ext === 'xls') {
      if (!window.XLSX) {
        throw new Error('Excel 解析库加载失败，请刷新后重试。')
      }
      const wb = window.XLSX.read(reader.result, { type: 'array' })
      const meta = { original_name: file.name, ext, sheets: [] }
      wb.SheetNames.forEach((sheetName, idx) => {
        const ws = wb.Sheets[sheetName]
        const csv = window.XLSX.utils.sheet_to_csv(ws)
        const path = `/home/pyodide/data.sheet${idx + 1}.csv`
        pyodide.FS.writeFile(path, csv)
        meta.sheets.push({ index: idx + 1, name: sheetName, path })
      })
      pyodide.FS.writeFile('/home/pyodide/upload_meta.json', JSON.stringify(meta))
      pyodide.FS.writeFile('/home/pyodide/upload_name.txt', file.name)
      window.latestUploadPayload = {
        kind: 'excel',
        originalName: file.name,
        ext,
        sheets: wb.SheetNames.map((sheetName, idx) => {
          const ws = wb.Sheets[sheetName]
          return {
            index: idx + 1,
            name: sheetName,
            path: `/home/pyodide/data.sheet${idx + 1}.csv`,
            csv: window.XLSX.utils.sheet_to_csv(ws)
          }
        })
      }
    } else {
      const vfsPath = `/home/pyodide/data.${ext}`
      const bytes = new Uint8Array(reader.result)
      pyodide.FS.writeFile(vfsPath, bytes)
      const meta = {
        original_name: file.name,
        ext,
        sheets: [{ index: 1, name: 'sheet1', path: vfsPath }]
      }
      pyodide.FS.writeFile('/home/pyodide/upload_meta.json', JSON.stringify(meta))
      pyodide.FS.writeFile('/home/pyodide/upload_name.txt', file.name)
      window.latestUploadPayload = {
        kind: 'file',
        originalName: file.name,
        ext,
        path: vfsPath,
        bytes: reader.result,
      }
    }
    if (typeof window.ensureClusteringWorker === 'function') {
      window.ensureClusteringWorker()
        .then(() => window.callClusteringWorker?.('upload', window.latestUploadPayload))
        .catch(err => console.error('Failed to upload dataset to clustering worker:', err))
    }
    showUploadSuccess(file.name, file.size)
  }
  reader.readAsArrayBuffer(file)
}

function showUploadSuccess(name, size) {
  document.getElementById('dropZone').innerHTML = `
    <div class="dataset-card">
      <button class="cancel-btn" onclick="resetUpload()"><i class="fas fa-times"></i></button>
      <div class="dataset-title"><i class="fas fa-database"></i> 当前数据集</div>
      <div class="dataset-detail">
        <span><i class="fas fa-file-csv"></i> ${name}</span>
        <span><i class="fas fa-hashtag"></i> ${(size / 1024).toFixed(1)} KB</span>
      </div>
      <div style="margin-top:12px"><span class="badge-success"><i class="far fa-check-circle"></i> 已写入 Pyodide 虚拟 FS</span></div>
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
  initUpload()
}

// --- stdout capture ---
function captureStdout(moduleName, funcName, params = {}) {
  if (moduleName === 'Clustering' && typeof window.ensureClusteringWorker === 'function') {
    return window.ensureClusteringWorker().then(() =>
      window.callClusteringWorker('run', { moduleName, funcName, params })
    )
  }
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

  const tbody = container.querySelector('.simple-table tbody')
  if (tbody && out.result.table) {
    tbody.innerHTML = out.result.table.map(
      row => `<tr>${row.map(c => `<td>${c}</td>`).join('')}</tr>`
    ).join('')
  }

  const headerRow = container.querySelector('.simple-table thead tr')
  if (headerRow && out.result.table_header) {
    headerRow.innerHTML = out.result.table_header.map(h => `<th>${h}</th>`).join('')
  }

  if (outputPre && out.result.summary_table && out.result.summary_table.length) {
    const lines = out.result.summary_table.map(r => r.join(' | '))
    outputPre.textContent = `各 sheet 指标:\n${lines.join('\n')}`
  }
}

function collectParams(container) {
  const params = {}
  container.querySelectorAll('[data-param]').forEach(el => {
    const key = el.dataset.param
    let val = el.value
    if (el.type === 'number') val = Number(val)
    params[key] = val
  })
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
  const tableHtml = container.querySelector('.simple-table')?.outerHTML || '<p>No table.</p>'
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
      const outputPre = container.querySelector('.py-output')
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
        if (mod === 'Clustering' && typeof window.interruptClusteringWorker === 'function') {
          window.interruptClusteringWorker()
          if (typeof window.ensureClusteringWorker === 'function') {
            window.ensureClusteringWorker().catch(err => console.error('Failed to restart clustering worker:', err))
          }
        }
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
        const params = collectParams(container)
        const out = await captureStdout(mod, func, params)
        if (btn.dataset.canceled !== 'true' && btn.dataset.runId === runId) {
          renderModuleResult(container, out)
        }
      } catch (e) {
        if (btn.dataset.canceled !== 'true' && btn.dataset.runId === runId) {
          if (outputPre) outputPre.textContent = `错误: ${e.message}`
          const chartBox = container.querySelector('.chart-container')
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
