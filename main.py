import os
import sys
import uuid
import sqlite3
import secrets
import base64
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import urllib.parse
import json
import re
import uvicorn

db = os.path.join(os.path.dirname(__file__), "app.db")
app = FastAPI()

_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_dir, "templates"))

PROFILE_NAME_TPL = "\u0432\u0435\u0431\u0430 \u0432\u043f\u043d for {uname}"

STATUS_URL = "https://status.wiyba.workers.dev/raw"
BROWSER_KW = ["Mozilla", "Chrome", "Safari", "Firefox", "Opera", "Edge", "TelegramBot", "WhatsApp"]

with open(os.path.join(_dir, "clash.yaml")) as f:
    CLASH_TEMPLATE = f.read()
with open(os.path.join(_dir, "singbox.json")) as f:
    SINGBOX_TEMPLATE = json.load(f)

RE_SINGBOX = re.compile(r"sing-box|Hiddify|SFI|SFA|SFM", re.IGNORECASE)
RE_CLASH = re.compile(r"Clash|Stash|mihomo", re.IGNORECASE)

SERVERS = [
    {"host": "london.wiyba.org", "label": "🇬🇧"},
    {"host": "stockholm.wiyba.org", "label": "🇸🇪"},
]


def make_links(uname, pwd):
    return [
        {
            "uri": f"hysteria2://{uname}:{pwd}@{s['host']}:443/?sni={s['host']}#{s['label']}",
            "label": s["label"],
            "host": s["host"],
        }
        for s in SERVERS
    ]


