#!/usr/bin/env python3
"""
hr_shell.py — menu-driven terminal UI for a running HR Minds API, for trying everything by hand.

    uv run python scripts/hr_shell.py                          # opens the main menu
    uv run python scripts/hr_shell.py --server http://host:8000

Arrow keys move, Enter picks, Ctrl-C goes back one menu (and quits from the main menu).
The session (server URL, token, email, active org) is kept in ~/.hr_minds_shell.json so you
stay logged in between runs. Passwords are prompted, or read from HR_PASSWORD when set.
"""

import json
import os
import sys
from pathlib import Path

import httpx
import questionary
from questionary import Choice
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table

console = Console()
SESSION_FILE = Path.home() / ".hr_minds_shell.json"
DEFAULT_URL = "http://127.0.0.1:8000"
API = "/api/v1"
BACK = "back"

session = {"url": DEFAULT_URL, "token": None, "email": None, "org": None}


class Cancelled(Exception):
    """The user backed out of a prompt (Ctrl-C): return to the previous menu."""


class Done(Exception):
    """An action removed or moved what the current menu is about: leave that menu."""


class ApiError(Exception):
    def __init__(self, status: int, detail):
        self.status, self.detail = status, detail


# --- session ---


def load_session():
    if SESSION_FILE.exists():
        session.update(json.loads(SESSION_FILE.read_text()))


def save_session():
    SESSION_FILE.touch(mode=0o600)
    SESSION_FILE.write_text(json.dumps(session))


# --- prompts: each raises Cancelled when the user backs out ---


def ask(prompt):
    answer = prompt.ask()
    if answer is None:
        raise Cancelled
    return answer


def pick(message: str, choices: list[Choice]):
    return ask(questionary.select(message, choices=choices))


def text(message: str, default: str = "", required: bool = True) -> str:
    validate = (lambda s: bool(s.strip()) or "required") if required else None
    return ask(questionary.text(message, default=default, validate=validate)).strip()


def secret(message: str = "Password") -> str:
    return os.environ.get("HR_PASSWORD") or ask(questionary.password(message))


def confirm(message: str) -> bool:
    return ask(questionary.confirm(message, default=False))


# --- http ---


def _headers() -> dict:
    h = {}
    if session["token"]:
        h["Authorization"] = f"Bearer {session['token']}"
    if session["org"]:
        h["X-Org-Id"] = session["org"]
    return h


def _url(path: str) -> str:
    return path if path.startswith("http") else session["url"] + API + path


def _detail(r: httpx.Response):
    try:
        return r.json().get("detail", r.text)
    except ValueError:
        return r.text


def call(method: str, path: str, **kw) -> httpx.Response:
    try:
        r = httpx.request(method, _url(path), headers=_headers(), timeout=30, follow_redirects=True, **kw)
    except httpx.HTTPError as e:
        raise ApiError(0, f"cannot reach {session['url']} ({type(e).__name__}) — is the API running?")
    if r.status_code >= 400:
        raise ApiError(r.status_code, _detail(r))
    return r


def get(path: str, **params):
    return call("GET", path, params=params or None).json()


def send(method: str, path: str, body=None):
    r = call(method, path, json=body)
    return r.json() if r.content else None


def stream_scan(method: str, path: str, body=None):
    """Run a scan endpoint and show its SSE progress live; prints the summary at the end."""
    columns = [SpinnerColumn(), TextColumn("{task.completed} files"), TextColumn("[dim]{task.description}")]
    try:
        with httpx.stream(method, _url(path), json=body, headers=_headers(), timeout=None) as r:
            if r.status_code >= 400:
                r.read()
                raise ApiError(r.status_code, _detail(r))
            with Progress(*columns, console=console) as progress:
                task = progress.add_task("scanning…", total=None)
                event, summary = None, None
                for line in r.iter_lines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data = json.loads(line[5:])
                        if event == "progress":
                            progress.update(task, completed=data["count"], description=escape(data["file"]))
                        elif event == "summary":
                            summary = data
                        elif event == "error":
                            raise ApiError(0, data["detail"])
    except httpx.HTTPError as e:
        raise ApiError(0, f"cannot reach {session['url']} ({type(e).__name__}) — is the API running?")
    if summary:
        ok(f"{summary['total']} files ({summary['pdf']} pdf, {summary['document']} doc, "
           f"{summary['image']} img), {summary['removed']} removed")


# --- output ---


def ok(message: str):
    console.print(f"[green]✓[/] {message}")


def error(e: ApiError):
    detail = e.detail if isinstance(e.detail, str) else json.dumps(e.detail, indent=2)
    console.print(f"[red]✗ {e.status or 'error'}[/] {escape(detail)}")


def show_json(data):
    console.print_json(json.dumps(data))


