import random

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery

import keyboards as kb
import storage
from config import ADMIN_ID

router = Router()

# Временное хранилище "в оперативной памяти" (не переживает рестарт — это ок,
# т.к. это только промежуточное состояние текущей сессии игрока)
pending_wins: dict[int, int] = {}
withdraw_selection: dict[int, set[int]] = {}


@router.message(CommandStart())
async def cmd_start(message):
    await message.answer("👋 Добро пожаловать!\nВыберите действие:", reply_markup=kb.main_menu_kb())


@router.callback_query(F.data == "menu:back")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_text("Выберите действие:", reply_markup=kb.main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "menu:play")
async def open_play(call: CallbackQuery):
    await call.message.edit_text(
        "🎮 Игра\n\nНажмите «Крутить», чтобы испытать удачу!",
        reply_markup=kb.play_menu_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "play:back")
async def play_back(call: CallbackQuery):
    await call.message.edit_text("Выберите действие:", reply_markup=kb.main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "play:spin")
async def spin(call: CallbackQuery):
    prizes = storage.get_prizes()
    weights = [max(p["chance"], 0) for p in prizes]
    if not prizes or sum(weights) <= 0:
        await call.answer("Призы ещё не настроены администратором.", show_alert=True)
        return

    won = random.choices(prizes, weights=weights, k=1)[0]
    pending_wins[call.from_user.id] = won["amount"]

    await call.message.edit_text(f"🎉 Вы выиграли ⭐ {won['amount']}!", reply_markup=kb.claim_kb())
    await call.answer()


@router.callback_query(F.data == "play:claim")
async def claim(call: CallbackQuery):
    amount = pending_wins.pop(call.from_user.id, None)
    if amount is not None:
        storage.add_win(call.from_user.id, amount)
        await call.answer(f"Начислено ⭐ {amount} в портфель!", show_alert=True)
    await call.message.edit_text(
        "🎮 Игра\n\nНажмите «Крутить», чтобы испытать удачу!",
        reply_markup=kb.play_menu_kb(),
    )


@router.callback_query(F.data == "menu:portfolio")
async def show_portfolio(call: CallbackQuery):
    wins = storage.get_wins(call.from_user.id)
    if not wins:
        text = "💼 Ваш портфель пуст."
    else:
        lines = ["💼 Ваши выигрыши:\n"]
        for w in wins:
            status = "✅ выведено" if w["withdrawn"] else "🕒 в портфеле"
            lines.append(f"⭐ {w['amount']} — {status}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb.back_kb())
    await call.answer()


@router.callback_query(F.data == "menu:withdraw")
async def open_withdraw(call: CallbackQuery):
    wins = storage.get_wins(call.from_user.id, only_active=True)
    if not wins:
        await call.answer("Нет доступных выигрышей для вывода.", show_alert=True)
        return
    withdraw_selection[call.from_user.id] = set()
    await call.message.edit_text(
        "💸 Выберите призы для вывода:",
        reply_markup=kb.withdraw_select_kb(call.from_user.id, withdraw_selection[call.from_user.id]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("withdraw:toggle:"))
async def toggle_withdraw(call: CallbackQuery):
    win_id = int(call.data.split(":")[2])
    sel = withdraw_selection.setdefault(call.from_user.id, set())
    if win_id in sel:
        sel.remove(win_id)
    else:
        sel.add(win_id)
    await call.message.edit_reply_markup(reply_markup=kb.withdraw_select_kb(call.from_user.id, sel))
    await call.answer()


@router.callback_query(F.data == "withdraw:go")
async def withdraw_go(call: CallbackQuery):
    sel = withdraw_selection.get(call.from_user.id, set())
    if not sel:
        await call.answer("Выберите хотя бы один приз.", show_alert=True)
        return
    total = sum(w["amount"] for w in storage.get_wins(call.from_user.id) if w["id"] in sel)
    await call.message.edit_text(f"Вы собираетесь вывести ⭐ {total}.\nПодтвердить?", reply_markup=kb.confirm_kb())
    await call.answer()


@router.callback_query(F.data == "withdraw:confirm")
async def withdraw_confirm(call: CallbackQuery):
    sel = withdraw_selection.pop(call.from_user.id, set())
    if sel:
        storage.mark_withdrawn(call.from_user.id, sel)
        total = sum(w["amount"] for w in storage.get_wins(call.from_user.id) if w["id"] in sel)
        try:
            await call.bot.send_message(
                ADMIN_ID,
                f"📤 Запрос на вывод\n"
                f"Пользователь: {call.from_user.full_name} (id {call.from_user.id})\n"
                f"Сумма: ⭐ {total}",
            )
        except Exception:
            pass
        await call.message.edit_text(f"✅ Заявка на вывод ⭐ {total} отправлена!", reply_markup=kb.main_menu_kb())
    else:
        await call.message.edit_text("Выберите действие:", reply_markup=kb.main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "withdraw:cancel")
async def withdraw_cancel(call: CallbackQuery):
    withdraw_selection.pop(call.from_user.id, None)
    await call.message.edit_text("❌ Вывод отменён.", reply_markup=kb.main_menu_kb())
    await call.answer()
  
