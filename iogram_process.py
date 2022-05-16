from __future__ import annotations

import asyncio
import logging

import sqlalchemy
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.redis import RedisStorage2

import db_control
from bot_exceptions import *
from time_processes import TimeDispatcher as TD

import time

import datetime
import constants

from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton, ForceReply

API_TOKEN = constants.TOKEN

storage = RedisStorage2(
    host=constants.REDIS_HOST,
    port=constants.REDIS_PORT,
    # db=constants.REDIS_DB,
    password=constants.REDIS_PASSWORD,
)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)


class DayTasks(StatesGroup):
    choose_operation_variant = State()

    # add task scenario
    add_day_phase = State()
    add_task_name_phase = State()
    add_notification_phase = State()
    add_new_task_possibility_phase = State()

    # delete task scenario
    delete_day_phase = State()
    delete_number_phase = State()

    # show tasks scenario
    show_day_phase = State()


class Timezone(StatesGroup):
    add_timezone_offset = State()


@dp.message_handler(commands="start", state="*")
async def clear(message: types.Message, state: FSMContext):
    """
    Send welcome message to user and try to add him in database
    """
    await state.finish()
    await message.answer(text=constants.WELCOME_DESCRIPTION)
    await insert_user(message.from_user.id, message.from_user.first_name, message.from_user.last_name)


@dp.message_handler(commands="clear", state="*")
async def clear(message: types.Message, state: FSMContext):
    """
    Forget all states
    """
    await state.finish()
    await message.answer(text="Сброшено")


@dp.message_handler(commands="day_tasks", state="*")
async def process_day_tasks_start(message: types.Message, state: FSMContext):
    """
    Process sends to user day_tasks operation variants
    """
    inline_kb_full = InlineKeyboardMarkup(row_width=3)
    inline_btn_1 = InlineKeyboardButton('Добавить', callback_data="insert_day_task")
    inline_btn_3 = InlineKeyboardButton('Удалить', callback_data="delete_day_task")
    inline_btn_4 = InlineKeyboardButton('Показать', callback_data="get_day_tasks")
    inline_kb_full.row(inline_btn_1, inline_btn_3, inline_btn_4)

    await message.answer(text="Вы хотите добавить, удалить или показать дневные цели?",
                         reply_markup=inline_kb_full)
    await DayTasks.choose_operation_variant.set()

    async with state.proxy() as data:
        data['user_id'] = message.from_user.id


@dp.callback_query_handler(state=DayTasks.choose_operation_variant)
async def process_day_tasks_choose_variant(callback, state: FSMContext):
    """
    Process user chooses variant of day_tasks operation
    """
    async with state.proxy() as data:
        user_id = data['user_id']
    if callback.data == "insert_day_task":
        await DayTasks.add_day_phase.set()
        await callback.message.edit_text("На какой день планируется задача? Введи в формате гггг мм дд, либо выбери "
                                         "из предложенного",
                                         reply_markup=get_near_days_markup(user_id))
        async with state.proxy() as data:
            data['message'] = callback.message.message_id
    elif callback.data == "delete_day_task":
        await DayTasks.delete_day_phase.set()
        await callback.message.edit_text("Введите в какой день была эта цель в формате гггг мм дд, либо выберите "
                                         "из предложенного",
                                         reply_markup=get_near_days_markup(user_id))
        async with state.proxy() as data:
            data['message'] = callback.message.message_id
    elif callback.data == "get_day_tasks":
        await DayTasks.show_day_phase.set()
        await callback.message.edit_text("График целей какого дня ты хочешь увидеть? Вводи в формате гггг мм дд, либо "
                                         "выбери из предложенного",
                                         reply_markup=get_near_days_markup(user_id))
        async with state.proxy() as data:
            data['message'] = callback.message.message_id

    # async with state.proxy() as data:
    #     data['name'] = message.data

    # await DayTasks.add_name.set()
    # async with state.proxy() as data:
    #     await message.answer(str(data['name']))
    # await message.answer("How old are you?")