def table(title: str, columns: list[str], rows: list[list]):
    t = Table(title=title, title_justify="left", show_lines=False)
    for c in columns:
        t.add_column(c)
    for row in rows:
        t.add_row(*[escape(str(v if v is not None else "")) for v in row])
    console.print(t)


def perms(permissions: list[dict]) -> str:
    return "  ".join(f"{p['feature']}:{','.join(p['actions'])}" for p in permissions)


def status_line():
    who = f"[bold]{session['email']}[/]" if session["email"] else "[dim]not logged in[/]"
    console.print(Rule(f"{who} · org: {session['org'] or 'own'} · {session['url']}", align="left"))


# --- menu plumbing ---


def run_menu(title: str, build):
    """
    Loop a menu. `build()` returns [(label, action), ...] and may call the API.
    Ctrl-C at the menu goes back; Ctrl-C inside an action returns to this menu;
    an action that raises Done (it deleted the thing this menu is about) goes back.
    (questionary turns Ctrl-C into None only while a prompt is showing; between
    prompts or during a request it is a plain KeyboardInterrupt, so catch both.)
    """
    while True:
        try:
            items = build()
            choice = pick(title, [Choice(label, i) for i, (label, _) in enumerate(items)] + [Choice("← Back", BACK)])
        except (Cancelled, KeyboardInterrupt):
            return
        except ApiError as e:
            error(e)
            return
        if choice == BACK:
            return
        try:
            items[choice][1]()
        except Done:
            return
        except (Cancelled, KeyboardInterrupt):
            pass
        except ApiError as e:
            error(e)


# --- account ---


def login():
    email = text("Email")
    r = call("POST", "/auth/token", data={"username": email, "password": secret()})
    session.update(token=r.json()["access_token"], email=email, org=None)
    save_session()
    ok(f"logged in as {email}")


def register():
    body = {"email": text("Email"), "first_name": text("First name"), "last_name": text("Last name")}
    body["password"] = secret("Password (min 8 chars)")
    user = send("POST", "/auth/register", body)
    ok(f"registered {user['email']} (id {user['id']})")
    if confirm("Log in as this user now?"):
        r = call("POST", "/auth/token", data={"username": user["email"], "password": body["password"]})
        session.update(token=r.json()["access_token"], email=user["email"], org=None)
        save_session()
        ok(f"logged in as {user['email']}")


def logout():
    call("POST", "/auth/logout")
    session.update(token=None, email=None, org=None)
    save_session()
    ok("logged out")


def delete_account():
    console.print("[red]This deletes your account and the organization you own.[/]")
    if text("Type DELETE to confirm") != "DELETE":
        return
    send("DELETE", "/auth/me", {"password": secret()})
    session.update(token=None, email=None, org=None)
    save_session()
    ok("account deleted")


def connect():
    session["url"] = text("API base URL", default=session["url"]).rstrip("/")
    save_session()
    ok(f"using {session['url']}")


def account_menu():
    def build():
        if session["token"]:
            return [("Who am I", lambda: show_json(get("/auth/me"))), ("Log out", logout),
                    ("Delete my account", delete_account), ("Connect to another server", connect)]
        return [("Log in", login), ("Register", register), ("Connect to another server", connect)]

    run_menu("Account", build)


# --- organizations ---


def org_menu():
    orgs = get("/orgs")
    table("Your organizations", ["id", "name", "your role"],
          [[o["id"], o["name"], "owner" if o["is_owner"] else o["role"]["name"]] for o in orgs])
    choices = [Choice("My own organization (no X-Org-Id)", "")] + \
              [Choice(f"{o['name']}  {o['id']}", o["id"]) for o in orgs if not o["is_owner"]] + \
              [Choice("← Back", BACK)]
    choice = pick("Act on which organization?", choices)
    if choice != BACK:
        session["org"] = choice or None
        save_session()
        ok(f"active org: {session['org'] or 'your own'}")


# --- roles ---


def permission_choices(current: list[dict]) -> list[Choice]:
    checked = {f"{p['feature']}:{a}" for p in current for a in p["actions"]}
    return [Choice(f"{f['slug']}:{a}", f"{f['slug']}:{a}", checked=f"{f['slug']}:{a}" in checked)
            for f in get("/features") for a in f["actions"]]


def grants(selected: list[str]) -> list[dict]:
    by_feature: dict[str, list[str]] = {}
    for item in selected:
        feature, action = item.split(":")
        by_feature.setdefault(feature, []).append(action)
    return [{"feature": f, "actions": a} for f, a in by_feature.items()]


