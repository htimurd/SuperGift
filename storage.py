import json
import os
import threading
from datetime import datetime, timezone

from config import DATA_FILE

_lock = threading.Lock()


def _default_data():
    return {
        "prizes": [
            {"id": 0, "name": "Ничего", "amount": 0, "chance": 99, "is_empty": True},
            {"id": 1, "name": "Мини-приз", "amount": 5, "chance": 40},
            {"id": 2, "name": "Малый приз", "amount": 25, "chance": 30},
            {"id": 3, "name": "Средний приз", "amount": 100, "chance": 20},
            {"id": 4, "name": "Большой приз", "amount": 500, "chance": 8},
            {"id": 5, "name": "Джекпот", "amount": 3000, "chance": 2},
        ],
        "next_prize_id": 6,
        "users": {},
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        data = _default_data()
        save_data(data)
        return data
    with _lock:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    changed = False
    # миграция старых записей без поля "name"
    for p in data.get("prizes", []):
        if "name" not in p:
            p["name"] = f"Приз ⭐{p['amount']}"
            changed = True

    # если в старых данных ещё нет "пустого" исхода — добавляем его
    if not any(p.get("is_empty") for p in data.get("prizes", [])):
        data["prizes"].insert(
            0, {"id": 0, "name": "Ничего", "amount": 0, "chance": 99, "is_empty": True}
        )
        changed = True

    if changed:
        save_data(data)
    return data


def save_data(data):
    with _lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- Призы ----------

def get_prizes():
    return load_data()["prizes"]


def get_prize(prize_id):
    for p in get_prizes():
        if p["id"] == prize_id:
            return p
    return None


def add_prize(name, amount, chance):
    data = load_data()
    pid = data["next_prize_id"]
    data["prizes"].append({"id": pid, "name": name, "amount": amount, "chance": chance})
    data["next_prize_id"] += 1
    save_data(data)
    return pid


def remove_prize(prize_id):
    data = load_data()
    data["prizes"] = [p for p in data["prizes"] if p["id"] != prize_id]
    save_data(data)


def edit_prize(prize_id, name=None, amount=None, chance=None):
    data = load_data()
    for p in data["prizes"]:
        if p["id"] == prize_id:
            if name is not None:
                p["name"] = name
            if amount is not None:
                p["amount"] = amount
            if chance is not None:
                p["chance"] = chance
    save_data(data)


# ---------- Пользователи / выигрыши ----------

def _ensure_user(data, user_id):
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"wins": [], "next_win_id": 1}
    return data["users"][uid]


def add_win(user_id, name, amount):
    data = load_data()
    user = _ensure_user(data, user_id)
    win_id = user["next_win_id"]
    user["wins"].append(
        {
            "id": win_id,
            "name": name,
            "amount": amount,
            "withdrawn": False,
            "won_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    user["next_win_id"] += 1
    save_data(data)
    return win_id


def get_wins(user_id, only_active=False):
    data = load_data()
    user = data["users"].get(str(user_id))
    if not user:
        return []
    wins = user["wins"]
    if only_active:
        wins = [w for w in wins if not w["withdrawn"]]
    return wins


def mark_withdrawn(user_id, win_ids):
    data = load_data()
    user = data["users"].get(str(user_id))
    if not user:
        return
    for w in user["wins"]:
        if w["id"] in win_ids:
            w["withdrawn"] = True
    save_data(data)
    
