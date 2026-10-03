# Третьи стороны / Third-party notices

Этот плагин — порт на Python/vanilla JS функциональности проекта
**[VAQYBIN/Remnawave-Xray-UI-Editor](https://github.com/VAQYBIN/Remnawave-Xray-UI-Editor)**
(MIT License, Copyright (c) 2026 VAQYBIN): граф топологии, формы по протоколам,
линтер целостности (`analyzeIntegrity`, `compat`), трассировщик маршрута
(`trace`, `traceMatch`), рецепты, серверные инструменты (x25519, проба
Reality-цели). Код переписан под Plugin API remnawave-admin, но идеи, структура
проверок и тексты подсказок во многом следуют оригиналу.

This plugin is a port of **VAQYBIN/Remnawave-Xray-UI-Editor** (MIT License,
Copyright (c) 2026 VAQYBIN) to the remnawave-admin Plugin API. The code was
rewritten in Python / vanilla JS, but the ideas, the integrity checks and many
hint texts follow the original.

---

**CodeMirror 5.65.16** — `rwa_xray_editor/vendor/cm.js`, `cm.css`.
MIT License, Copyright (C) 2017 by Marijn Haverbeke <marijn@haverbeke.berlin> and others.
Полный текст — `rwa_xray_editor/vendor/CODEMIRROR-LICENSE.txt`. Собрано в один файл:
lib + mode/javascript + addons (hint, lint, matchbrackets, closebrackets, fold,
active-line, searchcursor).

---

Во время работы плагин по команде администратора скачивает (не включает в состав):

- **Xray-core** — <https://github.com/XTLS/Xray-core> (Mozilla Public License 2.0),
  бинарь `Xray-linux-64.zip` приколоченного релиза, sha256 сверяется;
- **geosite.dat** — <https://github.com/v2fly/domain-list-community> (MIT);
- **geoip.dat** — <https://github.com/v2fly/geoip> (MIT);
- галерея шаблонов — <https://github.com/remnawave/templates>.
