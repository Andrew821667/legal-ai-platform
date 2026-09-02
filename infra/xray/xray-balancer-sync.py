#!/usr/bin/env python3
# Self-updating Xray balancer sync for the Mac mini (v3: split-tunnel routing).
# Mirrors Happ's cached subscription -> regenerates the balancer pool, maintains
# direct host-routes for the server IPs, and reloads the balancer ONLY if changed.
# SPLIT ROUTING: only geo-blocked domains (Telegram / Anthropic / OpenAI) go through
# the VPN pool; everything else (DeepSeek, general, pypi, etc.) goes DIRECT.
# Inbounds bind to the vmnet host IP so docker containers can reach the balancer.
import json, glob, copy, subprocess, hashlib, os, sys, time, socket
import base64, urllib.request
from urllib.parse import urlparse, parse_qs, unquote

CACHE_GLOB = "/Users/andrej/Library/Containers/su.ffg.happ.plus/Data/Library/Caches/su.ffg.happ.plus/fsCachedData/*"
OUT_DIR = "/Users/andrej/xray-balancer"
OUT_CFG = OUT_DIR + "/config.json"
ROUTES_STATE = OUT_DIR + "/routes.state"
LOG = "/Users/andrej/Library/Logs/xray-balancer-sync.log"
SERVICE = "system/ru.legalai.xray-balancer"
PROXY_PROTO = {"vless", "vmess", "trojan", "shadowsocks"}
SKIP_BASE = ("Автовыбор", "Россия", "Связь", "сотовая")
SKIP_LTE = ("LTE",)
BIND = "192.168.64.1"
SOCKS_PORT, HTTP_PORT = 10810, 10811

# Подписка как источник пула, не зависящий от Happ. Приложение по требованию
# эксплуатации остаётся выключенным, а его кэш перестал пополняться с 22.06,
# из-за чего пул устарел и балансировщик остался с мёртвыми узлами.
SUB_URL_FILE = "/usr/local/etc/xray-balancer-sub-url"
# Узлы, сохранённые вручную. Провайдер периодически перестаёт отдавать рабочие
# серверы и присылает вместо них только LTE и служебные заглушки, хотя ранее
# выданные узлы продолжают работать. Такие узлы держим отдельно и подмешиваем
# в пул: они не зависят от текущей выдачи подписки.
EXTRA_NODES_FILE = "/usr/local/etc/xray-balancer-extra-nodes.json"
# Второй путь — в домашнем каталоге: туда узел обновляется автоматически с
# рабочего ноутбука по ssh, без пароля root. Системный файл остаётся ручным
# резервом на случай, если автообновление недоступно.
EXTRA_NODES_USER_FILE = "/Users/andrej/.xray-balancer-extra-nodes.json"
# Сервер подписки отдаёт HTML браузерным агентам и рабочий пул — клиентским.
# Провайдер отдаёт разный ответ в зависимости от клиента: на Happ/1.0 и curl
# приходит 500, на браузерный UA — HTML-страница вместо подписки. Рабочим
# оказался клиентский UA v2rayNG.
SUB_UA = os.environ.get("XRAY_BALANCER_SUB_UA", "v2rayNG/1.8.0")
# Узлы, названия которых складываются в сервисное сообщение провайдера
# (например, о лимите устройств), рабочими не являются.
STUB_MARKERS = ("лимит", "limit", "подписк", "устройств", "поддержк", "бот", "bot",
                "использовать", "достигнут", "сброс", "только на")
# LTE-каналы медленные и лимитированные, поэтому по умолчанию исключены.
# Включаются переменной окружения на время аварийного восстановления.
ALLOW_LTE = os.environ.get("XRAY_BALANCER_ALLOW_LTE") == "1"
# Подписка ограничена числом одновременных устройств (сейчас 5). Observatory
# держит по соединению на каждый узел пула и переоткрывает их каждый цикл,
# поэтому большой пул исчерпывает лимит сам по себе: провайдер начинает
# отдавать вместо узлов служебные заглушки, и канал деградирует целиком.
MAX_POOL = int(os.environ.get("XRAY_BALANCER_MAX_POOL", "3"))

# Domains that MUST go through the VPN (geo-blocked from RU). Everything else -> direct.
VPN_DOMAINS = [
    "geosite:telegram",
    "domain:telegram.org", "domain:t.me", "domain:telegram.me", "domain:telesco.pe",
    "domain:anthropic.com", "domain:claude.ai",
    "domain:openai.com", "domain:oaistatic.com", "domain:oaiusercontent.com",
]

def log(m):
    try:
        with open(LOG, "a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")
    except Exception:
        pass

