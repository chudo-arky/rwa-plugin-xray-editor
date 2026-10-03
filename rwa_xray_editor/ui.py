"""UI редактора: HTML-страница и JS-модуль (vanilla, без сборки).

Один JS-модуль на оба рендера: standalone-страница и инъекция в SPA подгружают
его с одного роута (``/app``) — логика не дублируется.

Чтение и запись — родное API админки (``GET/PATCH /api/v2/config-profiles``):
RBAC (`resources:edit`), версионирование `config_versions`, аудит и человеческие
ошибки панели достаются бесплатно; у плагина своих write-эндпоинтов нет.
Для PATCH обязателен CSRF double-submit: заголовок ``X-CSRF-Token`` = кука
``rw_csrf``. Оптимистичной блокировки у админки нет — перед записью профиль
перечитывается и сверяется ``updatedAt``.
"""
from __future__ import annotations

from .codeedit import CODE_JS
from .schema import SCHEMA_JS

PAGE_HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Редактор Xray</title>
<style>
  :root {
    --bg: hsl(220 24% 7%);
    --card: hsl(220 20% 10%);
    --border: hsl(220 14% 18%);
    --fg: hsl(220 9% 84%);
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  .wrap { max-width: 1560px; margin: 0 auto; padding: 24px 20px 40px; }
</style>
</head>
<body>
<div class="wrap"><div id="xed-root"></div></div>
<script src="app" defer></script>
</body>
</html>
"""

APP_JS = r"""'use strict';
/* Редактор Xray-конфигов (порт VAQYBIN). window.__xrayEditor = {mount, unmount};
   при наличии #xed-root монтируется сам (standalone). */
(function () {
  if (window.__xrayEditor) return;

  function pluginBase() { return apiBase() + '/plugins/xray_editor'; }
  function apiBase() {
    var sp = (window.__ENV && window.__ENV.SECRET_PATH) || '';
    sp = String(sp).replace(/^\/+|\/+$/g, '');
    return (sp ? '/' + sp : '') + '/api/v2';
  }
  function csrfToken() {
    var m = document.cookie.match(/(?:^|;\s*)rw_csrf=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  var L = {
    ru: {
      title: 'Редактор Xray', sub: 'inbounds → правила → балансеры → outbounds · клик — правка, тащи карточку — двигать, тяни из точки — связать',
      loading: 'загрузка…', loadFail: 'не удалось загрузить профили: ',
      refresh: 'Обновить', updated: 'обновлён ', nodesUse: ' нод используют профиль',
      nodesUseNone: 'не привязан к нодам', wholeJson: 'JSON конфига',
      capIn: 'INBOUNDS', capRules: 'ПРАВИЛА', capBal: 'БАЛАНСЕРЫ', capOut: 'OUTBOUNDS',
      dns: 'DNS', dnsServers: 'серверов: ', ruleN: 'правило #', candidates: 'кандидатов: ',
      allInbounds: 'все inbound',
      defaultOut: 'default', noTarget: 'без цели', sniffOn: 'sniffing вкл', sniffOff: 'sniffing выкл',
      issues: 'Проблемы', noIssues: 'проблем не найдено', errors: 'ошибок: ', warns: 'предупреждений: ',
      inspClose: 'Закрыть',
      draft: 'черновик', undo: '↶ Undo', redo: '↷ Redo', reset: 'Сбросить к версии панели',
      resetPos: 'Сбросить расположение', versions: 'Версии',
      traceBtn: 'Куда пойдёт трафик', traceTitle: 'Разбор трассы',
      tabTopo: 'Топология', tabJson: 'JSON', cfgSettings: 'Настройки конфига',
      recipes: '+ Рецепт', recipesTitle: 'Рецепты', recPreview: 'Предпросмотр', recApply: 'Применить рецепт',
      recPlan: 'Что изменится', tplBtn: 'Из шаблона', tplTitle: 'Новый профиль из шаблона',
      tplName: 'Имя профиля', tplCreate: 'Создать', tplOk: 'профиль создан',
      tplFail: 'не удалось создать профиль: ', tplNameBad: 'имя: 2–30 символов, латиница/цифры/_/-/пробел',
      hintTags: '(частая причина: тег инбаунда уже занят другим профилем — панель требует уникальности по всей базе)',
      tplPick: 'выбери шаблон в списке',
      checkBtn: 'Проверить конфиг', checkTitle: 'Проверка ядром xray', checkOk: 'Конфиг валиден',
      checkBad: 'Ядро отвергло конфиг', checkNoBin: 'Ядро не скачано — проверка недоступна',
      checkDl: 'Скачать ядро (~40 МБ)', checkBusy: 'работаю…', checkWarn: 'Предупреждения ядра',
      checkGeoDl: 'Скачать geo-базы и повторить', checkHttp: 'Сервер не ответил по-человечески: ',
      checkNote: 'Ядро видит не то же, что линтер: висячую ссылку на outbound оно пропускает, зато ловит ограничения реализации. Обе проверки нужны.',
      tabSubs: 'Подписки', subsPick: 'Шаблон подписки', subsSave: 'Сохранить в панель',
      subsOpen: 'Шаблоны подписок', subsBack: '← Все конфиги',
      pickTitle: 'Конфиг-профили', pickProfiles: 'профилей: ', pickSubsHd: 'Шаблоны подписок',
      pickSubsCnt: 'шаблонов: ', pickNew: 'Создать профиль', pickNoNodes: 'нет привязанных нод',
      pickNodes: ' нод', pickEmptyIn: 'без инбаундов', pickLoading: 'загрузка…',
      pickHint: 'Сверху — конфиги нод (маршрутизация), ниже — шаблоны подписок (то, что получает клиент).',
      recPre: 'Готовые рецепты',
      subsTitle: 'Редактор шаблонов подписки',
      subsSub: 'то, что получает клиентское приложение · тот же визуальный редактор, что и для конфига ноды',
      subsRaw: 'Показать JSON', subsGraph: 'Показать схему', subsNew: '+ Шаблон',
      subsNewTitle: 'Новый шаблон подписки', subsType: 'Тип', subsName: 'Имя',
      subsCreate: 'Создать', subsCreated: 'шаблон создан', subsDirtyChip: 'есть правки',
      subsSaved: 'шаблон сохранён', subsFail: 'не удалось сохранить: ', subsLoad: 'загрузка шаблона…',
      subsNote: 'Шаблон подписки — то, что отдаётся клиентскому приложению. Это не конфиг ноды: правки здесь на маршрутизацию не влияют.',
      geoBtn: 'Geo-базы', geoTitle: 'Geo-базы',
      geoTabSrc: 'Источники', geoTabView: 'Просмотр',
      geoSrcSite: 'Ссылка на geosite', geoSrcIp: 'Ссылка на geoip', geoPresets: 'Пресеты:',
      geoKindSite: 'geosite — домены', geoKindIp: 'geoip — подсети',
      geoFindCat: 'поиск категории…', geoFindVal: 'поиск значения…',
      geoCopy: 'Скопировать', geoToRule: 'В правило', geoShown: 'показаны ',
      geoPrev: '← Назад', geoNext: 'Вперёд →', geoOf: ' из ',
      geoInserted: 'добавлено в правило ', geoNoRule: 'нет ни одного правила — создай его сначала',
      cfgRouting: 'Маршрутизация', cfgLog: 'Лог',
      cfgAccess: 'Файл access-лога', cfgError: 'Файл error-лога', cfgDns: 'Логировать DNS-запросы (dnsLog)',
      cfgPathHint: 'Путь к файлу; none — отключить; пусто — стандартный вывод',
      cfgStratHint: 'Как резолвить домены при сопоставлении с ip-правилами',
      cfgMatchHint: 'Алгоритм сопоставления доменных правил',
      recWill: 'Будет сделано', recShowDiff: 'Показать diff',
      geoNote: 'Базы нужны, чтобы отвечать на вопросы geosite:/geoip:. Ядро на нодах имеет свои копии — эти лежат рядом с плагином и на маршрутизацию не влияют.',
      geoAbsent: 'не скачана', geoCats: ' категорий', geoDl: 'Скачать / обновить', geoBusy: 'качаю…',
      geoUpd: 'обновлено ',
      tplLocal: 'Встроенные', tplGallery: 'Галерея remnawave/templates', tplLoading: 'загрузка галереи…',
      tplGalleryErr: 'галерея недоступна: ', tplBy: 'от ',
      cfgTitle: 'Настройки конфига', domStrategy: 'Стратегия домена (routing.domainStrategy)',
      domMatcher: 'Матчер доменов (routing.domainMatcher)', logLevel: 'Уровень лога (log.loglevel)',
      domStrategyHint: 'AsIs — не резолвить домены (ip-правила не сработают по доменной цели); '
        + 'IPIfNonMatch — резолвить, если по домену никто не совпал; IPOnDemand — резолвить сразу',
      apply2: 'Применить', zoomIn: '+', zoomOut: '−', zoomFit: 'сброс',
      trWhere: 'Куда', trFrom: 'Откуда', trAnyIn: 'любой inbound', trClose: 'Закрыть разбор', trPort: 'Порт',
      trProto: 'Протокол приложения', trProtoAny: 'не задан', trProtoOther: 'другой / не определился',
      trDomIp: 'IP домена', trDomIpPh: 'куда резолвится', trResolve: 'узнать', trNoResolve: 'не резолвится',
      trUser: 'Пользователь', trSrc: 'IP клиента',
      trEmpty: 'Введи домен или IP — покажу, какое правило сработает и в какой outbound уйдёт трафик.', trTry: 'например:',
      trNoOut: 'в конфиге нет ни одного outbound — трафику некуда идти',
      trDefault: 'ни одно правило не подошло → outbound по умолчанию (первый в списке)',
      trByRule: 'сработало правило #', trBal: 'балансер ',
      trBalNone: 'у балансера нет кандидатов — трафик уйдёт в fallback или будет отброшен',
      trSure: 'Точно: все правила выше проверены', trUnsure: 'Может отличаться',
      trUnsureWhy: 'выше по списку есть правила, которые не удалось проверить:',
      trPass1: '1-й проход по домену: совпадений нет', trPass2: '2-й проход по IP ',
      trPassHint: '(IPIfNonMatch: если по домену никто не совпал, ядро резолвит его и проверяет IP-правила)',
      trNeedIpPass: 'стратегия IPIfNonMatch: укажи IP домена — покажу 2-й проход',
      trGeoOff: 'geo-базы не скачаны — правила по geosite:/geoip: не проверить', trGeoDl: 'скачать geo-базы',
      trGeoMissing: 'категории нет в базе — ядро отвергнет конфиг: ',
      trSniffBlind: 'на inbound «{v}» выключен sniffing: протокол приложения ядро не определит (правила по protocol не сработают), а домен увидит, только если клиент передаёт его, а не IP',
      trOrder: 'Правила по порядку', trOrderHint: 'ядро берёт первое совпавшее и дальше не смотрит',
      trBelow: ' ниже сработавшего — ядро до них не дойдёт', trShow: 'показать', trHide: 'скрыть', trSet: 'указать',
      trRoute: 'маршрут',
      trStates: { yes: 'совпало', no: 'не совпало', unknown: 'нет данных', skipped: 'не дошло' },
      trR: {
        domain_hit: 'домен подходит под «{v}»', domain_miss: 'домен не из списка ({v})', domain_unknown: 'не проверить «{v}»',
        geo_need: 'нужна geo-база для «{v}»',
        ip_asis: 'правило по IP, а цель — домен: при domainStrategy AsIs ядро домен не резолвит, правило не действует (проверить — введи IP вместо домена)',
        proto_nosniff: 'на этом inbound выключен sniffing — протокол ядро не определит',
        ip_pass1: 'на 1-м проходе домен ещё не резолвлен — IP-правила проверяются на 2-м',
        ip_need: 'нужен IP домена', ip_hit: 'адрес входит в «{v}»', ip_miss: 'адрес не входит ни в одну из подсетей ({v})',
        ip_unknown: 'не проверить «{v}»', src_need: 'нужен IP клиента',
        port_bad: 'непонятный формат портов: {v}', port_need: 'порт не задан',
        port_hit: 'порт {v} входит в «{s}»', port_miss: 'порт {v} не входит в «{s}»',
        net_hit: '{v} подходит', net_miss: 'только {s}, а у нас {v}',
        proto_need: 'нужен протокол приложения — ядро узнаёт его через sniffing', user_need: 'нужен пользователь',
        in_need: 'нужно выбрать inbound', exact_hit: '«{v}» есть в списке', exact_miss: '«{v}» не в списке'
      },
      versionsTitle: 'История версий профиля', verEmpty: 'версий пока нет',
      verLoad: 'В черновик', verDiff: 'Сравнить', verBy: 'автор ', verBytes: ' Б',
      verLoaded: 'версия загружена в черновик — проверь и сохрани',
      verFail: 'не удалось получить версии: ',
      save: 'Сохранить в панель', saveBlocked: 'ошибки линтера блокируют сохранение',
      addRule: '+ Правило', addOut: '+ Outbound', addIn: '+ Inbound', addBal: '+ Балансер',
      searchPh: 'Поиск: тег, порт, домен…', found: 'найдено: ', notFound: 'ничего не найдено',
      ruleWord: 'ПРАВИЛО', balWord: 'БАЛАНСЕР', resolver: 'РЕЗОЛВЕР', noConds: 'без условий',
      formTab: 'Форма', jsonTab: 'JSON', apply: 'Применить', delNode: 'Удалить',
      up: '↑', down: '↓', badJson: 'невалидный JSON: ',
      tag: 'Тег', port: 'Порт', protocol: 'Протокол', network: 'network',
      domains: 'Домены (по строке)', ips: 'IP/CIDR (по строке)', protocols: 'protocol',
      ruleInbounds: 'Инбаунды (пусто = все)', target: 'Цель',
      selector: 'Селектор (префиксы тегов, по строке)', strategy: 'Стратегия', fallback: 'fallbackTag',
      sniffing: 'Sniffing', destOverride: 'destOverride',
      confirmDel: 'Удалить узел из конфига?', confirmReset: 'Отбросить черновик и вернуться к версии панели?',
      diffTitle: 'Изменения перед сохранением', diffNone: 'отличий нет',
      diffWarn: 'Панель раскатает конфиг на ноды профиля сразу после сохранения.',
      confirm: 'Сохранить', cancel: 'Отмена',
      conflictTitle: 'Конфликт версий', conflictBody: 'Профиль изменён в панели, пока ты редактировал. Перезапись затрёт чужие правки.',
      conflictLoad: 'Загрузить версию панели', conflictForce: 'Перезаписать',
      savedOk: 'сохранено, версия записана', saveFail: 'ошибка сохранения: ',
      none: '— нет —'
    },
    en: {
      title: 'Xray editor', sub: 'inbounds → rules → balancers → outbounds · click to edit, drag a card to move, drag from a dot to link',
      loading: 'loading…', loadFail: 'failed to load profiles: ',
      refresh: 'Refresh', updated: 'updated ', nodesUse: ' nodes use this profile',
      nodesUseNone: 'not attached to nodes', wholeJson: 'Config JSON',
      capIn: 'INBOUNDS', capRules: 'RULES', capBal: 'BALANCERS', capOut: 'OUTBOUNDS',
      dns: 'DNS', dnsServers: 'servers: ', ruleN: 'rule #', candidates: 'candidates: ',
      allInbounds: 'all inbounds',
      defaultOut: 'default', noTarget: 'no target', sniffOn: 'sniffing on', sniffOff: 'sniffing off',
      issues: 'Issues', noIssues: 'no issues found', errors: 'errors: ', warns: 'warnings: ',
      inspClose: 'Close',
      draft: 'draft', undo: '↶ Undo', redo: '↷ Redo', reset: 'Reset to panel version',
      resetPos: 'Reset layout', versions: 'Versions',
      traceBtn: 'Where traffic goes', traceTitle: 'Route trace',
      tabTopo: 'Topology', tabJson: 'JSON', cfgSettings: 'Config settings',
      recipes: '+ Recipe', recipesTitle: 'Recipes', recPreview: 'Preview', recApply: 'Apply recipe',
      recPlan: 'What changes', tplBtn: 'From template', tplTitle: 'New profile from template',
      tplName: 'Profile name', tplCreate: 'Create', tplOk: 'profile created',
      tplFail: 'failed to create profile: ', tplNameBad: 'name: 2-30 chars, latin/digits/_/-/space',
      hintTags: '(common cause: inbound tag already used by another profile — the panel requires global uniqueness)',
      tplPick: 'pick a template first',
      checkBtn: 'Validate config', checkTitle: 'Validation by xray core', checkOk: 'Config is valid',
      checkBad: 'Core rejected the config', checkNoBin: 'Core not downloaded — validation unavailable',
      checkDl: 'Download core (~40 MB)', checkBusy: 'working…', checkWarn: 'Core warnings',
      checkGeoDl: 'Download geo databases and retry', checkHttp: 'Unexpected server response: ',
      checkNote: 'The core sees differently than the linter: it ignores dangling outbound refs but catches implementation limits. Both matter.',
      tabSubs: 'Subscriptions', subsPick: 'Subscription template', subsSave: 'Save to panel',
      subsOpen: 'Subscription templates', subsBack: '← All configs',
      pickTitle: 'Config profiles', pickProfiles: 'profiles: ', pickSubsHd: 'Subscription templates',
      pickSubsCnt: 'templates: ', pickNew: 'Create profile', pickNoNodes: 'no nodes attached',
      pickNodes: ' nodes', pickEmptyIn: 'no inbounds', pickLoading: 'loading…',
      pickHint: 'Above — node configs (routing), below — subscription templates (what the client receives).',
      recPre: 'Ready-made recipes',
      subsTitle: 'Subscription template editor',
      subsSub: 'what client apps receive · same visual editor as for the node config',
      subsRaw: 'Show JSON', subsGraph: 'Show graph', subsNew: '+ Template',
      subsNewTitle: 'New subscription template', subsType: 'Type', subsName: 'Name',
      subsCreate: 'Create', subsCreated: 'template created', subsDirtyChip: 'unsaved edits',
      subsSaved: 'template saved', subsFail: 'save failed: ', subsLoad: 'loading template…',
      subsNote: 'A subscription template is what client apps receive. Not a node config: edits here do not affect routing.',
      geoBtn: 'Geo bases', geoTitle: 'Geo bases',
      geoTabSrc: 'Sources', geoTabView: 'Browse',
      geoSrcSite: 'geosite URL', geoSrcIp: 'geoip URL', geoPresets: 'Presets:',
      geoKindSite: 'geosite — domains', geoKindIp: 'geoip — subnets',
      geoFindCat: 'find category…', geoFindVal: 'find value…',
      geoCopy: 'Copy', geoToRule: 'To rule', geoShown: 'showing ',
      geoPrev: '← Back', geoNext: 'Next →', geoOf: ' of ',
      geoInserted: 'added to rule ', geoNoRule: 'no rules yet — create one first',
      cfgRouting: 'Routing', cfgLog: 'Log',
      cfgAccess: 'Access log file', cfgError: 'Error log file', cfgDns: 'Log DNS queries (dnsLog)',
      cfgPathHint: 'File path; none — disable; empty — standard output',
      cfgStratHint: 'How domains are resolved when matching ip rules',
      cfgMatchHint: 'Domain rule matching algorithm',
      recWill: 'What will happen', recShowDiff: 'Show diff',
      geoNote: 'Needed to answer geosite:/geoip: questions. Node cores keep their own copies — these live next to the plugin and do not affect routing.',
      geoAbsent: 'not downloaded', geoCats: ' categories', geoDl: 'Download / update', geoBusy: 'downloading…',
      geoUpd: 'updated ',
      tplLocal: 'Built-in', tplGallery: 'Gallery remnawave/templates', tplLoading: 'loading gallery…',
      tplGalleryErr: 'gallery unavailable: ', tplBy: 'by ',
      cfgTitle: 'Config settings', domStrategy: 'Domain strategy (routing.domainStrategy)',
      domMatcher: 'Domain matcher (routing.domainMatcher)', logLevel: 'Log level (log.loglevel)',
      domStrategyHint: 'AsIs — do not resolve domains; IPIfNonMatch — resolve if nothing matched by '
        + 'domain; IPOnDemand — resolve upfront',
      apply2: 'Apply', zoomIn: '+', zoomOut: '−', zoomFit: 'reset',
      trWhere: 'Where to', trFrom: 'From', trAnyIn: 'any inbound', trClose: 'Close tracer', trPort: 'Port',
      trProto: 'App protocol', trProtoAny: 'not set', trProtoOther: 'other / not detected',
      trDomIp: 'Domain IP', trDomIpPh: 'what it resolves to', trResolve: 'look up', trNoResolve: 'does not resolve',
      trUser: 'User', trSrc: 'Client IP',
      trEmpty: 'Type a domain or IP — I will show which rule fires and which outbound the traffic takes.', trTry: 'e.g.',
      trNoOut: 'the config has no outbounds — traffic has nowhere to go',
      trDefault: 'no rule matched → default outbound (first in the list)',
      trByRule: 'matched rule #', trBal: 'balancer ',
      trBalNone: 'the balancer has no candidates — traffic goes to the fallback or is dropped',
      trSure: 'Certain: every rule above was checked', trUnsure: 'May differ',
      trUnsureWhy: 'rules higher in the list could not be checked:',
      trPass1: 'pass 1 by domain: no match', trPass2: 'pass 2 by IP ',
      trPassHint: '(IPIfNonMatch: when nothing matches by domain, the core resolves it and checks IP rules)',
      trNeedIpPass: 'IPIfNonMatch strategy: set the domain IP to see the second pass',
      trGeoOff: 'geo databases not downloaded — geosite:/geoip: rules cannot be checked', trGeoDl: 'download geo databases',
      trGeoMissing: 'category missing from the database — the core will reject the config: ',
      trSniffBlind: 'sniffing is off on inbound “{v}”: the core cannot detect the app protocol (protocol rules never fire), and sees the domain only if the client sends it rather than an IP',
      trOrder: 'Rules in order', trOrderHint: 'the core takes the first match and stops',
      trBelow: ' below the match — the core never reaches them', trShow: 'show', trHide: 'hide', trSet: 'set',
      trRoute: 'route',
      trStates: { yes: 'matched', no: 'no match', unknown: 'no data', skipped: 'not reached' },
      trR: {
        domain_hit: 'domain matches “{v}”', domain_miss: 'domain not in the list ({v})', domain_unknown: 'cannot check “{v}”',
        geo_need: 'needs the geo database for “{v}”',
        ip_asis: 'IP rule, but the target is a domain: with domainStrategy AsIs the core never resolves it, the rule does not apply (to check, enter an IP instead of the domain)',
        proto_nosniff: 'sniffing is off on this inbound — the core cannot detect the protocol',
        ip_pass1: 'domain is not resolved on pass 1 — IP rules are checked on pass 2',
        ip_need: 'needs the domain IP', ip_hit: 'address is within “{v}”', ip_miss: 'address is in none of the subnets ({v})',
        ip_unknown: 'cannot check “{v}”', src_need: 'needs the client IP',
        port_bad: 'unreadable port spec: {v}', port_need: 'port not set',
        port_hit: 'port {v} is within “{s}”', port_miss: 'port {v} is not within “{s}”',
        net_hit: '{v} allowed', net_miss: 'only {s}, but we have {v}',
        proto_need: 'needs the app protocol — the core learns it via sniffing', user_need: 'needs the user',
        in_need: 'pick an inbound', exact_hit: '“{v}” is in the list', exact_miss: '“{v}” is not in the list'
      },
      versionsTitle: 'Profile version history', verEmpty: 'no versions yet',
      verLoad: 'To draft', verDiff: 'Compare', verBy: 'by ', verBytes: ' B',
      verLoaded: 'version loaded into the draft — review and save',
      verFail: 'failed to load versions: ',
      save: 'Save to panel', saveBlocked: 'lint errors block saving',
      addRule: '+ Rule', addOut: '+ Outbound', addIn: '+ Inbound', addBal: '+ Balancer',
      searchPh: 'Search: tag, port, domain…', found: 'found: ', notFound: 'nothing found',
      ruleWord: 'RULE', balWord: 'BALANCER', resolver: 'RESOLVER', noConds: 'no conditions',
      formTab: 'Form', jsonTab: 'JSON', apply: 'Apply', delNode: 'Delete',
      up: '↑', down: '↓', badJson: 'invalid JSON: ',
      tag: 'Tag', port: 'Port', protocol: 'Protocol', network: 'network',
      domains: 'Domains (one per line)', ips: 'IP/CIDR (one per line)', protocols: 'protocol',
      ruleInbounds: 'Inbounds (empty = all)', target: 'Target',
      selector: 'Selector (tag prefixes, one per line)', strategy: 'Strategy', fallback: 'fallbackTag',
      sniffing: 'Sniffing', destOverride: 'destOverride',
      confirmDel: 'Remove this node from the config?', confirmReset: 'Discard the draft and return to the panel version?',
      diffTitle: 'Changes before saving', diffNone: 'no differences',
      diffWarn: 'The panel pushes the config to this profile’s nodes right after saving.',
      confirm: 'Save', cancel: 'Cancel',
      conflictTitle: 'Version conflict', conflictBody: 'The profile changed in the panel while you were editing. Overwriting will discard those changes.',
      conflictLoad: 'Load panel version', conflictForce: 'Overwrite',
      savedOk: 'saved, version recorded', saveFail: 'save failed: ',
      none: '— none —'
    }
  };
  function lang() {
    var v = '';
    try { v = (localStorage.getItem('i18nextLng') || '').toLowerCase(); } catch (e) { v = ''; }
    if (!v) v = (navigator.language || 'ru').toLowerCase();
    return v.indexOf('en') === 0 ? 'en' : 'ru';
  }
  function t() { return L[lang()]; }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function ser(cfg) { return JSON.stringify(cfg, null, 2); }

  /* ---------- доменная логика ---------- */

  function balCandidates(bal, outbounds) {
    var sel = bal.selector || [];
    return outbounds.filter(function (o) {
      return sel.some(function (p) { return String(o.tag || '').indexOf(p) === 0; });
    });
  }
  function ruleChips(r) {
    var chips = [];
    if (r.domain && r.domain.length) chips.push('domain:' + r.domain.length);
    if (r.ip && r.ip.length) chips.push('ip:' + r.ip.length);
    if (r.port != null) chips.push('port:' + r.port);
    if (r.sourcePort != null) chips.push('srcPort:' + r.sourcePort);
    if (r.network) chips.push(r.network);
    if (r.protocol && r.protocol.length) chips.push(r.protocol.join('/'));
    if (r.user && r.user.length) chips.push('user:' + r.user.length);
    if (r.source && r.source.length) chips.push('src:' + r.source.length);
    return chips;
  }
  function sniffingOn(inb) { return !!(inb.sniffing && inb.sniffing.enabled); }

  function buildGraph(cfg) {
    cfg = cfg || {};
    var inbounds = cfg.inbounds || [];
    var outbounds = cfg.outbounds || [];
    var routing = cfg.routing || {};
    var rules = routing.rules || [];
    var balancers = routing.balancers || [];
    var edges = [];
    var inTags = inbounds.map(function (i) { return i.tag; });
    rules.forEach(function (r, i) {
      var srcTags = (r.inboundTag && r.inboundTag.length) ? r.inboundTag : inTags;
      srcTags.forEach(function (tag) {
        if (inTags.indexOf(tag) >= 0) edges.push({ from: 'in:' + tag, to: 'rule:' + i });
      });
      if (r.outboundTag) edges.push({ from: 'rule:' + i, to: 'out:' + r.outboundTag });
      if (r.balancerTag && !r.outboundTag) edges.push({ from: 'rule:' + i, to: 'bal:' + r.balancerTag });
    });
    balancers.forEach(function (b) {
      balCandidates(b, outbounds).forEach(function (o) {
        edges.push({ from: 'bal:' + b.tag, to: 'out:' + o.tag });
      });
      if (b.fallbackTag) edges.push({ from: 'bal:' + b.tag, to: 'out:' + b.fallbackTag, dashed: true });
    });
    return { inbounds: inbounds, outbounds: outbounds, rules: rules, balancers: balancers,
             dns: cfg.dns || null, edges: edges };
  }

  /* ---------- совместимость транспорта (порт compat.ts) ---------- */

  var ALL_NETWORKS = ['tcp', 'ws', 'grpc', 'httpupgrade', 'xhttp', 'hysteria'];
  var REALITY_NETWORKS = ['tcp', 'xhttp', 'grpc'];
  var BALANCER_STRATEGIES = ['random', 'roundRobin', 'leastPing', 'leastLoad'];
  var SS2022_KEY_BYTES = {
    '2022-blake3-aes-128-gcm': 16,
    '2022-blake3-aes-256-gcm': 32,
    '2022-blake3-chacha20-poly1305': 32
  };
  var DOMAIN_PREFIXES = ['domain:', 'full:', 'regexp:', 'geosite:', 'keyword:', 'ext:'];

  function normalizeNetwork(network) {
    var n = (network === undefined || network === null) ? 'tcp' : network;
    return n === 'raw' ? 'tcp' : n;
  }
  // method приоритетнее network (Xray 26.7.28, PR #6426) — единственная точка чтения транспорта
  function streamNetwork(stream) {
    if (!stream) return undefined;
    return stream.method !== undefined && stream.method !== null ? stream.method : stream.network;
  }
  function allowedNetworks(security) {
    return security === 'reality' ? REALITY_NETWORKS.slice() : ALL_NETWORKS.slice();
  }
  function allowedSecurities(network) {
    var n = normalizeNetwork(network);
    if (n === 'hysteria') return ['tls'];
    if (REALITY_NETWORKS.indexOf(n) >= 0) return ['none', 'tls', 'reality'];
    return ['none', 'tls'];
  }
  function securityNetworkIssue(security, network) {
    var n = normalizeNetwork(network);
    var sec = (security === undefined || security === null) ? 'none' : security;
    if (sec === 'reality' && REALITY_NETWORKS.indexOf(n) < 0) {
      return 'Reality несовместим с транспортом «' + n + '» — допустимы только raw (tcp), xhttp и grpc';
    }
    if (n === 'hysteria' && sec !== 'tls') {
      return 'Транспорт hysteria требует security «tls» с настоящим сертификатом';
    }
    return null;
  }
  function flowNetworkIssue(flow, network) {
    if (!flow || String(flow).indexOf('xtls-rprx-vision') !== 0) return null;
    if (normalizeNetwork(network) !== 'tcp') {
      return 'Flow «' + flow + '» работает только поверх raw (tcp) — уберите flow или смените транспорт';
    }
    return null;
  }
  function hysteriaCertificateIssue(network, security, tlsSettings) {
    if (normalizeNetwork(network) !== 'hysteria') return null;
    if (((security === undefined || security === null) ? 'none' : security) !== 'tls') return null;
    var certs = (tlsSettings && tlsSettings.certificates) || [];
    if (!certs.length) return 'Для hysteria нужен настоящий TLS-сертификат — добавьте certificates в tlsSettings';
    return null;
  }

  function keywordEntries(items) {
    return (items || []).filter(function (s) {
      return !DOMAIN_PREFIXES.some(function (p) { return String(s).indexOf(p) === 0; });
    });
  }
  // Формат порта: 443 | 1000-2000 | список через запятую. Возвращает первую ошибку.
  function portSpecError(value) {
    if (value === undefined || value === null) return null;
    var parts = String(value).split(',').map(function (s) { return s.trim(); });
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i];
      if (part === '') return 'Пустой элемент в списке портов';
      var m = part.match(/^(\d{1,5})(?:-(\d{1,5}))?$/);
      if (!m) return 'Некорректный формат «' + part + '» — ожидается 443, 1000-2000 или их список через запятую';
      var lo = Number(m[1]), hi = m[2] === undefined ? lo : Number(m[2]);
      if (lo < 1 || hi > 65535) return 'Порт вне диапазона 1–65535: «' + part + '»';
      if (lo > hi) return 'Начало диапазона больше конца: «' + part + '»';
    }
    return null;
  }
  function outboundTagsOf(cfg) {
    return (cfg.outbounds || []).map(function (o) { return o.tag; })
      .filter(function (t) { return typeof t === 'string'; });
  }
  // selector матчит теги ПО ПРЕФИКСУ; пустой selector = ноль кандидатов
  function balancerCandidates(cfg, bal) {
    var prefixes = bal.selector || [];
    if (!prefixes.length) return [];
    return outboundTagsOf(cfg).filter(function (tag) {
      return prefixes.some(function (p) { return tag.indexOf(p) === 0; });
    });
  }
  function subjectCovers(subjectSelector, tag) {
    return (subjectSelector || []).some(function (p) { return tag.indexOf(p) === 0; });
  }
  function base64Bytes(v) {
    try { return atob(v).length; } catch (e) { return null; }
  }
  function isPrivateAddress(address) {
    var host = String(address || '').trim().toLowerCase();
    if (!host) return false;
    if (host[0] === '[' && host[host.length - 1] === ']') host = host.slice(1, -1);
    if (host[host.length - 1] === '.') host = host.slice(0, -1);
    if (host === 'localhost') return true;
    var p = host.split('.');
    if (p.length === 4 && p.every(function (x) { return /^\d{1,3}$/.test(x) && +x <= 255; })) {
      var a = +p[0], b = +p[1];
      if (a === 0 || a === 10 || a === 127) return true;
      if (a === 169 && b === 254) return true;
      if (a === 172 && b >= 16 && b <= 31) return true;
      if (a === 192 && b === 168) return true;
      if (a === 100 && b >= 64 && b <= 127) return true;
      return false;
    }
    if (host.indexOf(':') >= 0) {
      if (host === '::1' || host === '::') return true;
      return /^f[cd]/.test(host) || /^fe[89ab]/.test(host);
    }
    return ['.local', '.lan', '.internal', '.home', '.home.arpa'].some(function (s) {
      return host.length > s.length && host.slice(-s.length) === s;
    });
  }

  /* ---------- линтер целостности (порт analyzeIntegrity) ----------
     Уровни ровно два: error блокирует сохранение, warning — нет. Порядок
     проверок сохранён как в оригинале: он определяет порядок в списке. */

  function lint(cfg) {
    cfg = cfg || {};
    var issues = [];
    // node — id узла графа для бейджа/навигации, parts — путь в JSON (как в оригинале)
    function add(level, node, msg) { issues.push({ level: level, node: node, msg: msg }); }

    var inbounds = cfg.inbounds || [];
    var outbounds = cfg.outbounds || [];
    var routing = cfg.routing || {};
    var rules = routing.rules || [];
    var balancers = routing.balancers || [];
    var inboundTags = {}, outboundTags = {}, balancerTags = {};
    inbounds.forEach(function (x) { if (x.tag) inboundTags[x.tag] = true; });
    outbounds.forEach(function (x) { if (x.tag) outboundTags[x.tag] = true; });
    balancers.forEach(function (b) { if (b.tag) balancerTags[b.tag] = true; });

    // A. корень
    if (!outbounds.length) {
      add('error', null, 'Панель Remnawave 3.x не примет конфиг без outbounds — добавьте хотя бы один выход');
    }

    // B. дубликаты тегов (первое вхождение не помечается)
    var seenTags = {};
    inbounds.forEach(function (inb) {
      var k = 'inbound:' + inb.tag;
      if (seenTags[k]) add('warn', 'in:' + inb.tag, 'Дубликат тега inbound «' + inb.tag + '»');
      seenTags[k] = true;
    });
    outbounds.forEach(function (out) {
      var k = 'outbound:' + out.tag;
      if (seenTags[k]) add('warn', 'out:' + out.tag, 'Дубликат тега outbound «' + out.tag + '»');
      seenTags[k] = true;
    });

    // C. занятые порты inbound (владелец — первый)
    var seenPorts = {};
    inbounds.forEach(function (inb) {
      if (inb.port === undefined || inb.port === null) return;
      var key = String(inb.port);
      if (seenPorts[key]) add('warn', 'in:' + inb.tag, 'Порт ' + key + ' уже занят inbound «' + seenPorts[key] + '»');
      else seenPorts[key] = inb.tag;
    });

    // D. правила
    rules.forEach(function (rule, i) {
      var node = 'rule:' + i;
      if (rule.outboundTag && !outboundTags[rule.outboundTag]) {
        add('warn', node, 'Правило ссылается на несуществующий outbound «' + rule.outboundTag + '»');
      }
      (rule.inboundTag || []).forEach(function (tag) {
        if (!inboundTags[tag]) add('warn', node, 'Правило ссылается на несуществующий inbound «' + tag + '»');
      });
      if (rule.balancerTag && !balancerTags[rule.balancerTag]) {
        add('warn', node, 'Правило ссылается на несуществующий балансер «' + rule.balancerTag + '»');
      }
      if (rule.balancerTag && rule.outboundTag) {
        add('warn', node, 'У правила заданы и outboundTag «' + rule.outboundTag + '», и балансер «' +
          rule.balancerTag + '» — ядро возьмёт outboundTag, балансер не сработает');
      }
      var kw = keywordEntries(rule.domain);
      if (kw.length) add('warn', node, 'Домены без префикса матчатся как подстрока (keyword): ' + kw.join(', '));
      var pe = portSpecError(rule.port);
      if (pe) add('error', node, pe);
      var spe = portSpecError(rule.sourcePort);
      if (spe) add('error', node, spe);
    });

    // E. балансеры
    var seenBal = {};
    balancers.forEach(function (bal, i) {
      var node = 'bal:' + bal.tag;
      if (seenBal[bal.tag]) add('error', node, 'Дубликат тега балансера «' + bal.tag + '»');
      seenBal[bal.tag] = true;
      var candidates = balancerCandidates(cfg, bal);
      if (!candidates.length) {
        add('error', node, 'Селектор не совпал ни с одним outbound — балансеру не из чего выбирать');
      }
      if (bal.fallbackTag !== undefined && !outboundTags[bal.fallbackTag]) {
        add('warn', node, 'Запасной выход «' + bal.fallbackTag + '» не найден среди outbound\'ов');
      }
      var type = (bal.strategy || {}).type;
      if (type && BALANCER_STRATEGIES.indexOf(type) < 0) {
        add('warn', node, 'Неизвестная стратегия «' + type + '»; ядро знает: ' + BALANCER_STRATEGIES.join(', '));
      }
      if (type === 'leastPing' || type === 'leastLoad') {
        var kindKey = type === 'leastPing' ? 'observatory' : 'burstObservatory';
        var section = cfg[kindKey];
        if (section === undefined) {
          // error, а не warning: без секции ядро не стартует («not all dependencies are resolved»)
          add('error', node, 'Стратегия ' + type + ' измеряет выходы через ' + kindKey +
            ' — без этой секции ядро не запустится');
        } else {
          var missed = candidates.filter(function (tag) { return !subjectCovers(section.subjectSelector, tag); });
          if (missed.length) {
            add('warn', node, 'Обсерватория не покрывает ' + missed.join(', ') + ' — ядро не будет их мерить');
          }
        }
      }
    });

    // F. inbounds
    inbounds.forEach(function (inb) {
      var node = 'in:' + inb.tag;
      var stream = inb.streamSettings;
      if (stream) {
        var si = securityNetworkIssue(stream.security, streamNetwork(stream));
        if (si) add('error', node, si);
        var hi = hysteriaCertificateIssue(streamNetwork(stream), stream.security, stream.tlsSettings);
        if (hi) add('error', node, hi);
        var sec = (stream.security === undefined || stream.security === null) ? 'none' : stream.security;
        if (sec === 'reality' && stream.realitySettings !== undefined &&
            stream.realitySettings.minClientVer === undefined) {
          add('warn', node, 'Ядро 26.7.11+ по умолчанию требует клиента 26.3.27 и новее — Mihomo, Sing-Box ' +
            'и старые Xray не подключатся. Задайте minClientVer «0.0.0», если они нужны');
        }
      }
      if (inb.protocol === 'vless') {
        // flow у панели плоский (применяется ко всем клиентам), а не в clients[]
        var fi = flowNetworkIssue((inb.settings || {}).flow, streamNetwork(stream));
        if (fi) add('error', node, fi);
      }
      if (inb.protocol === 'shadowsocks') {
        var ss = inb.settings || {};
        var expected = SS2022_KEY_BYTES[ss.method];
        if (expected !== undefined && typeof ss.password === 'string' && base64Bytes(ss.password) !== expected) {
          add('error', node, 'Метод ' + ss.method + ' требует ключ ровно ' + expected +
            ' байт в base64 — панель отклонит конфиг с другим');
        }
      }
    });

    // G. outbounds
    outbounds.forEach(function (out) {
      var node = 'out:' + out.tag;
      var stream = out.streamSettings;
      if (stream) {
        var si = securityNetworkIssue(stream.security, streamNetwork(stream));
        if (si) add('error', node, si);
        var dialer = (stream.sockopt || {}).dialerProxy;
        if (dialer !== undefined && dialer !== '' && !outboundTags[dialer]) {
          add('warn', node, 'dialerProxy ссылается на несуществующий outbound «' + dialer + '»');
        }
      }
      var flat = out.settings || {};
      var address = flat.address;
      var secured = ((stream || {}).security || 'none') !== 'none';
      var encrypted = out.protocol === 'vless' && (flat.encryption || 'none') !== 'none';
      if (typeof address === 'string' && address !== '' && !secured && !encrypted && !isPrivateAddress(address)) {
        if (out.protocol === 'vless') {
          add('error', node, 'Ядро 26.7.28+ не соберёт VLESS без TLS/Reality и без encryption на публичный ' +
            'адрес — включите security или задайте encryption');
        } else if (out.protocol === 'trojan') {
          add('error', node, 'Ядро 26.7.28+ не соберёт Trojan без TLS на публичный адрес — включите security');
        }
      }
      if (out.protocol === 'vless') {
        ((flat.vnext) || []).forEach(function (server) {
          ((server || {}).users || []).forEach(function (user) {
            var fi = flowNetworkIssue(user.flow, streamNetwork(stream));
            if (fi) add('error', node, fi);
          });
        });
      }
    });

    // H. sniffing против доменных/протокольных правил
    var blindTags = inbounds.filter(function (inb) {
      var s = inb.sniffing;
      return !s || s.enabled !== true || !((s.destOverride || []).length);
    }).map(function (inb) { return inb.tag; });

    if (blindTags.length) {
      rules.forEach(function (rule, i) {
        var node = 'rule:' + i;
        var scope = (rule.inboundTag && rule.inboundTag.length) ? rule.inboundTag : Object.keys(inboundTags);
        var blind = scope.filter(function (tag) { return blindTags.indexOf(tag) >= 0; });
        if (!blind.length) return;
        var list = blind.map(function (t) { return '«' + t + '»'; }).join(', ');
        if (rule.domain && rule.domain.length) {
          add('warn', node, 'Правило матчит по домену, но на ' + list + ' выключен sniffing — ядро не увидит домен');
        }
        if (rule.protocol && rule.protocol.length) {
          add('warn', node, 'Правило матчит по протоколу, но на ' + list +
            ' выключен sniffing — ядро не определит протокол');
        }
      });
    }

    return issues;
  }

  /* ---------- построчный дифф (LCS) ---------- */

  function lineDiff(aText, bText) {
    var a = aText.split('\n'), b = bText.split('\n');
    var n = a.length, m = b.length;
    var dp = [];
    for (var i = n; i >= 0; i--) {
      dp[i] = [];
      for (var j = m; j >= 0; j--) {
        if (i === n || j === m) dp[i][j] = 0;
        else if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
        else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    var out = [], x = 0, y = 0;
    while (x < n && y < m) {
      if (a[x] === b[y]) { out.push([' ', a[x]]); x++; y++; }
      else if (dp[x + 1][y] >= dp[x][y + 1]) { out.push(['-', a[x]]); x++; }
      else { out.push(['+', b[y]]); y++; }
    }
    while (x < n) { out.push(['-', a[x]]); x++; }
    while (y < m) { out.push(['+', b[y]]); y++; }
    return out;
  }
  // Сжимаем контекст: вокруг изменений по 2 строки, остальное — «⋯ N строк»
  function diffHtml(aText, bText) {
    var d = lineDiff(aText, bText);
    var changed = d.some(function (r) { return r[0] !== ' '; });
    if (!changed) return null;
    var keep = [];
    d.forEach(function (r, i) {
      if (r[0] !== ' ') for (var k = Math.max(0, i - 2); k <= Math.min(d.length - 1, i + 2); k++) keep[k] = true;
    });
    var html = '', skip = 0;
    function flushSkip() {
      if (skip > 0) { html += '<div class="xed-dskip">⋯ ' + skip + '</div>'; skip = 0; }
    }
    d.forEach(function (r, i) {
      if (!keep[i]) { skip++; return; }
      flushSkip();
      var cls = r[0] === '+' ? 'add' : r[0] === '-' ? 'del' : 'ctx';
      html += '<div class="xed-dline ' + cls + '">' + esc(r[0] + ' ' + r[1]) + '</div>';
    });
    flushSkip();
    return html;
  }

  /* ---------- иконки и геометрия ---------- */

  var ICONS = {
    inbound: '<path d=\"M12 3v12\"/><path d=\"M7 10l5 5 5-5\"/><rect x=\"3\" y=\"19\" width=\"18\" height=\"2\" rx=\"1\"/>',
    rule: '<path d=\"M3 6h18\"/><path d=\"M7 12h10\"/><path d=\"M10 18h4\"/>',
    balancer: '<circle cx=\"12\" cy=\"5\" r=\"2\"/><circle cx=\"5\" cy=\"19\" r=\"2\"/><circle cx=\"19\" cy=\"19\" r=\"2\"/><path d=\"M12 7v5\"/><path d=\"M12 12L6 17\"/><path d=\"M12 12l6 5\"/>',
    outbound: '<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M2 12h20\"/><path d=\"M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z\"/>',
    block: '<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M4.93 4.93l14.14 14.14\"/>',
    warp: '<path d=\"M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z\"/>',
    dns: '<rect x=\"3\" y=\"4\" width=\"18\" height=\"6\" rx=\"2\"/><rect x=\"3\" y=\"14\" width=\"18\" height=\"6\" rx=\"2\"/><path d=\"M7 7h.01\"/><path d=\"M7 17h.01\"/>'
  };
  function ico(kind, x, y) {
    var p = ICONS[kind];
    return p ? '<g class="xed-ico" transform="translate(' + x + ',' + y + ') scale(0.7)">' + p + '</g>' : '';
  }
  function outIcon(o) {
    var pr = o.protocol || '';
    if (pr === 'blackhole') return 'block';
    if (pr === 'wireguard') return 'warp';
    return 'outbound';
  }

  // Геометрия колонок. Карточки крупнее, чем в первой версии: в них теперь
  // строка протокола, тег моноширинным и ряд чипов-условий.
  var GEO = {
    inX: 40, inW: 300, ruleX: 560, ruleW: 320, balX: 960, balW: 260, outX: 1320, outW: 280,
    top: 64, inH: 92, inStep: 124, ruleH: 84, ruleStep: 112, balH: 84, balStep: 112, outH: 84, outStep: 112,
    W: 1680
  };
  function edgePath(x1, y1, x2, y2) {
    var mx = (x1 + x2) / 2;
    return 'M ' + x1 + ' ' + y1 + ' C ' + mx + ' ' + y1 + ', ' + mx + ' ' + y2 + ', ' + x2 + ' ' + y2;
  }

  // Чипы-условия правила: человеческая сводка того, по чему оно матчит.
  function ruleChipList(r, tr) {
    var chips = [];
    chips.push((r.inboundTag && r.inboundTag.length) ? r.inboundTag.join(', ') : tr.allInbounds);
    if (r.domain && r.domain.length) chips.push('домены: ' + r.domain.length);
    if (r.ip && r.ip.length) chips.push('IP: ' + r.ip.length);
    if (r.port !== undefined && r.port !== null && r.port !== '') chips.push('порт: ' + r.port);
    if (r.sourcePort) chips.push('srcPort: ' + r.sourcePort);
    if (r.network) chips.push(r.network);
    if (r.protocol && r.protocol.length) chips.push('протоколы: ' + r.protocol.join(','));
    if (r.user && r.user.length) chips.push('user: ' + r.user.length);
    if (r.source && r.source.length) chips.push('source: ' + r.source.length);
    if (chips.length === 1 && !r.domain && !r.ip && r.port === undefined && !r.network && !r.protocol) {
      return [tr.noConds];
    }
    return chips;
  }

  function renderSvg(g, issues, selected, tr) {
    var G = GEO;
    var pos = {};
    g.inbounds.forEach(function (n, i) {
      pos['in:' + n.tag] = { x: G.inX, y: G.top + i * G.inStep, w: G.inW, h: G.inH };
    });
    var dnsY = G.top + g.inbounds.length * G.inStep + 8;
    if (g.dns) pos.dns = { x: G.inX, y: dnsY, w: G.inW, h: 72 };
    g.rules.forEach(function (r, i) {
      pos['rule:' + i] = { x: G.ruleX, y: G.top + i * G.ruleStep, w: G.ruleW, h: G.ruleH };
    });
    g.balancers.forEach(function (b, i) {
      pos['bal:' + b.tag] = { x: G.balX, y: G.top + i * G.balStep, w: G.balW, h: G.balH };
    });
    g.outbounds.forEach(function (o, i) {
      pos['out:' + o.tag] = { x: G.outX, y: G.top + i * G.outStep, w: G.outW, h: G.outH };
    });

    // Пользовательские сдвиги карточек (перетаскивание) — чтобы разводить линии.
    var ov = state.pos || {};
    Object.keys(pos).forEach(function (k) {
      if (ov[k]) { pos[k].x += ov[k].dx || 0; pos[k].y += ov[k].dy || 0; }
    });

    state.lastPos = pos;                        // для попадания курсором при протяжке связи
    var H = G.top + 80;
    Object.keys(pos).forEach(function (k) { H = Math.max(H, pos[k].y + pos[k].h + 60); });

    var byNode = {};
    issues.forEach(function (it) {
      if (!it.node) return;
      var b = byNode[it.node] || { error: 0, warn: 0, info: 0 };
      b[it.level] = (b[it.level] || 0) + 1;
      byNode[it.node] = b;
    });

    var s = '<svg viewBox="0 0 ' + G.W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg" ' +
            'style="display:block;width:100%;height:auto">';
    // сетка-подложка, как в референсе
    s += '<defs><pattern id="xed-grid" width="26" height="26" patternUnits="userSpaceOnUse">' +
         '<circle cx="1" cy="1" r="1" class="xed-griddot"/></pattern></defs>';
    s += '<rect x="0" y="0" width="' + G.W + '" height="' + H + '" fill="url(#xed-grid)"/>';
    var vw = state.view || { k: 1, tx: 0, ty: 0 };
    s += '<g transform="translate(' + vw.tx + ',' + vw.ty + ') scale(' + vw.k + ')">';

    s += '<text class="xed-cap" x="' + G.inX + '" y="34">' + tr.capIn + '</text>';
    s += '<text class="xed-cap" x="' + G.ruleX + '" y="34">' + tr.capRules + '</text>';
    if (g.balancers.length) s += '<text class="xed-cap" x="' + G.balX + '" y="34">' + tr.capBal + '</text>';
    s += '<text class="xed-cap" x="' + G.outX + '" y="34">' + tr.capOut + '</text>';

    g.edges.forEach(function (e) {
      var a = pos[e.from], b = pos[e.to];
      if (!a || !b) return;
      var active = selected && (e.from === selected || e.to === selected);
      s += '<path class="xed-edge' + (active ? ' active' : '') + (e.dashed ? ' dashed' : '') +
        '" d="' + edgePath(a.x + a.w, a.y + a.h / 2, b.x, b.y + b.h / 2) + '"/>';
    });

    // Карточка: цветная полоса слева, строка вида (протокол/род), тег
    // моноширинным, ряд чипов. kindCls красит полосу и подпись вида.
    function card(id, p, kindCls, kindLabel, title, chips, opts) {
      opts = opts || {};
      var sel = id === selected ? ' selected' : '';
      var x = p.x, y = p.y, w = p.w, h = p.h;
      var tcls = connTargetCls(id);
      var out = '<g data-node="' + esc(id) + '" class="xed-node' + (tcls ? ' t-' + tcls : '') + '">';
      out += '<rect class="xed-box' + sel + '" x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="10"/>';
      out += '<rect class="xed-accent ' + kindCls + '" x="' + x + '" y="' + (y + 10) + '" width="3" height="' + (h - 20) + '" rx="2"/>';
      out += '<text class="xed-kind ' + kindCls + '" x="' + (x + 18) + '" y="' + (y + 24) + '">' + esc(kindLabel) + '</text>';
      if (opts.badgeText) {
        out += '<rect class="xed-tagbadge" x="' + (x + w - 82) + '" y="' + (y + 12) + '" width="70" height="18" rx="4"/>';
        out += '<text class="xed-tagbadge-t" x="' + (x + w - 47) + '" y="' + (y + 22) + '" text-anchor="middle">' + esc(opts.badgeText) + '</text>';
      }
      if (opts.number) {
        out += '<text class="xed-num" x="' + (x + w - 18) + '" y="' + (y + 40) + '" text-anchor="end">' + opts.number + '</text>';
      }
      out += '<text class="xed-title" x="' + (x + 18) + '" y="' + (y + 48) + '">' + esc(title) + '</text>';
      // чипы в один ряд, с обрезкой по ширине карточки
      // низкие карточки (резолвер, h=72): не даём ряду чипов наехать на заголовок
      var cx = x + 18, cy = Math.max(y + h - 22, y + 62), budget = w - 34;
      (chips || []).forEach(function (c) {
        var text = String(c);
        var cw = Math.min(text.length * 7.0 + 14, 150);
        if (budget - cw < 0) return;
        budget -= cw + 6;
        out += '<rect class="xed-chip" x="' + cx + '" y="' + (cy - 12) + '" width="' + cw + '" height="18" rx="4"/>';
        out += '<text class="xed-chip-t" x="' + (cx + cw / 2) + '" y="' + (cy - 2.5) + '" text-anchor="middle">' + esc(text) + '</text>';
        cx += cw + 6;
      });
      // точки-коннекторы на рёбрах карточки
      // точки-порты: из правой тянется связь, левая — приёмник
      if (opts.inDot !== false) {
        out += '<circle class="xed-dot' + (connTargetCls(id) === 'ok' ? ' live' : '') + '" cx="' + x + '" cy="' + (y + h / 2) + '" r="3"/>';
      }
      if (opts.outDot !== false) {
        out += '<circle class="xed-dot' + (canConnectFrom(id) ? ' port' : '') + '" cx="' + (x + w) + '" cy="' + (y + h / 2) + '" r="3"/>';
        if (canConnectFrom(id)) {
          out += '<circle class="xed-dothit" data-port="' + esc(id) + '" cx="' + (x + w) + '" cy="' + (y + h / 2) + '" r="10"/>';
        }
      }
      if (opts.trace) {
        var tl = opts.trace === 'winner' ? t().trRoute : trStateLabel(opts.trace);
        var tw = tl.length * 6.4 + 14;
        out += '<rect class="xed-trtag ' + opts.trace + '" x="' + (x + w - tw - 10) + '" y="' + (y + h - 20) + '" width="' + tw + '" height="16" rx="4"/>';
        out += '<text class="xed-trtag-t" x="' + (x + w - tw / 2 - 10) + '" y="' + (y + h - 8.5) + '" text-anchor="middle">' + esc(tl) + '</text>';
      }
      var b = byNode[id];
      if (b) {
        var lvl = b.error ? 'error' : b.warn ? 'warn' : 'info';
        var n = b.error || b.warn || b.info;
        out += '<circle class="xed-badge ' + lvl + '" cx="' + (x + w - 4) + '" cy="' + (y + 4) + '" r="9"/>';
        out += '<text class="xed-badge-t" x="' + (x + w - 4) + '" y="' + (y + 4) + '" text-anchor="middle" dominant-baseline="central">' + n + '</text>';
      }
      return out + '</g>';
    }

    g.inbounds.forEach(function (n) {
      var p = pos['in:' + n.tag];
      var ss = n.streamSettings || {};
      var net = streamNetwork(ss) || 'tcp';
      var chips = [':' + (n.port !== undefined && n.port !== null ? n.port : '—'), normalizeNetwork(net), (ss.security || 'none')];
      if (!sniffingOn(n)) chips.push(tr.sniffOff);
      s += card('in:' + n.tag, p, 'k-in', String(n.protocol || '?').toUpperCase(), n.tag || '—', chips, { inDot: false });
    });
    if (g.dns) {
      s += card('dns', pos.dns, 'k-dns', tr.resolver, 'DNS', [tr.dnsServers + ((g.dns.servers || []).length)], { inDot: false });
    }
    g.rules.forEach(function (r, i) {
      var p = pos['rule:' + i];
      var tst = traceStateOf(state.traceRes, i);
      s += card('rule:' + i, p, 'k-rule', tr.ruleWord, r.outboundTag ? '→ ' + r.outboundTag
        : r.balancerTag ? '→ ⚖ ' + r.balancerTag : tr.noTarget, ruleChipList(r, tr),
        { number: i + 1, trace: tst });
    });
    g.balancers.forEach(function (b) {
      var p = pos['bal:' + b.tag];
      var strat = ((b.strategy || {}).type) || 'random';
      s += card('bal:' + b.tag, p, 'k-bal', tr.balWord, b.tag,
        [strat, tr.candidates + balancerCandidates({ outbounds: g.outbounds }, b).length]);
    });
    g.outbounds.forEach(function (o, i) {
      var p = pos['out:' + o.tag];
      var chips = [];
      var addr = (o.settings || {}).address;
      if (addr) chips.push(String(addr));
      var oss = o.streamSettings || {};
      if (oss.security) chips.push(oss.security);
      if (streamNetwork(oss)) chips.push(normalizeNetwork(streamNetwork(oss)));
      s += card('out:' + o.tag, p, 'k-out', String(o.protocol || '?').toUpperCase(), o.tag || '—', chips,
        { outDot: false, badgeText: i === 0 ? tr.defaultOut : null });
    });

    // тянущаяся связь поверх всего: к допустимой цели притягивается, иначе обрывается у курсора
    var cn = state.conn;
    if (cn && pos[cn.from]) {
      var pf = pos[cn.from];
      var sx = pf.x + pf.w, sy = pf.y + pf.h / 2;
      var ex = cn.x, ey = cn.y, ok = false;
      if (cn.to && pos[cn.to]) { var pt2 = pos[cn.to]; ex = pt2.x; ey = pt2.y + pt2.h / 2; ok = true; }
      s += '<path class="xed-conn' + (ok ? ' ok' : (cn.over ? ' bad' : '')) + '" d="' + edgePath(sx, sy, ex, ey) + '"/>';
      s += '<circle class="xed-conn-end' + (ok ? ' ok' : '') + '" cx="' + ex + '" cy="' + ey + '" r="' + (ok ? 5 : 3) + '"/>';
    }
    return s + '</g></svg>';
  }
  /* ---------- стили ---------- */

  function ensureStyle() {
    if (document.getElementById('xed-style')) return;
    var st = document.createElement('style');
    st.id = 'xed-style';
    st.textContent =
/*__CODECSS__*/
      '.xed-root{position:relative;font:400 14px/1.5 ui-sans-serif,system-ui,sans-serif;color:hsl(var(--foreground, 220 9% 84%))}' +
      '.xed-h1{font:500 30px/1.2 ui-sans-serif,system-ui,sans-serif;margin:0 0 4px}' +
      '.xed-sub{color:hsl(var(--muted-foreground, 220 9% 56%));font-size:14px;margin:0 0 18px}' +
      '.xed-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}' +
      // селекторы стилизуем во всём редакторе (в т.ч. в диалогах): у админки
      // свой тёмный фон, а браузерный дефолт даёт нечитаемый серый текст
      '.xed-root select,.xed-dialog select{background:hsl(var(--muted, 220 14% 16%));color:hsl(var(--foreground, 220 9% 90%));border:1px solid hsl(var(--border, 220 14% 22%));border-radius:8px;padding:7px 10px;font:inherit;max-width:100%;-webkit-appearance:none;appearance:none;background-image:linear-gradient(45deg,transparent 50%,hsl(var(--muted-foreground, 220 9% 62%)) 50%),linear-gradient(135deg,hsl(var(--muted-foreground, 220 9% 62%)) 50%,transparent 50%);background-position:calc(100% - 16px) center,calc(100% - 11px) center;background-size:5px 5px,5px 5px;background-repeat:no-repeat;padding-right:32px}' +
      '.xed-root select option,.xed-dialog select option{background:hsl(220 20% 12%);color:hsl(220 9% 90%)}' +
      '.xed-dialog label{display:block;font-size:12px;color:hsl(var(--muted-foreground, 220 9% 60%));margin:12px 0 5px}' +
      '.xed-btn{background:hsl(var(--card, 220 20% 10%));color:inherit;border:1px solid hsl(var(--border, 220 14% 18%));border-radius:8px;padding:7px 14px;font:inherit;cursor:pointer}' +
      '.xed-btn:hover{border-color:hsl(var(--primary, 239 84% 67%) / .6)}' +
      '.xed-btn:disabled{opacity:.45;cursor:default}' +
      '.xed-btn.primary{background:hsl(var(--primary, 239 84% 67%) / .18);border-color:hsl(var(--primary, 239 84% 67%) / .6)}' +
      '.xed-btn.danger:hover{border-color:hsl(0 72% 52%)}' +
      '.xed-chip{color:hsl(var(--muted-foreground, 220 9% 56%));font-size:12px}' +
      '.xed-chip.draft{border:1px solid hsl(38 80% 50% / .6);color:hsl(38 80% 60%);border-radius:99px;padding:3px 10px}' +
      '.xed-card{position:relative;background:hsl(var(--card, 220 20% 10%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:14px;padding:14px 16px}' +
      '.xed-cap{fill:hsl(var(--muted-foreground, 220 9% 56%));font:500 10px/1 ui-monospace,Menlo,monospace;letter-spacing:.16em}' +
      '.xed-griddot{fill:hsl(var(--muted-foreground, 220 9% 56%) / .13)}' +
      '.xed-box{fill:hsl(var(--card, 220 20% 10%) / .92);stroke:hsl(var(--border, 220 14% 20%));stroke-width:1}' +
      '.xed-box.selected{stroke:hsl(var(--primary, 239 84% 67%));stroke-width:1.6}' +
      '.xed-node{cursor:grab}.xed-node:hover .xed-box{stroke:hsl(var(--primary, 239 84% 67%) / .55)}' +
      '.xed-node.dragging{cursor:grabbing}' +
      '.xed-accent{stroke:none}' +
      '.xed-accent.k-in{fill:hsl(239 84% 67%)}.xed-accent.k-out{fill:hsl(38 85% 58%)}' +
      '.xed-accent.k-rule{fill:hsl(220 9% 50%)}.xed-accent.k-bal{fill:hsl(280 70% 65%)}.xed-accent.k-dns{fill:hsl(190 70% 55%)}' +
      '.xed-kind{font:600 9.5px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em}' +
      '.xed-kind.k-in{fill:hsl(239 84% 72%)}.xed-kind.k-out{fill:hsl(38 85% 62%)}' +
      '.xed-kind.k-rule{fill:hsl(220 9% 55%)}.xed-kind.k-bal{fill:hsl(280 70% 70%)}.xed-kind.k-dns{fill:hsl(190 70% 60%)}' +
      '.xed-title{fill:hsl(var(--foreground, 220 9% 90%));font:500 15px/1 ui-monospace,Menlo,monospace}' +
      '.xed-num{fill:hsl(var(--muted-foreground, 220 9% 56%) / .5);font:600 22px/1 ui-sans-serif,system-ui,sans-serif}' +
      '.xed-chip{fill:hsl(var(--muted, 220 14% 18%) / .8);stroke:hsl(var(--border, 220 14% 24%));stroke-width:1}' +
      '.xed-chip-t{fill:hsl(var(--muted-foreground, 220 9% 68%));font:400 10.5px/1 ui-monospace,Menlo,monospace}' +
      '.xed-tagbadge{fill:hsl(var(--muted, 220 14% 20%));stroke:none}' +
      '.xed-tagbadge-t{fill:hsl(var(--muted-foreground, 220 9% 62%));font:600 8.5px/1 ui-monospace,Menlo,monospace;letter-spacing:.1em}' +
      '.xed-dot{fill:hsl(var(--muted-foreground, 220 9% 56%) / .85);stroke:none}' +
      '.xed-dot.port{fill:hsl(var(--primary, 239 84% 67%) / .9)}' +
      '.xed-dot.live{fill:hsl(150 60% 50%)}' +
      '.xed-dothit{fill:transparent;cursor:crosshair}' +
      '.xed-dothit:hover{fill:hsl(var(--primary, 239 84% 67%) / .18)}' +
      '.xed-conn{fill:none;stroke:hsl(var(--primary, 239 84% 67%) / .8);stroke-width:2;stroke-dasharray:5 4;pointer-events:none}' +
      '.xed-conn.ok{stroke:hsl(150 60% 50%);stroke-dasharray:none}' +
      '.xed-conn.bad{stroke:hsl(0 70% 55% / .85)}' +
      '.xed-conn-end{fill:hsl(var(--primary, 239 84% 67%) / .8);pointer-events:none}' +
      '.xed-conn-end.ok{fill:hsl(150 60% 50%)}' +
      '.xed-node.t-ok .xed-box{stroke:hsl(150 60% 50%);stroke-width:1.6}' +
      '.xed-node.t-no{opacity:.45}' +
      '.xed-main{display:flex;gap:14px;align-items:flex-start}' +
      '.xed-cwrap{flex:1;min-width:0}' +
      '.xed-edge{fill:none;stroke:hsl(38 60% 55% / .45);stroke-width:1.5}' +
      '.xed-edge.dashed{stroke-dasharray:6 5}' +
      '.xed-edge.active{stroke:hsl(var(--primary, 239 84% 67%) / .95);stroke-width:2.2}' +
      '.xed-badge{stroke:none}.xed-badge.error{fill:hsl(0 72% 45%)}.xed-badge.warn{fill:hsl(38 80% 42%)}.xed-badge.info{fill:hsl(220 9% 40%)}' +
      '.xed-badge-t{fill:#fff;font:600 10px/1 sans-serif}' +
      '.xed-dock{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:12px;padding:10px 12px;background:hsl(var(--card, 220 20% 10%) / .7);border:1px solid hsl(var(--border, 220 14% 18%));border-radius:12px}' +
      '.xed-recgrid{display:flex;gap:14px;align-items:flex-start}' +
      '.xed-reclist{flex:none;width:300px;max-height:66vh;overflow:auto}' +
      '.xed-recbody{flex:1;min-width:0;max-height:66vh;overflow:auto;padding-right:6px}' +
      '.xed-recbody select,.xed-recbody input[type=text],.xed-recbody textarea{width:100%;max-width:720px}' +
      '.xed-planlist li.warn{color:hsl(38 80% 62%)}' +
      '.xed-checkline{display:flex;align-items:center;gap:8px;color:inherit;font-size:13px;margin:0}' +
      '.xed-dialog.xed-dialog-wide{width:min(1500px,95vw);max-width:none}' +
      '.xed-geotabs{margin-bottom:10px}' +
      '.xed-geobrowse{display:flex;gap:12px;align-items:flex-start;margin-top:10px}' +
      '.xed-geocats{flex:none;width:300px;max-height:58vh;overflow:auto;border:1px solid hsl(var(--border, 220 14% 18%));border-radius:10px;padding:4px}' +
      '.xed-geocat{display:flex;justify-content:space-between;gap:8px;padding:5px 8px;border-radius:6px;cursor:pointer;font:12px/1.4 ui-monospace,Menlo,monospace}' +
      '.xed-geocat:hover{background:hsl(var(--muted, 220 14% 16%))}' +
      '.xed-geocat.sel{background:hsl(var(--primary, 239 84% 67%) / .16);outline:1px solid hsl(var(--primary, 239 84% 67%) / .5)}' +
      '.xed-geovals{flex:1;min-width:0;max-height:58vh;overflow:auto}' +
      '.xed-geovals input{width:100%;background:hsl(var(--muted, 220 14% 14%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:8px;padding:6px 10px;font:inherit;color:inherit;margin-bottom:6px}' +
      '.xed-georow{display:flex;gap:10px;align-items:baseline;padding:2px 0}' +
      '.xed-geokind{color:hsl(var(--muted-foreground, 220 9% 48%));font:10px/1 ui-monospace,Menlo,monospace;text-transform:uppercase;min-width:56px}' +
      '.xed-georow code{font:12px/1.5 ui-monospace,Menlo,monospace}' +
      '.xed-token{font:12px/1.6 ui-monospace,Menlo,monospace;background:hsl(var(--muted, 220 14% 16%));padding:4px 10px;border-radius:6px}' +
      '.xed-okline{color:hsl(140 55% 62%);margin:8px 0}' +
      '.xed-checkrow{margin:6px 0;padding:8px 10px;border-radius:8px;background:hsl(var(--muted, 220 14% 14%))}' +
      '.xed-checkrow code{font:12px/1.5 ui-monospace,Menlo,monospace;color:hsl(var(--foreground, 220 9% 86%));white-space:pre-wrap}' +
      '.xed-checkrow.err{border-left:3px solid hsl(0 72% 52%)}.xed-checkrow.warn{border-left:3px solid hsl(38 80% 50%)}' +
      '.xed-grouphd{margin:14px 0 4px;font:600 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.12em;color:hsl(var(--muted-foreground, 220 9% 52%))}' +
      '.xed-recrow{padding:9px 10px;border:1px solid hsl(var(--border, 220 14% 18%));border-radius:10px;margin:8px 0;cursor:pointer}' +
      '.xed-recrow:hover{border-color:hsl(var(--primary, 239 84% 67%) / .6)}' +
      '.xed-recrow.sel{border-color:hsl(var(--primary, 239 84% 67%));background:hsl(var(--primary, 239 84% 67%) / .1)}' +
      '.xed-planlist{margin:4px 0 0;padding-left:18px;font-size:12.5px}.xed-planlist li{margin:2px 0}' +
      '.xed-tabs2{display:inline-flex;gap:2px;border:1px solid hsl(var(--border, 220 14% 18%));border-radius:8px;overflow:hidden}' +
      '.xed-tab2{background:none;border:none;color:hsl(var(--muted-foreground, 220 9% 56%));font:inherit;padding:7px 14px;cursor:pointer}' +
      '.xed-tab2.on{background:hsl(var(--primary, 239 84% 67%) / .18);color:hsl(var(--foreground, 220 9% 88%))}' +
      '.xed-fulljson{width:100%;min-height:60vh;background:hsl(var(--muted, 220 14% 14%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:8px;padding:12px;font:12px/1.55 ui-monospace,Menlo,monospace;color:inherit;resize:vertical}' +
      '.xed-zoom{display:inline-flex;gap:4px;margin-left:auto}' +
      '.xed-hint{color:hsl(var(--muted-foreground, 220 9% 52%));font-size:11.5px;margin-top:4px}' +
      '.xed-tracebar{margin-top:8px}.xed-tracebar label{display:flex;align-items:center;gap:6px;font-size:12px;color:hsl(var(--muted-foreground, 220 9% 56%))}' +
      '.xed-tracebar input{max-width:220px;min-width:120px}.xed-tracebar input.xed-trport{max-width:72px;min-width:56px;flex:0 0 auto}' +
      '.xed-trlbl{font-size:12px;color:hsl(var(--muted-foreground, 220 9% 56%))}.xed-tracebar2{margin-top:6px}' +
      '.xed-btn-sm{padding:4px 9px;font-size:12px}.xed-trflash{outline:2px solid hsl(var(--primary, 239 84% 67%))!important}' +
      '.xed-tracepanel{margin-top:12px;padding:12px 14px;background:hsl(var(--card, 220 20% 10%) / .7);border:1px solid hsl(var(--border, 220 14% 18%));border-radius:12px}' +
      '.xed-tracepanel h3{margin:0 0 8px;font:500 14px/1.2 ui-sans-serif,system-ui,sans-serif}' +
      '.xed-trcard{margin:10px 0 12px;padding:12px 14px;border-radius:12px;border:1px solid hsl(var(--border, 220 14% 18%));background:hsl(var(--card, 220 20% 10%))}' +
      '.xed-trcard.sure{border-color:hsl(140 55% 45% / .45)}.xed-trcard.unsure{border-color:hsl(38 80% 50% / .55)}.xed-trcard.bad{border-color:hsl(0 72% 52% / .55)}' +
      '.xed-trflow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}' +
      '.xed-trtgt{font:600 14px/1.4 ui-monospace,Menlo,monospace}.xed-trarrow{color:hsl(var(--muted-foreground, 220 9% 50%));font-size:16px}.xed-tror{color:hsl(var(--muted-foreground, 220 9% 50%))}' +
      '.xed-trout{font:600 15px/1.4 ui-monospace,Menlo,monospace;color:hsl(var(--primary, 239 84% 74%));border:1px solid hsl(var(--primary, 239 84% 67%) / .5);background:hsl(var(--primary, 239 84% 67%) / .12);border-radius:8px;padding:3px 12px}' +
      '.xed-trhow{margin-top:6px;font-size:12.5px;color:hsl(var(--muted-foreground, 220 9% 60%))}' +
      '.xed-trconf{margin-top:8px;font-size:12.5px;padding:8px 10px;border-radius:8px}' +
      '.xed-trconf.sure{color:hsl(140 55% 64%);background:hsl(140 60% 40% / .1)}.xed-trconf.unsure{color:hsl(38 80% 66%);background:hsl(38 80% 50% / .1)}' +
      '.xed-trconf ul{margin:4px 0 0;padding-left:18px}.xed-trconf li{margin:3px 0}' +
      '.xed-trfix{color:hsl(var(--primary, 239 84% 74%));cursor:pointer;text-decoration:underline dotted;margin-left:4px}' +
      '.xed-trempty{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:13px;color:hsl(var(--muted-foreground, 220 9% 60%))}' +
      '.xed-trhd{display:flex;gap:10px;align-items:baseline;margin:8px 0 4px;font:600 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase;color:hsl(var(--muted-foreground, 220 9% 52%))}' +
      '.xed-trhd span{font:12px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:0;text-transform:none}' +
      '.xed-trerr{color:hsl(0 72% 62%)}' +
      '.xed-metric{border:1px solid hsl(var(--border, 220 14% 22%));border-radius:6px;padding:2px 8px;font:12px/1.4 ui-monospace,Menlo,monospace}' +
      '.xed-metric.accent{border-color:hsl(var(--primary, 239 84% 67%) / .5);color:hsl(var(--primary, 239 84% 72%))}' +
      '.xed-trcaveats{margin:8px 0 0;padding-left:18px}.xed-trcaveats li{color:hsl(38 80% 62%);font-size:12.5px;margin:3px 0}' +
      '.xed-trrules{display:flex;flex-direction:column;gap:3px}' +
      '.xed-trrow{display:grid;grid-template-columns:34px 112px 14px auto 1fr;gap:4px 8px;align-items:center;padding:6px 8px;border-radius:8px;cursor:pointer;font-size:12.5px;border:1px solid transparent}' +
      '.xed-trrow:hover{background:hsl(var(--muted, 220 14% 18%) / .45)}' +
      '.xed-trrow.no{color:hsl(var(--muted-foreground, 220 9% 58%))}.xed-trrow.skipped{opacity:.55}' +
      '.xed-trrow.win{background:hsl(var(--primary, 239 84% 67%) / .1);border-color:hsl(var(--primary, 239 84% 67%) / .35)}' +
      '.xed-trrow.unknown{background:hsl(38 80% 50% / .07)}' +
      '.xed-trchips{display:flex;gap:4px;flex-wrap:wrap}.xed-trchips span{border:1px solid hsl(var(--border, 220 14% 22%));border-radius:5px;padding:1px 6px;font:11px/1.5 ui-monospace,Menlo,monospace;color:hsl(var(--muted-foreground, 220 9% 58%))}' +
      '.xed-trwhy{grid-column:2 / -1;font-size:12px;color:hsl(var(--muted-foreground, 220 9% 58%))}.xed-trwhy:empty{display:none}' +
      '.xed-trrow.unknown .xed-trwhy{color:hsl(38 80% 64%)}.xed-trrow.win .xed-trwhy{color:hsl(140 55% 64%)}' +
      '.xed-trtoggle{cursor:pointer;color:hsl(var(--muted-foreground, 220 9% 56%));font-size:12px;padding:6px 8px}' +
      '.xed-trno{color:hsl(var(--muted-foreground, 220 9% 56%));font:600 12px/1 ui-monospace,Menlo,monospace;min-width:26px}' +
      '.xed-trbadge{border-radius:5px;padding:2px 8px;font-size:11.5px}' +
      '.xed-trbadge.yes{background:hsl(140 60% 40% / .22);color:hsl(140 55% 68%)}' +
      '.xed-trbadge.no{background:hsl(220 9% 40% / .22);color:hsl(220 9% 62%)}' +
      '.xed-trbadge.unknown{background:hsl(38 80% 50% / .18);color:hsl(38 80% 66%)}' +
      '.xed-trbadge.skipped{background:hsl(220 9% 40% / .12);color:hsl(220 9% 52%)}' +
      '.xed-trtag{stroke:none}.xed-trtag.winner{fill:hsl(var(--primary, 239 84% 67%) / .35)}' +
      '.xed-trtag.yes{fill:hsl(140 60% 40% / .3)}.xed-trtag.no{fill:hsl(220 9% 40% / .3)}.xed-trtag.unknown{fill:hsl(38 80% 50% / .28)}.xed-trtag.skipped{fill:hsl(220 9% 40% / .16)}' +
      '.xed-trtag-t{fill:hsl(var(--foreground, 220 9% 88%));font:500 9.5px/1 sans-serif}' +
      '.xed-verrow{display:flex;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid hsl(var(--border, 220 14% 18%) / .5);font-size:13px}' +
      '.xed-verrow span:first-child{min-width:150px}' +
      '.xed-dock input{flex:1;min-width:160px;background:hsl(var(--muted, 220 14% 14%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:8px;padding:6px 10px;font:inherit;color:inherit}' +
      '.xed-insp{flex:none;width:400px;max-width:42%;align-self:stretch;max-height:78vh;overflow:auto;background:hsl(var(--card-2, 220 20% 13%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:12px;padding:14px 16px}' +
      '.xed-insp h3{margin:0 0 8px;font:500 15px/1.3 ui-sans-serif,system-ui,sans-serif;display:flex;align-items:center;gap:8px}' +
      '.xed-insp h3 .xed-x{margin-left:auto}' +
      '.xed-insp pre,.xed-insp textarea{width:100%;background:hsl(var(--muted, 220 14% 14%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:8px;padding:10px 12px;font:12px/1.5 ui-monospace,Menlo,monospace;overflow:auto;white-space:pre;margin:8px 0 0;color:inherit}' +
      '.xed-insp textarea{min-height:220px;resize:vertical}' +
      '.xed-field{margin:10px 0 0}' +
      '.xed-field label{display:block;font-size:12px;color:hsl(var(--muted-foreground, 220 9% 56%));margin-bottom:4px}' +
      '.xed-field input[type=text],.xed-field textarea{width:100%;background:hsl(var(--muted, 220 14% 14%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:8px;padding:7px 10px;font:inherit;color:inherit}' +
      '.xed-field textarea{font:12px/1.5 ui-monospace,Menlo,monospace;min-height:64px;resize:vertical}' +
      '.xed-chips{display:flex;gap:6px;flex-wrap:wrap}' +
      '.xed-chipbtn{border:1px solid hsl(var(--border, 220 14% 18%));border-radius:99px;padding:3px 10px;font-size:12px;cursor:pointer;background:none;color:inherit}' +
      '.xed-chipbtn.on{border-color:hsl(var(--primary, 239 84% 67%));color:hsl(var(--primary, 239 84% 67%))}' +
      '.xed-tabs{display:flex;gap:6px;margin:4px 0 2px}' +
      '.xed-tab{border:none;background:none;color:hsl(var(--muted-foreground, 220 9% 56%));font:inherit;padding:4px 8px;cursor:pointer;border-bottom:2px solid transparent}' +
      '.xed-tab.on{color:inherit;border-bottom-color:hsl(var(--primary, 239 84% 67%))}' +
      '.xed-row{display:flex;gap:8px;margin-top:12px}' +
      '.xed-err{color:hsl(0 72% 60%);font-size:12px;margin-top:6px}' +
      '.xed-tplrecs{display:flex;flex-direction:column;gap:6px;margin:4px 0 10px}' +
      '.xed-tplrec{display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer}' +
      '.xed-curname{font:600 14px/1 ui-monospace,Menlo,monospace;color:hsl(var(--foreground, 210 20% 92%));padding:0 4px}' +
      /* витрина конфигов */
      '.xed-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:10px}' +
      '.xed-pcard{border:1px solid hsl(var(--border, 220 13% 20%));border-radius:12px;padding:12px 14px;' +
        'background:hsl(var(--card, 222 15% 9%));cursor:pointer;transition:border-color .12s,transform .12s}' +
      '.xed-pcard:hover{border-color:hsl(var(--primary, 244 65% 63%));transform:translateY(-1px)}' +
      '.xed-pcard-hd{display:flex;align-items:center;gap:8px;justify-content:space-between;font-size:15px}' +
      '.xed-pcard-in{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:10px 0 12px;min-height:22px}' +
      '.xed-pcard-in code{font:12px/1 ui-monospace,Menlo,monospace;color:hsl(var(--foreground, 210 20% 92%))}' +
      '.xed-pcard-ft{display:flex;justify-content:space-between;gap:8px;padding-top:8px;' +
        'border-top:1px solid hsl(var(--border, 220 13% 20%));font-size:12px;' +
        'color:hsl(var(--muted-foreground, 220 9% 52%))}' +
      '.xed-picksep{margin-top:22px;padding-top:14px;border-top:1px solid hsl(var(--border, 220 13% 20%))}' +
      '.xed-issues{margin-top:14px}' +
      '.xed-issues .hd{font:500 13px/1.2 ui-sans-serif,system-ui,sans-serif;margin-bottom:6px}' +
      '.xed-issue{display:flex;gap:8px;align-items:baseline;padding:3px 0;font-size:13px;cursor:pointer}' +
      '.xed-issue:hover{color:hsl(var(--foreground, 220 9% 90%))}' +
      '.xed-dot{width:8px;height:8px;border-radius:99px;flex:none;position:relative;top:-1px}' +
      '.xed-dot.error{background:hsl(0 72% 52%)}.xed-dot.warn{background:hsl(38 80% 50%)}.xed-dot.info{background:hsl(220 9% 45%)}' +
      '.xed-meta{color:hsl(var(--muted-foreground, 220 9% 56%));font-size:12px;margin-left:auto}' +
      '.xed-overlay{position:fixed;inset:0;background:rgb(0 0 0 / .55);display:flex;align-items:center;justify-content:center;z-index:9999}' +
      '.xed-dialog{background:hsl(var(--card, 220 20% 10%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:14px;padding:18px 22px;width:min(900px,93vw);max-height:88vh;overflow:auto;color:hsl(var(--foreground, 220 9% 84%))}' +
      '.xed-dialog h3{margin:0 0 10px;font:500 17px/1.3 ui-sans-serif,system-ui,sans-serif}' +
      '.xed-dwarn{color:hsl(38 80% 60%);font-size:13px;margin:0 0 10px}' +
      '.xed-diff{background:hsl(var(--muted, 220 14% 14%));border:1px solid hsl(var(--border, 220 14% 18%));border-radius:8px;padding:8px 0;font:12px/1.5 ui-monospace,Menlo,monospace;overflow:auto;max-height:48vh}' +
      '.xed-dline{padding:0 12px;white-space:pre}' +
      '.xed-dline.add{background:hsl(140 60% 40% / .16);color:hsl(140 55% 65%)}' +
      '.xed-dline.del{background:hsl(0 72% 52% / .14);color:hsl(0 70% 70%)}' +
      '.xed-dline.ctx{color:hsl(var(--muted-foreground, 220 9% 56%))}' +
      '.xed-dskip{padding:0 12px;color:hsl(var(--muted-foreground, 220 9% 45%));user-select:none}';
    document.head.appendChild(st);
  }

  /* ---------- состояние ---------- */

  var state = {
    root: null, profiles: [], sel: null, node: null, wholeJson: false,
    timer: null, curLang: lang(),
    draft: null,                 // объект конфига-черновика (null = нет правок)
    hist: { past: [], future: [] },
    mode: 'form', dialog: null, conflict: null, toast: '',
    pos: {},                     // сдвиги карточек {id:{dx,dy}} (перетаскивание)
    search: '', versions: null, verErr: '', verCompare: '',
    trace: { on: false, address: '', port: 443, network: 'tcp', ip: '', inbound: '', protocol: '', user: '', sourceIp: '' },
    traceRes: null, traceUi: { showBelow: false },
    geo: { loaded: false, answers: {}, missing: [] }, geoStatus: null, geoBusy: false, geoTimer: null,
    screen: 'picker',
    tplRecipes: {},
    conn: null,
    subs: null, subsSel: null, subsDoc: null, subsBusy: false, subsMsg: '',
    subsCfg: null, subsDirty: false, subsRaw: false,
    check: null, checkBusy: false,
    geoTab: 'src', geoKind: 'geosite', geoCats: null, geoCatQ: '', geoCode: null,
    geoRows: null, geoRowQ: '', geoOff: 0, geoUrls: null, geoMsg: '',
    view: { k: 1, tx: 0, ty: 0 }, tab: 'topo',
    recipe: null, recParams: {}, recPreviewCfg: null, recPlanList: [], recShowDiff: false, tpl: null,
    tplRemote: null, tplRemoteCfg: null, gallery: null, galleryErr: '',
    repaintCanvas: null, _suppressClick: false
  };
  var dragState = null;          // активное перетаскивание

  function draftKey(uuid) { return 'xed-draft:' + uuid; }
  function posKey(uuid) { return 'xed-pos:' + uuid; }
  function loadPos() {
    var p = selProfile();
    state.pos = {};
    if (!p) return;
    try { var raw = localStorage.getItem(posKey(p.uuid)); if (raw) state.pos = JSON.parse(raw) || {}; } catch (e) { state.pos = {}; }
  }
  function persistPos() {
    var p = selProfile();
    if (!p) return;
    try {
      if (state.pos && Object.keys(state.pos).length) localStorage.setItem(posKey(p.uuid), JSON.stringify(state.pos));
      else localStorage.removeItem(posKey(p.uuid));
    } catch (e) {}
  }
  function hasPos() { return state.pos && Object.keys(state.pos).length > 0; }

  // Перетаскивание карточек графа: mousedown на [data-node] → сдвиг в единицах
  // viewBox → сохранение в state.pos → лёгкая перерисовка холста.
  /* ---------- визуальный коннектор ----------
     Тянем связь из правой точки карточки в другую карточку. Допустимы только те
     связи, которые реально существуют в xray-конфиге: инбаунд задаётся в правиле
     полем inboundTag, правило уходит либо в outbound, либо в балансер, балансер
     набирает выходы селектором. Всё остальное линия просто не принимает. */
  function connKind(id) {
    if (id === 'dns') return 'dns';
    return String(id).split(':')[0];
  }
  function canConnectFrom(id) {
    var k = connKind(id);
    return k === 'in' || k === 'rule' || k === 'bal';
  }
  function connAllowed(from, to) {
    if (!from || !to || from === to) return false;
    var a = connKind(from), b = connKind(to);
    if (a === 'in') return b === 'rule';
    if (a === 'rule') return b === 'out' || b === 'bal';
    if (a === 'bal') return b === 'out';
    return false;
  }
  // класс подсветки карточки во время протяжки: ok — можно принять, no — нельзя
  function connTargetCls(id) {
    var cn = state.conn;
    if (!cn || !cn.from || id === cn.from) return '';
    return connAllowed(cn.from, id) ? 'ok' : 'no';
  }
  function connApply(from, to) {
    var next = clone(cfg());
    var a = connKind(from), b = connKind(to);
    var fromTag = from.slice(from.indexOf(':') + 1);
    var toTag = to.slice(to.indexOf(':') + 1);
    if (a === 'in' && b === 'rule') {
      var r = (next.routing && next.routing.rules || [])[parseInt(toTag, 10)];
      if (!r) return false;
      var lst = r.inboundTag || [];
      if (lst.indexOf(fromTag) >= 0) return false;      // уже связаны — повтор не нужен
      r.inboundTag = lst.concat([fromTag]);
    } else if (a === 'rule' && (b === 'out' || b === 'bal')) {
      var r2 = (next.routing && next.routing.rules || [])[parseInt(fromTag, 10)];
      if (!r2) return false;
      if (b === 'out') { r2.outboundTag = toTag; delete r2.balancerTag; }
      else { r2.balancerTag = toTag; delete r2.outboundTag; }
    } else if (a === 'bal' && b === 'out') {
      var bals = (next.routing && next.routing.balancers) || [];
      var bl = null;
      for (var i = 0; i < bals.length; i++) if (bals[i].tag === fromTag) bl = bals[i];
      if (!bl) return false;
      var sel = bl.selector || [];
      // селектор матчит по префиксу — если уже покрывает тег, второй раз не пишем
      for (var j = 0; j < sel.length; j++) if (toTag.indexOf(sel[j]) === 0) return false;
      bl.selector = sel.concat([toTag]);
    } else {
      return false;
    }
    writeDraft(next);
    return true;
  }
  // экранные координаты → координаты холста (с учётом зума и пана)
  function svgPoint(svg, clientX, clientY) {
    var rect = svg.getBoundingClientRect();
    var vb = svg.viewBox.baseVal;
    var sc = (vb && rect.width) ? vb.width / rect.width : 1;
    var vw = state.view || { k: 1, tx: 0, ty: 0 };
    return { x: ((clientX - rect.left) * sc - vw.tx) / (vw.k || 1),
             y: ((clientY - rect.top) * sc - vw.ty) / (vw.k || 1) };
  }
  function nodeAt(x, y) {
    var pos = state.lastPos || {};
    var keys = Object.keys(pos);
    for (var i = 0; i < keys.length; i++) {
      var b = pos[keys[i]];
      if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return keys[i];
    }
    return null;
  }

  function setupDrag() {
    var canvas = document.getElementById('xed-canvas');
    var svg = canvas && canvas.querySelector('svg');
    if (!svg) return;
    canvas.addEventListener('mousedown', function (e) {
      var port = e.target.closest && e.target.closest('[data-port]');
      if (port) {                                 // протяжка связи из точки
        e.preventDefault(); e.stopPropagation();
        var pt = svgPoint(svg, e.clientX, e.clientY);
        state.conn = { from: port.getAttribute('data-port'), x: pt.x, y: pt.y, to: null };
        if (state.repaintCanvas) state.repaintCanvas();
        return;
      }
      var g = e.target.closest && e.target.closest('[data-node]');
      if (!g) {                                   // пустое место — пан холста
        var rect0 = svg.getBoundingClientRect();
        var vb0 = svg.viewBox.baseVal;
        var sc0 = (vb0 && rect0.width) ? vb0.width / rect0.width : 1;
        dragState = { pan: true, x0: e.clientX, y0: e.clientY,
                      tx0: state.view.tx, ty0: state.view.ty, scale: sc0, moved: false };
        e.preventDefault();
        return;
      }
      e.preventDefault();
      var rect = svg.getBoundingClientRect();
      var vb = svg.viewBox.baseVal;
      var scale = (vb && rect.width) ? vb.width / rect.width : 1;
      var id = g.getAttribute('data-node');
      var cur = state.pos[id] || { dx: 0, dy: 0 };
      dragState = { id: id, x0: e.clientX, y0: e.clientY, dx0: cur.dx || 0, dy0: cur.dy || 0,
                    scale: scale / (state.view.k || 1), moved: false };
    });
  }
  function onDragMove(e) {
    if (state.conn) {
      var canvas0 = document.getElementById('xed-canvas');
      var svg0 = canvas0 && canvas0.querySelector('svg');
      if (svg0) {
        var pt = svgPoint(svg0, e.clientX, e.clientY);
        state.conn.x = pt.x; state.conn.y = pt.y;
        var hit = nodeAt(pt.x, pt.y);
        state.conn.to = (hit && connAllowed(state.conn.from, hit)) ? hit : null;
        state.conn.over = hit || null;
        if (state.repaintCanvas) state.repaintCanvas();
      }
      return;
    }
    if (!dragState) return;
    var mx = e.clientX - dragState.x0, my = e.clientY - dragState.y0;
    if (Math.abs(mx) + Math.abs(my) > 3) dragState.moved = true;
    if (dragState.pan) {
      state.view.tx = dragState.tx0 + mx * dragState.scale;
      state.view.ty = dragState.ty0 + my * dragState.scale;
    } else {
      state.pos[dragState.id] = { dx: dragState.dx0 + mx * dragState.scale, dy: dragState.dy0 + my * dragState.scale };
    }
    if (state.repaintCanvas) state.repaintCanvas();
  }
  function onDragUp() {
    if (state.conn) {
      var cn = state.conn;
      state.conn = null;
      if (cn.to) { state._suppressClick = true; connApply(cn.from, cn.to); }
      else if (state.repaintCanvas) state.repaintCanvas();
      return;
    }
    if (!dragState) return;
    if (dragState.moved) {
      state._suppressClick = true;
      if (!dragState.pan) { persistPos(); render(); }   // full render → кнопка сброса расположения
    }
    dragState = null;
  }
  function selProfile() {
    for (var i = 0; i < state.profiles.length; i++) {
      if (state.profiles[i].uuid === state.sel) return state.profiles[i];
    }
    return state.profiles[0] || null;
  }
  function panelCfg() { var p = selProfile(); return p ? (p.config || {}) : {}; }

  // XRAY_JSON-шаблон подписки — это тот же xray-конфиг, поэтому его правит тот же
  // визуальный редактор. Разница только в источнике документа и в том, куда
  // сохранять: профиль идёт в config-profiles, шаблон — в subscription-templates.
  function isSubsJson() {
    return state.screen === 'subs' && state.subsDoc && state.subsDoc.format === 'json';
  }
  function cfg() {
    if (isSubsJson()) return state.subsCfg || {};
    return state.draft || panelCfg();
  }
  function dirty() { return !!state.draft && ser(state.draft) !== ser(panelCfg()); }

  function loadDraftLS() {
    var p = selProfile();
    if (!p) { state.draft = null; return; }
    state.draft = null;
    try {
      var raw = localStorage.getItem(draftKey(p.uuid));
      if (raw) {
        var d = JSON.parse(raw);
        if (d && d.json) state.draft = JSON.parse(d.json);
      }
    } catch (e) { state.draft = null; }
  }
  function persistDraft() {
    var p = selProfile();
    if (!p) return;
    try {
      if (state.draft) localStorage.setItem(draftKey(p.uuid), JSON.stringify({ json: ser(state.draft), savedAt: new Date().toISOString() }));
      else localStorage.removeItem(draftKey(p.uuid));
    } catch (e) {}
  }
  function clearDraft() {
    state.draft = null;
    state.hist = { past: [], future: [] };
    persistDraft();
  }

  // Единственная точка записи черновика: снимок в историю + персист + перерисовка.
  function writeDraft(next) {
    if (isSubsJson()) {                       // правки шаблона живут отдельно от черновика профиля
      state.hist.past.push(ser(cfg()));
      if (state.hist.past.length > 50) state.hist.past.shift();
      state.hist.future = [];
      state.subsCfg = next;
      state.subsDirty = true;
      render();
      return;
    }
    state.hist.past.push(ser(cfg()));
    if (state.hist.past.length > 50) state.hist.past.shift();
    state.hist.future = [];
    state.draft = next;
    persistDraft();
    render();
  }
  function undo() {
    if (!state.hist.past.length) return;
    state.hist.future.push(ser(cfg()));
    state.draft = JSON.parse(state.hist.past.pop());
    state.node = null;
    persistDraft();
    render();
  }
  function redo() {
    if (!state.hist.future.length) return;
    state.hist.past.push(ser(cfg()));
    state.draft = JSON.parse(state.hist.future.pop());
    state.node = null;
    persistDraft();
    render();
  }

  /* ---------- мутации (structuredClone + patch; пустое = удалить ключ) ---------- */

  function patch(mut) {
    var next = clone(cfg());
    mut(next);
    writeDraft(next);
  }
  function ensureRouting(c) {
    if (!c.routing) c.routing = {};
    if (!c.routing.rules) c.routing.rules = [];
    return c.routing;
  }
  function nodeObj(c, id) {
    if (!id || !c) return null;
    if (id === 'dns') return c.dns;
    var m = id.match(/^(in|out|bal|rule):([\s\S]*)$/);
    if (!m) return null;
    if (m[1] === 'rule') return ((c.routing || {}).rules || [])[+m[2]];
    var arr = m[1] === 'in' ? c.inbounds : m[1] === 'out' ? c.outbounds : (c.routing || {}).balancers;
    return (arr || []).filter(function (x) { return x.tag === m[2]; })[0];
  }
  function setNode(id, obj) {
    var m = id.match(/^(in|out|bal|rule):([\s\S]*)$/);
    patch(function (c) {
      if (id === 'dns') { if (obj == null) delete c.dns; else c.dns = obj; return; }
      if (!m) return;
      if (m[1] === 'rule') {
        var rules = ensureRouting(c).rules;
        var i = +m[2];
        if (obj == null) rules.splice(i, 1); else rules[i] = obj;
        return;
      }
      var key = m[1] === 'in' ? 'inbounds' : m[1] === 'out' ? 'outbounds' : null;
      var arr = key ? (c[key] = c[key] || []) : (ensureRouting(c).balancers = (c.routing.balancers || []));
      for (var j = 0; j < arr.length; j++) {
        if (arr[j].tag === m[2]) {
          if (obj == null) arr.splice(j, 1); else arr[j] = obj;
          return;
        }
      }
    });
    // выделение едет за узлом: при переименовании тега id меняется
    if (obj == null) state.node = null;
    else if (m && m[1] !== 'rule' && obj.tag && obj.tag !== m[2]) state.node = m[1] + ':' + obj.tag;
    render();
  }
  function moveRule(i, dir) {
    var j = i + dir;
    var rules = (cfg().routing || {}).rules || [];
    if (j < 0 || j >= rules.length) return;
    patch(function (c) {
      var rs = ensureRouting(c).rules;
      var tmp = rs[i]; rs[i] = rs[j]; rs[j] = tmp;
    });
    state.node = 'rule:' + j;
    render();
  }
  function addRule() {
    var n;
    patch(function (c) {
      var rs = ensureRouting(c).rules;
      var firstOut = ((c.outbounds || [])[0] || {}).tag;
      rs.push(firstOut ? { outboundTag: firstOut } : {});
      n = rs.length - 1;
    });
    state.node = 'rule:' + n;
    state.mode = 'form';
    render();
  }
  function addInbound() {
    var tag;
    patch(function (c) {
      c.inbounds = c.inbounds || [];
      var i = 1;
      while (c.inbounds.some(function (x) { return x.tag === 'in-' + i; })) i++;
      tag = 'in-' + i;
      c.inbounds.push({
        tag: tag, protocol: 'vless', port: 443,
        settings: { clients: [] },
        streamSettings: { network: 'tcp', security: 'none' },
        sniffing: { enabled: true, destOverride: ['http', 'tls'] }
      });
    });
    state.node = 'in:' + tag;
    state.mode = 'form';
    render();
  }

  function addBalancer() {
    var tag;
    patch(function (c) {
      var r = ensureRouting(c);
      r.balancers = r.balancers || [];
      var i = 1;
      while (r.balancers.some(function (b) { return b.tag === 'bal-' + i; })) i++;
      tag = 'bal-' + i;
      r.balancers.push({ tag: tag, selector: [], strategy: { type: 'random' } });
    });
    state.node = 'bal:' + tag;
    state.mode = 'form';
    render();
  }

  function addOutbound() {
    var tag;
    patch(function (c) {
      c.outbounds = c.outbounds || [];
      var i = 1;
      while (c.outbounds.some(function (o) { return o.tag === 'NEW-' + i; })) i++;
      tag = 'NEW-' + i;
      c.outbounds.push({ tag: tag, protocol: 'freedom' });
    });
    state.node = 'out:' + tag;
    state.mode = 'form';
    render();
  }

  /* ---------- сохранение ---------- */

  function fetchProfile(uuid) {
    return fetch(apiBase() + '/config-profiles/' + encodeURIComponent(uuid), { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) { return d.response || d; });   // на случай обёртки панели
  }

  function doPatch(uuid, config) {
    return fetch(apiBase() + '/config-profiles/' + encodeURIComponent(uuid), {
      method: 'PATCH',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
      body: JSON.stringify(config)
    }).then(function (r) {
      if (r.ok) return r.json().catch(function () { return {}; });
      return r.json().catch(function () { return {}; }).then(function (body) {
        throw new Error(body.detail || body.message || ('HTTP ' + r.status));
      });
    });
  }

  function startSave() {
    var p = selProfile();
    if (!p || !dirty()) return;
    if (lint(cfg()).some(function (i) { return i.level === 'error'; })) return;
    state.dialog = 'diff';
    render();
  }

  function confirmSave(force) {
    var p = selProfile();
    if (!p) return;
    state.dialog = 'saving';
    render();
    fetchProfile(p.uuid).then(function (fresh) {
      if (!force && fresh.updatedAt && p.updatedAt && fresh.updatedAt !== p.updatedAt) {
        state.conflict = fresh;
        state.dialog = 'conflict';
        render();
        return null;
      }
      return doPatch(p.uuid, cfg()).then(function () {
        clearDraft();
        state.dialog = null;
        state.node = null;
        state.toast = t().savedOk;
        load(true);
      });
    }).catch(function (e) {
      state.dialog = null;
      state.toast = t().saveFail + e.message;
      render();
    });
  }

  function conflictLoadPanel() {
    var fresh = state.conflict;
    var p = selProfile();
    if (fresh && p) {
      p.config = fresh.config || p.config;
      p.updatedAt = fresh.updatedAt || p.updatedAt;
    }
    clearDraft();
    state.conflict = null;
    state.dialog = null;
    state.node = null;
    render();
  }

  /* ---------- версии конфига (родная история админки) ----------
     Админка сама пишет снимок в config_versions при каждом PATCH, включая
     baseline до первой правки. Плагину остаётся только показать список и
     дать загрузить версию в черновик — записи это не делает. */

  function loadVersions() {
    var p = selProfile();
    if (!p) return;
    state.dialog = 'versions';
    state.versions = null;
    state.verErr = '';
    render();
    fetch(apiBase() + '/config-profiles/' + encodeURIComponent(p.uuid) + '/versions',
          { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) { state.versions = d.items || []; render(); })
      .catch(function (e) { state.verErr = t().verFail + e.message; state.versions = []; render(); });
  }

  function versionContent(id, cb) {
    fetch(apiBase() + '/config-profiles/versions/' + encodeURIComponent(id), { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (row) {
        var raw = (row && (row.content !== undefined ? row.content : (row.item || {}).content)) || '';
        try { cb(JSON.parse(raw)); } catch (e) { state.toast = t().badJson + e.message; render(); }
      })
      .catch(function (e) { state.toast = t().verFail + e.message; render(); });
  }

  /* ---------- формы инспектора ---------- */

  function fld(labelText, inner) {
    return '<div class="xed-field"><label>' + esc(labelText) + '</label>' + inner + '</div>';
  }
  function txt(id, value) {
    return '<input type="text" id="' + id + '" value="' + esc(value == null ? '' : value) + '">';
  }
  function ta(id, lines) {
    return '<textarea id="' + id + '">' + esc((lines || []).join('\n')) + '</textarea>';
  }
  function sel(id, options, current, withNone) {
    var h = '<select id="' + id + '">';
    if (withNone) h += '<option value=""' + (current ? '' : ' selected') + '>' + t().none + '</option>';
    options.forEach(function (o) {
      h += '<option value="' + esc(o) + '"' + (o === current ? ' selected' : '') + '>' + esc(o) + '</option>';
    });
    return h + '</select>';
  }
  function chips(id, options, currentArr) {
    var cur = currentArr || [];
    return '<div class="xed-chips" id="' + id + '">' + options.map(function (o) {
      return '<button type="button" class="xed-chipbtn' + (cur.indexOf(o) >= 0 ? ' on' : '') + '" data-v="' + esc(o) + '">' + esc(o) + '</button>';
    }).join('') + '</div>';
  }
  function taLines(el) {
    return el.value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
  }
  function setOrDel(obj, key, val) {
    var empty = val == null || val === '' || (Array.isArray(val) && !val.length);
    if (empty) delete obj[key]; else obj[key] = val;
  }

  function formHtml(id, obj, c, tr) {
    var kind = id === 'dns' ? 'dns' : id.split(':')[0];
    var outTags = (c.outbounds || []).map(function (o) { return o.tag; });
    var balTags = ((c.routing || {}).balancers || []).map(function (b) { return b.tag; });
    var inTags = (c.inbounds || []).map(function (i) { return i.tag; });
    if (kind === 'rule') {
      var target = obj.outboundTag ? 'out:' + obj.outboundTag : obj.balancerTag ? 'bal:' + obj.balancerTag : '';
      var targetOpts = outTags.map(function (x) { return 'out:' + x; }).concat(balTags.map(function (x) { return 'bal:' + x; }));
      return fld(tr.target, sel('f-target', targetOpts, target, true)) +
        fld(tr.domains, ta('f-domain', obj.domain)) +
        fld(tr.ips, ta('f-ip', obj.ip)) +
        fld(tr.port, txt('f-port', obj.port)) +
        fld(tr.network, sel('f-network', ['tcp', 'udp', 'tcp,udp'], obj.network || '', true)) +
        fld(tr.protocols, chips('f-protocol', ['http', 'tls', 'bittorrent', 'quic'], obj.protocol)) +
        fld(tr.ruleInbounds, chips('f-inbounds', inTags, obj.inboundTag));
    }
    if (kind === 'out') {
      return fld(tr.tag, txt('f-tag', obj.tag)) +
        fld(tr.protocol, sel('f-proto', ['freedom', 'blackhole', 'wireguard', 'socks', 'http', 'vless'], obj.protocol || 'freedom'));
    }
    if (kind === 'in') {
      var dov = (obj.sniffing || {}).destOverride || [];
      return fld(tr.tag, txt('f-tag', obj.tag)) +
        fld(tr.port, txt('f-port', obj.port)) +
        fld(tr.sniffing, chips('f-sniff', ['enabled'], sniffingOn(obj) ? ['enabled'] : [])) +
        fld(tr.destOverride, chips('f-dov', ['http', 'tls', 'quic', 'fakedns'], dov));
    }
    if (kind === 'bal') {
      return fld(tr.tag, txt('f-tag', obj.tag)) +
        fld(tr.selector, ta('f-selector', obj.selector)) +
        fld(tr.strategy, sel('f-strategy', ['random', 'roundRobin', 'leastPing', 'leastLoad'], (obj.strategy || {}).type || 'random')) +
        fld(tr.fallback, sel('f-fallback', outTags, obj.fallbackTag || '', true));
    }
    return '';   // dns и прочее — только JSON-вкладка
  }

  function readForm(id, obj) {
    var kind = id === 'dns' ? 'dns' : id.split(':')[0];
    var next = clone(obj);
    function v(fid) { var el = document.getElementById(fid); return el ? el.value : null; }
    function chipVals(fid) {
      var el = document.getElementById(fid);
      if (!el) return null;
      return Array.prototype.filter.call(el.querySelectorAll('.xed-chipbtn'), function (b) {
        return b.classList.contains('on');
      }).map(function (b) { return b.getAttribute('data-v'); });
    }
    function portVal(raw) {
      if (raw == null || raw === '') return null;
      return /^\d+$/.test(raw) ? +raw : raw;
    }
    if (kind === 'rule') {
      var target = v('f-target') || '';
      delete next.outboundTag; delete next.balancerTag;
      if (target.indexOf('out:') === 0) next.outboundTag = target.slice(4);
      if (target.indexOf('bal:') === 0) next.balancerTag = target.slice(4);
      setOrDel(next, 'domain', taLines(document.getElementById('f-domain')));
      setOrDel(next, 'ip', taLines(document.getElementById('f-ip')));
      setOrDel(next, 'port', portVal(v('f-port')));
      setOrDel(next, 'network', v('f-network') || null);
      setOrDel(next, 'protocol', chipVals('f-protocol'));
      setOrDel(next, 'inboundTag', chipVals('f-inbounds'));
    } else if (kind === 'out') {
      setOrDel(next, 'tag', v('f-tag'));
      next.protocol = v('f-proto') || 'freedom';
    } else if (kind === 'in') {
      setOrDel(next, 'tag', v('f-tag'));
      setOrDel(next, 'port', portVal(v('f-port')));
      var on = (chipVals('f-sniff') || []).length > 0;
      var dov = chipVals('f-dov') || [];
      if (on || dov.length) {
        next.sniffing = next.sniffing || {};
        next.sniffing.enabled = on;
        setOrDel(next.sniffing, 'destOverride', dov);
      } else delete next.sniffing;
    } else if (kind === 'bal') {
      setOrDel(next, 'tag', v('f-tag'));
      setOrDel(next, 'selector', taLines(document.getElementById('f-selector')));
      next.strategy = { type: v('f-strategy') || 'random' };
      setOrDel(next, 'fallbackTag', v('f-fallback') || null);
    }
    return next;
  }

  /* ---------- трассировщик маршрута (порт trace.ts + traceMatch.ts) ----------
     Троичная логика: 'yes' | 'no' | 'unknown'. Смысл в том, чтобы честно
     говорить «нет данных», а не гадать: правило, зависящее от geo-базы или
     незаданного поля цели, не объявляется ни совпавшим, ни промахнувшимся.
     Geo-базы плагин пока не качает → NO_GEO, все geosite:/geoip: = unknown. */

  var NO_GEO = { loaded: false, answers: {}, missing: [] };

  function combine(fields) {                       // поля правила = И, «no» перевешивает
    if (fields.some(function (f) { return f.state === 'no'; })) return 'no';
    if (fields.some(function (f) { return f.state === 'unknown'; })) return 'unknown';
    return 'yes';                                  // пустой список полей = правило без условий
  }
  // Причины — кодами (trR в словаре L), текст подбирается под язык при отрисовке.
  function aggregate(field, states, codes) {      // значения поля = ИЛИ, «yes» перевешивает
    var hit = states.filter(function (s) { return s.state === 'yes'; })[0];
    if (hit) return { field: field, state: 'yes', code: codes.yes, v: hit.value };
    var unk = states.filter(function (s) { return s.state === 'unknown'; })[0];
    if (unk) return { field: field, state: 'unknown', code: codes.unknown, v: unk.value };
    return { field: field, state: 'no', code: codes.no, v: states.length };
  }
  function geoState(key, geo) {
    if (!geo.loaded) return 'unknown';
    var a = geo.answers[key];
    return a === undefined ? 'unknown' : (a ? 'yes' : 'no');
  }

  function parseIp(value) {
    var v = String(value);
    var m4 = v.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
    if (m4) {
      var bits = 0n;
      for (var i = 1; i <= 4; i++) {
        var o = Number(m4[i]);
        if (o > 255) return null;
        bits = (bits << 8n) | BigInt(o);
      }
      return { bits: bits, size: 32 };
    }
    if (v.indexOf(':') < 0) return null;
    var halves = v.split('::');
    if (halves.length > 2) return null;
    var head = halves[0] === '' ? [] : halves[0].split(':');
    var tail = halves.length === 2 ? (halves[1] === '' ? [] : halves[1].split(':')) : [];
    var groups = halves.length === 2 ? 8 - head.length - tail.length : 8 - head.length;
    if (groups < 0 || (halves.length === 1 && groups !== 0)) return null;
    var parts = head.slice();
    for (var g = 0; g < groups; g++) parts.push('0');
    parts = parts.concat(tail);
    var b6 = 0n;
    for (var j = 0; j < parts.length; j++) {
      if (!/^[0-9a-fA-F]{1,4}$/.test(parts[j])) return null;
      b6 = (b6 << 16n) | BigInt(parseInt(parts[j], 16));
    }
    return { bits: b6, size: 128 };
  }
  function isIpAddress(v) { return parseIp(v) !== null; }

  function ipInCidr(ip, cidr) {
    var sp = String(cidr).split('/');
    var a = parseIp(ip), b = parseIp(sp[0]);
    if (!a || !b) return null;
    if (a.size !== b.size) return false;
    var prefix = sp[1] === undefined ? a.size : Number(sp[1]);
    if (!Number.isInteger(prefix) || prefix < 0 || prefix > a.size) return null;
    var mask = prefix === 0 ? 0n : ((1n << BigInt(prefix)) - 1n) << BigInt(a.size - prefix);
    return (a.bits & mask) === (b.bits & mask);
  }

  function matchDomainPattern(pattern, address, geo) {
    var p = String(pattern);
    if (p.indexOf('full:') === 0) return address === p.slice(5) ? 'yes' : 'no';
    if (p.indexOf('domain:') === 0) {
      var base = p.slice(7);
      return (address === base || address.slice(-(base.length + 1)) === '.' + base) ? 'yes' : 'no';
    }
    if (p.indexOf('keyword:') === 0) return address.indexOf(p.slice(8)) >= 0 ? 'yes' : 'no';
    if (p.indexOf('regexp:') === 0) {
      try { return new RegExp(p.slice(7)).test(address) ? 'yes' : 'no'; } catch (e) { return 'unknown'; }
    }
    if (p.indexOf('geosite:') === 0) return geoState(p, geo);   // ключ целиком, с атрибутом
    if (p.indexOf('ext:') === 0) return 'unknown';
    return address.indexOf(p) >= 0 ? 'yes' : 'no';              // без префикса = подстрока
  }
  function matchDomainField(patterns, address, geo) {
    var states = patterns.map(function (p) { return { value: p, state: matchDomainPattern(p, address, geo) }; });
    return aggregate('domain', states, { yes: 'domain_hit', unknown: 'domain_unknown', no: 'domain_miss' });
  }

  function matchIpPattern(pattern, ip, geo) {
    var p = String(pattern);
    if (p.indexOf('geoip:') === 0) {
      var body = p.slice(6);
      var negated = body.charAt(0) === '!';
      var st = geoState('geoip:' + (negated ? body.slice(1) : body), geo);
      if (st === 'unknown') return 'unknown';
      return negated ? (st === 'yes' ? 'no' : 'yes') : st;
    }
    if (p.indexOf('ext:') === 0) return 'unknown';
    var r = ipInCidr(ip, p);
    return r === null ? 'unknown' : (r ? 'yes' : 'no');
  }
  function matchIpField(field, patterns, ip, availability, geo, neverCode) {
    if (availability === 'never') return { field: field, state: 'no', code: neverCode || 'ip_asis' };
    if (availability === 'unspecified' || ip === undefined) {
      return { field: field, state: 'unknown', code: field === 'source' ? 'src_need' : 'ip_need' };
    }
    var states = patterns.map(function (p) { return { value: p, state: matchIpPattern(p, ip, geo) }; });
    return aggregate(field, states, { yes: 'ip_hit', unknown: 'ip_unknown', no: 'ip_miss' });
  }

  function portMatches(spec, port) {
    if (spec === undefined) return true;
    var parts = String(spec).split(',').map(function (s) { return s.trim(); });
    for (var i = 0; i < parts.length; i++) {
      var m = parts[i].match(/^(\d{1,5})(?:-(\d{1,5}))?$/);
      if (!m) continue;
      var lo = Number(m[1]), hi = m[2] === undefined ? lo : Number(m[2]);
      if (port >= lo && port <= hi) return true;
    }
    return false;
  }
  function matchPortField(field, spec, port) {
    var err = portSpecError(spec);
    if (err) return { field: field, state: 'unknown', code: 'port_bad', v: err };
    if (port === undefined) return { field: field, state: 'unknown', code: 'port_need' };
    var ok = portMatches(spec, port);
    return { field: field, state: ok ? 'yes' : 'no', code: ok ? 'port_hit' : 'port_miss', v: port, s: spec };
  }
  function matchNetworkField(spec, network) {
    var allowed = String(spec).split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    var ok = allowed.indexOf(network) >= 0;
    return { field: 'network', state: ok ? 'yes' : 'no', code: ok ? 'net_hit' : 'net_miss', v: network, s: spec };
  }
  function matchExactField(field, patterns, value, needCode) {
    if (value === undefined) return { field: field, state: 'unknown', code: needCode };
    var ok = patterns.indexOf(value) >= 0;
    return { field: field, state: ok ? 'yes' : 'no', code: ok ? 'exact_hit' : 'exact_miss', v: value };
  }

  // Порядок добавления полей важен: он же порядок в панели разбора.
  function judgeRule(rule, index, target, geo, ipAvailability, neverCode) {
    var fields = [];
    if (rule.domain && rule.domain.length) fields.push(matchDomainField(rule.domain, target.address, geo));
    if (rule.ip && rule.ip.length) fields.push(matchIpField('ip', rule.ip, target.ip, ipAvailability, geo, neverCode));
    if (rule.port !== undefined) fields.push(matchPortField('port', rule.port, target.port));
    if (rule.network !== undefined) fields.push(matchNetworkField(rule.network, target.network));
    if (rule.source && rule.source.length) {
      fields.push(matchIpField('source', rule.source, target.sourceIp, target.sourceIp ? 'known' : 'unspecified', geo));
    }
    if (rule.sourcePort !== undefined) fields.push(matchPortField('sourcePort', rule.sourcePort, target.sourcePort));
    if (rule.protocol && rule.protocol.length) {
      // без sniffing ядро протокол приложения не определяет вовсе — такое правило для этого inbound мёртвое
      fields.push(target.sniffOff ? { field: 'protocol', state: 'no', code: 'proto_nosniff' }
                                  : matchExactField('protocol', rule.protocol, target.protocol, 'proto_need'));
    }
    if (rule.user && rule.user.length) {
      fields.push(matchExactField('user', rule.user, target.user, 'user_need'));
    }
    if (rule.inboundTag && rule.inboundTag.length) {
      fields.push(matchExactField('inboundTag', rule.inboundTag, target.inboundTag, 'in_need'));
    }
    return { index: index, state: combine(fields), outboundTag: rule.outboundTag,
             balancerTag: rule.balancerTag, fields: fields };
  }
  function judgeAll(cfgObj, target, geo, ipAvailability, neverCode) {
    return (((cfgObj.routing || {}).rules) || []).map(function (r, i) {
      return judgeRule(r, i, target, geo, ipAvailability, neverCode);
    });
  }

  function findBalancer(cfgObj, tag) {
    return (((cfgObj.routing || {}).balancers) || []).filter(function (b) { return b.tag === tag; })[0];
  }
  function withBalancer(winner, cfgObj) {
    if (!winner.balancerTag) return winner;
    var bal = findBalancer(cfgObj, winner.balancerTag);
    if (!bal) return winner;
    return {
      ruleIndex: winner.ruleIndex, outboundTag: winner.outboundTag, balancerTag: winner.balancerTag,
      balancerCandidates: balancerCandidates(cfgObj, bal),
      balancerStrategy: (bal.strategy || {}).type || 'random'
    };
  }
  function pickWinner(verdicts, cfgObj) {
    var hit = verdicts.filter(function (v) { return v.state === 'yes'; })[0];
    if (hit) return withBalancer({ ruleIndex: hit.index, outboundTag: hit.outboundTag, balancerTag: hit.balancerTag }, cfgObj);
    var fallback = ((cfgObj.outbounds || [])[0] || {}).tag;
    if (fallback === undefined) return undefined;      // выходов нет
    return { ruleIndex: null, outboundTag: fallback, balancerTag: undefined };
  }

  function geoKeysOf(cfgObj) {
    var keys = [];
    (((cfgObj.routing || {}).rules) || []).forEach(function (rule) {
      (rule.domain || []).forEach(function (v) { if (String(v).indexOf('geosite:') === 0) keys.push(v); });
      (rule.ip || []).concat(rule.source || []).forEach(function (v) {
        if (String(v).indexOf('geoip:') === 0) keys.push(v);
      });
    });
    return keys;
  }
  function sniffingBlind(cfgObj, inboundTag) {
    if (inboundTag === undefined) return false;
    var inb = (cfgObj.inbounds || []).filter(function (i) { return i.tag === inboundTag; })[0];
    if (!inb) return false;
    var s = inb.sniffing;
    return !s || s.enabled !== true || !((s.destOverride || []).length);
  }

  // Оговорки к вердикту — кодами; «нет данных выше победителя» карточка считает сама.
  function collectCaveats(cfgObj, target, geo, verdicts, winner, strategy) {
    var out = [];
    if (geoKeysOf(cfgObj).length && !geo.loaded) out.push({ code: 'geo_off' });
    (geo.missing || []).forEach(function (key) { out.push({ code: 'geo_missing', v: key }); });
    var needsSniffing = verdicts.some(function (v) {
      return v.fields.some(function (f) { return f.field === 'domain' || f.field === 'protocol'; });
    });
    if (needsSniffing && sniffingBlind(cfgObj, target.inboundTag)) out.push({ code: 'sniff_blind', v: target.inboundTag });
    if (strategy === 'IPIfNonMatch' && target.ip === undefined && !isIpAddress(target.address)) out.push({ code: 'need_ip_pass' });
    return out;
  }

  function traceRoute(cfgObj, target, geo) {
    geo = geo || NO_GEO;
    var strategy = ((cfgObj.routing || {}).domainStrategy) || 'AsIs';
    var targetIsIp = isIpAddress(target.address);
    var eff = target;
    if (targetIsIp && target.ip === undefined) {
      eff = { address: target.address, port: target.port, network: target.network, ip: target.address,
              sourceIp: target.sourceIp, sourcePort: target.sourcePort, inboundTag: target.inboundTag,
              user: target.user, protocol: target.protocol };
    }
    var firstPassIp = (targetIsIp || strategy === 'IPOnDemand')
      ? (eff.ip === undefined ? 'unspecified' : 'known') : 'never';
    var neverCode = strategy === 'IPIfNonMatch' ? 'ip_pass1' : 'ip_asis';

    if (sniffingBlind(cfgObj, eff.inboundTag)) {
      eff = Object.assign({}, eff, { sniffOff: true });
    }
    var verdicts = judgeAll(cfgObj, eff, geo, firstPassIp, neverCode);
    var winner = pickWinner(verdicts, cfgObj);
    var ipVerdicts;
    var noRuleMatched = !verdicts.some(function (v) { return v.state === 'yes'; });
    if (strategy === 'IPIfNonMatch' && noRuleMatched && eff.ip !== undefined) {
      ipVerdicts = judgeAll(cfgObj, eff, geo, 'known');
      winner = pickWinner(ipVerdicts, cfgObj);
    }
    var caveats = collectCaveats(cfgObj, eff, geo, ipVerdicts || verdicts, winner, strategy);
    return { verdicts: verdicts, ipVerdicts: ipVerdicts, winner: winner, caveats: caveats };
  }

  function trStateLabel(st) { return (t().trStates || {})[st] || st; }
  function trFmt(tpl, f) {
    return String(tpl).replace('{v}', f && f.v !== undefined ? String(f.v) : '')
                      .replace('{s}', f && f.s !== undefined ? String(f.s) : '');
  }
  function trNeedsGeo(f) {
    return (f.code === 'domain_unknown' || f.code === 'ip_unknown') && /^geo(site|ip):/.test(String(f.v));
  }
  function trReason(f, tr) {
    var R = tr.trR || {};
    var code = trNeedsGeo(f) ? 'geo_need' : f.code;
    return trFmt(R[code] || code, f);
  }
  // На какое поле формы ведёт «указать» у причины «нет данных»
  var TR_FOCUS = { ip_need: 'xed-tr-ip', proto_need: 'xed-tr-proto', user_need: 'xed-tr-user',
                   in_need: 'xed-tr-in', src_need: 'xed-tr-src', port_need: 'xed-tr-port' };
  // Состояние узла-правила в графе: победитель отделён от обычного совпадения,
  // правила ниже победителя ядро не смотрит — «не дошло».
  function traceStateOf(result, ruleIndex) {
    if (!result) return undefined;
    var shown = result.ipVerdicts || result.verdicts;
    var v = shown.filter(function (x) { return x.index === ruleIndex; })[0];
    if (!v) return undefined;
    var wi = result.winner ? result.winner.ruleIndex : null;
    if (wi === ruleIndex) return 'winner';
    if (wi !== null && wi !== undefined && ruleIndex > wi) return 'skipped';
    return v.state;
  }

  // Поиск по графу: тег, порт, домен — возвращает id узлов (первый подсвечиваем)
  function searchNodes(c, q) {
    q = String(q || '').trim().toLowerCase();
    if (!q) return [];
    var hits = [];
    (c.inbounds || []).forEach(function (n) {
      if (String(n.tag || '').toLowerCase().indexOf(q) >= 0 || String(n.port || '').indexOf(q) >= 0) hits.push('in:' + n.tag);
    });
    (c.outbounds || []).forEach(function (o) {
      var addr = String((o.settings || {}).address || '').toLowerCase();
      if (String(o.tag || '').toLowerCase().indexOf(q) >= 0 || addr.indexOf(q) >= 0) hits.push('out:' + o.tag);
    });
    (((c.routing || {}).rules) || []).forEach(function (r, i) {
      var hay = [(r.domain || []).join(' '), (r.ip || []).join(' '), String(r.port || ''),
                 r.outboundTag || '', r.balancerTag || ''].join(' ').toLowerCase();
      if (hay.indexOf(q) >= 0) hits.push('rule:' + i);
    });
    (((c.routing || {}).balancers) || []).forEach(function (b) {
      if (String(b.tag || '').toLowerCase().indexOf(q) >= 0) hits.push('bal:' + b.tag);
    });
    return hits;
  }

  /* ---------- рецепты (порт идеи recipes/* из VAQYBIN) ----------
     Каждый рецепт — чистая функция (cfg, params) → {cfg, plan[]}: возвращает
     НОВЫЙ конфиг и человеческий план изменений. Слияние идемпотентное: если
     нужный outbound/правило уже есть, рецепт это видит и не плодит дубли —
     повторное применение ничего не портит. Пишем только в черновик, панель
     обновляется отдельной кнопкой «Сохранить».
     Правила добавляются В НАЧАЛО списка: в xray побеждает первое совпавшее,
     а блокировки/спецмаршруты должны стоять выше общего DIRECT. */

  function recEnsureOutbound(c, outbound, plan) {
    c.outbounds = c.outbounds || [];
    var exists = c.outbounds.some(function (o) { return o.tag === outbound.tag; });
    if (exists) { plan.push('outbound «' + outbound.tag + '» уже есть — оставляем как есть'); return false; }
    c.outbounds.push(outbound);
    plan.push('добавить outbound «' + outbound.tag + '» (' + outbound.protocol + ')');
    return true;
  }
  function recRuleExists(c, pred) {
    return (((c.routing || {}).rules) || []).some(pred);
  }
  function recPrependRule(c, rule, plan, human) {
    var r = ensureRouting(c);
    r.rules.unshift(rule);
    plan.push(human);
  }

  var PRESET_RECIPES = ['block-torrent', 'block-ads', 'block-private'];

  var RECIPES = [
    {
      id: 'block-torrent',
      title: 'Заблокировать торренты',
      note: 'Правило по протоколу bittorrent → blackhole. Требует включённого sniffing на инбаундах, иначе ядро не увидит протокол.',
      params: [],
      apply: function (c, p, plan) {
        recEnsureOutbound(c, { tag: 'BLOCK', protocol: 'blackhole' }, plan);
        if (recRuleExists(c, function (x) { return (x.protocol || []).indexOf('bittorrent') >= 0; })) {
          plan.push('правило по bittorrent уже есть — пропускаем');
        } else {
          recPrependRule(c, { protocol: ['bittorrent'], outboundTag: 'BLOCK' }, plan,
            'добавить правило: протокол bittorrent → BLOCK');
        }
      }
    },
    {
      id: 'block-ads',
      title: 'Заблокировать рекламу',
      note: 'Правило по geosite:category-ads-all → blackhole. Нужны geo-базы на нодах (в образе ядра они есть).',
      params: [],
      apply: function (c, p, plan) {
        recEnsureOutbound(c, { tag: 'BLOCK', protocol: 'blackhole' }, plan);
        if (recRuleExists(c, function (x) { return (x.domain || []).indexOf('geosite:category-ads-all') >= 0; })) {
          plan.push('правило по рекламе уже есть — пропускаем');
        } else {
          recPrependRule(c, { domain: ['geosite:category-ads-all'], outboundTag: 'BLOCK' }, plan,
            'добавить правило: geosite:category-ads-all → BLOCK');
        }
      }
    },
    {
      id: 'block-private',
      title: 'Закрыть локальные сети',
      note: 'Запрещает клиентам ходить в приватные диапазоны через ноду (geoip:private → blackhole).',
      params: [],
      apply: function (c, p, plan) {
        recEnsureOutbound(c, { tag: 'BLOCK', protocol: 'blackhole' }, plan);
        if (recRuleExists(c, function (x) { return (x.ip || []).indexOf('geoip:private') >= 0; })) {
          plan.push('правило по локальным сетям уже есть — пропускаем');
        } else {
          recPrependRule(c, { ip: ['geoip:private'], outboundTag: 'BLOCK' }, plan,
            'добавить правило: geoip:private → BLOCK');
        }
      }
    },
    {
      id: 'warp-services',
      title: 'Сервисы через WARP',
      note: 'Отдельный wireguard-выход на Cloudflare WARP и правило для перечисленных доменов. Ключи возьми из wgcf.',
      params: [
        { key: 'tag', label: 'Тег outbound', def: 'WARP' },
        { key: 'services', label: 'Сервисы', type: 'chips', def: 'geosite:openai',
          hint: 'Категории geosite, которые пойдут через WARP',
          options: [
            { value: 'geosite:openai', label: 'OpenAI / ChatGPT' },
            { value: 'geosite:google', label: 'Google' },
            { value: 'geosite:netflix', label: 'Netflix' },
            { value: 'geosite:spotify', label: 'Spotify' },
            { value: 'geosite:twitter', label: 'Twitter / X' },
            { value: 'geosite:facebook', label: 'Meta / Facebook' },
            { value: 'geosite:discord', label: 'Discord' },
            { value: 'geosite:tiktok', label: 'TikTok' },
            { value: 'geosite:apple', label: 'Apple' },
            { value: 'geosite:microsoft', label: 'Microsoft' }
          ] },
        { key: 'domains', label: 'Свои домены и категории', type: 'textarea', def: '',
          ph: 'example.com\ngeosite:netflix', hint: 'По одному в строке' },
        { key: 'secretKey', label: 'Приватный ключ (secretKey)', def: '', hint: 'Из wgcf — без него конфиг не заработает' },
        { key: 'address', label: 'Адреса интерфейса', def: '172.16.0.2/32' },
        { key: 'endpoint', label: 'Endpoint', def: 'engage.cloudflareclient.com:2408' },
        { key: 'publicKey', label: 'publicKey пира', def: 'bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=' },
        { key: 'mtu', label: 'MTU', def: '1280' }
      ],
      apply: function (c, p, plan) {
        var wtag = p.tag || 'WARP';
        recEnsureOutbound(c, {
          tag: wtag, protocol: 'wireguard',
          settings: {
            secretKey: p.secretKey || '', address: [p.address || '172.16.0.2/32'],
            mtu: Number(p.mtu) || 1280,
            peers: [{ publicKey: p.publicKey, endpoint: p.endpoint, allowedIPs: ['0.0.0.0/0', '::/0'] }]
          }
        }, plan);
        var doms = String(p.services || '').split(',').concat(String(p.domains || '').split(/[\n,]/))
          .map(function (s) { return s.trim(); }).filter(Boolean);
        if (!doms.length) { plan.push('домены не заданы — правило не добавляем'); return; }
        if (recRuleExists(c, function (x) { return x.outboundTag === wtag; })) {
          plan.push('правило на «' + wtag + '» уже есть — пропускаем');
        } else {
          recPrependRule(c, { domain: doms, outboundTag: wtag }, plan,
            'добавить правило: ' + doms.slice(0, 4).join(', ') + (doms.length > 4 ? '…' : '') + ' → ' + wtag);
        }
        if (!p.secretKey) plan.push('⚠ secretKey пуст — конфиг не заработает, пока не впишешь ключ');
      }
    },
    {
      id: 'chain',
      title: 'Цепочка через второй сервер',
      note: 'VLESS-Reality выход на другую нашу ноду и правило для выбранного инбаунда — так строится каскад.',
      params: [
        { key: 'tag', label: 'Тег выхода', def: 'chain-out' },
        { key: 'address', label: 'Адрес второй ноды', def: '' },
        { key: 'port', label: 'Порт', def: '443' },
        { key: 'id', label: 'UUID пользователя', def: '' },
        { key: 'pbk', label: 'publicKey (Reality)', def: '' },
        { key: 'sid', label: 'shortId', def: '' },
        { key: 'sni', label: 'serverName (SNI)', def: '' },
        { key: 'inbound', label: 'Инбаунд-источник', type: 'select', def: '',
          options: function (c2) {
            return [{ value: '', label: 'весь трафик' }].concat(
              (c2.inbounds || []).map(function (i) { return { value: i.tag, label: i.tag }; }));
          } }
      ],
      apply: function (c, p, plan) {
        var tag = p.tag || 'chain-out';
        recEnsureOutbound(c, {
          tag: tag, protocol: 'vless',
          settings: { vnext: [{ address: p.address, port: Number(p.port) || 443,
            users: [{ id: p.id, encryption: 'none', flow: 'xtls-rprx-vision' }] }] },
          streamSettings: { network: 'tcp', security: 'reality',
            realitySettings: { serverName: p.sni, publicKey: p.pbk, shortId: p.sid, fingerprint: 'chrome' } }
        }, plan);
        if (recRuleExists(c, function (x) { return x.outboundTag === tag; })) {
          plan.push('правило на «' + tag + '» уже есть — пропускаем');
        } else {
          var rule = { outboundTag: tag };
          if (p.inbound) rule.inboundTag = [p.inbound];
          recPrependRule(c, rule, plan, 'добавить правило: ' +
            (p.inbound ? 'инбаунд «' + p.inbound + '»' : 'весь трафик') + ' → ' + tag);
        }
        if (!p.address || !p.id) plan.push('⚠ адрес или UUID пусты — цепочка не соберётся');
      }
    },
    {
      id: 'balance',
      title: 'Балансировка выходов',
      note: 'Балансер по префиксу тега. Для leastPing/leastLoad добавляется секция observatory — без неё ядро не стартует.',
      params: [
        { key: 'tag', label: 'Тег балансера', def: 'AUTO' },
        { key: 'outs', label: 'Балансируемые выходы', type: 'chips', def: '',
          hint: 'В selector уйдут выбранные теги — префикс можно дописать потом в форме балансера',
          options: function (c2) {
            return (c2.outbounds || []).map(function (o) { return { value: o.tag, label: o.tag }; });
          } },
        { key: 'strategy', label: 'Стратегия', type: 'select', def: 'roundRobin',
          hint: 'leastPing и leastLoad дополнительно заведут секцию наблюдения',
          options: [
            { value: 'random', label: 'random — случайно' },
            { value: 'roundRobin', label: 'roundRobin — по кругу' },
            { value: 'leastPing', label: 'leastPing — по отклику' },
            { value: 'leastLoad', label: 'leastLoad — по нагрузке' }
          ] },
        { key: 'fallback', label: 'Запасной выход', type: 'select', def: '',
          options: function (c2) {
            return [{ value: '', label: 'без запасного выхода' }].concat(
              (c2.outbounds || []).map(function (o) { return { value: o.tag, label: o.tag }; }));
          } }
      ],
      apply: function (c, p, plan) {
        var r = ensureRouting(c);
        r.balancers = r.balancers || [];
        var tag = p.tag || 'AUTO';
        var strat = p.strategy || 'random';
        var picked = String(p.outs || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean);
        if (picked.length < 2) plan.push('⚠ выбери хотя бы два выхода — балансировать один смысла нет');
        if (r.balancers.some(function (b) { return b.tag === tag; })) {
          plan.push('балансер «' + tag + '» уже есть — оставляем');
        } else {
          var bal = { tag: tag, selector: picked, strategy: { type: strat } };
          if (p.fallback) bal.fallbackTag = p.fallback;
          r.balancers.push(bal);
          plan.push('добавить балансер «' + tag + '» (' + strat + ', выходы: ' + (picked.join(', ') || '—') + ')');
          if (p.fallback) plan.push('запасной выход: ' + p.fallback);
          else plan.push('без запасного выхода недоступность всех кандидатов оборвёт соединения');
        }
        if (strat === 'leastPing' || strat === 'leastLoad') {
          var key = strat === 'leastPing' ? 'observatory' : 'burstObservatory';
          if (!c[key]) {
            c[key] = { subjectSelector: picked, probeUrl: 'https://www.gstatic.com/generate_204', probeInterval: '5m' };
            plan.push('добавить секцию ' + key + ' — иначе ядро не запустится');
          } else {
            plan.push('секция ' + key + ' уже есть');
          }
        }
        var cands = balancerCandidates(c, { selector: picked });
        plan.push(cands.length ? 'кандидатов: ' + cands.join(', ')
                               : '⚠ выбранные выходы не найдены в конфиге — балансер будет битым');
        if (!recRuleExists(c, function (x) { return x.balancerTag === tag; })) {
          recPrependRule(c, { network: 'tcp,udp', balancerTag: tag }, plan,
            'добавить правило: tcp,udp → балансер ' + tag);
        }
      }
    }
  ];

  // План и предпросмотр считаются на лету — как в референсе, без отдельной кнопки
  function recipePlanHtml(tr, c) {
    var h = '';
    if (state.recPlanList.length) {
      h += '<div class="xed-grouphd">' + tr.recWill + '</div><ul class="xed-planlist">'
        + state.recPlanList.map(function (l) {
            return '<li class="' + (l.indexOf('⚠') === 0 ? 'warn' : '') + '">' + esc(l) + '</li>';
          }).join('') + '</ul>';
    }
    if (state.recPreviewCfg && state.recShowDiff) {
      var dh = diffHtml(ser(c), state.recPreviewCfg);
      h += '<div class="xed-diff">' + (dh || '<div class="xed-dline ctx">' + tr.diffNone + '</div>') + '</div>';
    }
    return h;
  }

  function recipeRecalc(full) {
    if (!state.recipe) { render(); return; }
    var out = applyRecipe(state.recipe, state.recParams);
    state.recPreviewCfg = ser(out.cfg);
    state.recPlanList = out.plan;
    var host = document.getElementById('xed-recplan');
    if (host && !full) host.innerHTML = recipePlanHtml(t(), cfg());   // без перерисовки формы
    else render();
  }

  function applyRecipe(recipe, params) {
    var next = clone(cfg());
    var plan = [];
    recipe.apply(next, params, plan);
    return { cfg: next, plan: plan };
  }

  /* ---------- шаблоны конфигураций ----------
     Готовые валидные заготовки для нового профиля: создаются через родное
     POST /api/v2/config-profiles (право resources:create), поэтому попадают
     в общий список профилей и в историю версий как обычный профиль. */

  function randomKeyB64(bytes) {
    var a = new Uint8Array(bytes);
    (window.crypto || window.msCrypto).getRandomValues(a);
    var bin = '';
    for (var i = 0; i < a.length; i++) bin += String.fromCharCode(a[i]);
    return btoa(bin);
  }

  var TEMPLATES = [
    {
      id: 'vless-reality',
      title: 'VLESS + Reality (базовый)',
      note: 'Один inbound на 443 с Reality и sniffing, выходы DIRECT и BLOCK.',
      build: function () {
        return {
          log: { loglevel: 'warning' },
          inbounds: [{
            tag: 'VLESS-IN', protocol: 'vless', port: 443,
            settings: { clients: [], decryption: 'none' },
            streamSettings: { network: 'tcp', security: 'reality',
              realitySettings: { dest: 'www.microsoft.com:443', serverNames: ['www.microsoft.com'],
                privateKey: '', shortIds: [''], minClientVer: '0.0.0' } },
            sniffing: { enabled: true, destOverride: ['http', 'tls', 'quic'] }
          }],
          outbounds: [{ tag: 'DIRECT', protocol: 'freedom' }, { tag: 'BLOCK', protocol: 'blackhole' }],
          routing: { domainStrategy: 'IPIfNonMatch', rules: [] }
        };
      }
    },
    {
      id: 'vless-clean',
      title: 'VLESS + Reality с блокировками',
      note: 'То же плюс правила: торренты и реклама в blackhole.',
      build: function () {
        var c = TEMPLATES[0].build();
        c.routing.rules = [
          { protocol: ['bittorrent'], outboundTag: 'BLOCK' },
          { domain: ['geosite:category-ads-all'], outboundTag: 'BLOCK' }
        ];
        return c;
      }
    },
    {
      id: 'ss2022',
      title: 'Shadowsocks 2022',
      note: 'Инбаунд ss-2022 (метод blake3-aes-256-gcm). Ключ на 32 байта генерируется сразу — конфиг валиден с ходу.',
      build: function () {
        return {
          log: { loglevel: 'warning' },
          inbounds: [{
            tag: 'SS-IN', protocol: 'shadowsocks', port: 443,
            settings: { method: '2022-blake3-aes-256-gcm', password: randomKeyB64(32), network: 'tcp,udp' },
            streamSettings: { network: 'tcp' },
            sniffing: { enabled: true, destOverride: ['http', 'tls'] }
          }],
          outbounds: [{ tag: 'DIRECT', protocol: 'freedom' }, { tag: 'BLOCK', protocol: 'blackhole' }],
          routing: { rules: [] }
        };
      }
    },
    {
      id: 'cascade',
      title: 'Каскад на другую ноду',
      note: 'Инбаунд + VLESS-выход на второй сервер: адрес, UUID и ключи Reality вписать после создания.',
      build: function () {
        var c = TEMPLATES[0].build();
        c.outbounds.push({
          tag: 'chain-out', protocol: 'vless',
          settings: { vnext: [{ address: '', port: 443,
            users: [{ id: '', encryption: 'none', flow: 'xtls-rprx-vision' }] }] },
          streamSettings: { network: 'tcp', security: 'reality',
            realitySettings: { serverName: '', publicKey: '', shortId: '', fingerprint: 'chrome' } }
        });
        c.routing.rules = [{ inboundTag: ['VLESS-IN'], outboundTag: 'chain-out' }];
        return c;
      }
    }
  ];

  // 🔴 Панель требует уникальности тегов инбаундов ГЛОБАЛЬНО (по всем профилям):
  // при совпадении отвечает 409 A113, а админка превращает это в невнятное
  // «Service temporarily unavailable». Поэтому теги уникализируем заранее.
  function uniquifyInboundTags(cfgObj, taken) {
    (cfgObj.inbounds || []).forEach(function (inb) {
      if (!inb.tag) return;
      var base = inb.tag, tag = base, n = 2;
      while (taken.indexOf(tag) >= 0) { tag = base + '-' + n; n++; }
      if (tag !== base) {
        // правила ссылаются на тег — переименовываем и там
        (((cfgObj.routing || {}).rules) || []).forEach(function (r) {
          if (r.inboundTag) r.inboundTag = r.inboundTag.map(function (t2) { return t2 === base ? tag : t2; });
        });
        inb.tag = tag;
      }
      taken.push(tag);
    });
    return cfgObj;
  }

  function takenInboundTags(cb) {
    fetch(apiBase() + '/config-profiles/inbounds', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : { items: [] }; })
      .then(function (d) {
        var items = d.items || d.inbounds || [];
        cb(items.map(function (i) { return i.tag; }).filter(Boolean));
      })
      .catch(function () { cb([]); });
  }

  function createProfile(name, cfgObj, cb) {
    takenInboundTags(function (taken) {
      var body = uniquifyInboundTags(clone(cfgObj), taken.slice());
      fetch(apiBase() + '/config-profiles', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
        body: JSON.stringify({ name: name, config: body })
      }).then(function (r) {
        if (r.ok) return r.json().catch(function () { return {}; });
        return r.json().catch(function () { return {}; }).then(function (b) {
          var msg = b.detail || b.message || ('HTTP ' + r.status);
          if (r.status === 502 || r.status === 409) msg += ' ' + t().hintTags;
          throw new Error(msg);
        });
      }).then(function (resp) {
        var prof = (resp && resp.uuid) ? resp : ((resp || {}).response || null);
        cb(null, prof && prof.uuid ? prof : null);
      }).catch(function (e) { cb(e); });
    });
  }

  // Панель разбора: итог, оговорки, построчный разбор правил
  /* ---------- трассировщик: форма под конфиг, карточка-вердикт, правила по порядку ---------- */
  function rulesUse(c, key) {
    return (((c.routing || {}).rules) || []).some(function (r) {
      var v = r[key];
      return Array.isArray(v) ? v.length > 0 : (v !== undefined && v !== null && v !== '');
    });
  }
  function inboundTagsOf(c) {
    return (c.inbounds || []).map(function (i) { return i.tag; }).filter(Boolean);
  }
  function looksLikeHost(v) {
    v = String(v || '').trim();
    return isIpAddress(v) || /^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$/i.test(v);
  }
  var TR_PROTOS = ['tls', 'http', 'quic', 'bittorrent', 'dns'];

  function traceTarget() {
    var c = cfg();
    var inbs = inboundTagsOf(c);
    var inbound = state.trace.inbound || (inbs.length === 1 ? inbs[0] : '');   // один inbound — он и есть источник
    var portText = String(state.trace.port).trim();
    var ip = String(state.trace.ip || '').trim();
    var src = String(state.trace.sourceIp || '').trim();
    return {
      address: String(state.trace.address).trim(),
      port: /^\d+$/.test(portText) ? Number(portText) : 443,
      network: state.trace.network || 'tcp',
      ip: isIpAddress(ip) ? ip : undefined,
      inboundTag: inbound || undefined,
      protocol: state.trace.protocol || undefined,
      user: String(state.trace.user || '').trim() || undefined,
      sourceIp: isIpAddress(src) ? src : undefined
    };
  }

  // Поля формы — только те, что имеют смысл для ЭТОГО конфига: протокол — если
  // есть правила по protocol; inbound — если инбаундов больше одного или правила
  // их различают; IP домена — если ip-правила вообще применимы к домену
  // (стратегия не AsIs); пользователь и IP клиента — если есть такие правила.
  function traceFormHtml(tr, c) {
    var st = state.trace;
    var inbs = inboundTagsOf(c);
    var strategy = ((c.routing || {}).domainStrategy) || 'AsIs';
    var showIn = inbs.length > 1 || rulesUse(c, 'inboundTag');
    var showProto = rulesUse(c, 'protocol');
    var showIp = rulesUse(c, 'ip') && strategy !== 'AsIs';
    var showUser = rulesUse(c, 'user');
    var showSrc = rulesUse(c, 'source');
    var h = '<div class="xed-dock xed-tracebar">'
      + '<span class="xed-trlbl">' + tr.trWhere + '</span>'
      + '<input id="xed-tr-addr" value="' + esc(st.address) + '" placeholder="youtube.com · 1.1.1.1" autocomplete="off" spellcheck="false">'
      + '<input id="xed-tr-port" class="xed-trport" value="' + esc(st.port) + '" inputmode="numeric" title="' + tr.trPort + '">'
      + '<select id="xed-tr-net"><option value="tcp"' + (st.network === 'tcp' ? ' selected' : '') + '>tcp</option>'
      + '<option value="udp"' + (st.network === 'udp' ? ' selected' : '') + '>udp</option></select>';
    if (showIn) {
      h += '<span class="xed-trlbl">' + tr.trFrom + '</span><select id="xed-tr-in"><option value="">' + tr.trAnyIn + '</option>'
        + inbs.map(function (tg) {
          return '<option value="' + esc(tg) + '"' + (st.inbound === tg ? ' selected' : '') + '>' + esc(tg) + '</option>';
        }).join('') + '</select>';
    }
    h += '<button class="xed-btn" id="xed-tr-close" title="' + tr.trClose + '">✕</button></div>';
    if (showProto || showIp || showUser || showSrc) {
      h += '<div class="xed-dock xed-tracebar xed-tracebar2">';
      if (showProto) {
        h += '<label>' + tr.trProto + '<select id="xed-tr-proto"><option value="">' + tr.trProtoAny + '</option>'
          + TR_PROTOS.map(function (p) {
            return '<option value="' + p + '"' + (st.protocol === p ? ' selected' : '') + '>' + p + '</option>';
          }).join('')
          + '<option value="other"' + (st.protocol === 'other' ? ' selected' : '') + '>' + tr.trProtoOther + '</option></select></label>';
      }
      if (showIp) {
        h += '<label>' + tr.trDomIp + '<input id="xed-tr-ip" value="' + esc(st.ip) + '" placeholder="' + esc(tr.trDomIpPh) + '">'
          + '<button class="xed-btn xed-btn-sm" id="xed-tr-resolve">' + tr.trResolve + '</button></label>';
      }
      if (showUser) h += '<label>' + tr.trUser + '<input id="xed-tr-user" value="' + esc(st.user) + '" placeholder="user@example"></label>';
      if (showSrc) h += '<label>' + tr.trSrc + '<input id="xed-tr-src" value="' + esc(st.sourceIp) + '" placeholder="10.0.0.5"></label>';
      h += '</div>';
    }
    return h;
  }

  function trTargetChip(v, tr) {
    if (v.balancerTag) return '<span class="xed-metric">' + tr.trBal + esc(v.balancerTag) + '</span>';
    if (v.outboundTag) return '<span class="xed-metric accent">' + esc(v.outboundTag) + '</span>';
    return '<span class="xed-metric">' + tr.noTarget + '</span>';
  }
  function trFixLink(f, tr) {
    if (trNeedsGeo(f)) return ' <a class="xed-trfix" data-trgeo="1">' + tr.trGeoDl + '</a>';
    var id = TR_FOCUS[f.code];
    return id ? ' <a class="xed-trfix" data-trfocus="' + id + '">' + tr.trSet + '</a>' : '';
  }
  // Одна строка «почему»: совпало — по чему; промах — первое несовпавшее условие;
  // «нет данных» — чего не хватает и ссылка на нужное поле.
  function trWhy(v, tr) {
    if (v.state === 'skipped') return '';
    var fs = v.fields || [];
    if (!fs.length) return tr.noConds;
    if (v.state === 'yes') return fs.map(function (f) { return esc(trReason(f, tr)); }).join(' · ');
    if (v.state === 'no') {
      var bad = fs.filter(function (f) { return f.state === 'no'; })[0];
      return bad ? esc(trReason(bad, tr)) : '';
    }
    return fs.filter(function (f) { return f.state === 'unknown'; }).map(function (f) {
      return esc(trReason(f, tr)) + trFixLink(f, tr);
    }).join(' · ');
  }
  function trRowHtml(v, rules, tr, extra) {
    var r = rules[v.index] || {};
    var icon = { yes: '✓', no: '✗', unknown: '?', skipped: '·' }[v.state] || '';
    return '<div class="xed-trrow ' + v.state + (extra || '') + '" data-trrule="' + v.index + '">'
      + '<span class="xed-trno">#' + (v.index + 1) + '</span>'
      + '<span class="xed-trbadge ' + v.state + '">' + icon + ' ' + trStateLabel(v.state) + '</span>'
      + '<span class="xed-trarrow">→</span>' + trTargetChip(v, tr)
      + '<span class="xed-trchips">' + ruleChipList(r, tr).map(function (ch) { return '<span>' + esc(ch) + '</span>'; }).join('') + '</span>'
      + '<span class="xed-trwhy">' + trWhy(v, tr) + '</span></div>';
  }
  function trCaveatHtml(cv, tr) {
    if (cv.code === 'geo_off') return tr.trGeoOff + ' <a class="xed-trfix" data-trgeo="1">' + tr.trGeoDl + '</a>';
    if (cv.code === 'geo_missing') return tr.trGeoMissing + esc(cv.v);
    if (cv.code === 'sniff_blind') return esc(trFmt(tr.trSniffBlind, cv));
    if (cv.code === 'need_ip_pass') return tr.trNeedIpPass + ' <a class="xed-trfix" data-trfocus="xed-tr-ip">' + tr.trSet + '</a>';
    return esc(cv.code);
  }

  function tracePanelHtml(tr) {
    var c = cfg();
    var tgt = traceTarget();
    var h = '<div class="xed-tracepanel">';
    if (!tgt.address) {
      return h + '<div class="xed-trempty">' + tr.trEmpty + ' <span class="xed-chip">' + tr.trTry + '</span>'
        + ['youtube.com', 'speedtest.net', '1.1.1.1', '192.168.1.10'].map(function (x) {
          return '<button class="xed-btn xed-btn-sm" data-trex="' + x + '">' + x + '</button>';
        }).join('') + '</div></div>';
    }
    var res = state.traceRes;
    if (!res) return h + '</div>';
    var w = res.winner;
    var shown = res.ipVerdicts || res.verdicts;
    var rules = ((c.routing || {}).rules) || [];
    var hasWinRule = !!(w && w.ruleIndex !== null && w.ruleIndex !== undefined);
    var winIdx = hasWinRule ? w.ruleIndex : shown.length;
    var unknownAbove = shown.filter(function (v) { return v.state === 'unknown' && v.index < winIdx; });

    /* карточка-вердикт: цель → выход; как получилось; насколько точно */
    var tgtLabel = esc(tgt.address) + ':' + tgt.port + ' · ' + esc(tgt.network)
      + (tgt.protocol ? ' · ' + esc(tgt.protocol) : '') + (tgt.inboundTag ? ' · ' + esc(tgt.inboundTag) : '');
    h += '<div class="xed-trcard ' + (!w ? 'bad' : (unknownAbove.length ? 'unsure' : 'sure')) + '">'
      + '<div class="xed-trflow"><span class="xed-trtgt">' + tgtLabel + '</span><span class="xed-trarrow">→</span>';
    if (!w) {
      h += '<span class="xed-trerr">' + tr.trNoOut + '</span>';
    } else if (w.balancerTag) {
      var cands = w.balancerCandidates || [];
      h += '<span class="xed-metric">' + tr.trBal + esc(w.balancerTag) + ' · ' + esc(w.balancerStrategy || 'random') + '</span>'
        + '<span class="xed-trarrow">→</span>'
        + (cands.length
          ? cands.map(function (t2) { return '<span class="xed-trout">' + esc(t2) + '</span>'; }).join('<span class="xed-tror">/</span>')
          : '<span class="xed-trerr">' + tr.trBalNone + '</span>');
    } else {
      h += '<span class="xed-trout">' + esc(w.outboundTag) + '</span>';
      var ob = (c.outbounds || []).filter(function (o) { return o.tag === w.outboundTag; })[0];
      if (ob && ob.protocol) h += '<span class="xed-chip">' + esc(ob.protocol) + '</span>';
    }
    h += '</div>';
    if (w) {
      if (!hasWinRule) {
        h += '<div class="xed-trhow">' + tr.trDefault + '</div>';
      } else {
        var wv = shown.filter(function (v) { return v.index === w.ruleIndex; })[0];
        h += '<div class="xed-trhow">' + tr.trByRule + (w.ruleIndex + 1) + ' · '
          + esc(ruleChipList(rules[w.ruleIndex] || {}, tr).join(' · ')) + (wv ? ' — ' + trWhy(wv, tr) : '') + '</div>';
      }
      if (res.ipVerdicts) {
        h += '<div class="xed-trhow">' + tr.trPass1 + ' → ' + tr.trPass2 + esc(tgt.ip)
          + ' <span class="xed-chip">' + tr.trPassHint + '</span></div>';
      }
      if (unknownAbove.length) {
        h += '<div class="xed-trconf unsure"><b>⚠ ' + tr.trUnsure + '</b> — ' + tr.trUnsureWhy + '<ul>'
          + unknownAbove.map(function (v) {
            return '<li>#' + (v.index + 1) + ' ' + trTargetChip(v, tr) + ' ' + trWhy(v, tr) + '</li>';
          }).join('') + '</ul></div>';
      } else {
        h += '<div class="xed-trconf sure">✓ ' + tr.trSure + '</div>';
      }
    }
    if (res.caveats && res.caveats.length) {
      h += '<ul class="xed-trcaveats">' + res.caveats.map(function (cv) {
        return '<li>' + trCaveatHtml(cv, tr) + '</li>';
      }).join('') + '</ul>';
    }
    h += '</div>';

    /* правила по порядку: до сработавшего включительно — подробно, дальше — свёрнуто */
    var above = shown.filter(function (v) { return v.index <= winIdx; });
    var below = shown.filter(function (v) { return v.index > winIdx; });
    h += '<div class="xed-trhd">' + tr.trOrder + '<span>' + tr.trOrderHint + '</span></div>';
    h += '<div class="xed-trrules">' + above.map(function (v) {
      return trRowHtml(v, rules, tr, hasWinRule && v.index === winIdx ? ' win' : '');
    }).join('');
    if (below.length) {
      h += '<div class="xed-trtoggle" data-trtoggle="1">' + (state.traceUi.showBelow ? '▾ ' : '▸ ') + below.length + tr.trBelow
        + ' · ' + (state.traceUi.showBelow ? tr.trHide : tr.trShow) + '</div>';
      if (state.traceUi.showBelow) {
        h += below.map(function (v) {
          return trRowHtml({ index: v.index, state: 'skipped', outboundTag: v.outboundTag, balancerTag: v.balancerTag, fields: v.fields }, rules, tr, '');
        }).join('');
      }
    }
    h += '</div></div>';
    return h;
  }

  function refreshTrace() {
    recomputeTrace();
    var host = document.getElementById('xed-tracehost');
    if (host) { host.innerHTML = tracePanelHtml(t()); bindTracePanel(); }   // точечно: фокус в поле не теряем
    if (state.repaintCanvas) state.repaintCanvas();
  }
  function bindTracePanel() {
    var root = state.root;
    if (!root) return;
    root.querySelectorAll('[data-trrule]').forEach(function (el) {
      el.addEventListener('click', function () {
        state.node = 'rule:' + el.getAttribute('data-trrule'); state.mode = 'form'; render();
      });
    });
    root.querySelectorAll('[data-trfocus]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        var f = document.getElementById(el.getAttribute('data-trfocus'));
        if (!f) return;
        f.focus();
        if (f.scrollIntoView) f.scrollIntoView({ block: 'center', behavior: 'smooth' });
        f.classList.add('xed-trflash');
        setTimeout(function () { f.classList.remove('xed-trflash'); }, 1600);
      });
    });
    root.querySelectorAll('[data-trgeo]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.stopPropagation();
        el.textContent = t().geoBusy;
        downloadGeo(function () { refreshTrace(); });
      });
    });
    root.querySelectorAll('[data-trex]').forEach(function (el) {
      el.addEventListener('click', function () {
        state.trace.address = el.getAttribute('data-trex');
        var inp = document.getElementById('xed-tr-addr');
        if (inp) inp.value = state.trace.address;
        refreshTrace();
      });
    });
    root.querySelectorAll('[data-trtoggle]').forEach(function (el) {
      el.addEventListener('click', function () { state.traceUi.showBelow = !state.traceUi.showBelow; refreshTrace(); });
    });
  }
  // Скачать geo-базы (ссылки из диалога «Geo-базы» или пресет по умолчанию) и позвать then(msg)
  function downloadGeo(then) {
    state.geoBusy = true;
    fetch(pluginBase() + '/geo/download', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
      body: JSON.stringify({ urls: state.geoUrls || {} })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        state.geoBusy = false;
        state.geoStatus = d.status || null; state.geoCats = null;
        state.geo = { loaded: false, answers: {}, missing: [] };
        var errs = d.errors || {};
        var msg = Object.keys(errs).length ? Object.keys(errs).map(function (k) { return k + ': ' + errs[k]; }).join('; ') : '';
        state.geoMsg = msg;
        then(msg);
      })
      .catch(function (e) { state.geoBusy = false; state.geoMsg = e.message; then(e.message); });
  }
  // «узнать» IP домена — резолвит бэкенд плагина (DNS админки может отличаться от нодового, но для проверки хватает)
  function resolveTraceHost() {
    var tgt = traceTarget();
    var inp = document.getElementById('xed-tr-ip');
    if (!tgt.address || !inp) return;
    inp.placeholder = '…';
    fetch(pluginBase() + '/tools/resolve?host=' + encodeURIComponent(tgt.address), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var ips = (d && d.ips) || [];
        if (!ips.length) { inp.placeholder = t().trNoResolve; inp.title = (d && d.error) || ''; return; }
        state.trace.ip = ips[0]; inp.value = ips[0]; inp.title = ips.join(', ');
        refreshTrace();
      })
      .catch(function () { inp.placeholder = t().trNoResolve; });
  }

  function loadGeoStatus() {
    fetch(pluginBase() + '/geo/status', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) { state.geoStatus = d; if (state.dialog === 'geo') render(); })
      .catch(function () { state.geoStatus = {}; if (state.dialog === 'geo') render(); });
  }

  function loadGeoCats() {
    fetch(pluginBase() + '/geo/categories?kind=' + state.geoKind + '&query=' + encodeURIComponent(state.geoCatQ || ''),
          { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) { state.geoCats = d.items || []; if (state.dialog === 'geo') render(); })
      .catch(function () { state.geoCats = []; if (state.dialog === 'geo') render(); });
  }

  function loadGeoRows() {
    if (!state.geoCode) return;
    fetch(pluginBase() + '/geo/entries?kind=' + state.geoKind + '&code=' + encodeURIComponent(state.geoCode)
          + '&offset=' + state.geoOff + '&limit=100&query=' + encodeURIComponent(state.geoRowQ || ''),
          { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) { state.geoRows = d; if (state.dialog === 'geo') render(); })
      .catch(function () { state.geoRows = { items: [], total: 0 }; if (state.dialog === 'geo') render(); });
  }

  function loadSubsList(openFirst) {
    return fetch(pluginBase() + '/subs', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        state.subs = d.items || [];
        if (d.error) state.subsMsg = d.error;
        if (openFirst && state.subs.length && !state.subsSel) loadSubsDoc(state.subs[0].uuid);
        else render();
      })
      .catch(function (e) { state.subs = []; state.subsMsg = e.message; render(); });
  }

  function loadSubsDoc(uuid) {
    state.subsSel = uuid; state.subsDoc = null; state.subsMsg = '';
    render();
    fetch(pluginBase() + '/subs/' + encodeURIComponent(uuid), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) { state.subsMsg = d.error; render(); return; }
        state.subsDoc = d;
        state.subsDirty = false; state.subsRaw = false; state.subsCfg = null;
        state.hist = { past: [], future: [] };
        state.node = null; state.pos = {};
        if (d.format === 'json') {
          try { state.subsCfg = JSON.parse(d.text || '{}'); }
          catch (e) { state.subsMsg = t().badJson + e.message; state.subsRaw = true; }
        }
        render();
      })
      .catch(function (e) { state.subsMsg = e.message; render(); });
  }

  function recomputeTrace() {
    if (!state.trace.on || !String(state.trace.address).trim()) { state.traceRes = null; return; }
    state.traceRes = traceRoute(cfg(), traceTarget(), state.geo);
    fetchGeoAnswers();
  }

  // Вердикты по geosite:/geoip: считает бэкенд плагина (базы лежат в его томе).
  // Дебаунс 600 мс — чтобы не дёргать сервер на каждую букву в поле адреса.
  function fetchGeoAnswers() {
    var keys = geoKeysOf(cfg());
    if (!keys.length) return;
    if (state.geoTimer) clearTimeout(state.geoTimer);
    state.geoTimer = setTimeout(function () {
      var target = traceTarget();
      fetch(pluginBase() + '/geo/match', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
        body: JSON.stringify({ domain: target.address, ip: target.ip, keys: keys })
      })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (!d) return;
          state.geo = { loaded: !!d.loaded, answers: d.answers || {}, missing: d.missing || [] };
          if (state.trace.on) {
            state.traceRes = traceRoute(cfg(), traceTarget(), state.geo);
            var host = document.getElementById('xed-tracehost');
            if (host) { host.innerHTML = tracePanelHtml(t()); bindTracePanel(); }
            if (state.repaintCanvas) state.repaintCanvas();
          }
        })
        .catch(function () {});
    }, 600);
  }

  /* ---------- рендер ---------- */

  function render() {
    var root = state.root;
    if (!root) return;
    cleanupCodeUi();                 // всплывашки прежнего редактора кода
    var tr = t();
    var p = selProfile();
    var c = cfg();
    var issues = p ? lint(c) : [];
    var errs = issues.filter(function (i) { return i.level === 'error'; }).length;
    var warns = issues.filter(function (i) { return i.level === 'warn'; }).length;
    var isDirty = dirty();

    var subsScreen = state.screen === 'subs';
    var pickScreen = state.screen === 'picker';
    /* холст и нижний док показываем только там, где есть схема */
    var graphOn = (state.screen === 'profile' && state.tab === 'topo' && p)
      || (subsScreen && isSubsJson() && !state.subsRaw);
    var html = '<div class="xed-root">';
    html += '<h1 class="xed-h1">' + (pickScreen ? tr.pickTitle : subsScreen ? tr.subsTitle : tr.title) + '</h1>'
      + '<p class="xed-sub">' + (pickScreen ? tr.pickHint : subsScreen ? tr.subsSub : tr.sub) + '</p>';

    if (pickScreen) {
      /* витрина: сверху конфиг-профили, ниже шаблоны подписок — вход в редактор */
      html += '<div class="xed-bar">'
        + '<span class="xed-chip">' + tr.pickProfiles + state.profiles.length + '</span>'
        + '<span class="xed-chip">' + tr.pickSubsCnt + (state.subs === null ? '…' : state.subs.length) + '</span>'
        + '<button class="xed-btn primary" id="xed-pick-new">' + tr.pickNew + '</button>'
        + '<span class="xed-meta">' + esc(state.toast || '') + '</span>'
        + '</div>';
      html += '<div class="xed-grid">' + state.profiles.map(function (pr) {
        var pc = pr.config || {};
        var inb = (pc.inbounds || [])[0];
        var chips = [];
        if (inb) {
          if (inb.port != null) chips.push(':' + inb.port);
          var ss = inb.streamSettings || {};
          if (ss.network) chips.push(ss.network);
          if (ss.security && ss.security !== 'none') chips.push(ss.security);
        }
        var nn = (pr.nodes || []).length;
        var isDraftHere = state.sel === pr.uuid && isDirty;
        return '<div class="xed-pcard" data-pick-profile="' + esc(pr.uuid) + '">'
          + '<div class="xed-pcard-hd"><b>' + esc(pr.name) + '</b>'
          + (isDraftHere ? '<span class="xed-chip draft">' + tr.draft + '</span>' : '') + '</div>'
          + '<div class="xed-pcard-in">'
          + (inb ? '<code>' + esc(inb.tag || inb.protocol || '') + '</code>'
                   + chips.map(function (x) { return '<span class="xed-chip">' + esc(x) + '</span>'; }).join('')
                 : '<span class="xed-hint">' + tr.pickEmptyIn + '</span>')
          + '</div>'
          + '<div class="xed-pcard-ft"><span>' + (nn ? nn + tr.pickNodes : tr.pickNoNodes) + '</span>'
          + '<span>' + (pr.updatedAt ? new Date(pr.updatedAt).toLocaleString(lang() === 'en' ? 'en-GB' : 'ru-RU') : '') + '</span></div>'
          + '</div>';
      }).join('') + '</div>';
      html += '<div class="xed-grouphd xed-picksep">' + tr.pickSubsHd + '</div>';
      if (state.subs === null) {
        html += '<div class="xed-hint">' + tr.pickLoading + '</div>';
      } else {
        html += '<div class="xed-grid">' + state.subs.map(function (x) {
          return '<div class="xed-pcard" data-pick-tpl="' + esc(x.uuid) + '">'
            + '<div class="xed-pcard-hd"><b>' + esc(x.name) + '</b></div>'
            + '<div class="xed-pcard-in"><span class="xed-chip">' + esc(x.type) + '</span></div>'
            + '<div class="xed-pcard-ft"><span>' + esc(x.type.indexOf('XRAY') === 0 ? 'JSON' : 'YAML') + '</span><span></span></div>'
            + '</div>';
        }).join('') + '</div>';
        if (state.subsMsg) html += '<div class="xed-err">' + esc(state.subsMsg) + '</div>';
      }
    } else if (subsScreen) {
      /* отдельный экран шаблонов подписки: свой тулбар, без органов управления профилем */
      html += '<div class="xed-bar">';
      html += '<button class="xed-btn" id="xed-subs-back">' + tr.subsBack + '</button>';
      html += '<select id="xed-subs-sel">'
        + (state.subs === null ? '<option>' + tr.loading + '</option>'
           : (state.subs || []).map(function (x) {
               return '<option value="' + esc(x.uuid) + '"' + (state.subsSel === x.uuid ? ' selected' : '') + '>'
                 + esc(x.type) + ' · ' + esc(x.name) + '</option>';
             }).join(''))
        + '</select>';
      html += '<button class="xed-btn" id="xed-subs-new">' + tr.subsNew + '</button>';
      if (state.subsDoc) {
        /* тип виден в самом селекторе (XRAY_JSON · имя), отдельный чип только дублировал */
        if (state.subsDoc.format === 'json') {
          html += '<button class="xed-btn" id="xed-subs-toggle">'
            + (state.subsRaw ? tr.subsGraph : tr.subsRaw) + '</button>';
          html += '<button class="xed-btn" id="xed-geo">' + tr.geoBtn + '</button>';
          html += '<button class="xed-btn primary" id="xed-check">✓ ' + tr.checkBtn + '</button>';
        }
        if (state.subsDirty) html += '<span class="xed-chip draft">' + tr.subsDirtyChip + '</span>';
        html += '<button class="xed-btn primary" id="xed-subs-save"'
          + ((state.subsBusy || !state.subsDirty) ? ' disabled' : '') + '>' + tr.subsSave + '</button>';
      }
      html += '<span class="xed-meta">' + esc(state.subsMsg || '') + '</span>';
      html += '</div>';
      html += '<div class="xed-card"><div class="xed-hint">' + tr.subsNote + '</div>';
      if (!state.subsDoc) {
        html += '<div class="xed-hint">' + (state.subsSel ? tr.subsLoad : '') + '</div>';
      } else if (state.subsDoc.format === 'json' && !state.subsRaw) {
        html += '<div class="xed-main"><div id="xed-canvas" class="xed-cwrap"></div></div>';
      } else {
        html += '<textarea id="xed-subs-text" class="xed-fulljson">' + esc(state.subsDoc.text || '') + '</textarea>';
        html += '<div class="xed-err" id="xed-subs-err"></div>';
      }
    } else {
    html += '<div class="xed-bar">';
    html += '<button class="xed-btn" id="xed-back-pick">' + tr.subsBack + '</button>';
    html += '<span class="xed-curname">' + esc(p ? p.name : '') + '</span>';
    html += '<button class="xed-btn" id="xed-addrule">' + tr.addRule + '</button>';
    html += '<button class="xed-btn" id="xed-addout">' + tr.addOut + '</button>';
    html += '<button class="xed-btn" id="xed-undo"' + (state.hist.past.length ? '' : ' disabled') + '>' + tr.undo + '</button>';
    html += '<button class="xed-btn" id="xed-redo"' + (state.hist.future.length ? '' : ' disabled') + '>' + tr.redo + '</button>';
    html += '<button class="xed-btn" id="xed-versions">' + tr.versions + '</button>';
    html += '<button class="xed-btn" id="xed-cfgset">' + tr.cfgSettings + '</button>';
    html += '<button class="xed-btn" id="xed-geo">' + tr.geoBtn + '</button>';
    html += '<button class="xed-btn primary" id="xed-check">✓ ' + tr.checkBtn + '</button>';
    html += '<span class="xed-tabs2">'
      + '<button class="xed-tab2' + (state.tab === 'topo' ? ' on' : '') + '" id="xed-tab-topo">' + tr.tabTopo + '</button>'
      + '<button class="xed-tab2' + (state.tab === 'json' ? ' on' : '') + '" id="xed-tab-json">' + tr.tabJson + '</button>'
      + '</span>';
    if (hasPos()) html += '<button class="xed-btn" id="xed-respos" title="' + esc(tr.resetPos) + '">' + tr.resetPos + '</button>';
    if (isDirty) {
      html += '<span class="xed-chip draft">' + tr.draft + '</span>';
      html += '<button class="xed-btn" id="xed-reset">' + tr.reset + '</button>';
    }
    var saveBlocked = errs > 0;
    html += '<button class="xed-btn primary" id="xed-save"' + ((isDirty && !saveBlocked) ? '' : ' disabled') +
      (saveBlocked ? ' title="' + esc(tr.saveBlocked) + '"' : '') + '>' + tr.save + '</button>';
    if (p) {
      var nn = (p.nodes || []).length;
      html += '<span class="xed-chip">' + (nn ? nn + tr.nodesUse : tr.nodesUseNone) + '</span>';
    }
    html += '<span class="xed-meta">' + esc(state.toast || (p && p.updatedAt ? tr.updated + new Date(p.updatedAt).toLocaleString(lang() === 'en' ? 'en-GB' : 'ru-RU') : '')) + '</span>';
    html += '</div>';
      if (state.tab === 'json') {
        html += '<div class="xed-card"><textarea id="xed-fulljson" class="xed-fulljson">' + esc(ser(c)) + '</textarea>'
          + '<div class="xed-err" id="xed-fulljson-err"></div>'
          + '<div class="xed-row"><button class="xed-btn primary" id="xed-fulljson-apply">' + tr.apply2 + '</button></div>';
      } else {
        html += '<div class="xed-card"><div class="xed-main"><div id="xed-canvas" class="xed-cwrap"></div></div>';
      }
    }
    if (!pickScreen && (!subsScreen || isSubsJson())) {
    html += '<div class="xed-issues"><div class="hd">' + tr.issues + ': ' +
      (issues.length ? tr.errors + errs + ' · ' + tr.warns + warns : tr.noIssues) + '</div>';
    html += issues.map(function (it, idx) {
      return '<div class="xed-issue" data-issue="' + idx + '"><span class="xed-dot ' + it.level + '"></span><span>' +
        (it.node ? '<b>' + esc(it.node) + '</b> — ' : '') + esc(it.msg) + '</span></div>';
    }).join('');
    html += '</div>';
    }
    var dockOn = graphOn;
    if (dockOn) {
    html += '<div class="xed-dock">'
      + '<button class="xed-btn" id="xed-addin">' + tr.addIn + '</button>'
      + '<button class="xed-btn" id="xed-addout">' + tr.addOut + '</button>'
      + '<button class="xed-btn" id="xed-addrule">' + tr.addRule + '</button>'
      + '<button class="xed-btn" id="xed-addbal">' + tr.addBal + '</button>'
      + '<input id="xed-search" placeholder="' + esc(tr.searchPh) + '" value="' + esc(state.search || '') + '">'
      + '<button class="xed-btn" id="xed-recipes">' + tr.recipes + '</button>'
      + '<button class="xed-btn' + (state.trace.on ? ' primary' : '') + '" id="xed-trace">' + tr.traceBtn + '</button>'
      + (hasPos() ? '<button class="xed-btn" id="xed-respos">' + tr.resetPos + '</button>' : '')
      + '<span class="xed-zoom"><button class="xed-btn" id="xed-zin">' + tr.zoomIn + '</button>'
      + '<button class="xed-btn" id="xed-zout">' + tr.zoomOut + '</button>'
      + '<button class="xed-btn" id="xed-zfit">' + tr.zoomFit + '</button></span>'
      + '<span class="xed-chip" id="xed-searchres"></span>'
      + '</div>';
    if (state.trace.on) {
      html += traceFormHtml(tr, c);
      html += '<div id="xed-tracehost">' + tracePanelHtml(tr) + '</div>';
    }
    }
    html += '</div></div>';
    root.innerHTML = html;

    var canvasOn = graphOn;
    if (canvasOn) document.getElementById('xed-canvas').innerHTML = renderSvg(buildGraph(c), issues, state.node, tr);
    // Лёгкая перерисовка только холста (для перетаскивания — без пересборки страницы)
    state.repaintCanvas = function () {
      var el = document.getElementById('xed-canvas');
      if (el) el.innerHTML = renderSvg(buildGraph(c), issues, state.node, tr);
    };
    if (canvasOn) setupDrag();
    setupCodeEditor();     // на вкладке JSON и в сыром шаблоне подписки — полноценный редактор кода

    /* инспектор */
    if (p && (state.node || state.wholeJson)) {
      var obj = state.wholeJson ? c : nodeObj(c, state.node);
      if (obj != null) {
        var insp = document.createElement('div');
        insp.className = 'xed-insp';
        var title = state.wholeJson ? tr.wholeJson : state.node;
        var kind = state.wholeJson ? null : state.node.split(':')[0];
        var hasForm = !state.wholeJson && formHtml(state.node, obj, c, tr) !== '';
        var h = '<h3>' + esc(title) + '<button class="xed-btn xed-x" id="xed-close">' + tr.inspClose + '</button></h3>';
        var nodeIssues = issues.filter(function (i) { return !state.wholeJson && i.node === state.node; });
        h += nodeIssues.map(function (it) {
          return '<div class="xed-issue"><span class="xed-dot ' + it.level + '"></span><span>' + esc(it.msg) + '</span></div>';
        }).join('');
        if (hasForm) {
          h += '<div class="xed-tabs">' +
            // id не должны совпадать с верхними вкладками страницы (xed-tab-topo / xed-tab-json):
            // on() вешает обработчик по getElementById, и клик по инспектору уходил на верхнюю вкладку
            '<button class="xed-tab' + (state.mode === 'form' ? ' on' : '') + '" id="xed-insp-form">' + tr.formTab + '</button>' +
            '<button class="xed-tab' + (state.mode === 'json' ? ' on' : '') + '" id="xed-insp-json">' + tr.jsonTab + '</button></div>';
        }
        if (!state.wholeJson && hasForm && state.mode === 'form') {
          h += formHtml(state.node, obj, c, tr);
          h += '<div class="xed-row"><button class="xed-btn primary" id="xed-apply">' + tr.apply + '</button>';
          if (kind === 'rule') {
            var ri = +state.node.split(':')[1];
            h += '<button class="xed-btn" id="xed-up">' + tr.up + '</button><button class="xed-btn" id="xed-down">' + tr.down + '</button>';
          }
          h += '<button class="xed-btn danger" id="xed-del">' + tr.delNode + '</button></div>';
        } else {
          h += '<textarea id="xed-nodejson">' + esc(JSON.stringify(obj, null, 2)) + '</textarea>';
          h += '<div class="xed-err" id="xed-jsonerr"></div>';
          h += '<div class="xed-row"><button class="xed-btn primary" id="xed-apply-json">' + tr.apply + '</button>';
          if (!state.wholeJson) h += '<button class="xed-btn danger" id="xed-del">' + tr.delNode + '</button>';
          h += '</div>';
        }
        insp.innerHTML = h;
        (root.querySelector('.xed-main') || root.querySelector('.xed-card')).appendChild(insp);
      }
    }

    /* диалоги */
    if (state.dialog === 'diff' || state.dialog === 'saving') {
      var ov = document.createElement('div');
      ov.className = 'xed-overlay';
      var dh = diffHtml(ser(panelCfg()), ser(c));
      ov.innerHTML = '<div class="xed-dialog"><h3>' + tr.diffTitle + '</h3>' +
        '<p class="xed-dwarn">' + tr.diffWarn + '</p>' +
        '<div class="xed-diff">' + (dh || '<div class="xed-dline ctx">' + tr.diffNone + '</div>') + '</div>' +
        '<div class="xed-row"><button class="xed-btn primary" id="xed-dconfirm"' + (state.dialog === 'saving' ? ' disabled' : '') + '>' + tr.confirm + '</button>' +
        '<button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ov);
    }
    if (state.dialog === 'verdiff') {
      var ovd = document.createElement('div');
      ovd.className = 'xed-overlay';
      var dh2 = diffHtml(state.verCompare || '', ser(c));   // слева версия, справа текущее
      ovd.innerHTML = '<div class="xed-dialog"><h3>' + tr.verDiff + '</h3>' +
        '<div class="xed-diff">' + (dh2 || '<div class="xed-dline ctx">' + tr.diffNone + '</div>') + '</div>' +
        '<div class="xed-row"><button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ovd);
    }
    if (state.dialog === 'recipes') {
      var ovr = document.createElement('div');
      ovr.className = 'xed-overlay';
      var left = RECIPES.map(function (r) {
        return '<div class="xed-recrow' + (state.recipe && state.recipe.id === r.id ? ' sel' : '') + '" data-recipe="' + r.id + '">'
          + '<b>' + esc(r.title) + '</b><div class="xed-hint">' + esc(r.note) + '</div></div>';
      }).join('');
      var right;
      if (!state.recipe) {
        right = '<div class="xed-hint">' + tr.tplPick + '</div>';
      } else {
        var rc = state.recipe;
        right = rc.params.map(function (f) {
          var val = state.recParams[f.key] !== undefined ? state.recParams[f.key] : f.def;
          var body;
          // опции бывают статическим списком и функцией от конфига (теги выходов/инбаундов)
          var fopts = typeof f.options === 'function' ? f.options(c) : (f.options || []);
          if (f.type === 'select') {
            body = '<select data-recp="' + esc(f.key) + '">' + fopts.map(function (o) {
              return '<option value="' + esc(o.value) + '"' + (String(val) === String(o.value) ? ' selected' : '') + '>'
                + esc(o.label) + '</option>';
            }).join('') + '</select>';
          } else if (f.type === 'chips') {
            var chosen = String(val || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean);
            body = '<div class="xed-chips" data-recchips="' + esc(f.key) + '">' + fopts.map(function (o) {
              return '<button type="button" class="xed-chipbtn' + (chosen.indexOf(o.value) >= 0 ? ' on' : '')
                + '" data-v="' + esc(o.value) + '">' + esc(o.label) + '</button>';
            }).join('') + '</div>';
          } else if (f.type === 'textarea') {
            body = '<textarea data-recp="' + esc(f.key) + '" placeholder="' + esc(f.ph || '') + '">' + esc(val) + '</textarea>';
          } else {
            body = '<input type="text" data-recp="' + esc(f.key) + '" value="' + esc(val) + '" placeholder="' + esc(f.ph || '') + '">';
          }
          return '<div class="xed-field"><label>' + esc(f.label) + '</label>' + body
            + (f.hint ? '<div class="xed-hint">' + esc(f.hint) + '</div>' : '') + '</div>';
        }).join('');
        right += '<div id="xed-recplan">' + recipePlanHtml(tr, c) + '</div>';
        right += '<div class="xed-row">'
          + '<button class="xed-btn" id="xed-rec-diff">' + tr.recShowDiff + '</button>'
          + '<button class="xed-btn primary" id="xed-rec-apply">' + tr.recApply + '</button></div>';
      }
      ovr.innerHTML = '<div class="xed-dialog xed-dialog-wide"><h3>' + tr.recipesTitle + '</h3>'
        + '<div class="xed-recgrid"><div class="xed-reclist">' + left + '</div>'
        + '<div class="xed-recbody">' + right + '</div></div>'
        + '<div class="xed-row"><button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ovr);
    }
    if (state.dialog === 'subsnew') {
      var ovn = document.createElement('div');
      ovn.className = 'xed-overlay';
      ovn.innerHTML = '<div class="xed-dialog"><h3>' + tr.subsNewTitle + '</h3>'
        + '<div class="xed-field"><label>' + tr.subsType + '</label><select id="xed-subsnew-type">'
        + ['XRAY_JSON', 'MIHOMO', 'STASH', 'CLASH', 'SINGBOX'].map(function (x) {
            return '<option value="' + x + '">' + x + '</option>'; }).join('')
        + '</select></div>'
        + '<div class="xed-field"><label>' + tr.subsName + '</label>'
        + '<input type="text" id="xed-subsnew-name" placeholder="my-template"></div>'
        + '<div class="xed-err" id="xed-subsnew-err"></div>'
        + '<div class="xed-row"><button class="xed-btn primary" id="xed-subsnew-create">' + tr.subsCreate + '</button>'
        + '<button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ovn);
    }
    if (state.dialog === 'geo') {
      var ovg = document.createElement('div');
      ovg.className = 'xed-overlay';
      var st = state.geoStatus || {};
      var urls = state.geoUrls || {};
      var inner = '<div class="xed-tabs2 xed-geotabs">'
        + '<button class="xed-tab2' + (state.geoTab === 'src' ? ' on' : '') + '" id="xed-geo-tsrc">' + tr.geoTabSrc + '</button>'
        + '<button class="xed-tab2' + (state.geoTab === 'view' ? ' on' : '') + '" id="xed-geo-tview">' + tr.geoTabView + '</button>'
        + '</div>';
      if (state.geoTab === 'src') {
        inner += '<div class="xed-hint">' + tr.geoNote + '</div>';
        inner += ['geosite.dat', 'geoip.dat'].map(function (f) {
          var v = st[f] || {};
          var right = v.present
            ? '<span class="xed-chip">' + (v.categories || 0) + tr.geoCats + '</span>'
              + '<span class="xed-chip">' + (Math.round((v.size || 0) / 1048576 * 10) / 10) + ' МБ</span>'
              + (v.mtime ? '<span class="xed-chip">' + tr.geoUpd + new Date(v.mtime * 1000).toLocaleString(lang() === 'en' ? 'en-GB' : 'ru-RU') + '</span>' : '')
            : '<span class="xed-chip">' + tr.geoAbsent + '</span>';
          return '<div class="xed-verrow"><span>' + f.replace('.dat', '') + '</span>' + right + '</div>';
        }).join('');
        inner += '<div class="xed-field"><label>' + tr.geoSrcSite + '</label>'
          + '<input type="text" id="xed-geo-u1" value="' + esc(urls['geosite.dat'] || '') + '"></div>';
        inner += '<div class="xed-field"><label>' + tr.geoSrcIp + '</label>'
          + '<input type="text" id="xed-geo-u2" value="' + esc(urls['geoip.dat'] || '') + '"></div>';
        inner += '<div class="xed-row"><span class="xed-chip">' + tr.geoPresets + '</span>'
          + '<button class="xed-btn" data-geopreset="v2fly">v2fly</button>'
          + '<button class="xed-btn" data-geopreset="loyalsoldier">Loyalsoldier</button></div>';
        if (state.geoMsg) inner += '<div class="xed-err">' + esc(state.geoMsg) + '</div>';
        inner += '<div class="xed-row"><button class="xed-btn primary" id="xed-geo-dl"'
          + (state.geoBusy ? ' disabled' : '') + '>' + (state.geoBusy ? tr.geoBusy : tr.geoDl) + '</button></div>';
      } else {
        inner += '<div class="xed-row">'
          + '<select id="xed-geo-kind">'
          + '<option value="geosite"' + (state.geoKind === 'geosite' ? ' selected' : '') + '>' + tr.geoKindSite + '</option>'
          + '<option value="geoip"' + (state.geoKind === 'geoip' ? ' selected' : '') + '>' + tr.geoKindIp + '</option>'
          + '</select>'
          + '<input type="text" id="xed-geo-catq" placeholder="' + esc(tr.geoFindCat) + '" value="' + esc(state.geoCatQ) + '">'
          + '</div>';
        inner += '<div class="xed-geobrowse"><div class="xed-geocats">';
        if (state.geoCats === null) inner += '<div class="xed-hint">' + tr.loading + '</div>';
        else if (!state.geoCats.length) inner += '<div class="xed-hint">—</div>';
        else inner += state.geoCats.map(function (c) {
          return '<div class="xed-geocat' + (state.geoCode === c.code ? ' sel' : '') + '" data-geocat="' + esc(c.code) + '">'
            + '<span>' + esc(c.code) + '</span><span class="xed-chip">' + c.count + '</span></div>';
        }).join('');
        inner += '</div><div class="xed-geovals">';
        if (!state.geoCode) inner += '<div class="xed-hint">—</div>';
        else if (state.geoRows === null) inner += '<div class="xed-hint">' + tr.loading + '</div>';
        else {
          inner += '<input type="text" id="xed-geo-valq" placeholder="' + esc(tr.geoFindVal) + '" value="' + esc(state.geoRowQ) + '">';
          inner += (state.geoRows.items || []).map(function (r) {
            return '<div class="xed-georow"><span class="xed-geokind">' + esc(r.kind) + '</span><code>' + esc(r.value) + '</code></div>';
          }).join('') || '<div class="xed-hint">—</div>';
          var off = state.geoRows.offset || 0, tot = state.geoRows.total || 0;
          var to = Math.min(off + (state.geoRows.items || []).length, tot);
          inner += '<div class="xed-row"><span class="xed-chip">' + tr.geoShown + (tot ? (off + 1) : 0) + '–' + to + tr.geoOf + tot + '</span>'
            + '<button class="xed-btn" id="xed-geo-prev"' + (off <= 0 ? ' disabled' : '') + '>' + tr.geoPrev + '</button>'
            + '<button class="xed-btn" id="xed-geo-next"' + (to >= tot ? ' disabled' : '') + '>' + tr.geoNext + '</button></div>';
        }
        inner += '</div></div>';
        if (state.geoCode) {
          var token = (state.geoKind === 'geosite' ? 'geosite:' : 'geoip:') + String(state.geoCode).toLowerCase();
          inner += '<div class="xed-row"><code class="xed-token">' + esc(token) + '</code>'
            + '<button class="xed-btn" id="xed-geo-copy">' + tr.geoCopy + '</button>'
            + '<button class="xed-btn primary" id="xed-geo-torule">' + tr.geoToRule + '</button>'
            + (state.geoMsg ? '<span class="xed-chip">' + esc(state.geoMsg) + '</span>' : '') + '</div>';
        }
      }
      ovg.innerHTML = '<div class="xed-dialog xed-dialog-wide"><h3>' + tr.geoTitle + '</h3>' + inner +
        '<div class="xed-row"><button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ovg);
    }
    if (state.dialog === 'tpl') {
      var ovt = document.createElement('div');
      ovt.className = 'xed-overlay';
      var list = '<div class="xed-grouphd">' + tr.tplLocal + '</div>' + TEMPLATES.map(function (tp) {
        return '<div class="xed-recrow' + (state.tpl === tp.id && !state.tplRemote ? ' sel' : '') + '" data-tpl="' + tp.id + '">' +
          '<b>' + esc(tp.title) + '</b><div class="xed-hint">' + esc(tp.note) + '</div></div>';
      }).join('');
      list += '<div class="xed-grouphd">' + tr.tplGallery + '</div>';
      if (state.gallery === null) {
        list += '<div class="xed-hint">' + tr.tplLoading + '</div>';
      } else if (state.galleryErr) {
        list += '<div class="xed-err">' + esc(tr.tplGalleryErr + state.galleryErr) + '</div>';
      } else if (!state.gallery.length) {
        list += '<div class="xed-hint">—</div>';
      } else {
        list += state.gallery.map(function (g) {
          return '<div class="xed-recrow' + (state.tplRemote === g.path ? ' sel' : '') + '" data-tplr="' + esc(g.path) + '">' +
            '<b>' + esc(g.title) + '</b><div class="xed-hint">' + tr.tplBy + esc(g.author) + '</div></div>';
        }).join('');
      }
      // рецепты «из коробки» — те, что не требуют параметров
      var pre = PRESET_RECIPES.map(function (id) {
        var rc = RECIPES.filter(function (x) { return x.id === id; })[0];
        if (!rc) return '';
        return '<label class="xed-tplrec"><input type="checkbox" data-tplrec="' + esc(id) + '"'
          + (state.tplRecipes[id] ? ' checked' : '') + '> ' + esc(rc.title) + '</label>';
      }).join('');
      ovt.innerHTML = '<div class="xed-dialog"><h3>' + tr.tplTitle + '</h3>' + list +
        '<div class="xed-field"><label>' + tr.tplName + '</label>' +
        '<input type="text" id="xed-tpl-name" value="' + esc(state.tplName || '') + '" placeholder="my-profile"></div>' +
        '<div class="xed-grouphd">' + tr.recPre + '</div><div class="xed-tplrecs">' + pre + '</div>' +
        '<div class="xed-err" id="xed-tpl-err"></div>' +
        '<div class="xed-row"><button class="xed-btn primary" id="xed-tpl-create"' + ((state.tpl || state.tplRemoteCfg) ? '' : ' disabled') + '>' +
        tr.tplCreate + '</button><button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ovt);
    }
    if (state.dialog === 'cfgset') {
      var ovs = document.createElement('div');
      ovs.className = 'xed-overlay';
      var rt = c.routing || {}, lg = c.log || {};
      function opt(list, cur, labels) {
        return list.map(function (v) {
          var lab = (labels && labels[v]) || v || '—';
          return '<option value="' + esc(v) + '"' + (v === cur ? ' selected' : '') + '>' + esc(lab) + '</option>';
        }).join('');
      }
      ovs.innerHTML = '<div class="xed-dialog"><h3>' + tr.cfgTitle + '</h3>'
        + '<div class="xed-grouphd">' + tr.cfgRouting + '</div>'
        + '<div class="xed-field"><label>' + tr.domStrategy + '</label>'
        + '<select id="xed-cs-strategy">' + opt(['', 'AsIs', 'IPIfNonMatch', 'IPOnDemand'], rt.domainStrategy || '',
            { '': 'не задана (AsIs)' }) + '</select>'
        + '<div class="xed-hint">' + tr.cfgStratHint + '</div></div>'
        + '<div class="xed-field"><label>' + tr.domMatcher + '</label>'
        + '<select id="xed-cs-matcher">' + opt(['', 'hybrid', 'linear'], rt.domainMatcher || '',
            { '': 'не задан (hybrid)' }) + '</select>'
        + '<div class="xed-hint">' + tr.cfgMatchHint + '</div></div>'
        + '<div class="xed-grouphd">' + tr.cfgLog + '</div>'
        + '<div class="xed-field"><label>' + tr.logLevel + '</label>'
        + '<select id="xed-cs-log">' + opt(['', 'debug', 'info', 'warning', 'error', 'none'], lg.loglevel || '',
            { '': 'не задан (warning)' }) + '</select></div>'
        + '<div class="xed-field"><label>' + tr.cfgAccess + '</label>'
        + '<input type="text" id="xed-cs-access" value="' + esc(lg.access || '') + '" placeholder="/var/log/xray/access.log">'
        + '<div class="xed-hint">' + tr.cfgPathHint + '</div></div>'
        + '<div class="xed-field"><label>' + tr.cfgError + '</label>'
        + '<input type="text" id="xed-cs-error" value="' + esc(lg.error || '') + '" placeholder="/var/log/xray/error.log">'
        + '<div class="xed-hint">' + tr.cfgPathHint + '</div></div>'
        + '<div class="xed-field"><label class="xed-checkline"><input type="checkbox" id="xed-cs-dnslog"'
        + (lg.dnsLog ? ' checked' : '') + '> ' + tr.cfgDns + '</label></div>'
        + '<div class="xed-row"><button class="xed-btn primary" id="xed-cs-apply">' + tr.apply2 + '</button>'
        + '<button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ovs);
    }
    if (state.dialog === 'check') {
      var ovc = document.createElement('div');
      ovc.className = 'xed-overlay';
      var cr = state.check;
      var inner = '<div class="xed-hint">' + tr.checkNote + '</div>';
      if (state.checkBusy) {
        inner += '<div class="xed-hint">' + tr.checkBusy + '</div>';
      } else if (!cr) {
        inner += '<div class="xed-hint">—</div>';
      } else if (cr.available === false) {
        inner += '<div class="xed-err">' + tr.checkNoBin + '</div>'
          + '<div class="xed-row"><button class="xed-btn primary" id="xed-check-dl">' + tr.checkDl + '</button></div>';
      } else if (cr.available !== true) {
        // ответ не от плагина (401/403/5xx, {"detail": …}) — не прятать его за «отвергло конфиг»
        inner += '<div class="xed-err">' + esc(tr.checkHttp + (cr.detail || cr.error || JSON.stringify(cr))) + '</div>';
      } else {
        inner += cr.ok
          ? '<div class="xed-okline">✓ ' + tr.checkOk + (cr.version ? ' · ' + esc(cr.version) : '') + '</div>'
          : '<div class="xed-err">✕ ' + tr.checkBad + '</div>';
        (cr.errors || []).forEach(function (e) {
          inner += '<div class="xed-checkrow err"><code>' + esc(e.text) + '</code>'
            + (e.hint ? '<div class="xed-hint">' + esc(e.hint) + '</div>' : '') + '</div>';
        });
        if (cr.needGeo) {
          inner += '<div class="xed-row"><button class="xed-btn primary" id="xed-check-geo">' + tr.checkGeoDl + '</button></div>';
        }
        if ((cr.warnings || []).length) {
          inner += '<div class="xed-grouphd">' + tr.checkWarn + '</div>';
          (cr.warnings || []).forEach(function (w) {
            inner += '<div class="xed-checkrow warn"><code>' + esc(w.text) + '</code>'
              + (w.hint ? '<div class="xed-hint">' + esc(w.hint) + '</div>' : '') + '</div>';
          });
        }
      }
      ovc.innerHTML = '<div class="xed-dialog"><h3>' + tr.checkTitle + '</h3>' + inner +
        '<div class="xed-row"><button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ovc);
    }
    if (state.dialog === 'versions') {
      var ovv = document.createElement('div');
      ovv.className = 'xed-overlay';
      var rows;
      if (state.versions === null) rows = '<div class="xed-issue">' + tr.loading + '</div>';
      else if (!state.versions.length) rows = '<div class="xed-issue">' + esc(state.verErr || tr.verEmpty) + '</div>';
      else rows = state.versions.map(function (v) {
        var when = v.created_at ? new Date(v.created_at).toLocaleString(lang() === 'en' ? 'en-GB' : 'ru-RU') : '';
        return '<div class="xed-verrow"><span>' + esc(when) + '</span>' +
          '<span class="xed-chip">' + tr.verBy + esc(v.created_by || '—') + '</span>' +
          '<span class="xed-chip">' + (v.size_bytes || 0) + tr.verBytes + '</span>' +
          '<button class="xed-btn" data-verdiff="' + v.id + '">' + tr.verDiff + '</button>' +
          '<button class="xed-btn primary" data-verload="' + v.id + '">' + tr.verLoad + '</button></div>';
      }).join('');
      ovv.innerHTML = '<div class="xed-dialog"><h3>' + tr.versionsTitle + '</h3>' + rows +
        '<div class="xed-row"><button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ovv);
    }
    if (state.dialog === 'conflict') {
      var ov2 = document.createElement('div');
      ov2.className = 'xed-overlay';
      ov2.innerHTML = '<div class="xed-dialog"><h3>' + tr.conflictTitle + '</h3>' +
        '<p class="xed-dwarn">' + tr.conflictBody + '</p>' +
        '<div class="xed-row"><button class="xed-btn" id="xed-cload">' + tr.conflictLoad + '</button>' +
        '<button class="xed-btn danger" id="xed-cforce">' + tr.conflictForce + '</button>' +
        '<button class="xed-btn" id="xed-dcancel">' + tr.cancel + '</button></div></div>';
      root.querySelector('.xed-root').appendChild(ov2);
    }

    bind(issues);
  }

  function on(id, fn) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('click', fn);
  }

  function bind(issues) {
    var root = state.root;
    var sel_ = document.getElementById('xed-sel');
    if (sel_) sel_.addEventListener('change', function () {
      state.sel = sel_.value; state.node = null; state.wholeJson = false;
      state.hist = { past: [], future: [] };
      loadDraftLS();
      loadPos();
      render();
    });
    on('xed-respos', function () { state.pos = {}; persistPos(); render(); });
    on('xed-addin', addInbound);
    on('xed-addbal', addBalancer);
    var sb = document.getElementById('xed-search');
    if (sb) sb.addEventListener('input', function () {
      state.search = sb.value;
      var hits = searchNodes(cfg(), state.search);
      var out = document.getElementById('xed-searchres');
      if (out) out.textContent = state.search ? (hits.length ? t().found + hits.length : t().notFound) : '';
      if (state.search && hits.length) { state.node = hits[0]; if (state.repaintCanvas) state.repaintCanvas(); }
    });

    on('xed-addrule', addRule);
    on('xed-addout', addOutbound);
    on('xed-undo', undo);
    on('xed-redo', redo);
    on('xed-reset', function () {
      if (window.confirm(t().confirmReset)) { clearDraft(); state.node = null; render(); }
    });
    on('xed-save', startSave);
    on('xed-close', function () { state.node = null; state.wholeJson = false; render(); });
    on('xed-insp-form', function () { state.mode = 'form'; render(); });
    on('xed-insp-json', function () { state.mode = 'json'; render(); });
    on('xed-apply', function () {
      var obj = nodeObj(cfg(), state.node);
      if (obj) setNode(state.node, readForm(state.node, obj));
    });
    on('xed-apply-json', function () {
      var el = document.getElementById('xed-nodejson');
      try {
        var parsed = JSON.parse(el.value);
        if (state.wholeJson) writeDraft(parsed);
        else setNode(state.node, parsed);
      } catch (e) {
        var err = document.getElementById('xed-jsonerr');
        if (err) err.textContent = t().badJson + e.message;
      }
    });
    on('xed-del', function () {
      if (window.confirm(t().confirmDel)) setNode(state.node, null);
    });
    on('xed-up', function () { moveRule(+state.node.split(':')[1], -1); });
    on('xed-down', function () { moveRule(+state.node.split(':')[1], 1); });
    on('xed-trace', function () {
      state.trace.on = !state.trace.on;
      // в поиск по графу уже вписали домен/IP — второй раз не спрашиваем
      if (state.trace.on && !String(state.trace.address).trim() && looksLikeHost(state.search)) {
        state.trace.address = String(state.search).trim();
      }
      if (!state.trace.on) state.traceRes = null; else recomputeTrace();
      render();
      if (state.trace.on) {
        var host = document.getElementById('xed-tracehost');
        if (host && host.scrollIntoView) host.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        var a = document.getElementById('xed-tr-addr');
        if (a && !a.value) a.focus();
      }
    });
    on('xed-tr-close', function () { state.trace.on = false; state.traceRes = null; render(); });
    [['addr', 'address'], ['port', 'port'], ['ip', 'ip'], ['user', 'user'], ['src', 'sourceIp']].forEach(function (p) {
      var el = document.getElementById('xed-tr-' + p[0]);
      if (el) el.addEventListener('input', function () { state.trace[p[1]] = el.value; refreshTrace(); });
    });
    [['net', 'network'], ['in', 'inbound'], ['proto', 'protocol']].forEach(function (p) {
      var el = document.getElementById('xed-tr-' + p[0]);
      if (el) el.addEventListener('change', function () { state.trace[p[1]] = el.value; refreshTrace(); });
    });
    on('xed-tr-resolve', resolveTraceHost);
    bindTracePanel();
    on('xed-tab-topo', function () { state.tab = 'topo'; render(); });
    on('xed-tab-json', function () { state.tab = 'json'; state.node = null; render(); });
    function openPicker() {
      state.screen = 'picker'; state.node = null; state.wholeJson = false;
      state.trace.on = false; state.toast = '';
      render();
      if (state.subs === null) loadSubsList();
    }
    on('xed-back-pick', openPicker);
    if (root) root.querySelectorAll('[data-pick-profile]').forEach(function (el) {
      el.addEventListener('click', function () {
        var uuid = el.getAttribute('data-pick-profile');
        if (uuid !== state.sel) {
          state.sel = uuid; state.draft = null; state.node = null;
          state.pos = {}; state.hist = { past: [], future: [] };
        }
        state.screen = 'profile'; state.tab = 'topo'; render();
      });
    });
    if (root) root.querySelectorAll('[data-pick-tpl]').forEach(function (el) {
      el.addEventListener('click', function () {
        state.screen = 'subs'; state.node = null; state.subsMsg = '';
        loadSubsDoc(el.getAttribute('data-pick-tpl'));
      });
    });
    on('xed-subs-back', openPicker);
    on('xed-open-subs', function () {
      state.screen = 'subs'; state.node = null; state.wholeJson = false;
      state.trace.on = false; state.subsMsg = '';
      render();
      if (state.subs === null) loadSubsList(true);
    });
    var ssel = document.getElementById('xed-subs-sel');
    if (ssel) ssel.addEventListener('change', function () { loadSubsDoc(ssel.value); });
    on('xed-subs-new', function () { state.dialog = 'subsnew'; render(); });
    on('xed-subsnew-create', function () {
      var nm = (document.getElementById('xed-subsnew-name') || {}).value || '';
      var tp = (document.getElementById('xed-subsnew-type') || {}).value || 'XRAY_JSON';
      var err = document.getElementById('xed-subsnew-err');
      if (nm.trim().length < 2) { if (err) err.textContent = t().tplNameBad; return; }
      fetch(pluginBase() + '/subs', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
        body: JSON.stringify({ name: nm.trim(), type: tp })
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.error) { if (err) err.textContent = t().subsFail + d.error; return; }
          state.dialog = null; state.subs = null; state.subsMsg = t().subsCreated;
          fetch(pluginBase() + '/subs', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (l) {
              state.subs = l.items || [];
              if (d.uuid) loadSubsDoc(d.uuid); else render();
            });
        })
        .catch(function (e) { if (err) err.textContent = t().subsFail + e.message; });
    });
    on('xed-subs-toggle', function () { state.subsRaw = !state.subsRaw; state.node = null; render(); });
    on('xed-subs-save', function () {
      if (!state.subsDoc) return;
      var text = codeValue('xed-subs-text') || (state.subsCfg ? ser(state.subsCfg) : state.subsDoc.text);
      state.subsBusy = true; state.subsMsg = ''; render();
      fetch(pluginBase() + '/subs/' + encodeURIComponent(state.subsDoc.uuid), {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
        body: JSON.stringify({ type: state.subsDoc.type, text: text })
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          state.subsBusy = false;
          state.subsDoc.text = text;
          if (!d.error) { state.subsDirty = false; if (ta) { try { state.subsCfg = JSON.parse(text); } catch (e) {} } }
          state.subsMsg = d.error ? (t().subsFail + d.error) : t().subsSaved;
          render();
        })
        .catch(function (e) { state.subsBusy = false; state.subsMsg = t().subsFail + e.message; render(); });
    });
    on('xed-cfgset', function () { state.dialog = 'cfgset'; render(); });
    on('xed-cs-apply', function () {
      var st = (document.getElementById('xed-cs-strategy') || {}).value;
      var mt = (document.getElementById('xed-cs-matcher') || {}).value;
      var lv = (document.getElementById('xed-cs-log') || {}).value;
      var ac = (document.getElementById('xed-cs-access') || {}).value;
      var er = (document.getElementById('xed-cs-error') || {}).value;
      var dl = (document.getElementById('xed-cs-dnslog') || {}).checked;
      patch(function (cc) {
        var r = cc.routing = cc.routing || {};
        setOrDel(r, 'domainStrategy', st || null);
        setOrDel(r, 'domainMatcher', mt || null);
        if (!Object.keys(r).length) delete cc.routing;
        var l = cc.log = cc.log || {};
        setOrDel(l, 'loglevel', lv || null);
        setOrDel(l, 'access', (ac || '').trim() || null);
        setOrDel(l, 'error', (er || '').trim() || null);
        if (dl) l.dnsLog = true; else delete l.dnsLog;
        if (!Object.keys(l).length) delete cc.log;
      });
      state.dialog = null;
      render();
    });
    on('xed-fulljson-apply', function () {
      try { writeDraft(JSON.parse(codeValue('xed-fulljson'))); }
      catch (e) {
        var er = document.getElementById('xed-fulljson-err');
        if (er) er.textContent = t().badJson + e.message;
      }
    });
    // зум/пан: кнопки, колесо, перетаскивание пустого места холста
    on('xed-zin', function () { state.view.k = Math.min(2.5, state.view.k * 1.25); if (state.repaintCanvas) state.repaintCanvas(); });
    on('xed-zout', function () { state.view.k = Math.max(0.3, state.view.k / 1.25); if (state.repaintCanvas) state.repaintCanvas(); });
    on('xed-zfit', function () { state.view = { k: 1, tx: 0, ty: 0 }; if (state.repaintCanvas) state.repaintCanvas(); });
    var cv = document.getElementById('xed-canvas');
    if (cv) cv.addEventListener('wheel', function (e) {
      if (!e.ctrlKey && !e.metaKey) return;      // обычная прокрутка страницы не перехватывается
      e.preventDefault();
      var k = state.view.k * (e.deltaY < 0 ? 1.1 : 1 / 1.1);
      state.view.k = Math.max(0.3, Math.min(2.5, k));
      if (state.repaintCanvas) state.repaintCanvas();
    }, { passive: false });
    on('xed-recipes', function () {
      state.dialog = 'recipes'; state.recipe = null; state.recParams = {};
      state.recPreviewCfg = null; state.recPlanList = []; render();
    });
    if (root) root.querySelectorAll('[data-recipe]').forEach(function (el) {
      el.addEventListener('click', function () {
        var id = el.getAttribute('data-recipe');
        state.recipe = RECIPES.filter(function (r) { return r.id === id; })[0];
        state.recParams = {};
        state.recipe.params.forEach(function (f) { state.recParams[f.key] = f.def; });
        state.recPreviewCfg = null; state.recPlanList = []; state.recShowDiff = false;
        recipeRecalc(true);
      });
    });
    if (root) root.querySelectorAll('input[data-recp],textarea[data-recp]').forEach(function (el) {
      el.addEventListener('input', function () {
        state.recParams[el.getAttribute('data-recp')] = el.value;
        if (state.recTimer) clearTimeout(state.recTimer);
        state.recTimer = setTimeout(recipeRecalc, 400);   // план обновляется на лету
      });
    });
    on('xed-rec-diff', function () { state.recShowDiff = !state.recShowDiff; recipeRecalc(); });
    if (root) root.querySelectorAll('[data-recchips]').forEach(function (box) {
      box.querySelectorAll('.xed-chipbtn').forEach(function (b) {
        b.addEventListener('click', function () {
          b.classList.toggle('on');
          var key = box.getAttribute('data-recchips');
          state.recParams[key] = Array.prototype.filter.call(box.querySelectorAll('.xed-chipbtn'), function (x) {
            return x.classList.contains('on');
          }).map(function (x) { return x.getAttribute('data-v'); }).join(',');
          recipeRecalc();
        });
      });
    });
    if (root) root.querySelectorAll('select[data-recp]').forEach(function (el) {
      el.addEventListener('change', function () { state.recParams[el.getAttribute('data-recp')] = el.value; recipeRecalc(); });
    });
    on('xed-rec-apply', function () {
      writeDraft(JSON.parse(state.recPreviewCfg));   // только в черновик, панель — отдельной кнопкой
      state.dialog = null; state.recipe = null; state.recPreviewCfg = null; state.recPlanList = [];
      render();
    });
    function openTplDialog() {
      state.dialog = 'tpl'; state.tpl = null; state.tplName = ''; state.tplRecipes = {};
      state.tplRemote = null; state.tplRemoteCfg = null; state.gallery = null; state.galleryErr = '';
      render();
      fetch(pluginBase() + '/templates/remote', { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          state.gallery = d.items || [];
          state.galleryErr = d.error || '';
          if (state.dialog === 'tpl') render();
        })
        .catch(function (e) { state.gallery = []; state.galleryErr = e.message; if (state.dialog === 'tpl') render(); });
    }
    on('xed-tpl', openTplDialog);
    on('xed-pick-new', openTplDialog);
    if (root) root.querySelectorAll('[data-tplrec]').forEach(function (el) {
      el.addEventListener('change', function () {
        state.tplRecipes[el.getAttribute('data-tplrec')] = el.checked;
      });
    });
    if (root) root.querySelectorAll('[data-tplr]').forEach(function (el) {
      el.addEventListener('click', function () {
        var nameEl0 = document.getElementById('xed-tpl-name');
        if (nameEl0) state.tplName = nameEl0.value;
        var path = el.getAttribute('data-tplr');
        state.tplRemote = path; state.tpl = null; state.tplRemoteCfg = null;
        render();
        fetch(pluginBase() + '/templates/remote/raw?path=' + encodeURIComponent(path), { credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d.error) { state.galleryErr = d.error; }
            else { state.tplRemoteCfg = d.config; }
            if (state.dialog === 'tpl') render();
          })
          .catch(function (e) { state.galleryErr = e.message; if (state.dialog === 'tpl') render(); });
      });
    });
    if (root) root.querySelectorAll('[data-tpl]').forEach(function (el) {
      el.addEventListener('click', function () {
        var nameEl = document.getElementById('xed-tpl-name');
        if (nameEl) state.tplName = nameEl.value;
        state.tpl = el.getAttribute('data-tpl'); state.tplRemote = null; state.tplRemoteCfg = null; render();
      });
    });
    on('xed-tpl-create', function () {
      var nameEl = document.getElementById('xed-tpl-name');
      var name = (nameEl ? nameEl.value : '').trim();
      var err = document.getElementById('xed-tpl-err');
      if (!/^[A-Za-z0-9_\s-]{2,30}$/.test(name)) { if (err) err.textContent = t().tplNameBad; return; }
      // шаблон бывает двух видов: встроенный (state.tpl) и из галереи
      // (state.tplRemoteCfg) — раньше ветка галереи молча выходила
      var tp = TEMPLATES.filter(function (x) { return x.id === state.tpl; })[0];
      var built = state.tplRemoteCfg ? clone(state.tplRemoteCfg) : (tp ? tp.build() : null);
      if (!built) { if (err) err.textContent = t().tplPick; return; }
      // отмеченные рецепты вмешиваем в конфиг ДО создания — тем же кодом, что и в редакторе
      PRESET_RECIPES.forEach(function (rid) {
        if (!state.tplRecipes[rid]) return;
        var rc = RECIPES.filter(function (x) { return x.id === rid; })[0];
        if (rc) rc.apply(built, {}, []);
      });
      createProfile(name, built, function (e, prof) {
        if (e) { if (err) err.textContent = t().tplFail + e.message; return; }
        state.dialog = null; state.toast = t().tplOk;
        state.node = null; state.pos = {}; state.hist = { past: [], future: [] };
        state.screen = 'profile'; state.tab = 'topo';   // сразу открываем созданный профиль
        if (prof) {
          // 🔴 Список профилей у админки кэшируется до 60 с — свежесозданный там
          // ещё не появится. Берём объект прямо из ответа на создание и
          // открываем его сразу; фоновая перезагрузка догонит позже.
          state.profiles = [prof].concat(state.profiles.filter(function (x) { return x.uuid !== prof.uuid; }));
          state.sel = prof.uuid;
          render();
          setTimeout(function () { if (state.root) load(true); }, 61000);
        } else {
          load(true);
        }
      });
    });
    on('xed-check', function () {
      state.dialog = 'check'; state.check = null; state.checkBusy = true; render();
      fetch(pluginBase() + '/xray/check', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
        body: JSON.stringify({ config: cfg() })
      })
        .then(function (r) {
          return r.json().then(function (d) {
            if (!r.ok && d && d.available === undefined) d.detail = 'HTTP ' + r.status + ' ' + (d.detail || '');
            return d;
          });
        })
        .then(function (d) { state.check = d; state.checkBusy = false; render(); })
        .catch(function (e) { state.check = { available: true, ok: false, errors: [{ text: e.message }] };
                              state.checkBusy = false; render(); });
    });
    on('xed-check-geo', function () {
      // geo-базы нужны ядру для geoip:/geosite: в правилах — качаем и повторяем проверку
      state.checkBusy = true; render();
      downloadGeo(function (msg) {
        state.checkBusy = false;
        if (msg) { state.check = { available: true, ok: false, errors: [{ text: msg }] }; render(); return; }
        document.getElementById('xed-check') && document.getElementById('xed-check').click();
      });
    });
    on('xed-check-dl', function () {
      state.checkBusy = true; render();
      fetch(pluginBase() + '/xray/download', { method: 'POST', credentials: 'same-origin',
        headers: { 'X-CSRF-Token': csrfToken() } })
        .then(function (r) { return r.json(); })
        .then(function () {
          state.checkBusy = false;
          document.getElementById('xed-check') && document.getElementById('xed-check').click();
        })
        .catch(function () { state.checkBusy = false; render(); });
    });
    on('xed-geo', function () {
      state.dialog = 'geo'; state.geoStatus = null; state.geoMsg = '';
      if (!state.geoUrls) state.geoUrls = {
        'geosite.dat': 'https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat',
        'geoip.dat': 'https://github.com/v2fly/geoip/releases/latest/download/geoip.dat'
      };
      render();
      loadGeoStatus();
    });
    on('xed-geo-tsrc', function () { state.geoTab = 'src'; state.geoMsg = ''; render(); });
    on('xed-geo-tview', function () {
      state.geoTab = 'view'; state.geoMsg = '';
      render();
      if (state.geoCats === null) loadGeoCats();
    });
    if (root) root.querySelectorAll('[data-geopreset]').forEach(function (b) {
      b.addEventListener('click', function () {
        var v2 = b.getAttribute('data-geopreset') === 'v2fly';
        state.geoUrls = v2 ? {
          'geosite.dat': 'https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat',
          'geoip.dat': 'https://github.com/v2fly/geoip/releases/latest/download/geoip.dat'
        } : {
          'geosite.dat': 'https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat',
          'geoip.dat': 'https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat'
        };
        render();
      });
    });
    var gk = document.getElementById('xed-geo-kind');
    if (gk) gk.addEventListener('change', function () {
      state.geoKind = gk.value; state.geoCats = null; state.geoCode = null; state.geoRows = null;
      render(); loadGeoCats();
    });
    var gq = document.getElementById('xed-geo-catq');
    if (gq) gq.addEventListener('input', function () {
      state.geoCatQ = gq.value;
      if (state.geoCatTimer) clearTimeout(state.geoCatTimer);
      state.geoCatTimer = setTimeout(loadGeoCats, 300);
    });
    if (root) root.querySelectorAll('[data-geocat]').forEach(function (el) {
      el.addEventListener('click', function () {
        state.geoCode = el.getAttribute('data-geocat'); state.geoOff = 0; state.geoRowQ = '';
        state.geoRows = null; state.geoMsg = ''; render(); loadGeoRows();
      });
    });
    var gvq = document.getElementById('xed-geo-valq');
    if (gvq) gvq.addEventListener('input', function () {
      state.geoRowQ = gvq.value; state.geoOff = 0;
      if (state.geoRowTimer) clearTimeout(state.geoRowTimer);
      state.geoRowTimer = setTimeout(loadGeoRows, 300);
    });
    on('xed-geo-prev', function () { state.geoOff = Math.max(0, state.geoOff - 100); loadGeoRows(); });
    on('xed-geo-next', function () { state.geoOff = state.geoOff + 100; loadGeoRows(); });
    on('xed-geo-copy', function () {
      var token = (state.geoKind === 'geosite' ? 'geosite:' : 'geoip:') + String(state.geoCode).toLowerCase();
      try { navigator.clipboard.writeText(token); state.geoMsg = '✓'; } catch (e) { state.geoMsg = token; }
      render();
    });
    on('xed-geo-torule', function () {
      // вставляем токен в выбранное правило (или в первое, если ничего не выбрано)
      var token = (state.geoKind === 'geosite' ? 'geosite:' : 'geoip:') + String(state.geoCode).toLowerCase();
      var rules = ((cfg().routing || {}).rules) || [];
      if (!rules.length) { state.geoMsg = t().geoNoRule; render(); return; }
      var idx = 0;
      if (state.node && state.node.indexOf('rule:') === 0) idx = +state.node.split(':')[1];
      var field = state.geoKind === 'geosite' ? 'domain' : 'ip';
      patch(function (c) {
        var r = ensureRouting(c).rules[idx];
        r[field] = (r[field] || []).concat([token]);
      });
      state.dialog = null; state.node = 'rule:' + idx; state.mode = 'form';
      state.toast = t().geoInserted + '#' + (idx + 1);
      render();
    });
    on('xed-geo-dl', function () {
      state.geoBusy = true; render();
      var u1 = document.getElementById('xed-geo-u1'), u2 = document.getElementById('xed-geo-u2');
      state.geoUrls = { 'geosite.dat': u1 ? u1.value : '', 'geoip.dat': u2 ? u2.value : '' };
      fetch(pluginBase() + '/geo/download', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
        body: JSON.stringify({ urls: state.geoUrls })
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          state.geoBusy = false;
          state.geoStatus = d.status || null;
          state.geoCats = null;                                      // индекс сменился
          state.geo = { loaded: false, answers: {}, missing: [] };
          var errs = d.errors || {};
          state.geoMsg = Object.keys(errs).length ? Object.keys(errs).map(function (k) { return k + ': ' + errs[k]; }).join('; ') : '';
          render();
          if (state.trace.on) recomputeTrace();
        })
        .catch(function () { state.geoBusy = false; render(); });
    });
    on('xed-versions', loadVersions);
    if (root) root.querySelectorAll('[data-verload]').forEach(function (b) {
      b.addEventListener('click', function () {
        versionContent(b.getAttribute('data-verload'), function (cfgObj) {
          writeDraft(cfgObj);              // в черновик, не в панель — сохранение отдельным шагом
          state.dialog = null;
          state.toast = t().verLoaded;
          render();
        });
      });
    });
    if (root) root.querySelectorAll('[data-verdiff]').forEach(function (b) {
      b.addEventListener('click', function () {
        versionContent(b.getAttribute('data-verdiff'), function (cfgObj) {
          state.verCompare = ser(cfgObj);
          state.dialog = 'verdiff';
          render();
        });
      });
    });
    on('xed-dconfirm', function () { confirmSave(false); });
    on('xed-dcancel', function () { state.dialog = null; state.conflict = null; render(); });
    on('xed-cload', conflictLoadPanel);
    on('xed-cforce', function () { confirmSave(true); });

    // чипы инспектора: переключение по клику, коммит по «Применить».
    // Чипы рецептов (внутри [data-recchips]) имеют свой обработчик — иначе
    // сработали бы оба и переключение отменяло само себя.
    if (root) root.querySelectorAll('.xed-chipbtn').forEach(function (b) {
      if (b.closest('[data-recchips]')) return;
      b.addEventListener('click', function () { b.classList.toggle('on'); });
    });

    var canvas = document.getElementById('xed-canvas');
    if (canvas) canvas.addEventListener('click', function (e) {
      if (state._suppressClick) { state._suppressClick = false; return; }  // это было перетаскивание
      var el = e.target;
      while (el && el !== canvas && !(el.getAttribute && el.getAttribute('data-node'))) el = el.parentNode;
      if (el && el !== canvas) {
        state.wholeJson = false;
        state.node = el.getAttribute('data-node');
        state.mode = 'form';
        render();
      }
    });
    if (root) root.querySelectorAll('[data-issue]').forEach(function (el) {
      el.addEventListener('click', function () {
        var it = issues[+el.getAttribute('data-issue')];
        if (it && it.node) { state.wholeJson = false; state.node = it.node; state.mode = 'form'; render(); }
      });
    });
  }

  function keyHandler(e) {
    var mod = e.metaKey || e.ctrlKey;
    if (!mod) return;
    var tag = (e.target && e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
    else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') { e.preventDefault(); redo(); }
  }

  function load(force) {
    var root = state.root;
    if (!root) return;
    if (!state.profiles.length || force) {
      root.innerHTML = '<div class="xed-root"><h1 class="xed-h1">' + t().title + '</h1><p class="xed-sub">' + t().loading + '</p></div>';
    }
    fetch(apiBase() + '/config-profiles', { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        state.profiles = d.items || [];
        if (!state.sel && state.profiles.length) state.sel = state.profiles[0].uuid;
        loadDraftLS();
        loadPos();
        render();
        state.toast = '';
        // витрина показывает обе сущности сразу — тянем список шаблонов подписки
        if (state.subs === null) loadSubsList();
      })
      .catch(function (e) {
        root.innerHTML = '<div class="xed-root"><h1 class="xed-h1">' + t().title + '</h1><p class="xed-sub">' +
          esc(t().loadFail + e.message) + '</p></div>';
      });
  }

  function mount(el) {
    ensureStyle();
    state.root = el;
    state.node = null;
    state.wholeJson = false;
    state.dialog = null;
    state.toast = '';
    load(false);
    document.addEventListener('keydown', keyHandler);
    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', onDragUp);
    if (state.timer) clearInterval(state.timer);
    state.timer = setInterval(function () {
      var l = lang();
      if (l !== state.curLang) { state.curLang = l; if (state.root) render(); }
    }, 700);
  }

  function unmount() {
    if (state.timer) { clearInterval(state.timer); state.timer = null; }
    document.removeEventListener('keydown', keyHandler);
    document.removeEventListener('mousemove', onDragMove);
    document.removeEventListener('mouseup', onDragUp);
    dragState = null;
    cleanupCodeUi();                 // подсказки живут в body — иначе останутся на чужой странице
    state.cm = null;
    state.root = null;
  }

  window.__xrayEditor = { mount: mount, unmount: unmount };

/*__CODE__*/

  var auto = document.getElementById('xed-root');
  if (auto) mount(auto);
})();
"""

APP_JS = APP_JS.replace("/*__CODE__*/", SCHEMA_JS + CODE_JS).replace("/*__CODECSS__*/", "")
