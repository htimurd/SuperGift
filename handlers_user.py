import asyncio
import random

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery

import keyboards as kb
import storage
from config import ADMIN_ID

router = Router()

# Временное хранилище "в оперативной памяти" — не переживает рестарт,
# но это только промежуточное состояние текущей сессии игрока (это нормально).
pending_wins: dict[int, dict] = {}
withdraw_selection: dict[int, set[int]] = {}

SPIN_SYMBOLS = ["🍒", "🍋", "🍇", "⭐", "🎁", "💎", "7️⃣"]


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


async def _safe_edit(message, text, reply_markup=None):
    """Редактирует сообщение, игнорируя ошибку 'message is not modified'."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        pass


def _render_row(row):
    return "   ".join(row)


async def animate_slot(message, final_symbols):
    """
    Анимация как в игровых автоматах: 3 колеса крутятся одновременно,
    затем по очереди останавливаются одно за другим (сначала левое,
    потом среднее, потом правое), пока все три не покажут финальный результат.
    """
    # На каком кадре останавливается очередное колесо (индекс колеса 0,1,2)
    lock_schedule = {5: 0, 8: 1, 11: 2}
    total_frames = 12
    locked = [False, False, False]

    for frame in range(total_frames):
        if frame in lock_schedule:
            locked[lock_schedule[frame]] = True

        row = [
            final_symbols[i] if locked[i] else random.choice(SPIN_SYMBOLS)
            for i in range(3)
        ]

        stopped_count = locked.count(True)
        if stopped_count == 0:
            header = "🎰 Крутим барабан..."
            delay = 0.18
        elif stopped_count == 1:
            header = "🎰 Первое колесо остановилось!"
            delay = 0.28
        elif stopped_count == 2:
            header = "🎰 Второе колесо остановилось!"
            delay = 0.4
        else:
            header = "🎰 Барабан остановился!"
            delay = 0.6

        await _safe_edit(message, f"{header}\n\n{_render_row(row)}")
        await asyncio.sleep(delay)


@router.callback_query(F.data == "play:spin")
async def spin(call: CallbackQuery):
    prizes = storage.get_prizes()
    weights = [max(p["chance"], 0) for p in prizes]
    if not prizes or sum(weights) <= 0:
        await call.answer("Призы ещё не настроены администратором.", show_alert=True)
        return

    await call.answer()

    # Результат определяем заранее — анимация лишь оттягивает показ.
    won = random.choices(prizes, weights=weights, k=1)[0]
    is_empty = bool(won.get("is_empty"))

    if is_empty:
        # три РАЗНЫХ символа — визуально "не сошлось", проигрыш
        final_symbols = random.sample(SPIN_SYMBOLS, 3)
    else:
        # три ОДИНАКОВЫХ символа — визуально "джекпот", выигрыш
        symbol = random.choice(SPIN_SYMBOLS)
        final_symbols = [symbol, symbol, symbol]

    await animate_slot(call.message, final_symbols)

    if is_empty:
        await _safe_edit(
            call.message,
            "😔 Увы, в этот раз ничего не выпало.\nПопробуйте ещё раз!",
            reply_markup=kb.play_menu_kb(),
        )
        return

    pending_wins[call.from_user.id] = {"name": won["name"], "amount": won["amount"]}
    await _safe_edit(
        call.message,
        f"🎉 Вы выиграли: {won['name']}\n⭐ {won['amount']}!",
        reply_markup=kb.claim_kb(),
    )


@router.callback_query(F.data == "play:claim")
async def claim(call: CallbackQuery):
    win = pending_wins.pop(call.from_user.id, None)
    if win is not None:
        storage.add_win(call.from_user.id, win["name"], win["amount"])
        await call.answer(f"Начислено: {win['name']} ⭐ {win['amount']}!", show_alert=True)
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
            name = w.get("name", "Приз")
            lines.append(f"{name} — ⭐ {w['amount']} — {status}")
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


async def _show_withdraw_confirm(call: CallbackQuery, sel: set[int]):
    chosen = [w for w in storage.get_wins(call.from_user.id) if w["id"] in sel]
    total = sum(w["amount"] for w in chosen)
    names = "\n".join(f"— {w.get('name', 'Приз')} (⭐ {w['amount']})" for w in chosen)
    await call.message.edit_text(
        f"Вы собираетесь вывести:\n{names}\n\nИтого: ⭐ {total}\nПодтвердить?",
        reply_markup=kb.confirm_kb(),
    )


@router.callback_query(F.data == "withdraw:go")
async def withdraw_go(call: CallbackQuery):
    sel = withdraw_selection.get(call.from_user.id, set())
    if not sel:
        await call.answer("Выберите хотя бы один приз.", show_alert=True)
        return
    await _show_withdraw_confirm(call, sel)
    await call.answer()


@router.callback_query(F.data == "withdraw:all")
async def withdraw_all(call: CallbackQuery):
    wins = storage.get_wins(call.from_user.id, only_active=True)
    if not wins:
        await call.answer("Нет доступных выигрышей для вывода.", show_alert=True)
        return
    sel = {w["id"] for w in wins}
    withdraw_selection[call.from_user.id] = sel
    await _show_withdraw_confirm(call, sel)
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
                f"✅ Пользователь {call.from_user.full_name} (id {call.from_user.id}) "
                f"вывел ⭐ {total}",
            )
        except Exception:
            pass
        await call.message.edit_text(f"✅ Вы успешно вывели ⭐ {total}!", reply_markup=kb.main_menu_kb())
    else:
        await call.message.edit_text("Выберите действие:", reply_markup=kb.main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "withdraw:cancel")
async def withdraw_cancel(call: CallbackQuery):
    withdraw_selection.pop(call.from_user.id, None)
    await call.message.edit_text("❌ Вывод отменён.", reply_markup=kb.main_menu_kb())
    await call.answer()
    
