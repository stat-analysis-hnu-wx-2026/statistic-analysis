let pyodide = null

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

    setPyStatus('<i class="fas fa-spinner fa-pulse"></i> 加载中文字体...', 95)
    const fontUrls = [
      'https://cdn.jsdelivr.net/gh/StellarCN/scp_zh@master/fonts/SimHei.ttf',
      'https://raw.githubusercontent.com/StellarCN/scp_zh/master/fonts/SimHei.ttf'
    ]
    for (const url of fontUrls) {
      try {
        const resp = await fetch(url, { signal: AbortSignal.timeout(15000) })
        if (resp.ok) {
          pyodide.FS.writeFile('/home/pyodide/SimHei.ttf', new Uint8Array(await resp.arrayBuffer()))
          break
        }
      } catch (_) {}
    }

    await pyodide.runPythonAsync(`
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import warnings
try:
    fm.fontManager.addfont('/home/pyodide/SimHei.ttf')
    fp = fm.FontProperties(fname='/home/pyodide/SimHei.ttf')
    plt.rcParams['font.family'] = fp.get_name()
    plt.rcParams['axes.unicode_minus'] = False
except Exception as e:
    warnings.warn(f"中文字体配置失败: {e}")
`)

    setPyStatus('<i class="fas fa-check-circle" style="color:#2e7d32;"></i> Pyodide 已就绪', 100)
    document.querySelectorAll('.btn-run').forEach(b => { b.disabled = false })
    document.dispatchEvent(new Event('pyodideReady'))
  } catch (e) {
    setPyStatus('<i class="fas fa-times-circle" style="color:#c0392b;"></i> 加载失败')
    console.error(e)
  }
}

document.addEventListener('DOMContentLoaded', initPyodide)