def create_role():
    name = text("Role name")
    description = text("Description (optional)", required=False) or None
    selected = ask(questionary.checkbox("Permissions (space to toggle)", choices=permission_choices([])))
    role = send("POST", "/roles", {"name": name, "description": description, "permissions": grants(selected)})
    ok(f"created role {role['id']} {role['name']}")


def role_menu(role: dict):
    def rename():
        send("PATCH", f"/roles/{role['id']}", {"name": text("New name", default=role["name"])})
        ok("renamed")

    def edit_permissions():
        selected = ask(questionary.checkbox("Permissions (space to toggle)",
                                            choices=permission_choices(role["permissions"])))
        send("PATCH", f"/roles/{role['id']}", {"permissions": grants(selected)})
        ok("permissions updated")

    def delete():
        if confirm(f"Delete role {role['name']}?"):
            send("DELETE", f"/roles/{role['id']}")
            ok("deleted")
            raise Done

    def build():
        role.update(get(f"/roles/{role['id']}"))
        console.print(f"[bold]{escape(role['name'])}[/]  {escape(perms(role['permissions']))}")
        return [("Rename", rename), ("Edit permissions", edit_permissions), ("Delete", delete)]

    run_menu(f"Role {role['id']}", build)


def roles_menu():
    def build():
        roles = get("/roles")
        table("Roles", ["id", "name", "description", "permissions"],
              [[r["id"], r["name"], r["description"], perms(r["permissions"])] for r in roles])
        return [("Create a role", create_role)] + \
               [(f"{r['id']}  {r['name']}", lambda r=r: role_menu(r)) for r in roles]

    run_menu("Roles", build)


# --- members & invitations ---


def member_menu(member: dict):
    user = member["user"]

    def change_role():
        roles = get("/roles")
        role_id = pick("New role", [Choice(f"{r['id']}  {r['name']}", r["id"]) for r in roles])
        send("PATCH", f"/members/{user['id']}", {"role_id": role_id})
        ok("role changed")
        raise Done

    def remove():
        if confirm(f"Remove {user['email']} from the organization?"):
            send("DELETE", f"/members/{user['id']}")
            ok("removed")
            raise Done

    run_menu(f"Member {user['email']}", lambda: [("Change role", change_role), ("Remove", remove)])


def members_menu():
    def build():
        members = get("/members")
        table("Members", ["user id", "email", "name", "role"],
              [[m["user"]["id"], m["user"]["email"], f"{m['user']['first_name']} {m['user']['last_name']}",
                "owner" if m["is_owner"] else m["role"]["name"]] for m in members])
        return [(f"{m['user']['email']}  ({m['role']['name']})", lambda m=m: member_menu(m))
                for m in members if not m["is_owner"]]

    run_menu("Members", build)


def invite():
    email = text("Email to invite")
    roles = get("/roles")
    role_id = pick("Role", [Choice(f"{r['id']}  {r['name']}", r["id"]) for r in roles])
    inv = send("POST", "/invitations", {"email": email, "role_id": role_id})
    console.print(Panel(escape(inv["accept_url"]), title=f"Accept URL for {escape(email)} (expires {inv['expires_at']})"))


def accept_invitation():
    org = send("POST", text("Paste the accept URL"))
    ok(f"joined {org['name']} ({org['id']}) as {org['role']['name']}")


def invitations_menu():
    run_menu("Invitations", lambda: [("Invite someone", invite), ("Accept an invitation", accept_invitation)])


# --- media ---


def add_scan():
    name = text("Folder label")
    folder = ask(questionary.path("Folder path", only_directories=True))
    stream_scan("POST", "/media/local-scans", {"name": name, "folder_path": os.path.expanduser(folder)})


def scan_files(scan: dict):
    page = 1
    while True:
        data = get(f"/media/local-scans/{scan['id']}/files", page=page, page_size=50)
        table(f"{scan['name']} — files page {data['page']}/{data['total_pages']} ({data['total']} total)",
              ["id", "type", "size", "modified", "path"],
              [[f["id"], f["media_type"], f["file_size_bytes"], f["file_modified_at"][:19], f["relative_path"]]
               for f in data["items"]])
        choices = ([Choice("Next page", "next")] if page < data["total_pages"] else []) + \
                  ([Choice("Previous page", "prev")] if page > 1 else []) + [Choice("← Back", BACK)]
        choice = pick("Files", choices)
        if choice == BACK:
            return
        page += 1 if choice == "next" else -1


def scan_menu(scan: dict):
    def delete():
        if confirm(f"Remove folder {scan['name']}? (files on disk are untouched)"):
            send("DELETE", f"/media/local-scans/{scan['id']}")
            ok("removed")
            raise Done

    return run_menu(f"Folder {scan['name']}", lambda: [
        ("List files", lambda: scan_files(scan)),
        ("Re-scan now", lambda: stream_scan("POST", f"/media/local-scans/{scan['id']}/scan")),
        ("Remove folder", delete),
    ])


