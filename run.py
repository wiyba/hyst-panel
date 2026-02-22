import asyncio
import sys

import uvicorn

from app.database import (
    init_db,
    create_user, edit_user, delete_user, get_user, list_users, user_exists,
    get_traffic,
    create_host, edit_host, delete_host, get_host, list_hosts,
    list_config, get_config, set_config,
)
from app.utils.sub import fmt_bytes
from app.main import public_app, internal_app


# ── cli: users ───────────────────────────────────────────────────────────────

def _cli_users(args: list[str]):
    if not args:
        rows = list_users()
        if not rows:
            print("no users found")
            return
        col_u = max(len(u["username"]) for u in rows)
        col_p = max(len(u["password"]) for u in rows)
        col_s = max(len(u["sid"]) for u in rows)
        print(f"{'user'.ljust(col_u)} | {'password'.ljust(col_p)} | active | {'sid'.ljust(col_s)}")
        print("-" * (col_u + col_p + col_s + 14))
        for u in rows:
            print(f"{u['username'].ljust(col_u)} | {u['password'].ljust(col_p)} | {str(u['active']).ljust(6)} | {u['sid']}")
        return

    sub = args[0]

    if sub == "create" and len(args) == 2:
        r = create_user(args[1])
        if r:
            print(f"username: {r['username']}")
            print(f"password: {r['password']}")
            print(f"sid:      {r['sid']}")
        else:
            print(f"{args[1]} already exists")
        return

    if sub == "info" and len(args) == 2:
        row = get_user(args[1])
        if not row:
            print(f"{args[1]} does not exist")
            return
        print(f"username: {row['username']}")
        print(f"password: {row['password']}")
        print(f"active:   {row['active']}")
        print(f"sid:      {row['sid']}")
        return

    if sub == "edit" and len(args) == 2:
        username = args[1]
        if not user_exists(username):
            print(f"{username} does not exist")
            return
        new_pwd    = input("password (empty to skip): ").strip() or None
        new_sid    = input("sid (empty to skip): ").strip() or None
        active_in  = input("active (empty to skip): ").strip().lower()
        new_active = True if active_in in ("1", "true") else False if active_in in ("0", "false") else None
        edit_user(username, password=new_pwd, sid=new_sid, active=new_active)
        if new_pwd or new_sid or new_active is not None:
            print("updated")
            return
        print("nothing to update")
        return

    if sub == "delete" and len(args) == 2:
        if delete_user(args[1]):
            print(f"{args[1]} deleted")
        else:
            print(f"{args[1]} does not exist")
        return

    print("Usage: users [create|info|edit|delete] <username>")


# ── cli: traffic ─────────────────────────────────────────────────────────────

def _cli_traffic(args: list[str]):
    username = args[0] if args else None
    if username and not user_exists(username):
        print(f"{username} does not exist")
        return
    rows = get_traffic(username)
    if not rows:
        print("no traffic data yet")
        return

    periods = ["hour", "day", "week", "month", "total"]

    if username:
        r = rows[0]
        print(f"username:  {r['username']}")
        for p in periods:
            print(f"{p + ':':<10} {fmt_bytes(r[p])}")
        return

    col_u  = max(max(len(r["username"]) for r in rows), 4)
    col_p  = 10
    header = f"{'user'.ljust(col_u)} | " + " | ".join(f"{p:>{col_p}}" for p in periods)
    print()
    print(header)
    print("-" * len(header))
    for r in rows:
        line  = r["username"].ljust(col_u) + " | "
        line += " | ".join(f"{fmt_bytes(r[p]):>{col_p}}" for p in periods)
        print(line)


# ── cli: hosts ───────────────────────────────────────────────────────────────