@dp.callback_query_handler(state=DayTasks.add_day_phase)
async def process_day_tasks_add_day_phase(callback: types.CallbackQuery, state: FSMContext):
    """
    Process check day from CallbackQuery and user should input task
    """
    try:
        async with state.proxy() as data:
            user_id = data['user_id']
        goal_date = check_date(callback.data)
        async with state.proxy() as data:
            data['day'] = goal_date
            await DayTasks.add_task_name_phase.set()
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text="Какую дневную цель добавим? Введи её полностью")
    except WrongDayFormat as e:
        async with state.proxy() as data:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text="Что-то пошло не так. Отчёт об ошибке отправлен создателю.")
            await bot.send_message(constants.BUG_LOG_ACCOUNT, f"Ошибка в боте: {e.__class__.__name__}")


@dp.message_handler(state=DayTasks.add_day_phase)
async def process_day_tasks_add_day_phase(message: types.Message, state: FSMContext):
    """
    Process check day from Message and user should input task
    """
    try:
        goal_date = check_date(message.text)
        await DayTasks.add_task_name_phase.set()
        async with state.proxy() as data:
            data['day'] = goal_date
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Какую дневную цель добавим? Введи её полностью")
    except WrongDayFormat:
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Дата введена в неправильном формате. Попробуй еще раз. "
                                                   "Можно выбрать вариант снизу 👇",
                                              reply_markup=get_near_days_markup(message.from_user.id))


@dp.message_handler(state=DayTasks.add_task_name_phase)
async def process_day_tasks_add_task_name_phase(message: types.Message, state: FSMContext):
    """
    Process check task name and user should input reminder time for task
    """
    if len(message.text) > 1:
        async with state.proxy() as data:
            data['task'] = message.text
        await DayTasks.add_notification_phase.set()
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Введите время, когда следует напомнить о задаче в формате чч.мм\n"
                                                   "Либо нажмите на кнопку снизу", reply_markup=get_None_markup())
    else:
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Название задачи должно быть длиннее хотя бы одного символа. "
                                                   "Попробуй ввести еще раз.")


@dp.message_handler(state=DayTasks.add_notification_phase)
async def process_day_tasks_add_notification_phase(message: types.Message, state: FSMContext):
    """
    Process check notification. If there is a notification, the function checks its correctness.
    If the entered information is correct, the function enters the task into the database and
    offers to enter a new task.
    """
    try:
        hours, minutes = TD.check_time(message.text)
        time = datetime.time(hour=hours, minute=minutes)
        async with state.proxy() as data:
            date = datetime.datetime.strptime(data['day'], "%Y %m %d").date()
        offset = db_control.get_user_timezone(message.from_user.id)
        time_point = TD.convert_local_notification_time_and_date_to_global(time, date, offset)
        async with state.proxy() as data:
            try:
                db_control.insert_day_task(data['task'], date, message.from_user.id)
                db_control.insert_reminder(db_control.get_task_id(data['task'], date,
                                                                  message.from_user.id),
                                           time_point)
            except UserNotExistsYet:
                await insert_user(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
                db_control.insert_day_task(data['task'], date, message.from_user.id)
                db_control.insert_reminder(db_control.get_task_id(data['task'], date,
                                                                  message.from_user.id),
                                           time_point)
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Задача добавлена. Добавить еще задачи на этот же день?",
                                              reply_markup=get_suggest_new_task_markup())
        await DayTasks.add_new_task_possibility_phase.set()
    except Only24HoursInADay:
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Вы ввели время в неправильном формате. Указываемый час должен нахо"
                                                   "диться в диапазоне 0-23. Попробуйте еще раз",
                                              reply_markup=get_None_markup())
    except Only60MinutesInAHour:
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Вы ввели время в неправильном формате. Указываемые минуты должны "
                                                   "находиться в диапазоне 0-59. Попробуйте еще раз",
                                              reply_markup=get_None_markup())
    except BugInCheckTime as e:
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Возникла непредвиденная ситуация, о которой бот уже сообщил "
                                                   "создателю",
                                              reply_markup=get_None_markup())
        await bot.send_message(constants.BUG_LOG_ACCOUNT, f"Ошибка в боте: {e.__class__.__name__}")
    except WrongTimeFormat:
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Неправильно введено время, попробуй еще раз. Вводите в формате"
                                                   "чч.мм",
                                              reply_markup=get_None_markup())


