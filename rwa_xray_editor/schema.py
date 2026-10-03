"""Схема Xray-конфига для подсказок в редакторе кода.

Не валидатор: ядро проверяет конфиг само (``xray run -test``), а линтер ловит
смысловые ошибки. Здесь только то, что нужно IntelliSense — какие поля бывают в
данном месте документа, что они значат и какие значения допустимы.

Формат узла: ``d`` — описание (ru), ``e`` — то же (en), ``t`` — тип
(object/array/string/number/boolean), ``p`` — поля объекта, ``i`` — элемент
массива, ``v`` — список допустимых значений.
"""
from __future__ import annotations

SCHEMA_JS = r"""
  /* Схема конфига для подсказок: поля, их смысл и допустимые значения. */
  var XSCHEMA = (function () {
    function o(d, e, p) { return { t: 'object', d: d, e: e, p: p || {} }; }
    function a(d, e, i) { return { t: 'array', d: d, e: e, i: i }; }
    function s(d, e, v) { return { t: 'string', d: d, e: e, v: v || null }; }
    function n(d, e) { return { t: 'number', d: d, e: e }; }
    function b(d, e) { return { t: 'boolean', d: d, e: e }; }

    var TLS = o('Параметры TLS.', 'TLS parameters', {
      serverName: s('SNI, который отправит клиент / ожидает сервер.', 'SNI sent by client / expected by server'),
      allowInsecure: b('Не проверять сертификат сервера. В проде — нет.', 'Skip certificate verification. Not for production'),
      alpn: a('Список ALPN, например h2 и http/1.1.', 'ALPN list, e.g. h2 and http/1.1', s('', '', ['h2', 'http/1.1', 'h3'])),
      fingerprint: s('Отпечаток TLS-клиента (uTLS): под какой браузер маскироваться.',
        'uTLS client fingerprint: which browser to mimic',
        ['chrome', 'firefox', 'safari', 'ios', 'android', 'edge', 'random', 'randomized']),
      certificates: a('Сертификаты сервера.', 'Server certificates', o('Сертификат.', 'Certificate', {
        certificateFile: s('Путь к файлу сертификата.', 'Path to certificate file'),
        keyFile: s('Путь к файлу ключа.', 'Path to key file'),
        certificate: a('Сертификат построчно.', 'Certificate by lines', s('', '')),
        key: a('Ключ построчно.', 'Key by lines', s('', '')),
        usage: s('Назначение сертификата.', 'Certificate usage', ['encipherment', 'verify', 'issue'])
      })),
      minVersion: s('Минимальная версия TLS.', 'Minimum TLS version', ['1.2', '1.3']),
      maxVersion: s('Максимальная версия TLS.', 'Maximum TLS version', ['1.2', '1.3']),
      cipherSuites: s('Список шифров (TLS 1.2).', 'Cipher suites (TLS 1.2)'),
      rejectUnknownSni: b('Рвать соединение, если SNI не совпал с сертификатом.', 'Drop connection when SNI does not match')
    });

    var REALITY = o('Reality: маскировка под чужой сайт без своего сертификата.',
      'Reality: masquerade behind a real site without your own certificate', {
      show: b('Отладочный вывод.', 'Debug output'),
      dest: s('Куда проксировать нецелевой трафик — «сайт-прикрытие», host:port.',
        'Where to proxy non-target traffic — the cover site, host:port'),
      xver: n('Версия PROXY protocol к dest.', 'PROXY protocol version towards dest'),
      serverNames: a('SNI, которые сервер принимает (должны обслуживаться dest).',
        'SNI values the server accepts (must be served by dest)', s('', '')),
      privateKey: s('Приватный ключ x25519 (только на сервере).', 'x25519 private key (server side only)'),
      publicKey: s('Публичный ключ x25519 (на клиенте).', 'x25519 public key (client side)'),
      shortIds: a('Короткие идентификаторы, hex до 16 символов; пустая строка разрешает всех.',
        'Short ids, hex up to 16 chars; empty string allows any', s('', '')),
      spiderX: s('Путь для обхода на стороне клиента.', 'Crawler path on the client side'),
      minClientVer: s('Минимальная версия клиента.', 'Minimum client version'),
      maxTimeDiff: n('Допустимое расхождение часов, мс.', 'Allowed clock difference, ms')
    });

    var STREAM = o('Транспорт: как соединение выглядит в сети.', 'Transport: how the connection looks on the wire', {
      network: s('Тип транспорта.', 'Transport type',
        ['tcp', 'raw', 'ws', 'grpc', 'http', 'h2', 'httpupgrade', 'splithttp', 'xhttp', 'kcp', 'quic', 'domainsocket']),
      security: s('Слой шифрования поверх транспорта.', 'Security layer on top of the transport',
        ['none', 'tls', 'reality']),
      tlsSettings: TLS,
      realitySettings: REALITY,
      rawSettings: o('Настройки raw/tcp, включая маскировку под HTTP.', 'raw/tcp settings, including HTTP masquerade', {
        acceptProxyProtocol: b('Принимать PROXY protocol от фронтенда.', 'Accept PROXY protocol from the frontend'),
        header: o('Маскировка заголовком.', 'Header obfuscation', {
          type: s('Тип маскировки.', 'Obfuscation type', ['none', 'http'])
        })
      }),
      tcpSettings: o('То же, что rawSettings (старое имя).', 'Same as rawSettings (legacy name)', {
        acceptProxyProtocol: b('Принимать PROXY protocol.', 'Accept PROXY protocol'),
        header: o('Маскировка заголовком.', 'Header obfuscation', {
          type: s('Тип маскировки.', 'Obfuscation type', ['none', 'http'])
        })
      }),
      wsSettings: o('WebSocket.', 'WebSocket', {
        path: s('Путь URL.', 'URL path'),
        host: s('Заголовок Host.', 'Host header'),
        headers: o('Дополнительные заголовки.', 'Extra headers', {}),
        acceptProxyProtocol: b('Принимать PROXY protocol.', 'Accept PROXY protocol'),
        heartbeatPeriod: n('Период пинга, с.', 'Heartbeat period, s')
      }),
      grpcSettings: o('gRPC.', 'gRPC', {
        serviceName: s('Имя сервиса (аналог пути).', 'Service name (path analogue)'),
        multiMode: b('Мультиплексирование потоков.', 'Multiplexed streams'),
        idle_timeout: n('Таймаут простоя, с.', 'Idle timeout, s'),
        health_check_timeout: n('Таймаут health-check, с.', 'Health check timeout, s')
      }),
      httpSettings: o('HTTP/2.', 'HTTP/2', {
        host: a('Допустимые Host.', 'Allowed hosts', s('', '')),
        path: s('Путь URL.', 'URL path'),
        read_idle_timeout: n('Таймаут чтения, с.', 'Read idle timeout, s')
      }),
      httpupgradeSettings: o('HTTP Upgrade.', 'HTTP Upgrade', {
        path: s('Путь URL.', 'URL path'),
        host: s('Заголовок Host.', 'Host header'),
        acceptProxyProtocol: b('Принимать PROXY protocol.', 'Accept PROXY protocol')
      }),
      xhttpSettings: o('XHTTP (splithttp).', 'XHTTP (splithttp)', {
        path: s('Путь URL.', 'URL path'),
        host: s('Заголовок Host.', 'Host header'),
        mode: s('Режим передачи.', 'Transfer mode', ['auto', 'packet-up', 'stream-up', 'stream-one'])
      }),
      kcpSettings: o('mKCP — UDP-транспорт.', 'mKCP — UDP transport', {
        mtu: n('MTU.', 'MTU'), tti: n('Интервал отправки, мс.', 'Send interval, ms'),
        uplinkCapacity: n('Полоса вверх, МБ/с.', 'Uplink capacity, MB/s'),
        downlinkCapacity: n('Полоса вниз, МБ/с.', 'Downlink capacity, MB/s'),
        congestion: b('Контроль перегрузки.', 'Congestion control'),
        seed: s('Пароль обфускации.', 'Obfuscation seed'),
        header: o('Маскировка пакетов.', 'Packet masquerade', {
          type: s('Под что маскировать UDP.', 'What to mimic',
            ['none', 'srtp', 'utp', 'wechat-video', 'dtls', 'wireguard'])
        })
      }),
      sockopt: o('Опции сокета.', 'Socket options', {
        mark: n('SO_MARK для маршрутизации на хосте.', 'SO_MARK for host routing'),
        tcpFastOpen: b('TCP Fast Open.', 'TCP Fast Open'),
        tproxy: s('Прозрачный проксирующий режим.', 'Transparent proxy mode', ['off', 'redirect', 'tproxy']),
        domainStrategy: s('Как резолвить домен при исходящем соединении.', 'How to resolve domains for outgoing connections',
          ['AsIs', 'UseIP', 'UseIPv4', 'UseIPv6']),
        dialerProxy: s('Тег outbound, через который идёт само соединение (цепочка).',
          'Outbound tag used to dial this connection (chaining)'),
        tcpKeepAliveInterval: n('Интервал keep-alive, с.', 'Keep-alive interval, s'),
        tcpcongestion: s('Алгоритм контроля перегрузки TCP.', 'TCP congestion control algorithm',
          ['bbr', 'cubic', 'reno'])
      })
    });

    var SNIFF = o('Определение протокола и домена внутри соединения.',
      'Protocol and destination sniffing', {
      enabled: b('Включить разбор.', 'Enable sniffing'),
      destOverride: a('Что подменять адресом из разобранного трафика.',
        'Which protocols override the destination', s('', '', ['http', 'tls', 'quic', 'fakedns'])),
      metadataOnly: b('Только метаданные, без чтения тела.', 'Metadata only'),
      routeOnly: b('Результат использовать только для маршрутизации.', 'Use result for routing only'),
      domainsExcluded: a('Домены-исключения.', 'Excluded domains', s('', ''))
    });

    var RULE = o('Правило маршрутизации: условия сверху вниз, первое совпавшее выигрывает.',
      'Routing rule: matched top-down, first match wins', {
      type: s('Всегда field.', 'Always field', ['field']),
      inboundTag: a('Теги инбаундов, к которым применяется правило.', 'Inbound tags this rule applies to', s('', '')),
      outboundTag: s('Куда отправить трафик — тег outbound.', 'Where to send traffic — outbound tag'),
      balancerTag: s('Куда отправить трафик — тег балансера (взаимоисключающе с outboundTag).',
        'Where to send traffic — balancer tag (mutually exclusive with outboundTag)'),
      domain: a('Домены: обычная подстрока, full:, domain:, regexp:, geosite:.',
        'Domains: substring, full:, domain:, regexp:, geosite:', s('', '')),
      ip: a('IP и подсети: CIDR или geoip:.', 'IPs and subnets: CIDR or geoip:', s('', '')),
      port: s('Порт назначения: 443, 1000-2000, список через запятую.',
        'Destination port: 443, 1000-2000, comma-separated list'),
      sourcePort: s('Порт источника.', 'Source port'),
      source: a('Адреса источника.', 'Source addresses', s('', '')),
      network: s('Транспорт.', 'Network', ['tcp', 'udp', 'tcp,udp']),
      protocol: a('Протокол внутри соединения (нужен sniffing).',
        'Application protocol inside the connection (requires sniffing)',
        s('', '', ['http', 'tls', 'bittorrent', 'quic', 'dns'])),
      user: a('Пользователи (email).', 'Users (email)', s('', '')),
      attrs: o('Атрибуты HTTP-заголовков.', 'HTTP header attributes', {}),
      domainMatcher: s('Алгоритм сопоставления доменов.', 'Domain matching algorithm', ['hybrid', 'linear']),
      ruleTag: s('Имя правила для логов.', 'Rule name for logs')
    });

    var BAL = o('Балансер: выбирает один из outbound по стратегии.',
      'Balancer: picks one outbound by strategy', {
      tag: s('Тег балансера, на него ссылается balancerTag в правиле.',
        'Balancer tag referenced by balancerTag in a rule'),
      selector: a('Префиксы тегов outbound, попадающих в балансер.',
        'Prefixes of outbound tags included in the balancer', s('', '')),
      fallbackTag: s('Куда уйти, если ни один выход не годен.', 'Fallback outbound tag'),
      strategy: o('Стратегия выбора.', 'Selection strategy', {
        type: s('random — случайно, roundRobin — по кругу, leastPing/leastLoad — по замерам observatory.',
          'random, roundRobin, leastPing/leastLoad (require observatory)',
          ['random', 'roundRobin', 'leastPing', 'leastLoad']),
        settings: o('Параметры стратегии.', 'Strategy settings', {})
      })
    });

    return o('Корень конфига Xray.', 'Xray config root', {
      log: o('Логи.', 'Logging', {
        loglevel: s('Уровень подробности.', 'Verbosity', ['debug', 'info', 'warning', 'error', 'none']),
        access: s('Файл журнала соединений; none — выключить.', 'Access log file; none disables it'),
        error: s('Файл журнала ошибок.', 'Error log file'),
        dnsLog: b('Писать DNS-запросы в лог.', 'Log DNS queries'),
        maskAddress: s('Маскировать адреса в логах.', 'Mask addresses in logs', ['quarter', 'half', 'full'])
      }),
      dns: o('Встроенный DNS-резолвер.', 'Built-in DNS resolver', {
        servers: a('Серверы: строка-адрес либо объект с доменными фильтрами.',
          'Servers: plain address or object with domain filters', {
            t: 'any', d: 'Адрес сервера или объект {address, domains, expectIPs}.',
            e: 'Server address or object {address, domains, expectIPs}'
          }),
        hosts: o('Статические записи домен → IP.', 'Static domain → IP records', {}),
        clientIp: s('IP клиента для EDNS.', 'Client IP for EDNS'),
        queryStrategy: s('Какие адреса запрашивать.', 'Which records to query',
          ['UseIP', 'UseIPv4', 'UseIPv6']),
        disableCache: b('Не кэшировать ответы.', 'Disable cache'),
        disableFallback: b('Не переспрашивать другие серверы.', 'Disable fallback'),
        tag: s('Тег для маршрутизации самих DNS-запросов.', 'Tag for routing DNS queries themselves')
      }),
      inbounds: a('Входящие соединения: что слушает нода.', 'Inbound connections: what the node listens on',
        o('Инбаунд.', 'Inbound', {
          tag: s('Уникальное имя. По нему правило ссылается через inboundTag.',
            'Unique name, referenced by inboundTag in rules'),
          port: { t: 'any', d: 'Порт или диапазон.', e: 'Port or range' },
          listen: s('Адрес прослушивания, по умолчанию все интерфейсы.', 'Listen address, defaults to all interfaces'),
          protocol: s('Протокол приёма.', 'Inbound protocol',
            ['vless', 'vmess', 'trojan', 'shadowsocks', 'socks', 'http', 'dokodemo-door', 'wireguard']),
          settings: o('Настройки протокола: клиенты, метод шифрования и прочее.',
            'Protocol settings: clients, encryption method and so on', {
            clients: a('Пользователи инбаунда.', 'Inbound users', o('Клиент.', 'Client', {
              id: s('UUID (vless/vmess).', 'UUID (vless/vmess)'),
              email: s('Метка пользователя, попадает в логи и статистику.', 'User label, shows in logs and stats'),
              flow: s('Режим потока VLESS.', 'VLESS flow', ['', 'xtls-rprx-vision']),
              level: n('Уровень политики.', 'Policy level'),
              password: s('Пароль (trojan/shadowsocks).', 'Password (trojan/shadowsocks))')
            })),
            decryption: s('Для vless всегда none.', 'Always none for vless', ['none']),
            method: s('Шифр Shadowsocks.', 'Shadowsocks method',
              ['2022-blake3-aes-128-gcm', '2022-blake3-aes-256-gcm', '2022-blake3-chacha20-poly1305',
               'aes-128-gcm', 'aes-256-gcm', 'chacha20-ietf-poly1305']),
            password: s('Пароль/ключ.', 'Password or key'),
            network: s('Разрешённый транспорт.', 'Allowed network', ['tcp', 'udp', 'tcp,udp']),
            udp: b('Разрешить UDP (socks/http).', 'Allow UDP (socks/http)'),
            auth: s('Аутентификация socks.', 'socks authentication', ['noauth', 'password']),
            address: s('Адрес назначения (dokodemo-door).', 'Destination address (dokodemo-door)'),
            followRedirect: b('Брать адрес из прозрачного редиректа.', 'Take address from transparent redirect')
          }),
          streamSettings: STREAM,
          sniffing: SNIFF,
          allocate: o('Стратегия занятия портов.', 'Port allocation strategy', {
            strategy: s('always или random.', 'always or random', ['always', 'random']),
            refresh: n('Период смены, мин.', 'Refresh period, min'),
            concurrency: n('Сколько портов одновременно.', 'Concurrent ports')
          })
        })),
      outbounds: a('Исходящие: куда нода отправляет трафик. Первый — по умолчанию.',
        'Outbounds: where the node sends traffic. The first one is the default',
        o('Outbound.', 'Outbound', {
          tag: s('Уникальное имя, на него ссылается outboundTag правила.',
            'Unique name referenced by outboundTag in rules'),
          protocol: s('Протокол отправки. freedom — напрямую, blackhole — отбросить.',
            'Outbound protocol. freedom sends directly, blackhole drops',
            ['freedom', 'blackhole', 'vless', 'vmess', 'trojan', 'shadowsocks', 'socks', 'http', 'wireguard', 'dns', 'loopback']),
          settings: o('Настройки протокола.', 'Protocol settings', {
            vnext: a('Серверы назначения (vless/vmess).', 'Destination servers (vless/vmess)',
              o('Сервер.', 'Server', {
                address: s('Адрес сервера.', 'Server address'),
                port: n('Порт сервера.', 'Server port'),
                users: a('Учётные данные.', 'Credentials', o('Пользователь.', 'User', {
                  id: s('UUID.', 'UUID'),
                  encryption: s('Для vless — none.', 'none for vless', ['none']),
                  flow: s('Режим потока VLESS.', 'VLESS flow', ['', 'xtls-rprx-vision']),
                  level: n('Уровень политики.', 'Policy level')
                }))
              })),
            servers: a('Серверы назначения (trojan/shadowsocks/socks/http).',
              'Destination servers (trojan/shadowsocks/socks/http)', o('Сервер.', 'Server', {
                address: s('Адрес сервера.', 'Server address'),
                port: n('Порт сервера.', 'Server port'),
                password: s('Пароль.', 'Password'),
                method: s('Шифр Shadowsocks.', 'Shadowsocks method'),
                uot: b('UDP over TCP.', 'UDP over TCP')
              })),
            domainStrategy: s('Как резолвить домены (freedom).', 'Domain resolution (freedom)',
              ['AsIs', 'UseIP', 'UseIPv4', 'UseIPv6', 'ForceIP', 'ForceIPv4', 'ForceIPv6']),
            redirect: s('Перенаправить всё на адрес:порт.', 'Redirect everything to address:port'),
            response: o('Ответ blackhole.', 'blackhole response', {
              type: s('none — молча оборвать, http — отдать 403.', 'none drops silently, http returns 403',
                ['none', 'http'])
            }),
            secretKey: s('Приватный ключ WireGuard.', 'WireGuard private key'),
            peers: a('Пиры WireGuard.', 'WireGuard peers', o('Пир.', 'Peer', {
              endpoint: s('Адрес пира.', 'Peer endpoint'),
              publicKey: s('Публичный ключ пира.', 'Peer public key'),
              preSharedKey: s('Предварительный ключ.', 'Pre-shared key'),
              allowedIPs: a('Разрешённые подсети.', 'Allowed IPs', s('', ''))
            })),
            address: a('Локальные адреса интерфейса WireGuard.', 'WireGuard interface addresses', s('', '')),
            mtu: n('MTU интерфейса.', 'Interface MTU')
          }),
          streamSettings: STREAM,
          proxySettings: o('Отправить это соединение через другой outbound (каскад).',
            'Send this connection through another outbound (chaining)', {
            tag: s('Тег промежуточного outbound.', 'Intermediate outbound tag'),
            transportLayerProxy: b('Проксировать на транспортном уровне.', 'Proxy at the transport layer')
          }),
          mux: o('Мультиплексирование соединений.', 'Connection multiplexing', {
            enabled: b('Включить mux.', 'Enable mux'),
            concurrency: n('Сколько потоков в одном соединении.', 'Streams per connection'),
            xudpConcurrency: n('То же для UDP.', 'Same for UDP'),
            xudpProxyUDP443: s('Что делать с UDP 443.', 'What to do with UDP 443', ['reject', 'allow', 'skip'])
          }),
          sendThrough: s('С какого локального адреса отправлять.', 'Local address to send from')
        })),
      routing: o('Маршрутизация: куда какой трафик.', 'Routing: which traffic goes where', {
        domainStrategy: s('AsIs — только домены; IPIfNonMatch — резолвить, если не совпало; IPOnDemand — резолвить сразу.',
          'AsIs uses domains only; IPIfNonMatch resolves after a miss; IPOnDemand resolves upfront',
          ['AsIs', 'IPIfNonMatch', 'IPOnDemand']),
        domainMatcher: s('Алгоритм сопоставления доменов.', 'Domain matching algorithm', ['hybrid', 'linear']),
        rules: a('Правила по порядку.', 'Rules in order', RULE),
        balancers: a('Балансеры.', 'Balancers', BAL)
      }),
      policy: o('Лимиты и учёт по уровням и системе.', 'Limits and accounting', {
        levels: o('Настройки по уровню пользователя.', 'Per-level settings', {}),
        system: o('Системная статистика.', 'System statistics', {
          statsInboundUplink: b('Считать входящий трафик инбаундов.', 'Count inbound uplink'),
          statsInboundDownlink: b('Считать исходящий трафик инбаундов.', 'Count inbound downlink'),
          statsOutboundUplink: b('Считать трафик outbound вверх.', 'Count outbound uplink'),
          statsOutboundDownlink: b('Считать трафик outbound вниз.', 'Count outbound downlink')
        })
      }),
      api: o('Служебный gRPC API ядра.', 'Core gRPC API', {
        tag: s('Тег служебного inbound.', 'Service inbound tag'),
        services: a('Включённые сервисы.', 'Enabled services',
          s('', '', ['HandlerService', 'LoggerService', 'StatsService', 'ReflectionService', 'RoutingService']))
      }),
      stats: o('Включает сбор статистики (пустой объект).', 'Enables statistics collection (empty object)', {}),
      metrics: o('Метрики Prometheus.', 'Prometheus metrics', {
        tag: s('Тег служебного inbound.', 'Service inbound tag'),
        listen: s('Адрес прослушивания.', 'Listen address')
      }),
      observatory: o('Замер живости выходов — нужен для leastPing/leastLoad.',
        'Outbound probing — required by leastPing/leastLoad', {
        subjectSelector: a('Префиксы тегов, которые замерять.', 'Tag prefixes to probe', s('', '')),
        probeUrl: s('URL для проверки.', 'Probe URL'),
        probeInterval: s('Период проверки, например 10s.', 'Probe interval, e.g. 10s'),
        enableConcurrency: b('Замерять параллельно.', 'Probe concurrently')
      }),
      burstObservatory: o('Замер с накоплением статистики (для leastLoad).',
        'Burst probing with accumulated statistics (for leastLoad)', {
        subjectSelector: a('Префиксы тегов.', 'Tag prefixes', s('', '')),
        pingConfig: o('Параметры пинга.', 'Ping settings', {
          destination: s('URL проверки.', 'Probe URL'),
          interval: s('Период.', 'Interval'),
          timeout: s('Таймаут.', 'Timeout'),
          sampling: n('Размер выборки.', 'Sampling size')
        })
      }),
      reverse: o('Обратное проксирование (bridge/portal).', 'Reverse proxying (bridge/portal)', {
        bridges: a('Мосты.', 'Bridges', o('Мост.', 'Bridge', {
          tag: s('Тег.', 'Tag'), domain: s('Домен.', 'Domain')
        })),
        portals: a('Порталы.', 'Portals', o('Портал.', 'Portal', {
          tag: s('Тег.', 'Tag'), domain: s('Домен.', 'Domain')
        }))
      }),
      fakedns: { t: 'any', d: 'Поддельный DNS для перехвата доменов.', e: 'Fake DNS for domain interception' },
      transport: o('Глобальные настройки транспортов (устаревшее в пользу streamSettings).',
        'Global transport settings (legacy in favour of streamSettings)', {})
    });
  })();
"""
