import pytz
import db_connector
import re
from datetime import datetime
from telegram_calendar_keyboard import calendar_keyboard
from telegram import ReplyKeyboardRemove


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
    print(chat_id, user_id)
    # remove leading command
    task_id = re.sub('/dl ', '', update.message.text, 1)

    # todo: Get real datetime
    update.message.reply_text(f'Please select a date for task {task_id}', reply_markup=calendar_keyboard.create_calendar())    


def inline_handler(update, context):
    selected, date, update.message = calendar_keyboard.process_calendar_selection(update, context)

    if selected:
        update.message.reply_text(f'You selected {date.strftime("%d/%m/%Y")}\n', reply_markup=ReplyKeyboardRemove())

    
    handler = db_connector.DataBaseConnector()
    # 563114293 
    update.message.bot.delete_message(update.message.chat.id, update.message.message_id)
    print(update)
    
    task_id = re.sub('Please select a date for task ', '', update.message.text, 1)
    chat_id = update.message.chat.id
    user_id = update._effective_user.id #need to be fixed
    print(chat_id, update.message, 'lol')
    
    year = int(date.strftime("%Y"))
    month = int(date.strftime("%m"))
    date = int(date.strftime("%d"))
    due_date = datetime(year, month, date, 12, 0, 0)
    due_date = DEF_TZ.localize(due_date)

    try:
        success = handler.set_deadline(29, chat_id, user_id, due_date)
    except (ValueError, ConnectionError):
        update.message.reply_text('Извините, не получилось.')
        return
    if not success:
        update.message.reply_text('Вы не можете установить срок этому заданию.')
    else:
        update.message.reply_text('Срок выполнения установлен.')

def get_time(update, context):
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    # remove leading command
    time = re.sub('/time ', '', update.message.text, 1)

    hours = time[:time.find(':')].strip()
    minutes = time[time.find(':') + 1:time.find(':', time.find(':') + 1)].strip()
    seconds = time[time.find(':', time.find(':') + 1) + 1:].strip()

    if (hours.isdigit() and minutes.isdigit() and seconds.isdigit()):
        due_date = datetime(2018, 5, 30, int(hours), int(minutes), int(seconds))
        due_date = DEF_TZ.localize(due_date)
    else:
        due_date = datetime(2018, 5, 30, 12, 0, 0)
        due_date = DEF_TZ.localize(due_date)
        
    try:
        success = handler.set_deadline(29, chat_id, user_id, due_date)
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