@dp.callback_query_handler(state=DayTasks.add_notification_phase)
async def process_day_tasks_cancel_notification_adding(callback: types.CallbackQuery, state: FSMContext):
    """
    Process add task and offer enter a new task.
    """
    async with state.proxy() as data:
        date = datetime.datetime.strptime(data['day'], "%Y %m %d").date()
        try:
            db_control.insert_day_task(data['task'], date, callback.from_user.id)
        except UserNotExistsYet:
            await insert_user(callback.from_user.id, callback.from_user.first_name, callback.from_user.last_name)
            db_control.insert_day_task(data['task'], date, callback.from_user.id)
    await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                text="Задача добавлена. Добавить еще задачи на этот же день?",
                                reply_markup=get_suggest_new_task_markup())
    await DayTasks.add_new_task_possibility_phase.set()


@dp.callback_query_handler(state=DayTasks.add_new_task_possibility_phase)
async def process_day_tasks_add_new_task_possibility_phase(callback: types.CallbackQuery, state: FSMContext):
    """
    Process user choose add new task or end session
    """
    if callback.data == "add_new_task":
        await DayTasks.add_task_name_phase.set()
        async with state.proxy() as data:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text=f"Задача '{data['task']}' добавлена.")
            message = await bot.send_message(chat_id=callback.message.chat.id,
                                             text="Какую дневную цель добавим? Введи её полностью")
            data['message'] = message.message_id

    elif callback.data == "cancel_add_new_task":
        async with state.proxy() as data:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text=f"Задача '{data['task']}' добавлена.")
        await state.finish()


@dp.callback_query_handler(state=DayTasks.delete_day_phase)
async def process_day_tasks_delete_day_phase(callback: types.CallbackQuery, state: FSMContext):
    """
    Process check day from CallbackQuery, send tasks to user, and he should input task
    """
    try:
        async with state.proxy() as data:
            goal_date = check_date(callback.data)
            await DayTasks.delete_number_phase.set()
            formatted_day_tasks = get_formatted_user_day_tasks(
                goal_date, data['user_id']
            )
            text = formatted_day_tasks + "Укажите номер задачи для удаления" if \
                formatted_day_tasks != "День пока бесцелен" else formatted_day_tasks
            day_tasks = db_control.get_day_tasks_by_user_id(
                datetime.datetime.strptime(goal_date, "%Y %m %d").date(), data['user_id']
            )
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text=text,
                                        reply_markup=get_tasks_numbers_markup(
                                            day_tasks
                                        ))
            data["day"] = goal_date
    except WrongDayFormat as e:
        async with state.proxy() as data:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text="Что-то пошло не так. Отчёт об ошибке отправлен создателю.")
            await bot.send_message(constants.BUG_LOG_ACCOUNT, f"Ошибка в боте: {e.__class__.__name__}")


@dp.message_handler(state=DayTasks.delete_day_phase)
async def process_day_tasks_delete_day_phase(message: types.Message, state: FSMContext):
    """
    Process check day from Message and user should click on task number
    """
    try:
        goal_date = check_date(message.text)
        async with state.proxy() as data:
            await DayTasks.delete_number_phase.set()
            formatted_day_tasks = get_formatted_user_day_tasks(
                goal_date, message.from_user.id
            )
            text = formatted_day_tasks + "Укажите номер задачи для удаления" if \
                formatted_day_tasks != "День пока бесцелен" else formatted_day_tasks
            day_tasks = db_control.get_day_tasks_by_user_id(
                datetime.datetime.strptime(goal_date, "%Y %m %d").date(), message.from_user.id
            )
            await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                                  text=text,
                                                  reply_markup=get_tasks_numbers_markup(
                                                      day_tasks
                                                  ))
            data["day"] = goal_date
    except WrongDayFormat:
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Дата введена в неправильном формате. Попробуй еще раз. "
                                                   "Можно выбрать вариант снизу 👇",
                                              reply_markup=get_near_days_markup(message.from_user.id))


