from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import keyboards as kb
import storage
from config import ADMIN_ID

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


class AddPrize(StatesGroup):
    name = State()
    amount = State()
    chance = State()


class EditPrize(StatesGroup):
    name = State()
    amount = State()
    chance = State()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 Админ-панель", reply_markup=kb.admin_menu_kb())


@router.callback_query(F.data == "admin:menu")
async def admin_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    await call.message.edit_text("🛠 Админ-панель", reply_markup=kb.admin_menu_kb())
    await call.answer()


@router.callback_query(F.data == "admin:list")
async def admin_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    prizes = storage.get_prizes()
    if not prizes:
        text = "Список призов пуст."
    else:
        lines = ["📋 Призы:\n"]
        for p in prizes:
            lines.append(f"#{p['id']} — {p['name']} — ⭐ {p['amount']}, шанс {p['chance']}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb.admin_menu_kb())
    await call.answer()


# ---------- Добавление ----------

@router.callback_query(F.data == "admin:add")
async def admin_add_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await state.set_state(AddPrize.name)
    await call.message.edit_text("Введите название приза (например: «Плюшевый мишка»):")
    await call.answer()


@router.message(StateFilter(AddPrize.name))
async def admin_add_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if not name:
        return await message.answer("Название не может быть пустым.")
    await state.update_data(name=name)
    await state.set_state(AddPrize.amount)
    await message.answer("Введите количество ⭐ для этого приза:")


@router.message(StateFilter(AddPrize.amount))
async def admin_add_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.isdigit():
        return await message.answer("Введите целое число.")
    await state.update_data(amount=int(message.text))
    await state.set_state(AddPrize.chance)
    await message.answer("Введите шанс выпадения (целое число, например 10):")


@router.message(StateFilter(AddPrize.chance))
async def admin_add_chance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.isdigit():
        return await message.answer("Введите целое число.")
    data = await state.get_data()
    storage.add_prize(data["name"], data["amount"], int(message.text))
    await state.clear()
    await message.answer("✅ Приз добавлен.", reply_markup=kb.admin_menu_kb())


# ---------- Удаление ----------

@router.callback_query(F.data == "admin:remove")
async def admin_remove_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await call.message.edit_text("Выберите приз для удаления:", reply_markup=kb.admin_prize_list_kb("do_remove"))
    await call.answer()


@router.callback_query(F.data.startswith("admin:do_remove:"))
async def admin_remove_do(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    prize_id = int(call.data.split(":")[2])
    storage.remove_prize(prize_id)
    await call.answer("Удалено.")
    await call.message.edit_text("Выберите приз для удаления:", reply_markup=kb.admin_prize_list_kb("do_remove"))


# ---------- Изменение (название + сумма + шанс) ----------

@router.callback_query(F.data == "admin:edit")
async def admin_edit_start(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await call.message.edit_text("Выберите приз для изменения:", reply_markup=kb.admin_prize_list_kb("do_edit"))
    await call.answer()


@router.callback_query(F.data.startswith("admin:do_edit:"))
async def admin_edit_choose(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    prize_id = int(call.data.split(":")[2])
    await state.update_data(prize_id=prize_id)
    await state.set_state(EditPrize.name)
    await call.message.edit_text("Введите новое название приза (или «-», чтобы не менять):")
    await call.answer()


@router.message(StateFilter(EditPrize.name))
async def admin_edit_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    await state.update_data(name=None if text == "-" else text)
    await state.set_state(EditPrize.amount)
    await message.answer("Введите новое количество ⭐ (0 — не менять):")


@router.message(StateFilter(EditPrize.amount))
async def admin_edit_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.isdigit():
        return await message.answer("Введите целое число.")
    await state.update_data(amount=int(message.text))
    await state.set_state(EditPrize.chance)
    await message.answer("Введите новый шанс (0 — не менять):")


@router.message(StateFilter(EditPrize.chance))
async def admin_edit_chance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.isdigit():
        return await message.answer("Введите целое число.")
    data = await state.get_data()
    amount = data["amount"] or None
    chance = int(message.text) or None
    storage.edit_prize(data["prize_id"], name=data.get("name"), amount=amount, chance=chance)
    await state.clear()
    await message.answer("✅ Приз обновлён.", reply_markup=kb.admin_menu_kb())
    
