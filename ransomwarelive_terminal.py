import os
import sys
import time
import json
import sqlite3
import calendar
import requests

from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel

# Configuration
BASE_URL      = "https://api.ransomware.live/v2"
CACHE_PATH    = Path.home() / ".ransomware_cache.db"
CACHE_TTL     = 3600    # seconds
MAX_RETRIES   = 5
BACKOFF_INITIAL = 1
BACKOFF_MAX     = 60

console = Console()


def init_cache():
    conn = sqlite3.connect(str(CACHE_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            response TEXT,
            timestamp INTEGER
        )
    """)
    conn.commit()
    return conn


cache_conn = init_cache()


def get_cached(key):
    c = cache_conn.cursor()
    c.execute("SELECT response, timestamp FROM cache WHERE key = ?", (key,))
    row = c.fetchone()
    if row:
        resp_text, ts = row
        if time.time() - ts < CACHE_TTL:
            return json.loads(resp_text)
    return None


def set_cache(key, data):
    c = cache_conn.cursor()
    resp_text = json.dumps(data)
    ts = int(time.time())
    c.execute("""
        INSERT INTO cache(key, response, timestamp)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          response=excluded.response,
          timestamp=excluded.timestamp
    """, (key, resp_text, ts))
    cache_conn.commit()


def fetch_endpoint(path: str):
    key = BASE_URL + path
    cached = get_cached(key)
    if cached is not None:
        return cached

    backoff = BACKOFF_INITIAL
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(BASE_URL + path, timeout=10)
        except requests.RequestException as e:
            console.print(f"[red]Request error:[/red] {e}")
            return None

        if resp.status_code == 200:
            data = resp.json()
            set_cache(key, data)
            return data

        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After")
            wait = int(ra) if ra and ra.isdigit() else backoff
            console.print(f"[yellow]Rate limit hit; retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})[/yellow]")
            time.sleep(wait)
            backoff = min(backoff * 2, BACKOFF_MAX)
            continue

        if resp.status_code == 404:
            console.print("[yellow]No records found.[/yellow]")
        else:
            console.print(f"[red]HTTP {resp.status_code} error[/red]")
        return None

    console.print("[red]Max retries exceeded; aborting request.[/red]")
    return None


def apply_advanced_filters(data: list) -> list:
    """Apply user-selected advanced filters to victim list."""
    if Prompt.ask("Apply advanced filters? (y/n)", choices=["y", "n"], default="n") != "y":
        return data

    filters = []
    if Prompt.ask("Only records with press coverage? (y/n)", choices=["y", "n"]) == "y":
        filters.append(lambda v: bool(v.get("press")))
    if Prompt.ask("Only records with infostealer data? (y/n)", choices=["y", "n"]) == "y":
        filters.append(lambda v: bool(v.get("infostealer")))
    if Prompt.ask("Only records with updates? (y/n)", choices=["y", "n"]) == "y":
        filters.append(lambda v: bool(v.get("updates")))
    if Prompt.ask("Filter by sector? (y/n)", choices=["y", "n"]) == "y":
        sector = Prompt.ask("Enter sector name (e.g. Healthcare)").lower()
        filters.append(lambda v, sec=sector: v.get("sector", "").lower() == sec)

    for f in filters:
        data = list(filter(f, data))
    return data


def display_victims(victims: list):
    """Show victim table with Sector column, drill-down detail view, then export."""
    victims = apply_advanced_filters(victims)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Victim", overflow="fold")
    table.add_column("Group")
    table.add_column("Sector")
    table.add_column("Date")
    table.add_column("Country")

    for idx, v in enumerate(victims, 1):
        table.add_row(
            str(idx),
            v.get("victim", ""),
            v.get("group", ""),
            v.get("sector", "Not informed"),
            v.get("attackdate", ""),
            v.get("country", "")
        )
    console.print(table)

    # Drill-down detail view
    while True:
        sel = Prompt.ask("Enter record # for details (or press Enter to continue)", default="")
        if not sel.isdigit():
            break
        i = int(sel) - 1
        if 0 <= i < len(victims):
            rec = victims[i]
            # ensure 'sector' key exists
            rec.setdefault("sector", "Not informed")
            details = Table(show_header=False)
            details.add_column("Field", style="bold")
            details.add_column("Value", overflow="fold")
            for k, val in rec.items():
                details.add_row(k, json.dumps(val) if isinstance(val, (dict, list)) else str(val))
            console.print(Panel(details, title=f"Details for record #{sel}", expand=False))
        else:
            console.print("[red]Invalid record number.[/red]")

    _export_option(victims)


def _export_option(data: list):
    choice = Prompt.ask("Export results? (y/n)", choices=["y", "n"], default="n")
    if choice == "n":
        return
    fmt = Prompt.ask("Select format", choices=["json", "csv"], default="json")
    ts = time.strftime("%Y%m%d%H%M%S")
    filename = f"victims_{ts}.{fmt}"
    try:
        if fmt == "json":
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
        else:
            import csv as _csv
            keys = data[0].keys() if data else []
            with open(filename, "w", newline="") as f:
                writer = _csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)
        console.print(f"[green]Exported to {filename}[/green]")
    except Exception as e:
        console.print(f"[red]Export failed:[/red] {e}")


def search_victims():
    kw = Prompt.ask("Enter search keyword")
    data = fetch_endpoint(f"/searchvictims/{kw}")
    if data:
        display_victims(data)


def victims_by_date():
    year = Prompt.ask("Enter year (YYYY)")
    month_str = Prompt.ask("Enter month (1–12) or leave blank", default="")
    month = int(month_str) if month_str.isdigit() else None
    results = []
    if month is None:
        for m in range(1, 13):
            batch = fetch_endpoint(f"/victims/{year}/{m}")
            if batch:
                results.extend(batch)
    else:
        batch = fetch_endpoint(f"/victims/{year}/{month}")
        if batch:
            results = batch
    if results:
        display_victims(results)


def victims_by_country():
    cc = Prompt.ask("Enter country code (ISO-2)").upper()
    data = fetch_endpoint(f"/countryvictims/{cc}")
    if data:
        display_victims(data)


def victims_by_country_and_date():
    cc = Prompt.ask("Enter country code (ISO-2)").upper()
    year = Prompt.ask("Enter year (YYYY)")
    month_str = Prompt.ask("Enter month (1–12) or leave blank", default="")
    month = int(month_str) if month_str.isdigit() else None
    temp = []
    if month is None:
        for m in range(1, 13):
            batch = fetch_endpoint(f"/victims/{year}/{m}")
            if batch:
                temp.extend(batch)
    else:
        batch = fetch_endpoint(f"/victims/{year}/{month}")
        if batch:
            temp = batch
    filtered = [v for v in temp if v.get("country", "").upper() == cc]
    if filtered:
        display_victims(filtered)
    else:
        console.print("[yellow]No matching records.[/yellow]")


def list_groups():
    """List all known ransomware groups."""
    data = fetch_endpoint("/groups")
    if not data:
        return
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Group Name")
    table.add_column("Description", overflow="fold")
    table.add_column("Onion Link", overflow="fold")
    for g in data:
        table.add_row(
            g.get("name", ""),
            g.get("description", ""),
            g.get("onion", "N/A")
        )
    console.print(table)


def group_details():
    """Fetch details for a specific ransomware group."""
    name = Prompt.ask("Enter exact group name")
    data = fetch_endpoint(f"/group/{name}")
    if not data:
        return
    panel = Panel.fit(
        "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in data.items()),
        title=f"Details for group '{name}'"
    )
    console.print(panel)


def dashboard():
    """Plot incident counts per month for a country or group."""
    console.print("\n[bold]Dashboard Mode[/bold]")
    choice = Prompt.ask(
        "1) By Country  2) By Group  3) Back",
        choices=["1", "2", "3"],
        default="3"
    )
    if choice == "3":
        return

    year = Prompt.ask("Enter year (YYYY)")
    counts = [0] * 12

    if choice == "1":
        cc = Prompt.ask("Enter country code (ISO-2)").upper()
        for m in range(1, 13):
            batch = fetch_endpoint(f"/victims/{year}/{m}")
            if batch:
                counts[m-1] = sum(1 for v in batch if v.get("country", "").upper() == cc)
        title = f"Incidents in {cc} during {year}"
    else:
        grp = Prompt.ask("Enter group name")
        batch = fetch_endpoint(f"/groupvictims/{grp}") or []
        for v in batch:
            date = v.get("attackdate", "")
            if date.startswith(f"{year}-"):
                month = int(date.split("-")[1])
                counts[month-1] += 1
        title = f"Incidents by {grp} during {year}"

    # Scale bars to max width 40
    maxc = max(counts) or 1
    console.print(f"\n[bold underline]{title}[/bold underline]")
    for idx, cnt in enumerate(counts, 1):
        bar_len = int(cnt / maxc * 40)
        bar = "█" * bar_len
        month_label = calendar.month_abbr[idx]
        console.print(f"{month_label:>3} │ {bar} {cnt}")


def main():
    console.print("[bold underline]Ransomware.live Terminal[/bold underline]")
    actions = {
        "1": ("Search victims by keyword", search_victims),
        "2": ("List victims by date", victims_by_date),
        "3": ("List victims by country", victims_by_country),
        "4": ("List victims by country and date", victims_by_country_and_date),
        "5": ("Search victims by group", lambda: display_victims(
            fetch_endpoint(f"/groupvictims/{Prompt.ask('Enter group name')}") or []
        )),
        "6": ("List all ransomware groups", list_groups),
        "7": ("Fetch ransomware group details", group_details),
        "8": ("Dashboard (time-series)", dashboard),
        "9": ("Exit", lambda: sys.exit(0)),
    }
    while True:
        console.print("\n[bold]Menu[/bold]")
        for key, (desc, _) in actions.items():
            console.print(f"  {key}. {desc}")
        choice = Prompt.ask("Select an option", choices=list(actions.keys()), default="9")
        actions[choice][1]()


if __name__ == "__main__":
    main()