def gw():
    r = subprocess.run(["ipconfig", "getoption", "en0", "router"], capture_output=True, text=True).stdout.strip()
    return r or "192.168.0.1"

def find_servers(o):
    best = []
    def walk(x):
        nonlocal best
        if isinstance(x, list):
            if x and all(isinstance(e, dict) for e in x):
                blob = json.dumps(x)[:5000]
                if ("remarks" in blob or "address" in blob) and len(x) > len(best):
                    best = x
            for e in x: walk(e)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
    walk(o)
    return best

def proxy_ob(entry):
    for o in entry.get("outbounds", []):
        if o.get("protocol") in PROXY_PROTO:
            s = o.get("settings", {})
            v = (s.get("vnext") or s.get("servers") or [])
            if v and v[0].get("address"):
                return o
    return None


def _decode_subscription(raw):
    """Подписка приходит в base64; иногда — уже в открытом виде."""
    text = raw.decode("utf-8", "ignore").strip()
    if "://" in text:
        return text
    return base64.b64decode(text + "=" * (-len(text) % 4)).decode("utf-8", "ignore")


def _stream_settings(q):
    """Собирает streamSettings из query-параметров ссылки vless."""
    net = (q.get("type") or ["tcp"])[0]
    sec = (q.get("security") or ["none"])[0]
    st = {"network": net, "security": sec}
    if sec == "tls":
        st["tlsSettings"] = {"serverName": (q.get("sni") or q.get("host") or [""])[0],
                             "fingerprint": (q.get("fp") or ["chrome"])[0],
                             "allowInsecure": False}
    elif sec == "reality":
        st["realitySettings"] = {"serverName": (q.get("sni") or [""])[0],
                                 "fingerprint": (q.get("fp") or ["chrome"])[0],
                                 "publicKey": (q.get("pbk") or [""])[0],
                                 "shortId": (q.get("sid") or [""])[0],
                                 "spiderX": (q.get("spx") or ["/"])[0]}
    if net == "ws":
        st["wsSettings"] = {"path": unquote((q.get("path") or ["/"])[0]),
                            "headers": {"Host": (q.get("host") or [""])[0]}}
    elif net == "grpc":
        st["grpcSettings"] = {"serviceName": (q.get("serviceName") or [""])[0]}
    elif net == "tcp" and (q.get("headerType") or [""])[0] == "http":
        st["tcpSettings"] = {"header": {"type": "http"}}
    return st


def parse_vless(link):
    """Превращает ссылку vless:// в запись формата, ожидаемого сборкой пула."""
    if not link.startswith("vless://"):
        return None
    u = urlparse(link)
    if not (u.hostname and u.port and u.username):
        return None
    q = parse_qs(u.query)
    user = {"id": u.username, "encryption": (q.get("encryption") or ["none"])[0]}
    flow = (q.get("flow") or [""])[0]
    if flow:
        user["flow"] = flow
    ob = {"protocol": "vless",
          "settings": {"vnext": [{"address": u.hostname, "port": u.port, "users": [user]}]},
          "streamSettings": _stream_settings(q)}
    return {"remarks": unquote(u.fragment or ""), "outbounds": [ob]}