@dp.callback_query_handler(state=DayTasks.delete_number_phase)
async def process_day_tasks_delete_day_phase(callback: types.CallbackQuery, state: FSMContext):
    """
    Process delete task and user should input task or cancel input
    """
    if callback.data == "cancel":
        await delete_old_and_send_new_message(state=state, chat_id=callback.message.chat.id,
                                              text="Готово")
        await state.finish()
    elif callback.data != "filler":
        try:
            db_control.delete_reminders_by_id(int(callback.data))
            db_control.delete_day_task(int(callback.data))
            async with state.proxy() as data:
                formatted_day_tasks = get_formatted_user_day_tasks(
                    data['day'], data["user_id"]
                )
                text = formatted_day_tasks + "Укажите номер задачи для удаления" if \
                    formatted_day_tasks != "День пока бесцелен" else formatted_day_tasks
                day_tasks = db_control.get_day_tasks_by_user_id(
                    datetime.datetime.strptime(data["day"], "%Y %m %d").date(), data["user_id"]
                )
                await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                            text=text,
                                            reply_markup=get_tasks_numbers_markup(
                                                day_tasks
                                            ))
            await callback.answer(text="Удалено")
        except ValueError:
            pass


@dp.callback_query_handler(state=DayTasks.show_day_phase)
async def process_day_tasks_show_day_phase(callback: types.CallbackQuery, state: FSMContext):
    """
    Process check day and show tasks
    """
    try:
        async with state.proxy() as data:
            user_id = data['user_id']
        goal_date = check_date(callback.data)
        async with state.proxy() as data:
            await DayTasks.delete_number_phase.set()
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text=get_formatted_user_day_tasks(
                                            goal_date, data['user_id']
                                        ))
            await state.finish()
    except WrongDayFormat as e:
        async with state.proxy() as data:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text="Что-то пошло не так. Отчёт об ошибке отправлен создателю.")
            await bot.send_message(constants.BUG_LOG_ACCOUNT, f"Ошибка в боте: {e.__class__.__name__}")


@dp.message_handler(state=DayTasks.show_day_phase)
async def process_day_tasks_show_day_phase(message: types.Message, state: FSMContext):
    """
    Process check day and show tasks
    """
    try:
        goal_date = check_date(message.text)
        async with state.proxy() as data:
            await DayTasks.delete_number_phase.set()
            await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                                  text=get_formatted_user_day_tasks(
                                                      goal_date, message.from_user.id
                                                  ))
            await state.finish()
    except WrongDayFormat:
        await delete_old_and_send_new_message(state=state, chat_id=message.chat.id,
                                              text="Дата введена в неправильном формате. Попробуй еще раз. "
                                                   "Можно выбрать вариант снизу 👇",
                                              reply_markup=get_near_days_markup(message.from_user.id))