def _cli_hosts(args: list[str]):
    if not args:
        rows = list_hosts()
        if not rows:
            print("no hosts found")
            return
        col_a   = max(max(len(h["address"]) for h in rows), 7)
        col_n   = max(max(len(h["name"]) for h in rows), 4) + 2
        col_p   = max(max(len(str(h["port"])) for h in rows), 4)
        col_api = max(max(len(h["api_address"]) for h in rows), 11)
        print(f"{'address'.ljust(col_a)} | {'name'.ljust(col_n)} | {'port'.ljust(col_p)} | active | api_address")
        print("-" * (col_a + col_n + col_p + col_api + 16))
        for h in rows:
            print(f"{h['address'].ljust(col_a)} | {h['name'].ljust(col_n)} | {str(h['port']).ljust(col_p)} | {str(h['active']).ljust(6)} | {h['api_address']}")
        return

    sub = args[0]

    if sub == "create" and len(args) == 2:
        address = args[1]
        r = create_host(address, name=address, api_address="", api_secret="")
        if r:
            print(f"address:     {r['address']}")
            print(f"name:        {r['name']}")
            print(f"port:        {r['port']}")
            print(f"api_address: {r['api_address']}")
            print(f"api_secret:  {r['api_secret']}")
            print(f"active:      {r['active']}")
        else:
            print(f"{address} already exists")
        return

    if sub == "info" and len(args) == 2:
        row = get_host(args[1])
        if not row:
            print(f"{args[1]} does not exist")
            return
        print(f"address:     {row['address']}")
        print(f"name:        {row['name']}")
        print(f"port:        {row['port']}")
        print(f"api_address: {row['api_address']}")
        print(f"api_secret:  {row['api_secret']}")
        print(f"active:      {row['active']}")
        return

    if sub == "edit" and len(args) == 2:
        address = args[1]
        if not get_host(address):
            print(f"{address} does not exist")
            return
        new_name       = input("name (empty to skip): ").strip() or None
        new_port_in    = input("port (empty to skip): ").strip()
        new_port       = int(new_port_in) if new_port_in else None
        new_api_addr   = input("api_address (empty to skip): ").strip() or None
        new_api_secret = input("api_secret (empty to skip): ").strip() or None
        active_in      = input("active (empty to skip): ").strip().lower()
        new_active     = True if active_in in ("1", "true") else False if active_in in ("0", "false") else None
        edit_host(address, name=new_name, port=new_port, api_address=new_api_addr, api_secret=new_api_secret, active=new_active)
        print("updated")
        return

    if sub == "delete" and len(args) == 2:
        if delete_host(args[1]):
            print(f"{args[1]} deleted")
        else:
            print(f"{args[1]} does not exist")
        return

    print("Usage: hosts [create|info|edit|delete] <address>")


# ── cli: config ──────────────────────────────────────────────────────────────

def _cli_config(args: list[str]):
    if not args:
        cfg = list_config()
        if not cfg:
            print("no config found")
            return
        col_k = max(len(k) for k in cfg)
        print(f"{'key'.ljust(col_k)} | value")
        print("-" * (col_k + 10))
        for k, v in cfg.items():
            print(f"{k.ljust(col_k)} | {v}")
        return

    if len(args) == 1:
        print(f"{args[0]}: {get_config(args[0])}")
        return

    key, value = args[0], " ".join(args[1:])
    set_config(key, value)
    print(f"{key}: {value}")


# ── server ───────────────────────────────────────────────────────────────────

async def _run_servers():
    cfg_public   = uvicorn.Config(public_app,   host="127.0.0.1", port=11111, log_level="info")
    cfg_internal = uvicorn.Config(internal_app, host="127.0.0.1", port=22222, log_level="info")
    srv_public   = uvicorn.Server(cfg_public)
    srv_internal = uvicorn.Server(cfg_internal)
    await asyncio.gather(srv_public.serve(), srv_internal.serve())


# ── entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    
    init_db()

    cmd  = sys.argv[1] if len(sys.argv) > 1 else ""
    args = sys.argv[2:]

    if cmd == "run" and not args:
        if not user_exists("admin"):
            print(f"created default user: admin / {create_user('admin')['password']}")
        try:
            asyncio.run(_run_servers())
        except KeyboardInterrupt:
            pass
        sys.exit(0)

    if cmd == "users":
        _cli_users(args)
        sys.exit(0)

    if cmd == "traffic":
        _cli_traffic(args)
        sys.exit(0)

    if cmd == "hosts":
        _cli_hosts(args)
        sys.exit(0)

    if cmd == "config":
        _cli_config(args)
        sys.exit(0)

    print("Usage:")
    print("  run.py run")
    print("  run.py users [create|info|edit|delete <username>]")
    print("  run.py traffic [<username>]")
    print("  run.py hosts [create|info|edit|delete <address>]")
    print("  run.py config [<key> [<value>]]")
    sys.exit(1)
