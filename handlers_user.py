import asyncio
import random

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import keyboards as kb
import storage
from config import ADMIN_ID

router = Router()

# Временное хранилище "в оперативной памяти" — не переживает рестарт,
# но это только промежуточное состояние текущей сессии игрока (это нормально).
pending_wins: dict[int, dict] = {}
withdraw_selection: dict[int, set[int]] = {}
skip_events: dict[int, asyncio.Event] = {}

SPIN_SYMBOLS = ["🍒", "🍋", "🍇", "⭐", "🎁", "💎", "7️⃣"]

UPGRADE_FACTORS = {15: (1.5, 250), 20: (2.0, 500)}


class WalletSend(StatesGroup):
    username = State()
    amount = State()
    confirm = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    storage.register_user(message.from_user.id, message.from_user.username)
    await message.answer("👋 Добро пожаловать!\nВыберите действие:", reply_markup=kb.main_menu_kb())


@router.callback_query(F.data == "menu:back")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Выберите действие:", reply_markup=kb.main_menu_kb())
    await call.answer()


# ---------- Игра ----------

@router.callback_query(F.data == "menu:play")
async def open_play(call: CallbackQuery):
    await call.message.edit_text(
        "🌟 Звёздная рулетка\n\nНажмите «Крутить», чтобы испытать удачу!",
        reply_markup=kb.play_menu_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "play:back")
async def play_back(call: CallbackQuery):
    await call.message.edit_text("Выберите действие:", reply_markup=kb.main_menu_kb())
    await call.answer()