@dp.message_handler(commands="timezone", state="*")
async def timezone_start(message: types.Message, state: FSMContext):
    """
    Process show user timezone and ask about change
    """
    await Timezone.add_timezone_offset.set()
    user_timezone = db_control.get_user_timezone(message.from_user.id)
    if user_timezone is not None:
        user_timezone = f"+{user_timezone}" if user_timezone >= 0 else f"-{user_timezone}" if user_timezone < 0 else "0"
        sent_message = await message.answer(text=f"Ваш часовой пояс сейчас МСК{user_timezone}. Чтобы изменить укажите"
                                                 f' свой часовой пояс относительно МСК, '
                                                 f'например "+5" или "-2"', reply_markup=get_None_markup(
            "Отмена"
        ))
        async with state.proxy() as data:
            data['message'] = sent_message.message_id
    else:
        await insert_user(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
        user_timezone = db_control.get_user_timezone(message.from_user.id)
        user_timezone = f"+{user_timezone}" if user_timezone >= 0 else f"-{user_timezone}" if user_timezone < 0 else "0"
        sent_message = await message.answer(text=f'Ваш часовой пояс сейчас МСК{user_timezone}. Чтобы изменить'
                                                 f' укажите свой часовой пояс относительно МСК, например "+5" '
                                                 f'или "-2"', reply_markup=get_None_markup(
            "Отмена"
        ))
        async with state.proxy() as data:
            data['message'] = sent_message.message_id


@dp.message_handler(state=Timezone.add_timezone_offset)
async def timezone_select(message: types.Message, state: FSMContext):
    """
    Process handle user timezone
    """
    try:
        offset = int(message.text)
        offset = (offset + 12) % 24 - 12
        db_control.change_user_timezone(message.from_user.id, offset)
        user_timezone = f"+{offset}" if offset >= 0 else f"-{offset}" if offset < 0 else " 0"
        await delete_old_and_send_new_message(state, message.chat.id,
                                              f"Часовой пояс изменен на МСК{user_timezone}")
        await state.finish()
    except ValueError:
        await delete_old_and_send_new_message(state, message.chat.id, "Часовой пояс введен в неправильном "
                                                                      "формате", reply_markup=get_None_markup(
            "Отмена"
        ))


@dp.callback_query_handler(state=Timezone.add_timezone_offset)
async def timezone_select(callback: types.CallbackQuery, state: FSMContext):
    """
    Process handle user cancel timezone change variant
    """
    if callback.data == "None":
        async with state.proxy() as data:
            await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=data['message'],
                                        text="Готово")
        await state.finish()


async def delete_old_and_send_new_message(state: FSMContext, chat_id: int, text: str,
                                          reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup |
                                                        ReplyKeyboardRemove | ForceReply | None = None):
    """
    Delete old message by id from state data, send new message and remember new message id in state data
    """
    async with state.proxy() as data:
        await bot.delete_message(chat_id=chat_id, message_id=data['message'])
        message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        data['message'] = message.message_id


async def insert_user(user_id, first_name, last_name):
    """
    Try to add new user. Also send message to BUG_LOG_ACCOUNT about new user.
    """
    try:
        user_name = f"{first_name} {last_name}" if last_name is not None else f"{first_name}"
        db_control.insert_user(user_id,
                               user_name)
        await bot.send_message(
            constants.BUG_LOG_ACCOUNT,
            f"Новый пользователь! "
            f"{user_name}"
        )
    except UserAlreadyExists:
        pass


def get_near_days_markup(user_id: int):
    """Make markup with 3 buttons: 'Вчера', 'Сегодня', 'Завтра'"""
    today = TD.today_userside(db_control.get_user_timezone(user_id))
    inline_kb_full = InlineKeyboardMarkup(row_width=3)
    inline_btn_3 = InlineKeyboardButton('вчера', callback_data=
    str(today - datetime.timedelta(days=1)).replace("-", " "))
    inline_btn_4 = InlineKeyboardButton('сегодня', callback_data=
    str(today).replace("-", " "))
    inline_btn_5 = InlineKeyboardButton('завтра', callback_data=
    str(today + datetime.timedelta(days=1)).replace("-", " "))
    inline_kb_full.row(inline_btn_3, inline_btn_4, inline_btn_5)
    return inline_kb_full


def get_None_markup(text='Напоминать не нужно'):
    """Make markup with 'None' callback query button"""
    inline_kb_full = InlineKeyboardMarkup(row_width=3)
    inline_btn = InlineKeyboardButton(text, callback_data="None")
    inline_kb_full.row(inline_btn)
    return inline_kb_full


