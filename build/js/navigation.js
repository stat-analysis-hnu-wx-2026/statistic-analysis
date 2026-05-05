async function loadModule(name) {
  const existing = document.getElementById(name)
  if (existing) {
    document.querySelectorAll('.module-content').forEach(el => el.classList.remove('active'))
    existing.classList.add('active')
    return
  }

  const main = document.querySelector('.main')
  const placeholder = main.querySelector('.module-loading')
  if (placeholder) placeholder.style.display = 'block'

  try {
    const html = MODULE_HTML && MODULE_HTML[name]
    if (!html) throw new Error(`Module "${name}" not found`)

    const temp = document.createElement('div')
    temp.innerHTML = html
    const moduleEl = temp.firstElementChild
    if (!moduleEl || !moduleEl.classList.contains('module-content')) return

    if (placeholder) placeholder.style.display = 'none'
    main.appendChild(moduleEl)

    document.querySelectorAll('.module-content').forEach(el => el.classList.remove('active'))
    moduleEl.classList.add('active')

    if (typeof bindRunButtons === 'function') bindRunButtons()
    if (typeof bindExportButtons === 'function') bindExportButtons()
    if (window.pyodideReady) {
      moduleEl.querySelectorAll('.btn-run').forEach(b => { b.disabled = false })
    }
  } catch (e) {
    console.error(`Failed to load module ${name}:`, e)
    if (placeholder) placeholder.textContent = '模块加载失败: ' + e.message
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadModule('clustering')

  document.querySelectorAll('.nav-item[data-module]').forEach(item => {
    item.addEventListener('click', () => {
      const name = item.dataset.module
      document.querySelectorAll('.nav-item[data-module]').forEach(n => n.classList.remove('active'))
      item.classList.add('active')
      loadModule(name)
    })
  })
})
