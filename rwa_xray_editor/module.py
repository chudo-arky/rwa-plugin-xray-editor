"""JS-модуль для generic-маршрута админки — см. ``routes.py`` (``/ui-module``).

Тонкий адаптер: редактор целиком живёт в ``/app`` (``window.__xrayEditor``),
здесь только контракт ``window.rwaPluginUI[<id>] = {mount, unmount}`` и
подгрузка ``/app`` по требованию. DOM админки не трогаем — контейнер даёт
сама админка (ExternalPluginPage), сайдбар/шапка/крошки родные.
"""

MODULE_JS = r"""// xray_editor: UI-модуль для generic-маршрута админки (/plugins/:pluginId).
(function () {
  var PLUGIN_ID = 'xray_editor';
  // База — из адреса самого скрипта (переживает SECRET_PATH и любой префикс).
  var SRC = (document.currentScript && document.currentScript.src) || '';
  var M = SRC.match(/^(.*)\/ui-module(\?.*)?$/);
  var APP_URL = (M ? M[1] : '/api/v2/plugins/xray_editor') + '/app';
  var LOADER_ID = 'xed-loader';
  var pending = null;   // Promise загрузки /app
  var mountedEl = null;

  function loadApp() {
    if (window.__xrayEditor) return Promise.resolve();
    if (pending) return pending;
    pending = new Promise(function (resolve, reject) {
      var existing = document.getElementById(LOADER_ID);
      if (existing) {
        existing.addEventListener('load', function () { resolve(); }, { once: true });
        existing.addEventListener('error', function () { existing.remove(); reject(new Error('app load failed')); }, { once: true });
        return;
      }
      var sc = document.createElement('script');
      sc.id = LOADER_ID;
      sc.src = APP_URL;
      sc.addEventListener('load', function () { resolve(); }, { once: true });
      // при ошибке тег снимаем — иначе следующий заход повиснет на отстрелявших событиях
      sc.addEventListener('error', function () { sc.remove(); reject(new Error('app load failed')); }, { once: true });
      document.head.appendChild(sc);
    });
    pending.then(function () { pending = null; }, function () { pending = null; });
    return pending;
  }

  function mount(el) {
    mountedEl = el;
    el.innerHTML = '';
    loadApp().then(function () {
      // если за время загрузки уже размонтировали — не рисовать в мёртвый контейнер
      if (mountedEl !== el || !el.isConnected) return;
      if (window.__xrayEditor) window.__xrayEditor.mount(el);
    }).catch(function (e) {
      if (mountedEl !== el) return;
      var p = document.createElement('p');
      p.textContent = 'xray_editor: ' + (e && e.message ? e.message : 'load failed');
      el.appendChild(p);
    });
  }

  function unmount() {
    var el = mountedEl;
    mountedEl = null;
    if (window.__xrayEditor) window.__xrayEditor.unmount();
    // редактор сам содержимое не убирает — чистим контейнер, чтобы при
    // переключении на другой плагин наши узлы не остались рядом с его
    if (el) el.innerHTML = '';
  }

  window.rwaPluginUI = window.rwaPluginUI || {};
  window.rwaPluginUI[PLUGIN_ID] = { mount: mount, unmount: unmount };
})();
"""
