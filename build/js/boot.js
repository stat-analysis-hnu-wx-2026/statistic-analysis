let pyodide = null
let clusteringWorker = null
let clusteringWorkerReady = false
let clusteringWorkerInitPromise = null
let clusteringWorkerSeq = 0
const clusteringWorkerPending = new Map()

function collectPythonSources() {
  const sources = {}
  document.querySelectorAll('script[type="text/python-src"]').forEach(script => {
    if (script.dataset.module) sources[script.dataset.module] = script.textContent
  })
  return sources
}

function rejectClusteringWorkerPending(message = '聚类分析已中断。') {
  clusteringWorkerPending.forEach(({ reject }) => reject(new Error(message)))
  clusteringWorkerPending.clear()
}

function teardownClusteringWorker(message) {
  if (clusteringWorker) clusteringWorker.terminate()
  clusteringWorker = null
  clusteringWorkerReady = false
  clusteringWorkerInitPromise = null
  if (message) rejectClusteringWorkerPending(message)
}

function callClusteringWorker(type, payload = {}) {
  if (!clusteringWorker) return Promise.reject(new Error('聚类分析引擎未启动。'))
  const requestId = `cw-${Date.now()}-${++clusteringWorkerSeq}`
  return new Promise((resolve, reject) => {
    clusteringWorkerPending.set(requestId, { resolve, reject })
    clusteringWorker.postMessage({ type, requestId, payload })
  })
}

function syncUploadToClusteringWorker() {
  if (!window.latestUploadPayload || !clusteringWorkerReady) return Promise.resolve()
  return callClusteringWorker('upload', window.latestUploadPayload).catch(err => {
    console.error('Failed to sync upload to clustering worker:', err)
  })
}

function ensureClusteringWorker() {
  if (!window.Worker) {
    return Promise.reject(new Error('当前浏览器不支持 Worker，无法中断聚类任务。'))
  }
  if (clusteringWorkerReady && clusteringWorker) return Promise.resolve()
  if (clusteringWorkerInitPromise) return clusteringWorkerInitPromise

  clusteringWorkerInitPromise = new Promise((resolve, reject) => {
    clusteringWorker = new Worker('js/py-worker.js')

    clusteringWorker.onmessage = event => {
      const { type, requestId, payload, error } = event.data || {}

      if (type === 'ready') {
        clusteringWorkerReady = true
        clusteringWorkerInitPromise = null
        syncUploadToClusteringWorker().finally(() => {
          document.dispatchEvent(new Event('clusteringWorkerReady'))
          resolve()
        })
        return
      }

      if (!requestId) return
      const pending = clusteringWorkerPending.get(requestId)
      if (!pending) return
      clusteringWorkerPending.delete(requestId)

      if (type === 'success') pending.resolve(payload)
      else pending.reject(new Error(error || '聚类分析引擎返回未知错误。'))
    }

    clusteringWorker.onerror = event => {
      const msg = event?.message || '聚类分析引擎初始化失败。'
      teardownClusteringWorker(msg)
      reject(new Error(msg))
    }

    clusteringWorker.postMessage({
      type: 'init',
      payload: {
        pythonSources: collectPythonSources(),
      }
    })
  })

  return clusteringWorkerInitPromise
}

function interruptClusteringWorker() {
  teardownClusteringWorker('聚类分析已中断。')
}

window.ensureClusteringWorker = ensureClusteringWorker
window.callClusteringWorker = callClusteringWorker
window.interruptClusteringWorker = interruptClusteringWorker
window.isClusteringWorkerReady = () => clusteringWorkerReady

function setPyStatus(html, pct) {
  const el = document.querySelector('.py-status')
  if (el) el.innerHTML = html || ''
  if (pct === undefined) {
    const c = document.querySelector('.progress-bar-container')
    if (c) c.style.display = 'none'
    return
  }
  const bar = document.querySelector('.progress-bar')
  const txt = document.querySelector('.progress-text')
  const con = document.querySelector('.progress-bar-container')
  if (!con) return
  con.style.display = 'block'
  if (bar) bar.style.width = Math.min(pct, 100) + '%'
  if (txt) txt.textContent = Math.min(pct, 100) + '%'
  if (pct >= 100) {
    setTimeout(() => { con.style.display = 'none' }, 2000)
  }
}

async function initPyodide() {
  try {
    setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 连接 CDN...', 2)

    if (typeof loadPyodide !== 'function') {
      throw new Error('Pyodide 脚本未加载，请检查网络/CDN 连通性。')
    }

    pyodide = await loadPyodide()

    setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 下载 Python 包...', 35)

    await pyodide.loadPackage(['numpy', 'matplotlib', 'pandas', 'scipy', 'scikit-learn'], {
      messageCallback: (msg) => {
        const lower = msg.toLowerCase()
        if (lower.includes('numpy')) setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 下载 numpy...', 48)
        else if (lower.includes('matplotlib')) setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 下载 matplotlib...', 60)
        else if (lower.includes('pandas')) setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 下载 pandas...', 66)
        else if (lower.includes('scipy')) setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 下载 scipy...', 70)
        else if (lower.includes('scikit-learn')) setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 下载 scikit-learn...', 74)
        const m = msg.match(/(\d+)\s*\/\s*(\d+)/)
        if (m) {
          const pct = 35 + Math.round((parseInt(m[1]) / parseInt(m[2])) * 30)
          setPyStatus(`<i class="fas fa-spinner fa-pulse"></i> 加载包... ${m[1]}/${m[2]}`, pct)
        }
      }
    })

    setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 写入 Python 文件...', 75)

    const scripts = document.querySelectorAll('script[type="text/python-src"]')
    for (let i = 0; i < scripts.length; i++) {
      const s = scripts[i]
      pyodide.FS.writeFile(`/home/pyodide/${s.dataset.module}.py`, s.textContent)
      const pct = 75 + Math.round(((i + 1) / scripts.length) * 10)
      setPyStatus(`<i class="fas fa-spinner fa-pulse"></i> 写入 ${s.dataset.module}.py...`, pct)
    }

    for (let i = 0; i < scripts.length; i++) {
      const s = scripts[i]
      await pyodide.runPythonAsync(`import ${s.dataset.module}`)
      const pct = 85 + Math.round(((i + 1) / scripts.length) * 15)
      setPyStatus(`<i class="fas fa-spinner fa-pulse"></i> 导入 ${s.dataset.module}...`, pct)
    }

    setPyStatus('<i class="fas fa-check-circle" style="color:#2e7d32;"></i> Pyodide 已就绪', 100)
    document.querySelectorAll('.btn-run').forEach(b => { b.disabled = false })
    document.dispatchEvent(new Event('pyodideReady'))
    ensureClusteringWorker().catch(err => {
      console.error('Failed to warm up clustering worker:', err)
    })
  } catch (e) {
    setPyStatus('<i class="fas fa-times-circle" style="color:#c0392b;"></i> 加载失败')
    console.error(e)
  }
}

document.addEventListener('DOMContentLoaded', initPyodide)