def subscription_entries():
    """Читает пул из подписки. Возвращает [] при любой проблеме."""
    if not os.path.exists(SUB_URL_FILE):
        return []
    try:
        url = open(SUB_URL_FILE).read().strip()
        if not url:
            return []
        req = urllib.request.Request(url, headers={"User-Agent": SUB_UA})
        raw = urllib.request.urlopen(req, timeout=25).read()
    except Exception as e:
        log("WARN subscription fetch failed: %s" % type(e).__name__)
        return []

    entries, stubs = [], 0
    for line in _decode_subscription(raw).splitlines():
        line = line.strip()
        if not line:
            continue
        e = parse_vless(line)
        if not e:
            continue
        low = e["remarks"].lower()
        # Провайдер кодирует служебные сообщения в названиях узлов.
        if any(m in low for m in STUB_MARKERS):
            stubs += 1
            continue
        entries.append(e)
    if stubs:
        log("NOTE subscription returned %d service placeholders (provider message)" % stubs)
    return entries


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    entries = []
    for f in glob.glob(CACHE_GLOB):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        s = find_servers(d)
        if len(s) > len(entries):
            entries = s
    if not entries:
        # Happ выключен и его кэш больше не пополняется — берём подписку напрямую.
        entries = subscription_entries()
        if entries:
            log("pool source: subscription (%d entries)" % len(entries))
    else:
        log("pool source: Happ cache (%d entries)" % len(entries))

    if not entries:
        log("WARN no pool found in Happ cache nor subscription; leaving balancer as-is")
        return

    pool, seen, ips = [], set(), []
    for e in entries:
        rem = e.get("remarks", "")
        skip = SKIP_BASE if ALLOW_LTE else SKIP_BASE + SKIP_LTE
        if any(k in rem for k in skip):
            continue
        ob = proxy_ob(e)
        if not ob:
            continue
        v = (ob["settings"].get("vnext") or ob["settings"].get("servers"))[0]
        key = (v["address"], v.get("port"))
        if key in seen:
            continue
        seen.add(key)
        o2 = copy.deepcopy(ob)
        o2["tag"] = "proxy-%d" % (len(pool) + 1)
        pool.append(o2)
        ips.append(v["address"])

    if not pool:
        log("WARN pool empty after filter; leaving balancer as-is")
        return

    # Сохранённые узлы ставим в начало и учитываем до обрезки. Провайдер сейчас
    # отдаёт в подписке только LTE и служебные заглушки, поэтому вручную
    # сохранённый рабочий узел — единственный полноценный канал. Если добавлять
    # его в конец, обрезка под лимит устройств срезала бы именно его.
    extra = []
    for path in (EXTRA_NODES_USER_FILE, EXTRA_NODES_FILE):
        if not os.path.exists(path):
            continue
        try:
            with open(path) as fh:
                loaded = json.load(fh)
        except Exception as exc:
            log("WARN cannot read extra nodes from %s: %s" % (path, type(exc).__name__))
            continue
        if loaded:
            extra = loaded
            break

    saved_pool, saved_ips = [], []
    for ob in extra:
        v = (ob.get("settings", {}).get("vnext") or ob.get("settings", {}).get("servers") or [{}])[0]
        addr, port = v.get("address"), v.get("port")
        if not addr or (addr, port) in seen:
            continue
        seen.add((addr, port))
        o2 = copy.deepcopy(ob)
        o2.pop("remarks", None)
        saved_pool.append(o2)
        saved_ips.append(addr)

    room = max(0, MAX_POOL - len(saved_pool))
    if len(pool) > room:
        log("subscription nodes trimmed %d -> %d (saved nodes take priority)"
            % (len(pool), room))
        pool = pool[:room]
        ips = ips[:room]

    pool = saved_pool + pool
    ips = saved_ips + ips
    if saved_pool:
        log("pool: %d saved + %d from subscription" % (len(saved_pool), len(pool) - len(saved_pool)))

    for idx, ob in enumerate(pool, start=1):
        ob["tag"] = "proxy-%d" % idx


    cfg = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {"tag": "socks-in", "listen": BIND, "port": SOCKS_PORT, "protocol": "socks", "settings": {"udp": True}},
            {"tag": "http-in", "listen": BIND, "port": HTTP_PORT, "protocol": "http"},
        ],
        "outbounds": pool + [
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "observatory": {"subjectSelector": ["proxy-"], "probeURL": "https://api.telegram.org/",
                        "probeInterval": "120s", "enableConcurrency": False},
        "routing": {"domainStrategy": "AsIs",
                    "balancers": [{"tag": "auto", "selector": ["proxy-"], "strategy": {"type": "leastPing"}}],
                    "rules": [
                        # geo-blocked domains -> VPN pool (balancer)
                        {"type": "field", "inboundTag": ["socks-in", "http-in"],
                         "domain": VPN_DOMAINS, "balancerTag": "auto"},
                        # everything else from the proxy -> direct
                        {"type": "field", "inboundTag": ["socks-in", "http-in"],
                         "outboundTag": "direct"},
                    ]},
    }
    new = json.dumps(cfg, ensure_ascii=False, indent=2)

    g = gw()
    route_ips = set()
    for a in ips:
        try:
            rip = socket.gethostbyname(a) if any(c.isalpha() for c in a) else a
            route_ips.add(rip)
        except Exception:
            pass
    for rip in route_ips:
        r = subprocess.run(["route", "-n", "add", "-host", rip, g], capture_output=True, text=True)
        if r.returncode != 0:
            subprocess.run(["route", "-n", "change", "-host", rip, g], capture_output=True, text=True)
    open(ROUTES_STATE, "w").write("\n".join(sorted(route_ips)) + "\n")

    old = open(OUT_CFG).read() if os.path.exists(OUT_CFG) else ""
    if hashlib.md5(new.encode()).hexdigest() != hashlib.md5(old.encode()).hexdigest():
        open(OUT_CFG, "w").write(new)
        log("pool CHANGED -> %d servers, %d routes; reloading balancer" % (len(pool), len(route_ips)))
        subprocess.run(["/bin/launchctl", "kickstart", "-k", SERVICE], capture_output=True)
    else:
        log("pool unchanged (%d servers, %d routes)" % (len(pool), len(route_ips)))

if __name__ == "__main__":
    main()