def media_menu():
    def build():
        scans = get("/media/local-scans")
        table("Resume folders", ["id", "name", "path", "host", "last scanned", "by"],
              [[s["id"], s["name"], s["folder_path"], s["hostname"],
                (s["last_scanned_at"] or "")[:19], s["last_scanned_by_email"]] for s in scans])
        return [("Add a folder (scans it now)", add_scan)] + \
               [(f"{s['id']}  {s['name']}", lambda s=s: scan_menu(s)) for s in scans]

    run_menu("Media", build)


# --- chat ---


def new_chat():
    body = {"title": text("Title (optional)", required=False) or None}
    if confirm("Attach it to something (e.g. a job posting)?"):
        body.update(context_type=text("Context type", default="job_posting"), context_id=text("Context id"))
    chat = send("POST", "/conversations", body)
    ok(f"started conversation {chat['id']}")
    chat_menu(chat)


def show_messages(chat_id: int):
    data = get(f"/conversations/{chat_id}/messages", page_size=100)
    for m in data["items"]:
        body = m["content"] if m["content"] is not None else json.dumps(m["tool_calls"])
        style = {"user": "cyan", "assistant": "green"}.get(m["role"], "yellow")
        console.print(f"[{style}]{m['role']:>9}[/] │ {escape(body)}")
    console.print(f"[dim]{data['total']} messages[/]")


def chat_menu(chat: dict):
    def say():
        send("POST", f"/conversations/{chat['id']}/messages", {"content": text("You")})

    def rename():
        send("PATCH", f"/conversations/{chat['id']}", {"title": text("New title", default=chat["title"] or "")})

    def delete():
        if confirm("Delete this conversation and its messages?"):
            send("DELETE", f"/conversations/{chat['id']}")
            ok("deleted")
            raise Done

    def build():
        chat.update(get(f"/conversations/{chat['id']}"))
        context = f"  [dim]({chat['context_type']} {chat['context_id']})[/]" if chat["context_type"] else ""
        console.print(f"[bold]{escape(chat['title'] or 'untitled')}[/]{context}")
        show_messages(chat["id"])
        return [("Say something", say), ("Rename", rename), ("Delete", delete)]

    run_menu(f"Conversation {chat['id']}", build)


def chats_menu():
    def build():
        data = get("/conversations", page_size=100)
        table(f"Conversations ({data['total']})", ["id", "title", "context", "last message"],
              [[c["id"], c["title"], f"{c['context_type'] or ''} {c['context_id'] or ''}".strip(),
                c["last_message_at"][:19]] for c in data["items"]])
        return [("New conversation", new_chat)] + \
               [(f"{c['id']}  {c['title'] or 'untitled'}", lambda c=c: chat_menu(c)) for c in data["items"]]

    run_menu("Chat", build)


# --- raw request ---


def raw_request():
    method = pick("Method", [Choice(m, m) for m in ("GET", "POST", "PATCH", "DELETE")])
    path = text("Path under /api/v1", default="/")
    body = None
    if method in ("POST", "PATCH"):
        raw = text("JSON body (optional)", required=False)
        if raw:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ApiError(0, f"body is not valid JSON: {e}")
    r = call(method, path, json=body)
    show_json(r.json()) if r.content else ok(f"{r.status_code} no content")


# --- main ---


def main() -> int:
    load_session()
    if len(sys.argv) == 3 and sys.argv[1] == "--server":
        session["url"] = sys.argv[2].rstrip("/")
        save_session()
    elif len(sys.argv) > 1:
        print(__doc__)
        return 2

    sections = [
        ("Account        login, register, who am I, log out", account_menu),
        ("Organization   choose which organization to act on", org_menu),
        ("Roles          list, create, edit permissions, delete", roles_menu),
        ("Members        change roles, remove", members_menu),
        ("Invitations    invite, accept", invitations_menu),
        ("Media          resume folders, scans with live progress", media_menu),
        ("Chat           conversations and messages", chats_menu),
        ("Raw request    any /api/v1 call", raw_request),
    ]
    console.print(Panel("[bold]HR Minds[/]  arrow keys move · Enter picks · Ctrl-C goes back", expand=False))
    while True:
        status_line()
        try:
            choice = pick("What do you want to do?",
                          [Choice(label, i) for i, (label, _) in enumerate(sections)] + [Choice("Quit", BACK)])
        except (Cancelled, KeyboardInterrupt):
            return 0
        if choice == BACK:
            return 0
        try:
            sections[choice][1]()
        except (Cancelled, KeyboardInterrupt):
            pass
        except ApiError as e:
            error(e)


if __name__ == "__main__":
    sys.exit(main())
