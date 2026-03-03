import asyncio
import aiohttp
import os
import sqlite3
import time
from datetime import datetime

def splash():
    print("\n" + "=" * 50)
    print("                  ITEM SNIPER")
    print("=" * 50 + "\n")

splash()

ITEMS = [
    {
        "asset_id": 126565976059224,
        "target_price": 560000,
        "name": "The Classic ROBLOX Fedora"
    }
]

CHECK_DELAY = 5
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
PING_ROLE_ID = os.getenv("PING_ROLE_ID")

conn = sqlite3.connect("data.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    asset_id INTEGER,
    price INTEGER,
    remaining INTEGER,
    timestamp TEXT
)
""")
conn.commit()

async def send_discord(session, item_name, price, remaining, velocity):
    if not DISCORD_WEBHOOK:
        return

    content = f"<@&{PING_ROLE_ID}>" if PING_ROLE_ID else None

    embed = {
        "title": f"Item Sniper | {item_name}",
        "color": 15158332,
        "fields": [
            {"name": "Price", "value": f"{price} Robux", "inline": True},
            {"name": "Remaining", "value": str(remaining), "inline": True},
            {"name": "Velocity/min", "value": str(velocity), "inline": False}
        ],
        "timestamp": datetime.utcnow().isoformat()
    }

    payload = {"content": content, "embeds": [embed]}

    try:
        await session.post(DISCORD_WEBHOOK, json=payload)
    except Exception:
        pass

async def fetch_item(session, asset_id):
    url = f"https://economy.roblox.com/v2/assets/{asset_id}/details"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception:
        return None

def calculate_velocity(asset_id):
    cursor.execute("""
        SELECT remaining, timestamp
        FROM logs
        WHERE asset_id = ?
        ORDER BY timestamp DESC
        LIMIT 2
    """, (asset_id,))
    
    rows = cursor.fetchall()
    if len(rows) < 2:
        return 0

    latest_remaining, latest_time = rows[0]
    prev_remaining, prev_time = rows[1]

    time_diff = (datetime.fromisoformat(latest_time) - datetime.fromisoformat(prev_time)).total_seconds()
    if time_diff <= 0:
        return 0

    sold = prev_remaining - latest_remaining
    if sold <= 0:
        return 0

    return round((sold / time_diff) * 60, 2)

def display_dashboard(items_data):
    print("\033[2J\033[H", end="")
    print("="*50)
    print("            ITEM SNIPER DASHBOARD")
    print("="*50)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"Last Update: {now}\n")
    print(f"{'Item Name':30} | {'Price':8} | {'Remaining':8} | {'Vel/min':8}")
    print("-"*50)
    for data in items_data:
        print(f"{data['name'][:30]:30} | {data['price']:8} | {data['remaining']:8} | {data['velocity']:8}")
    print("\n" + "="*50 + "\n")

async def monitor():
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            items_data = []
            try:
                for item in ITEMS:
                    data = await fetch_item(session, item["asset_id"])
                    if not data:
                        continue

                    price = data.get("priceInRobux")
                    remaining = data.get("remaining")
                    name = data.get("name", item["name"])

                    if price is None or remaining is None:
                        continue

                    now = datetime.utcnow().isoformat()
                    cursor.execute(
                        "INSERT INTO logs VALUES (?, ?, ?, ?)",
                        (item["asset_id"], price, remaining, now)
                    )
                    conn.commit()

                    velocity = calculate_velocity(item["asset_id"])

                    items_data.append({
                        "name": name,
                        "price": price,
                        "remaining": remaining,
                        "velocity": velocity
                    })

                    if price <= item["target_price"]:
                        await send_discord(session, name, price, remaining, velocity)

                display_dashboard(items_data)
                await asyncio.sleep(CHECK_DELAY)

            except Exception as e:
                print("Loop error:", e)
                await asyncio.sleep(5)

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(monitor())
        except Exception:
            print("Restarting in 5 seconds...")
            time.sleep(5)
