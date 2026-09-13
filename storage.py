import json
import os
import threading
from datetime import datetime, timedelta, timezone

from config import DATA_FILE

_lock = threading.Lock()

SPIN_LIMIT = 5
SPIN_WINDOW_HOURS = 3
SG_PLUS_COST = 7000
SG_PLUS_DAYS = 7


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
    for p in data.get("prizes", []):
        if "name" not in p:
            p["name"] = f"Приз ⭐{p['amount']}"
            changed = True

    if not any(p.get("is_empty") for p in data.get("prizes", [])):
        data["prizes"].insert(
            0, {"id": 0, "name": "Ничего", "amount": 0, "chance": 99, "is_empty": True}
        )
        changed = True

    for u in data.get("users", {}).values():
        if "username" not in u:
            u["username"] = None
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
        data["users"][uid] = {
            "wins": [],
            "next_win_id": 1,
            "username": None,
            "spin_times": [],
            "sg_plus_until": None,
        }
    else:
        data["users"][uid].setdefault("spin_times", [])
        data["users"][uid].setdefault("sg_plus_until", None)
    return data["users"][uid]


def register_user(user_id, username):
    """Сохраняет username пользователя, чтобы его можно было находить для переводов."""
    data = load_data()
    user = _ensure_user(data, user_id)
    user["username"] = username.lower() if username else None
    save_data(data)


def find_user_id_by_username(username):
    uname = username.lower().lstrip("@").strip()
    data = load_data()
    for uid, u in data["users"].items():
        if u.get("username") and u["username"] == uname:
            return int(uid)
    return None


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


def get_win(user_id, win_id):
    for w in get_wins(user_id):
        if w["id"] == win_id:
            return w
    return None


def mark_withdrawn(user_id, win_ids):
    data = load_data()
    user = data["users"].get(str(user_id))
    if not user:
        return
    for w in user["wins"]:
        if w["id"] in win_ids:
            w["withdrawn"] = True
    save_data(data)


def get_balance(user_id):
    """Сумма всех невыведенных/непотраченных звёзд пользователя (кошелёк)."""
    return sum(w["amount"] for w in get_wins(user_id, only_active=True))


def _spend(data, user_id, amount, exclude_win_id=None):
    """Внутренняя функция: списывает amount звёзд с активных записей пользователя,
    не трогая запись exclude_win_id (если указана). Возвращает True/False."""
    user = data["users"].get(str(user_id))
    if not user:
        return False
    active = [w for w in user["wins"] if not w["withdrawn"] and w["id"] != exclude_win_id]
    total = sum(w["amount"] for w in active)
    if total < amount:
        return False
    remaining = amount
    for w in active:
        if remaining <= 0:
            break
        if w["amount"] <= remaining:
            remaining -= w["amount"]
            w["amount"] = 0
            w["withdrawn"] = True
        else:
            w["amount"] -= remaining
            remaining = 0
    return True


def spend_balance(user_id, amount):
    data = load_data()
    ok = _spend(data, user_id, amount)
    if ok:
        save_data(data)
    return ok


def spend_balance_excluding(user_id, amount, exclude_win_id):
    data = load_data()
    ok = _spend(data, user_id, amount, exclude_win_id=exclude_win_id)
    if ok:
        save_data(data)
    return ok


def multiply_win(user_id, win_id, factor):
    """Умножает сумму конкретного (ещё активного) выигрыша на factor. Возвращает новую сумму или None."""
    data = load_data()
    user = data["users"].get(str(user_id))
    if not user:
        return None
    for w in user["wins"]:
        if w["id"] == win_id and not w["withdrawn"]:
            w["amount"] = int(round(w["amount"] * factor))
            save_data(data)
            return w["amount"]
    return None


def transfer_stars(from_user_id, to_user_id, amount, note_name):
    """Переводит amount звёзд от одного пользователя другому. Возвращает True/False."""
    data = load_data()
    if not _spend(data, from_user_id, amount):
        return False
    recipient = _ensure_user(data, to_user_id)
    win_id = recipient["next_win_id"]
    recipient["wins"].append(
        {
            "id": win_id,
            "name": note_name,
            "amount": amount,
            "withdrawn": False,
            "won_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    recipient["next_win_id"] += 1
    save_data(data)
    return True


# ---------- SG Plus (снятие лимита круток) ----------

def get_sg_plus_until(user_id):
    data = load_data()
    user = data["users"].get(str(user_id))
    if not user:
        return None
    return user.get("sg_plus_until")


def has_sg_plus(user_id):
    until = get_sg_plus_until(user_id)
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > datetime.now(timezone.utc)
    except ValueError:
        return False


def buy_sg_plus(user_id, cost=SG_PLUS_COST, days=SG_PLUS_DAYS):
    """Списывает cost звёзд и продлевает/активирует SG Plus. Возвращает True/False."""
    data = load_data()
    if not _spend(data, user_id, cost):
        return False
    user = _ensure_user(data, user_id)
    now = datetime.now(timezone.utc)
    base = now
    current = user.get("sg_plus_until")
    if current:
        try:
            cur_dt = datetime.fromisoformat(current)
            if cur_dt > now:
                base = cur_dt
        except ValueError:
            pass
    user["sg_plus_until"] = (base + timedelta(days=days)).isoformat()
    save_data(data)
    return True


# ---------- Лимит круток (5 раз в 3 часа, если нет SG Plus) ----------

def check_spin_limit(user_id):
    """
    Возвращает (allowed, remaining, reset_in_seconds).
    Если у пользователя активен SG Plus — лимита нет: (True, None, None).
    """
    if has_sg_plus(user_id):
        return True, None, None

    data = load_data()
    user = _ensure_user(data, user_id)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=SPIN_WINDOW_HOURS)

    times = []
    for t in user.get("spin_times", []):
        try:
            dt = datetime.fromisoformat(t)
        except ValueError:
            continue
        if dt > window_start:
            times.append(dt)

    if len(times) != len(user.get("spin_times", [])):
        user["spin_times"] = [t.isoformat() for t in times]
        save_data(data)

    remaining = SPIN_LIMIT - len(times)
    if remaining <= 0:
        oldest = min(times)
        reset_at = oldest + timedelta(hours=SPIN_WINDOW_HOURS)
        reset_in = max(int((reset_at - now).total_seconds()), 0)
        return False, 0, reset_in

    return True, remaining, None


def record_spin(user_id):
    """Отмечает факт крутки (не действует, если у пользователя активен SG Plus)."""
    if has_sg_plus(user_id):
        return
    data = load_data()
    user = _ensure_user(data, user_id)
    user["spin_times"].append(datetime.now(timezone.utc).isoformat())
    save_data(data)
    