def get_db():
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        sid TEXT UNIQUE NOT NULL
    )
    """)
    conn.commit()
    conn.close()


def user_exists(username):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def create_user(username):
    if user_exists(username):
        print(f"{username} already exists")
        return

    password = str(uuid.uuid4())
    sid = secrets.token_urlsafe(12)[:16]

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password, sid) VALUES (?, ?, ?)",
        (username, password, sid)
    )
    conn.commit()
    conn.close()

    print("username:", username)
    print("password:", password)
    print("sid:", sid)

def edit_user(username, password):
    if not user_exists(username):
        print(f"{username} does not exist")
        return

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET password = ? WHERE username = ?",
        (password, username)
    )
    conn.commit()
    conn.close()

    print()
    print("username:", username)
    print("password:", password)

def info_user(username):    
    if username == "all":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users")
        users = cur.fetchall()
        conn.close()
        
        if users is None:
            print("no users found")
            return
        
        print(f"{"user".ljust(max(len(u["username"]) for u in users))} | {"password".ljust(max(len(u["password"]) for u in users))} | sub")
        print("-" * (max(len(u["username"]) for u in users) + max(len(u["password"]) for u in users) + 49))
        for u in users:
            name = u["username"].ljust(max(len(u["username"]) for u in users))
            pwd = u["password"].ljust(max(len(u["password"]) for u in users))
            print(f"{name} | {pwd} | https://hyst.wiyba.org/sub/{u['sid']}")

        return
    
    if username is None:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users")
        users = cur.fetchall()
        conn.close()

        if users is None:
            print("no users found")
            return
        
        print("users")
        print("-" * (max(len(u["username"]) for u in users)))
        for u in users:
            print(u["username"])
        return
        
    if not user_exists(username):
        print(f"{username} does not exist")
        return
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    )
    user = cur.fetchone()
    conn.close()

    print("username:", user["username"])
    print("password:", user["password"])
    print("sub:", f"https://hyst.wiyba.org/sub/{user['sid']}")

def import_users(path):
    if not os.path.isfile(path):
        print(f"{path} does not exist or is not a file")
        return
    
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            username, password = line.split(":", 1)
            username = username.strip()
            password = password.strip()
            if user_exists(username):
                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT password FROM users WHERE username = ?", (username,))
                row = cur.fetchone()
                conn.close()
                if row and row["password"] == password:
                    print(f"{username} exists")
                else:
                    print(f"{username} exists, fixing password")
                    edit_user(username, password)
                continue
            create_user(username)
            edit_user(username, password)



@app.get("/")
def root():
    return Response(status_code=404)


@app.post("/auth")
async def auth(request: Request):
    data = await request.json()
    auth_field = data.get("auth", "")

    if ":" not in auth_field:
        return JSONResponse({"ok": False})

    username, password = auth_field.split(":", 1)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password)
    )
    user = cur.fetchone()
    conn.close()

    print()
    print(f"username: {username}")
    print(f"result: {bool(user)}")
    print(f"requester: {request.client.host}")
    print()


    if user:
        return JSONResponse({"ok": True, "id": username})

    return JSONResponse({"ok": False})

@app.head("/sub/{sid}")
@app.get("/sub/{sid}")
async def subscription(sid: str, request: Request):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE sid = ?", (sid,))
    user = cur.fetchone()
    conn.close()

    if not user:
        return Response(status_code=404)

    uname, pwd = user["username"], user["password"]
    sub_url = f"https://hyst.wiyba.org/sub/{sid}"
    link_list = make_links(uname, pwd)

    accept = request.headers.get("accept", "")
    ua = request.headers.get("user-agent", "")
    if "text/html" not in accept and not any(k in ua for k in BROWSER_KW):
        print()
        print(f"useragent: {ua}")
        print(f"accept: {accept}")
        print(f"requester: {request.client.host}")
        print()
        profile_name = PROFILE_NAME_TPL.format(uname=uname)

        if RE_SINGBOX.search(ua):
            import copy
            config = copy.deepcopy(SINGBOX_TEMPLATE)

            proxy_names = []
            for s in SERVERS:
                proxy_names.append(s["label"])
                config["outbounds"].append({
                    "type": "hysteria2",
                    "tag": s["label"],
                    "server": s["host"],
                    "server_port": 443,
                    "password": f"{uname}:{pwd}",
                    "tls": {
                        "enabled": True,
                        "server_name": s["host"],
                    },
                })

            config["outbounds"][0]["outbounds"] = proxy_names

            title_b64 = base64.b64encode(profile_name.encode()).decode()
            return PlainTextResponse(json.dumps(config, indent=4, ensure_ascii=False), media_type="application/json", headers={
                "profile-title": f"base64:{title_b64}",
                "profile-update-interval": "12",
                "content-disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(profile_name)}",
                "subscription-userinfo": "upload=0; download=0; total=0; expire=0",
            })

        if RE_CLASH.search(ua):
            proxies_yaml = ""
            for s in SERVERS:
                proxies_yaml += (
                    f"  - name: {s['label']}\n"
                    f"    type: hysteria2\n"
                    f"    server: {s['host']}\n"
                    f"    port: 443\n"
                    f"    password: {uname}:{pwd}\n"
                    f"    skip-cert-verify: true\n"
                )

            yaml_body = CLASH_TEMPLATE.format(proxies=proxies_yaml.rstrip("\n"))

            return PlainTextResponse(yaml_body, media_type="text/yaml", headers={
                "content-disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(profile_name)}",
                "profile-update-interval": "12",
                "subscription-userinfo": "upload=0; download=0; total=0; expire=0",
            })

        body = "\n".join(l["uri"] for l in link_list)
        title_b64 = base64.b64encode(profile_name.encode()).decode()
        return PlainTextResponse(base64.b64encode(body.encode()).decode(), headers={
            "profile-title": f"base64:{title_b64}",
            "profile-update-interval": "12",
            "profile-web-page-url": sub_url,
            "support-url": "https://t.me/wiybaa",
            "content-disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(profile_name)}",
            "subscription-userinfo": "upload=0; download=0; total=0; expire=0",
        })

    status_map = {}
    checked = ""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(STATUS_URL)
            if r.status_code == 200:
                data = r.json()
                for s in data.get("results", []):
                    status_map[s["name"]] = s
                checked = (data.get("checkedAt") or "").replace("T", " ")[:19]
    except Exception:
        pass

    links_with_status = []
    for l in link_list:
        s = status_map.get(l["host"], {})
        ms = s.get("ms")
        links_with_status.append({
            "uri": l["uri"],
            "label": l["label"],
            "up": s.get("up", False),
            "ping": "—" if ms is None else (f"{ms / 1000:.1f}s" if ms >= 1000 else f"{ms}ms"),
        })
    
    print()
    print(f"user: {uname}")
    print(f"requester: {request.client.host}")
    print()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "username": uname,
        "sub_url": sub_url,
        "links": links_with_status,
        "checked": f"status checked {checked} UTC" if checked else "",
    })


def run_server():
    init_db()

    if not user_exists("wiyba"):
        create_user("wiyba")

    uvicorn.run("main:app", host="127.0.0.1", port=8888)


if __name__ == "__main__":
    init_db()

    try:
        if sys.argv[1] == "run" and len(sys.argv) == 2:
            run_server()
            sys.exit(0)
        if sys.argv[1] == "generate" and len(sys.argv) == 3:
            username = sys.argv[2]
            create_user(username)
            sys.exit(0)
        if sys.argv[1] == "edit" and len(sys.argv) == 3:
            username = sys.argv[2]
            password = input("new password: ")
            edit_user(username, password)
            sys.exit(0)
        if sys.argv[1] == "info":
            username = None
            if len(sys.argv) == 3: username = sys.argv[2]
            info_user(username)
            sys.exit(0)
        if sys.argv[1] == "import" and len(sys.argv) == 3:
            path = sys.argv[2]
            import_users(path)
            sys.exit(0)
        raise Exception("wrong args")
    except Exception as e:
        print(f"Error: {e}")
        print("Usage:")
        print("  python3 main.py run")
        print("  python3 main.py generate <username>")
        print("  python3 main.py edit <username>")
        print("  python3 main.py info")
        print("  python3 main.py info all")
        print("  python3 main.py info <username>")
        print("  python3 main.py import <path>")
        sys.exit(0)