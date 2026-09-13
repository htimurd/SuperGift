from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import storage


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎮 Играть", callback_data="menu:play")
    kb.button(text="💸 Вывод", callback_data="menu:withdraw")
    kb.button(text="💼 Портфель", callback_data="menu:portfolio")
    kb.adjust(1)
    return kb.as_markup()


def play_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎰 Крутить", callback_data="play:spin")
    kb.button(text="⬅️ Назад", callback_data="play:back")
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
        kb.button(text=f"{mark} ⭐ {w['amount']}", callback_data=f"withdraw:toggle:{w['id']}")
    kb.adjust(1)
    kb.row(
        InlineKeyboardButton(text="📤 Вывести", callback_data="withdraw:go"),
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
            text=f"⭐ {p['amount']} (шанс {p['chance']})",
            callback_data=f"admin:{action_prefix}:{p['id']}",
        )
    kb.button(text="⬅️ Назад", callback_data="admin:menu")
    kb.adjust(1)
    return kb.as_markup()
  
