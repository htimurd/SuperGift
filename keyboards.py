from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import storage


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎮 Играть", callback_data="menu:play")
    kb.button(text="💸 Вывод", callback_data="menu:withdraw")
    kb.button(text="💼 Портфель", callback_data="menu:portfolio")
    kb.button(text="🛒 Магазин", callback_data="menu:shop")
    kb.button(text="👤 Профиль", callback_data="menu:profile")
    kb.adjust(1)
    return kb.as_markup()


def play_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎰 Крутить", callback_data="play:spin")
    kb.button(text="⬅️ Назад", callback_data="play:back")
    kb.adjust(1)
    return kb.as_markup()


def spin_skip_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Пропустить", callback_data="spin:skip")
    kb.adjust(1)
    return kb.as_markup()


def claim_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Забрать", callback_data="play:claim")
    kb.adjust(1)
    return kb.as_markup()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="menu:back")
    kb.adjust(1)
    return kb.as_markup()


def withdraw_select_kb(user_id, selected):
    wins = storage.get_wins(user_id, only_active=True)
    kb = InlineKeyboardBuilder()
    for w in wins:
        mark = "☑️" if w["id"] in selected else "⬜️"
        name = w.get("name", "Приз")
        kb.button(text=f"{mark} {name} — ⭐ {w['amount']}", callback_data=f"withdraw:toggle:{w['id']}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="💰 Вывести всё", callback_data="withdraw:all"))
    kb.row(
        InlineKeyboardButton(text="📤 Вывести выбранное", callback_data="withdraw:go"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:back"),
    )
    return kb.as_markup()


def confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="withdraw:confirm")
    kb.button(text="❌ Отмена", callback_data="withdraw:cancel")
    kb.adjust(2)
    return kb.as_markup()


def admin_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить приз", callback_data="admin:add")
    kb.button(text="✏️ Изменить приз", callback_data="admin:edit")
    kb.button(text="🗑 Удалить приз", callback_data="admin:remove")
    kb.button(text="📋 Список призов", callback_data="admin:list")
    kb.adjust(1)
    return kb.as_markup()


def admin_prize_list_kb(action_prefix):
    kb = InlineKeyboardBuilder()
    for p in storage.get_prizes():
        kb.button(
            text=f"{p['name']} — ⭐{p['amount']} (шанс {p['chance']})",
            callback_data=f"admin:{action_prefix}:{p['id']}",
        )
    kb.button(text="⬅️ Назад", callback_data="admin:menu")
    kb.adjust(1)
    return kb.as_markup()


# ---------- Магазин ----------

def shop_prize_list_kb(user_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="💎 SG Plus — 7000⭐ (снять лимит круток на 7 дней)", callback_data="shop:sgplus")
    for w in storage.get_wins(user_id, only_active=True):
        kb.button(
            text=f"⬆️ {w.get('name', 'Приз')} — ⭐ {w['amount']}",
            callback_data=f"shop:select:{w['id']}",
        )
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:back"))
    return kb.as_markup()


def shop_upgrade_options_kb(win_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✨ x1.5 — 250⭐", callback_data=f"shop:buy:{win_id}:15")
    kb.button(text="🌟 x2.0 — 500⭐", callback_data=f"shop:buy:{win_id}:20")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:shop"))
    return kb.as_markup()


# ---------- Профиль (включает кошелёк) ----------

def profile_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Перевести звёзды", callback_data="wallet:send")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:back"))
    return kb.as_markup()


def wallet_confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="wallet:confirm")
    kb.button(text="❌ Отмена", callback_data="wallet:cancel")
    kb.adjust(2)
    return kb.as_markup()


def wallet_cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="wallet:cancel")
    kb.adjust(1)
    return kb.as_markup()
    