async def _safe_edit(message, text, reply_markup=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        pass


def _render_row(row):
    return "   ".join(row)


async def animate_slot(message, final_symbols, skip_event: asyncio.Event):
    lock_schedule = {5: 0, 8: 1, 11: 2}
    total_frames = 12
    locked = [False, False, False]

    for frame in range(total_frames):
        if skip_event.is_set():
            break

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

        await _safe_edit(message, f"{header}\n\n{_render_row(row)}", reply_markup=kb.spin_skip_kb())

        try:
            await asyncio.wait_for(skip_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            continue
        else:
            break


@router.callback_query(F.data == "play:spin")
async def spin(call: CallbackQuery):
    prizes = storage.get_prizes()
    weights = [max(p["chance"], 0) for p in prizes]
    if not prizes or sum(weights) <= 0:
        await call.answer("Призы ещё не настроены администратором.", show_alert=True)
        return

    await call.answer()

    won = random.choices(prizes, weights=weights, k=1)[0]
    is_empty = bool(won.get("is_empty"))

    if is_empty:
        final_symbols = random.sample(SPIN_SYMBOLS, 3)
    else:
        symbol = random.choice(SPIN_SYMBOLS)
        final_symbols = [symbol, symbol, symbol]

    skip_event = asyncio.Event()
    skip_events[call.from_user.id] = skip_event
    try:
        await animate_slot(call.message, final_symbols, skip_event)
    finally:
        skip_events.pop(call.from_user.id, None)

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


@router.callback_query(F.data == "spin:skip")
async def spin_skip(call: CallbackQuery):
    event = skip_events.get(call.from_user.id)
    if event:
        event.set()
    await call.answer("Пропускаем...")


@router.callback_query(F.data == "play:claim")
async def claim(call: CallbackQuery):
    win = pending_wins.pop(call.from_user.id, None)
    if win is not None:
        storage.add_win(call.from_user.id, win["name"], win["amount"])
        await call.answer(f"Начислено: {win['name']} ⭐ {win['amount']}!", show_alert=True)
    await call.message.edit_text(
        "🌟 Звёздная рулетка\n\nНажмите «Крутить», чтобы испытать удачу!",
        reply_markup=kb.play_menu_kb(),
    )


# ---------- Портфель ----------

@router.callback_query(F.data == "menu:portfolio")
async def show_portfolio(call: CallbackQuery):
    wins = storage.get_wins(call.from_user.id)
    if not wins:
        text = "💼 Ваш портфель пуст."
    else:
        lines = ["💼 Ваши выигрыши:\n"]
        for w in wins:
            if w["withdrawn"]:
                status = "✅ выведено / потрачено"
            else:
                status = "🕒 в портфеле"
            name = w.get("name", "Приз")
            lines.append(f"{name} — ⭐ {w['amount']} — {status}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb.back_kb())
    await call.answer()


# ---------- Вывод ----------

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


# ---------- Магазин (гарантированный апгрейд приза за звёзды) ----------

@router.callback_query(F.data == "menu:shop")
async def open_shop(call: CallbackQuery):
    wins = storage.get_wins(call.from_user.id, only_active=True)
    if not wins:
        await call.answer("В портфеле нет призов для апгрейда.", show_alert=True)
        return
    await call.message.edit_text(
        "🛒 Магазин\n\nВыберите приз, который хотите улучшить:",
        reply_markup=kb.shop_prize_list_kb(call.from_user.id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("shop:select:"))
async def shop_select(call: CallbackQuery):
    win_id = int(call.data.split(":")[2])
    win = storage.get_win(call.from_user.id, win_id)
    if not win or win["withdrawn"]:
        await call.answer("Этот приз уже недоступен.", show_alert=True)
        return
    await call.message.edit_text(
        f"Приз: {win['name']} — ⭐ {win['amount']}\n\n"
        f"Выберите множитель апгрейда (оплата — из остальных звёзд вашего портфеля):",
        reply_markup=kb.shop_upgrade_options_kb(win_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("shop:buy:"))
async def shop_buy(call: CallbackQuery):
    _, _, win_id_str, code_str = call.data.split(":")
    win_id = int(win_id_str)
    code = int(code_str)

    if code not in UPGRADE_FACTORS:
        await call.answer("Неизвестный вариант апгрейда.", show_alert=True)
        return

    factor, cost = UPGRADE_FACTORS[code]

    win = storage.get_win(call.from_user.id, win_id)
    if not win or win["withdrawn"]:
        await call.answer("Этот приз уже недоступен.", show_alert=True)
        return

    ok = storage.spend_balance_excluding(call.from_user.id, cost, exclude_win_id=win_id)
    if not ok:
        await call.answer(
            "Недостаточно ⭐ на балансе (не считая апгрейдируемого приза).",
            show_alert=True,
        )
        return

    new_amount = storage.multiply_win(call.from_user.id, win_id, factor)
    await call.answer(f"Готово! Новое количество: ⭐ {new_amount}", show_alert=True)
    await call.message.edit_text(
        f"✅ Приз «{win['name']}» улучшен в x{factor}!\nНовое количество: ⭐ {new_amount}",
        reply_markup=kb.back_kb(),
    )


# ---------- Кошелёк (перевод по username) ----------

@router.callback_query(F.data == "menu:wallet")
async def open_wallet(call: CallbackQuery):
    balance = storage.get_balance(call.from_user.id)
    await call.message.edit_text(
        f"👛 Кошелёк\n\nВаш баланс: ⭐ {balance}",
        reply_markup=kb.wallet_menu_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "wallet:send")
async def wallet_send_start(call: CallbackQuery, state: FSMContext):
    balance = storage.get_balance(call.from_user.id)
    if balance <= 0:
        await call.answer("На балансе нет звёзд для перевода.", show_alert=True)
        return
    await state.set_state(WalletSend.username)
    await call.message.edit_text(
        "Введите @username получателя (он должен хотя бы раз запускать этого бота):",
        reply_markup=kb.wallet_cancel_kb(),
    )
    await call.answer()


@router.message(StateFilter(WalletSend.username))
async def wallet_send_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    if not username:
        return await message.answer("Введите корректный @username.")

    to_user_id = storage.find_user_id_by_username(username)
    if to_user_id is None:
        return await message.answer(
            "Пользователь не найден. Он должен хотя бы раз написать боту /start. "
            "Попробуйте ещё раз или нажмите «Отмена».",
            reply_markup=kb.wallet_cancel_kb(),
        )
    if to_user_id == message.from_user.id:
        return await message.answer(
            "Нельзя перевести звёзды самому себе. Введите другой @username.",
            reply_markup=kb.wallet_cancel_kb(),
        )

    await state.update_data(to_user_id=to_user_id, to_username=username)
    await state.set_state(WalletSend.amount)
    balance = storage.get_balance(message.from_user.id)
    await message.answer(
        f"Ваш баланс: ⭐ {balance}\nВведите количество ⭐ для перевода @{username}:",
        reply_markup=kb.wallet_cancel_kb(),
    )


@router.message(StateFilter(WalletSend.amount))
async def wallet_send_amount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите целое положительное число.")
    amount = int(message.text)
    if amount <= 0:
        return await message.answer("Сумма должна быть больше нуля.")

    balance = storage.get_balance(message.from_user.id)
    if amount > balance:
        return await message.answer(f"Недостаточно ⭐. Ваш баланс: {balance}.")

    data = await state.get_data()
    await state.update_data(amount=amount)
    await state.set_state(WalletSend.confirm)
    await message.answer(
        f"Перевести ⭐ {amount} пользователю @{data['to_username']}?",
        reply_markup=kb.wallet_confirm_kb(),
    )


@router.callback_query(F.data == "wallet:confirm")
async def wallet_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    to_user_id = data.get("to_user_id")
    to_username = data.get("to_username")
    amount = data.get("amount")
    await state.clear()

    if not to_user_id or not amount:
        await call.message.edit_text("Что-то пошло не так, начните перевод заново.", reply_markup=kb.main_menu_kb())
        await call.answer()
        return

    sender_username = call.from_user.username
    sender_label = f"@{sender_username}" if sender_username else call.from_user.full_name
    note_name = f"Перевод от {sender_label}"

    ok = storage.transfer_stars(call.from_user.id, to_user_id, amount, note_name)
    if not ok:
        await call.message.edit_text("Недостаточно ⭐ для перевода.", reply_markup=kb.main_menu_kb())
        await call.answer()
        return

    await call.message.edit_text(
        f"✅ Вы перевели ⭐ {amount} пользователю @{to_username}!",
        reply_markup=kb.main_menu_kb(),
    )
    try:
        await call.bot.send_message(
            to_user_id,
            f"💌 Вам перевели ⭐ {amount} от {sender_label}!",
        )
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "wallet:cancel")
async def wallet_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Перевод отменён.", reply_markup=kb.main_menu_kb())
    await call.answer()
                