def get_tasks_numbers_markup(task_list):
    """
    Make markup with fixed number of buttons (row_len) in the row. Make fillers,
    if the number of buttons is not a multiple of this fixed number.
    """
    row_len = 7
    if not task_list:
        return
    inline_kb_full = InlineKeyboardMarkup()
    k = 0
    row = list()
    for i in range(len(task_list)):
        k += 1
        inline_btn = InlineKeyboardButton(f"{i + 1}", callback_data=f"{task_list[i][0]}")
        row.append(inline_btn)
        if k == row_len or i == len(task_list) - 1:
            for _ in range(row_len - k):
                inline_btn = InlineKeyboardButton(" ", callback_data="filler")
                row.append(inline_btn)
            inline_kb_full.row(*row)
            row = list()
            k = 0
    inline_btn = InlineKeyboardButton("Готово", callback_data="cancel")
    inline_kb_full.row(inline_btn)
    return inline_kb_full


def get_suggest_new_task_markup():
    """
    Make markup with 'Добавить еще' and 'Не добавлять' buttons
    """
    inline_kb_full = InlineKeyboardMarkup(row_width=3)
    inline_btn1 = InlineKeyboardButton("Добавить еще", callback_data="add_new_task")
    inline_btn2 = InlineKeyboardButton("Не добавлять", callback_data="cancel_add_new_task")
    inline_kb_full.row(inline_btn1, inline_btn2)
    return inline_kb_full


def get_week_days_markup(user_id: int):
    """
    Make markup like get_near_days_markup(), but with a week later and a week earlier buttons
    """
    today = TD.today_userside(db_control.get_user_timezone(user_id))
    inline_kb_full = InlineKeyboardMarkup(row_width=3)
    inline_btn_2 = InlineKeyboardButton('неделю назад', callback_data=
    str(today - datetime.timedelta(days=7)).replace("-", " "))
    inline_btn_3 = InlineKeyboardButton('вчера', callback_data=
    str(today - datetime.timedelta(days=1)).replace("-", " "))
    inline_btn_4 = InlineKeyboardButton('сегодня', callback_data=
    str(today).replace("-", " "))
    inline_btn_5 = InlineKeyboardButton('завтра', callback_data=
    str(today + datetime.timedelta(days=1)).replace("-", " "))
    inline_btn_6 = InlineKeyboardButton('через неделю', callback_data=
    str(today + datetime.timedelta(days=7)).replace("-", " "))
    inline_kb_full.row(inline_btn_2, inline_btn_6)
    inline_kb_full.row(inline_btn_3, inline_btn_4, inline_btn_5)
    return inline_kb_full


def get_formatted_user_day_tasks(day: datetime.date, user_id: int):
    """
    Format tasks from list or return a message if list is empty
    """
    task_list = db_control.get_day_tasks_with_reminders_by_user_id(
        datetime.datetime.strptime(day, "%Y %m %d").date(), user_id
    )
    offset = db_control.get_user_timezone(user_id)
    try:
        return TD.format_day_tasks(task_list, offset)
    except UselessDay:
        return "День пока бесцелен"


def check_date(date):
    """
    Try to make datetime object from user input
    """
    try:
        _date = datetime.datetime.strptime(date, "%Y %m %d")
        return date
    except ValueError:
        raise WrongDayFormat


async def do_schedule():
    while True:
        await asyncio.sleep(1)
        await reminders_check()


async def reminders_check():
    """
    Check reminders and send them to users in right time
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc).replace(tzinfo=None)
    for reminder in db_control.get_reminders_before_target_time_with_ids(now):
        offset = db_control.get_user_timezone(reminder[3])
        text = "Сегодня в " + TD.format_time(reminder[1], offset) + "\n" + reminder[2]
        await bot.send_message(reminder[3], text)
    db_control.delete_reminders_before_target_time(now)


async def on_startup(x):
    asyncio.create_task(do_schedule())


def start():
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)

