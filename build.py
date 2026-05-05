import os
import glob
import shutil
import re
import json
import html as html_module

try:
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.formatters import HtmlFormatter
    HAVE_PYGMENTS = True
except ImportError:
    HAVE_PYGMENTS = False

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, 'build')


def read_file(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def build_python_blocks():
    parts = []
    pattern = os.path.join(ROOT, 'python', '*.py')
    for fpath in sorted(glob.glob(pattern)):
        name = os.path.splitext(os.path.basename(fpath))[0]
        content = read_file(fpath)
        tag = f'  <script type="text/python-src" data-module="{name}">\n{content}\n  </script>'
        parts.append(tag)
    return '\n\n'.join(parts)


def build_python_viewer_content():
    pattern = os.path.join(ROOT, 'python', '*.py')
    files = sorted(glob.glob(pattern))
    if HAVE_PYGMENTS:
        lexer = PythonLexer()
        formatter = HtmlFormatter(style='monokai', nowrap=True, noclasses=True)

    cards = []
    for fpath in files:
        name = os.path.splitext(os.path.basename(fpath))[0]
        source = read_file(fpath)
        if HAVE_PYGMENTS:
            inner = highlight(source, lexer, formatter)
        else:
            inner = html_module.escape(source)
        card = f'''    <div class="python-file-card">
      <div class="python-file-header">
        <i class="fas fa-file-code"></i> {name}.py
        <span class="badge">{name}</span>
      </div>
      <pre class="python-code"><code>{inner}</code></pre>
    </div>'''
        cards.append(card)
    body = '\n'.join(cards)
    return f'''<div class="module-content" id="python">
  <div class="page-header">
    <div class="header-left">
      <h1>Python 代码</h1>
      <div class="breadcrumb"><i class="fas fa-folder-open"></i> 代码 / Python</div>
    </div>
  </div>
  <div class="python-files">
{body}
  </div>
</div>'''


def build_html_modules():
    entries = []
    pattern = os.path.join(ROOT, 'html', 'modules', '*.html')
    for fpath in sorted(glob.glob(pattern)):
        name = os.path.splitext(os.path.basename(fpath))[0]
        content = read_file(fpath)
        escaped = content.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
        entries.append(f'  "{name}": `{escaped}`')

    py_viewer = build_python_viewer_content()
    py_escaped = py_viewer.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
    entries.append(f'  "python": `{py_escaped}`')

    body = ',\n'.join(entries)
    return f'<script>\nwindow.MODULE_HTML = {{\n{body}\n}}\n</script>'


def build_nav_menu():
    cfg_path = os.path.join(ROOT, "modules.json")
    data = json.loads(read_file(cfg_path))
    items = data.get("nav", [])
    parts = []
    for item in items:
        itype = item.get("type", "button")
        if itype == "divider":
            parts.append('        <div class="nav-divider"></div>')
            continue
        icon = item.get("icon", "fas fa-circle")
        label = item.get("label", "")
        module = item.get("module")
        active = " active" if item.get("active") else ""
        if module:
            parts.append(f'        <button class="nav-item{active}" data-module="{module}"><i class="{icon}"></i> {label}</button>')
        else:
            parts.append(f'        <button class="nav-item{active}"><i class="{icon}"></i> {label}</button>')
    return "\n".join(parts)


def copy_static():
    for name in ('css', 'js'):
        src = os.path.join(ROOT, name)
        dst = os.path.join(BUILD, name)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        count = len(os.listdir(src))
        print(f'  {name}/: {count} file(s) copied')


def inline_assets(html):
    """将 html 中的本地 CSS/JS 链接替换为内联 <style>/<script> 标签.

    跳过外部 URL（以 http://、https:// 或 // 开头），
    生成一个完全自包含的 HTML 文件，不依赖外部 CSS/JS 文件。
    """

    # --- 内联本地 CSS ---
    def _replace_css(m):
        href = m.group(1)
        if href.startswith(('http://', 'https://', '//')):
            return m.group(0)  # 外部 CDN，跳过
        path = os.path.join(ROOT, href)
        if not os.path.exists(path):
            print(f'  [warn] 内联 CSS 未找到: {href}')
            return m.group(0)
        content = read_file(path)
        return f'<style>\n{content}\n</style>'

    html = re.sub(
        r'<link\s+(?=[^>]*rel="stylesheet")[^>]*href="([^"]+)"[^>]*>',
        _replace_css,
        html,
    )

    # --- 内联本地 JS（只匹配有 src 属性的 <script> 标签） ---
    def _replace_js(m):
        src = m.group(1)
        if src.startswith(('http://', 'https://', '//')):
            return m.group(0)  # 外部 CDN，跳过
        path = os.path.join(ROOT, src)
        if not os.path.exists(path):
            print(f'  [warn] 内联 JS 未找到: {src}')
            return m.group(0)
        content = read_file(path)
        return f'<script>\n{content}\n</script>'

    html = re.sub(
        r'<script\s+src="([^"]+)"[^>]*>\s*</script>',
        _replace_js,
        html,
    )

    return html


def main():
    if os.path.exists(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(BUILD)

    template = os.path.join(ROOT, 'html', 'index.html')
    output = os.path.join(BUILD, 'index.html')

    html = read_file(template)

    py_block = build_python_blocks()
    html = html.replace('<!--BUILD_PYTHON-->', py_block)

    mod_block = build_html_modules()
    html = html.replace('<!--BUILD_MODULES-->', mod_block)
    html = html.replace('<!--BUILD_NAV-->', build_nav_menu())

    with open(output, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[build.py] Generated {output}')

    # 生成全内联版本（CSS/JS 嵌入 HTML，零外部依赖）
    inline_html = inline_assets(html)
    inline_output = os.path.join(BUILD, 'index.inline.html')
    with open(inline_output, 'w', encoding='utf-8') as f:
        f.write(inline_html)
    inlined = len(inline_html) > len(html)
    print(f'[build.py] Generated {inline_output} ({len(inline_html)} bytes, {"inlined" if inlined else "already inline"})')

    print(f'  Python modules: {len(glob.glob(os.path.join(ROOT, "python", "*.py")))} files')
    print(f'  HTML modules:   {len(glob.glob(os.path.join(ROOT, "html", "modules", "*.html")))} files')
    if HAVE_PYGMENTS:
        print('  Syntax highlighting: pygments (Monokai)')
    else:
        print('  Syntax highlighting: none (install pygments for color)')

    copy_static()


if __name__ == '__main__':
    main()
