let pyodide = null

function postSuccess(requestId, payload) {
  self.postMessage({ type: 'success', requestId, payload })
}

function postError(requestId, error) {
  self.postMessage({ type: 'error', requestId, error: error?.message || String(error) })
}

async function initPyodideInWorker(pythonSources) {
  importScripts('https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js')
  pyodide = await loadPyodide()
  await pyodide.loadPackage(['numpy', 'matplotlib', 'pandas', 'scipy', 'scikit-learn'])

  for (const [name, content] of Object.entries(pythonSources || {})) {
    pyodide.FS.writeFile(`/home/pyodide/${name}.py`, content)
  }

  for (const name of Object.keys(pythonSources || {})) {
    await pyodide.runPythonAsync(`import ${name}`)
  }
}

async function applyUpload(payload) {
  if (!pyodide || !payload) return

  if (payload.kind === 'excel') {
    const meta = { original_name: payload.originalName, ext: payload.ext, sheets: [] }
    for (const sheet of payload.sheets || []) {
      pyodide.FS.writeFile(sheet.path, sheet.csv)
      meta.sheets.push({ index: sheet.index, name: sheet.name, path: sheet.path })
    }
    pyodide.FS.writeFile('/home/pyodide/upload_meta.json', JSON.stringify(meta))
    pyodide.FS.writeFile('/home/pyodide/upload_name.txt', payload.originalName)
    return
  }

  if (payload.kind === 'file') {
    const bytes = new Uint8Array(payload.bytes)
    pyodide.FS.writeFile(payload.path, bytes)
    pyodide.FS.writeFile('/home/pyodide/upload_meta.json', JSON.stringify({
      original_name: payload.originalName,
      ext: payload.ext,
      sheets: [{ index: 1, name: 'sheet1', path: payload.path }]
    }))
    pyodide.FS.writeFile('/home/pyodide/upload_name.txt', payload.originalName)
  }
}

async function runAnalysis(moduleName, funcName, params) {
  const lines = []
  pyodide.setStdout({ batched: s => lines.push(s) })
  try {
    const mod = pyodide.globals.get(moduleName)
    const fn = mod[funcName]
    const result = await Promise.resolve(fn(params))
    return {
      lines,
      result: result !== undefined ? result.toJs({ dict_converter: Object.fromEntries }) : null
    }
  } finally {
    pyodide.setStdout({ batched: () => {} })
  }
}

self.onmessage = async event => {
  const { type, requestId, payload } = event.data || {}

  try {
    if (type === 'init') {
      await initPyodideInWorker(payload?.pythonSources || {})
      self.postMessage({ type: 'ready' })
      return
    }

    if (type === 'upload') {
      await applyUpload(payload)
      postSuccess(requestId, { ok: true })
      return
    }

    if (type === 'run') {
      const out = await runAnalysis(payload.moduleName, payload.funcName, payload.params || {})
      postSuccess(requestId, out)
    }
  } catch (error) {
    postError(requestId, error)
  }
}
