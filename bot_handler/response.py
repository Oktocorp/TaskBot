import pytz
import db_connector
import re
from datetime import datetime
from telegram_calendar_keyboard import calendar_keyboard


DEF_TZ = pytz.timezone('Europe/Moscow')


# todo: Adequate start message
def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Greetings from DeltaSquad!')


def help_msg(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('HELP IS ON ITS WAY!!!')


def add(update, context):
    """Adds new task to the list"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    creator_id = update.message.from_user.id
    msg_text = update.message.text
    msg_text = re.sub('/add ', '', msg_text, 1)  # remove leading command
    try:
        handler.add_task(chat_id, creator_id, msg_text)
    except (ValueError, ConnectionError):
        update.message.reply_text('Извините, не получилось.')
        return

    update.message.reply_text('Задание успешно добавлено.')


# todo: Allow admin to close and modify any task
def close(update, context):
    """Mark the task as closed"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    # remove leading command
    task_id = re.sub('/close ', '', update.message.text, 1)
    try:
        success = handler.close_task(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text('Извините, не получилось.')
        return
    if not success:
        update.message.reply_text('Вы не можете закрыть это задание.')
    else:
        update.message.reply_text('Задание успешно закрыто.')


def update_deadline(update, context):
    """Updates task deadline"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    # remove leading command
    task_id = re.sub('/dl ', '', update.message.text, 1)

    # todo: Get real datetime
    due_date = datetime(2019, 5, 30, 12, 30, 0)
    due_date = DEF_TZ.localize(due_date)
    try:
        success = handler.set_deadline(task_id, chat_id, user_id, due_date)
    except (ValueError, ConnectionError):
        update.message.reply_text('Извините, не получилось.')
        return
    if not success:
        update.message.reply_text('Вы не можете установить срок этому заданию.')
    else:
        update.message.reply_text('Срок выполнения установлен.')


def get_list(update, context):
    """Sends the task list"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    try:
        rows = handler.get_tasks(chat_id)
    except (ValueError, ConnectionError):
        update.message.reply_text('Извините, не получилось.')
        return

    if not rows:
        lst_text = 'Ваш список задач пуст!'
        update.message.bot.send_message(chat_id=chat_id, text=lst_text)
        return

    lst_text = ''
    # todo: sort by deadline and pin marked to the top
    for i, row in enumerate(reversed(rows)):
        lst_text += f'{i + 1}. [id: {row["id"]}]\n{row["task_text"]}\n'
        # Localize UTC time
        dl = row["deadline"].astimezone(DEF_TZ) if row["deadline"] else '-'
        lst_text += f'Срок: {dl}\n\n'

    update.message.bot.send_message(chat_id=chat_id, text=lst_text)
