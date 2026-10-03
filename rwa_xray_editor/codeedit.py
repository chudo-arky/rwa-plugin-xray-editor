"""Полноценный редактор кода для вкладки JSON: CodeMirror 5 + подсказки по схеме.

Библиотека лежит внутри пакета (``vendor/cm.js``) и отдаётся своим же роутом:
CSP админки — ``script-src 'self'``, с CDN ничего не подгрузить.

Подсказки строятся не по тексту, а по позиции в документе: сканер один раз
проходит JSON, собирает путь под курсором и запоминает, на какой строке начинается
каждый узел. Отсюда и дополнение по схеме, и всплывающая справка, и перенос
замечаний линтера на конкретные строки.
"""
from __future__ import annotations

CODE_JS = r"""
  /* ---------- редактор кода: загрузка вендорной библиотеки ---------- */
  var CM_CSS =
      '.CodeMirror{height:62vh;font:13px/1.5 ui-monospace,Menlo,monospace;border:1px solid hsl(var(--border, 220 14% 20%));' +
        'border-radius:10px;background:hsl(var(--card, 222 15% 9%));color:hsl(var(--foreground, 210 20% 92%))}' +
      '.CodeMirror-gutters{background:hsl(var(--card, 222 15% 9%));border-right:1px solid hsl(var(--border, 220 14% 20%))}' +
      '.CodeMirror-linenumber{color:hsl(var(--muted-foreground, 220 9% 45%))}' +
      '.CodeMirror-cursor{border-left:1.5px solid hsl(var(--primary, 239 84% 67%))}' +
      '.CodeMirror-selected{background:hsl(var(--primary, 239 84% 67%) / .22)}' +
      '.CodeMirror-focused .CodeMirror-selected{background:hsl(var(--primary, 239 84% 67%) / .3)}' +
      '.CodeMirror-activeline-background{background:hsl(var(--muted, 220 14% 18%) / .35)}' +
      '.CodeMirror-matchingbracket{color:hsl(150 60% 55%) !important;font-weight:600}' +
      '.cm-s-default .cm-string{color:hsl(150 45% 62%)}' +
      '.cm-s-default .cm-property{color:hsl(210 90% 72%)}' +
      '.cm-s-default .cm-number{color:hsl(38 85% 65%)}' +
      '.cm-s-default .cm-atom{color:hsl(280 70% 72%)}' +
      '.cm-s-default .cm-comment{color:hsl(var(--muted-foreground, 220 9% 45%))}' +
      '.cm-s-default .cm-keyword{color:hsl(280 70% 72%)}' +
      '.cm-s-default .cm-def,.cm-s-default .cm-variable-2{color:hsl(210 90% 72%)}' +
      '.cm-s-default .cm-meta{color:hsl(38 70% 62%)}' +
      '.cm-s-default .cm-tag{color:hsl(150 45% 62%)}' +
      '.CodeMirror-foldmarker{color:hsl(var(--primary, 239 84% 67%));text-shadow:none;font-family:inherit}' +
      '.CodeMirror-hints{z-index:9999;background:hsl(var(--card, 222 15% 11%));border:1px solid hsl(var(--border, 220 14% 24%));' +
        'border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.45);font:13px/1.4 ui-sans-serif,system-ui,sans-serif;max-height:22em}' +
      '.CodeMirror-hint{color:hsl(var(--foreground, 210 20% 92%));padding:6px 10px;border-radius:6px;max-width:520px}' +
      'li.CodeMirror-hint-active{background:hsl(var(--primary, 239 84% 67%) / .22)}' +
      '.xed-hint-name{font:600 13px/1.4 ui-monospace,Menlo,monospace}' +
      '.xed-hint-type{margin-left:8px;font:11px/1 ui-monospace,Menlo,monospace;color:hsl(var(--muted-foreground, 220 9% 55%))}' +
      '.xed-hint-doc{margin-top:2px;font-size:12px;color:hsl(var(--muted-foreground, 220 9% 60%));white-space:normal}' +
      '.xed-cmtip{position:fixed;z-index:10000;max-width:420px;padding:8px 10px;border-radius:10px;' +
        'background:hsl(var(--card, 222 15% 11%));border:1px solid hsl(var(--border, 220 14% 24%));' +
        'box-shadow:0 10px 30px rgba(0,0,0,.45);font:12px/1.45 ui-sans-serif,system-ui,sans-serif;' +
        'color:hsl(var(--foreground, 210 20% 90%));pointer-events:none}' +
      '.xed-cmtip-v{margin-top:6px;font:11px/1.4 ui-monospace,Menlo,monospace;color:hsl(var(--muted-foreground, 220 9% 58%))}' +
      '.CodeMirror-lint-tooltip{z-index:10001;font:12px/1.4 ui-sans-serif,system-ui,sans-serif}';

  var cmState = { loaded: false, loading: null, failed: false };
  function loadCM() {
    if (cmState.loaded) return Promise.resolve();
    if (cmState.loading) return cmState.loading;
    cmState.loading = new Promise(function (res, rej) {
      var css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = pluginBase() + '/vendor/cm-css';
      document.head.appendChild(css);
      var sc = document.createElement('script');
      sc.src = pluginBase() + '/vendor/cm-js';
      sc.onload = function () {
        cmState.loaded = true;
        // свой лист кладём ПОСЛЕ cm.css, иначе светлая тема библиотеки перебивает
        if (!document.getElementById('xed-cmstyle')) {
          var st = document.createElement('style');
          st.id = 'xed-cmstyle';
          st.textContent = CM_CSS;
          document.head.appendChild(st);
        }
        res();
      };
      sc.onerror = function () { cmState.failed = true; rej(new Error('vendor')); };
      document.head.appendChild(sc);
    });
    return cmState.loading;
  }

  /* ---------- сканер JSON ----------
     Терпит незаконченный документ (пользователь печатает), поэтому не парсер, а
     линейный проход. Отдаёт: путь под курсором, что там ожидается (ключ или
     значение), уже занятые ключи текущего объекта и строку начала каждого узла. */
  function scanJson(text, target) {
    var marks = {}, at = null;
    var stack = [];                       // {type:'o'|'a', key:null, idx:0, keys:[], afterColon:false}
    var i = 0, n = text.length, line = 0;
    var inStr = false, esc = false, strStart = -1;
    function pathNow() {
      var p = [];
      for (var k = 0; k < stack.length; k++) {
        var f = stack[k];
        p.push(f.type === 'a' ? f.idx : f.key);
      }
      return p;
    }
    function markHere() {
      var p = pathNow();
      if (p.length && p[p.length - 1] !== null) marks[JSON.stringify(p)] = line;
    }
    function capture(inString) {
      if (at) return;
      var f = stack.length ? stack[stack.length - 1] : null;
      var p = pathNow();
      var isKey = !!(f && f.type === 'o' && !f.afterColon);
      if (isKey) p = p.slice(0, p.length - 1);          // ключ ещё не выбран — путь до контейнера
      at = { path: p, isKey: isKey, inString: inString,
             siblings: f ? (f.keys || []).slice() : [], container: f ? f.type : null };
    }
    for (i = 0; i < n; i++) {
      if (target != null && i === target) capture(inStr);
      var c = text.charAt(i);
      if (c === '\n') line++;
      if (inStr) {
        if (esc) { esc = false; }
        else if (c === '\\') { esc = true; }
        else if (c === '"') {
          inStr = false;
          var f0 = stack.length ? stack[stack.length - 1] : null;
          if (f0 && f0.type === 'o' && !f0.afterColon) {
            f0.key = text.slice(strStart + 1, i);
            if (f0.keys.indexOf(f0.key) < 0) f0.keys.push(f0.key);
          }
        }
        continue;
      }
      if (c === '"') { inStr = true; strStart = i; continue; }
      if (c === '{' || c === '[') {
        markHere();
        stack.push({ type: c === '{' ? 'o' : 'a', key: null, idx: 0, keys: [], afterColon: false });
        continue;
      }
      if (c === '}' || c === ']') { stack.pop(); continue; }
      if (c === ':') {
        var f1 = stack.length ? stack[stack.length - 1] : null;
        if (f1) { f1.afterColon = true; markHere(); }
        continue;
      }
      if (c === ',') {
        var f2 = stack.length ? stack[stack.length - 1] : null;
        if (f2) {
          if (f2.type === 'o') { f2.key = null; f2.afterColon = false; }
          else { f2.idx++; markHere(); }
        }
        continue;
      }
    }
    if (target != null && !at) capture(inStr);
    return { marks: marks, at: at };
  }

  /* Узел схемы по пути: числовой сегмент — элемент массива, строковый — поле объекта. */
  function schemaAt(path) {
    var node = XSCHEMA;
    for (var i = 0; i < path.length; i++) {
      if (!node) return null;
      var seg = path[i];
      if (node.t === 'array') node = node.i;
      else if (node.t === 'object') node = (node.p || {})[seg];
      else return null;
    }
    return node || null;
  }
  function schemaDoc(node) {
    if (!node) return '';
    return (lang() === 'en' ? (node.e || node.d) : (node.d || node.e)) || '';
  }

  /* ---------- дополнение ---------- */
  function xrayHint(cm) {
    var cur = cm.getCursor();
    var text = cm.getValue();
    var off = cm.indexFromPos(cur);
    var sc = scanJson(text, off);
    if (!sc.at) return null;
    var tok = cm.getTokenAt(cur);
    var isStr = !!(tok.type && tok.type.indexOf('string') >= 0);   // у ключей тип "string property"
    var raw = isStr ? tok.string.replace(/^"/, '').replace(/"$/, '') : (tok.string || '').trim();
    var prefix = /^[\w.\-:!]*$/.test(raw) ? raw : '';
    var from = isStr ? CodeMirror.Pos(cur.line, tok.start + 1) : CodeMirror.Pos(cur.line, cur.ch - prefix.length);
    var to = isStr ? CodeMirror.Pos(cur.line, tok.end - (/"$/.test(tok.string) ? 1 : 0)) : cur;

    var list = [];
    if (sc.at.isKey) {
      var owner = schemaAt(sc.at.path);
      if (owner && owner.t === 'array') owner = owner.i;
      if (!owner || owner.t !== 'object') return null;
      var props = owner.p || {};
      var exactK = prefix && props[prefix];
      Object.keys(props).forEach(function (k) {
        if (sc.at.siblings.indexOf(k) >= 0 && k !== prefix) return;   // уже есть в этом объекте
        if (!exactK && prefix && k.toLowerCase().indexOf(prefix.toLowerCase()) !== 0) return;
        list.push({ text: isStr ? k : '"' + k + '"', displayText: k, doc: schemaDoc(props[k]), kind: props[k].t });
      });
    } else {
      var node = schemaAt(sc.at.path);
      if (!node) return null;
      var vals = node.v || (node.t === 'boolean' ? ['true', 'false'] : null);
      if (!vals) return null;
      var exact = prefix && vals.indexOf(prefix) >= 0;
      vals.forEach(function (v) {
        if (!exact && prefix && String(v).toLowerCase().indexOf(prefix.toLowerCase()) !== 0) return;
        var quoted = node.t === 'boolean' ? v : (isStr ? v : '"' + v + '"');
        list.push({ text: quoted, displayText: String(v) || '(пусто)', doc: schemaDoc(node), kind: node.t });
      });
    }
    if (!list.length) return null;
    return {
      list: list.map(function (it) {
        return {
          text: it.text, displayText: it.displayText,
          render: function (el) {
            el.innerHTML = '<span class="xed-hint-name">' + esc(it.displayText) + '</span>' +
              (it.kind ? '<span class="xed-hint-type">' + esc(it.kind) + '</span>' : '') +
              (it.doc ? '<div class="xed-hint-doc">' + esc(it.doc) + '</div>' : '');
          }
        };
      }),
      from: from, to: to
    };
  }

  /* ---------- замечания на полях ----------
     Синтаксис — из JSON.parse (позиция точная), смысл — из нашего линтера,
     привязанный к строке узла через разметку сканера. */
  function nodeToPath(id, c) {
    var kind = String(id).split(':')[0], tag = String(id).slice(String(id).indexOf(':') + 1);
    function idxByTag(arr, t) {
      for (var i = 0; i < (arr || []).length; i++) if (arr[i] && arr[i].tag === t) return i;
      return -1;
    }
    if (id === 'dns') return ['dns'];
    if (kind === 'in') { var i1 = idxByTag(c.inbounds, tag); return i1 < 0 ? null : ['inbounds', i1]; }
    if (kind === 'out') { var i2 = idxByTag(c.outbounds, tag); return i2 < 0 ? null : ['outbounds', i2]; }
    if (kind === 'rule') return ['routing', 'rules', parseInt(tag, 10)];
    if (kind === 'bal') {
      var i3 = idxByTag((c.routing || {}).balancers, tag);
      return i3 < 0 ? null : ['routing', 'balancers', i3];
    }
    return null;
  }
  function jsonAnnotations(text) {
    var out = [];
    var parsed = null;
    try { parsed = JSON.parse(text); }
    catch (e) {
      var m = /position (\d+)/.exec(e.message || '');
      var pos = m ? parseInt(m[1], 10) : 0;
      var before = text.slice(0, pos);
      var ln = before.split('\n').length - 1;
      var ch = pos - (before.lastIndexOf('\n') + 1);
      out.push({ from: CodeMirror.Pos(ln, Math.max(0, ch)), to: CodeMirror.Pos(ln, Math.max(0, ch) + 1),
                 message: e.message, severity: 'error' });
      return out;
    }
    var sc = scanJson(text, null);
    lint(parsed).forEach(function (it) {
      var path = it.node ? nodeToPath(it.node, parsed) : null;
      var ln = path ? sc.marks[JSON.stringify(path)] : 0;
      if (ln == null) ln = 0;
      var lineText = text.split('\n')[ln] || '';
      out.push({
        from: CodeMirror.Pos(ln, 0), to: CodeMirror.Pos(ln, Math.max(1, lineText.length)),
        message: (it.node ? it.node + ' — ' : '') + it.msg,
        severity: it.level === 'error' ? 'error' : 'warning'
      });
    });
    return out;
  }

  /* ---------- уборка всплывашек редактора ----------
     Подсказка схемы, список автодополнения и тултип линтера живут в document.body,
     а не внутри контейнера плагина: при уходе со страницы (кнопка «назад» админки)
     контейнер исчезает без mouseleave, и подсказка оставалась висеть поверх
     чужих страниц. Зовётся из unmount() и перед каждой перерисовкой. */
  function cleanupCodeUi() {
    if (state.cm && state.cm._hoverT) { clearTimeout(state.cm._hoverT); state.cm._hoverT = null; }
    var stray = document.querySelectorAll('.xed-cmtip, .CodeMirror-hints, .CodeMirror-lint-tooltip');
    for (var i = 0; i < stray.length; i++) {
      if (stray[i].parentNode) stray[i].parentNode.removeChild(stray[i]);
    }
  }

  /* ---------- справка под курсором мыши ---------- */
  function attachHover(cm) {
    var tip = null;
    function hide() { if (tip && tip.parentNode) tip.parentNode.removeChild(tip); tip = null; }
    cm.getWrapperElement().addEventListener('mouseleave', hide);
    cm.getWrapperElement().addEventListener('mousemove', function (e) {
      if (cm._hoverT) clearTimeout(cm._hoverT);
      var x = e.clientX, y = e.clientY;
      cm._hoverT = setTimeout(function () {
        cm._hoverT = null;
        // редактор уже сняли со страницы, пока таймер ждал — не рисовать в пустоту
        if (!cm.getWrapperElement().isConnected || state.cm !== cm) { hide(); return; }
        var pos = cm.coordsChar({ left: x, top: y }, 'window');
        var tok = cm.getTokenAt(pos);
        if (!tok || !tok.type || tok.type.indexOf('string') < 0) { hide(); return; }
        var off = cm.indexFromPos({ line: pos.line, ch: tok.start + 1 });
        var sc = scanJson(cm.getValue(), off);
        if (!sc.at) { hide(); return; }
        // на ключе путь ведёт к контейнеру — дописываем сам ключ
        var path = sc.at.path.slice();
        if (sc.at.isKey) path.push(tok.string.replace(/"/g, ''));
        var node = schemaAt(path);
        var doc = schemaDoc(node);
        if (!doc) { hide(); return; }
        hide();
        tip = document.createElement('div');
        tip.className = 'xed-cmtip';
        tip.innerHTML = '<b>' + esc(String(path[path.length - 1])) + '</b>'
          + (node.t ? '<span class="xed-hint-type">' + esc(node.t) + '</span>' : '')
          + '<div>' + esc(doc) + '</div>'
          + (node.v && node.v.length ? '<div class="xed-cmtip-v">' + esc(node.v.filter(Boolean).join(' · ')) + '</div>' : '');
        tip.style.left = Math.round(x + 12) + 'px';
        tip.style.top = Math.round(y + 14) + 'px';
        document.body.appendChild(tip);
      }, 260);
    });
    cm.on('changes', hide);
    cm.on('scroll', hide);
  }

  /* ---------- подключение к textarea ---------- */
  function setupCodeEditor() {
    var ta = document.getElementById('xed-fulljson') || document.getElementById('xed-subs-text');
    state.cm = null;
    if (!ta || typeof Promise === 'undefined') return;
    // YAML-шаблоны подписки (MIHOMO/CLASH/STASH) — свой режим: ни json-подсветка,
    // ни схема Xray, ни линтер к ним не относятся
    var isYaml = ta.id === 'xed-subs-text' && state.subsDoc && state.subsDoc.format !== 'json';
    loadCM().then(function () {
      if (!document.body.contains(ta)) return;            // страница успела перерисоваться
      var cm = CodeMirror.fromTextArea(ta, {
        mode: isYaml ? 'yaml' : { name: 'javascript', json: true },
        lineNumbers: true,
        lineWrapping: false,
        matchBrackets: true,
        autoCloseBrackets: true,
        styleActiveLine: true,
        foldGutter: true,
        gutters: ['CodeMirror-lint-markers', 'CodeMirror-linenumbers', 'CodeMirror-foldgutter'],
        lint: isYaml ? false : { getAnnotations: jsonAnnotations, lintOnChange: true, delay: 400 },
        extraKeys: {
          'Ctrl-Space': function (c) { c.showHint({ hint: xrayHint, completeSingle: false }); },
          'Cmd-Space': function (c) { c.showHint({ hint: xrayHint, completeSingle: false }); },
          'Ctrl-Q': function (c) { c.foldCode(c.getCursor()); }
        }
      });
      cm.setSize(null, '62vh');
      if (isYaml) { state.cm = cm; return; }              // дальше только про Xray-JSON
      // подсказки сами всплывают, когда набирают имя поля или значение в кавычках
      cm.on('inputRead', function (c, ch) {
        if (!ch.text || !ch.text.length) return;
        var s = ch.text[0];
        if (/[\w"]/.test(s)) {
          clearTimeout(c._hintT);
          c._hintT = setTimeout(function () {
            if (!c.state.completionActive) c.showHint({ hint: xrayHint, completeSingle: false });
          }, 120);
        }
      });
      attachHover(cm);
      state.cm = cm;
      if (state.cmGoto != null) { cm.setCursor({ line: state.cmGoto, ch: 0 }); cm.focus(); state.cmGoto = null; }
    }).catch(function () { /* нет вендорных файлов — остаётся обычное поле */ });
  }
  // текст из редактора (или из простого поля, если библиотека не поднялась)
  function codeValue(id) {
    if (state.cm) { state.cm.save(); return state.cm.getValue(); }
    var el = document.getElementById(id);
    return el ? el.value : '';
  }
"""
