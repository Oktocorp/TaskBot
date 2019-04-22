import pytz
import db_connector
import re
from datetime import datetime
from telegram import ParseMode
import html
from telegram_calendar_keyboard import calendar_keyboard


DEF_TZ = pytz.timezone('Europe/Moscow')


# todo: Adequate start message
def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Greetings from DeltaSquad!',
                              disable_notification=True)


def help_msg(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('HELP IS ON ITS WAY!!!',
                              disable_notification=True)


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
        update.message.reply_text('Извините, не получилось.',
                                  disable_notification=True)
        return

    update.message.reply_text('Задание успешно добавлено.',
                              disable_notification=True)


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
        update.message.reply_text('Извините, не получилось.',
                                  disable_notification=True)
        return
    if not success:
        update.message.reply_text('Вы не можете закрыть это задание.',
                                  disable_notification=True)
    else:
        update.message.reply_text('Задание успешно закрыто.',
                                  disable_notification=True)


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
        update.message.reply_text('Извините, не получилось.',
                                  disable_notification=True)
        return
    if not success:
        update.message.reply_text('Вы не можете установить срок этому заданию.',
                                  disable_notification=True)
    else:
        update.message.reply_text('Срок выполнения установлен.',
                                  disable_notification=True)


def get_list(update, context):
    """Sends the task list"""
    handler = db_connector.DataBaseConnector()
    chat = update.message.chat
    try:
        rows = handler.get_tasks(chat.id)
    except (ValueError, ConnectionError):
        update.message.reply_text('Извините, не получилось.',
                                  disable_notification=True)
        return

    if not rows:
        reps_text = 'Ваш список задач пуст!'
        update.message.bot.send_message(chat_id=chat.id, text=reps_text,
                                        disable_notification=True)
        return

    reps_text = ''
    for row in (sorted(rows, key=_row_sort_key)):
        task_mark = u'<b>[ ! ]</b> ' if row['marked'] else u'\u25b8 '
        reps_text += f'{task_mark} {html.escape(row["task_text"])}\n\n'

        # Parse workers list
        if row['workers']:
            workers = ''
            for w_id in row['workers']:
                w_info = chat.get_member(w_id)
                f_name = w_info['user']['first_name']
                l_name = w_info['user']['last_name']
                username = w_info['user']['username']
                tg_link = f'https://t.me/{username}'
                workers += f'<a href="{tg_link}">{l_name} {f_name}</a>\n'

            reps_text += f'<b>Исполнители:</b> \n{workers}'

        # todo: strip date or year if possible
        # Localize UTC time
        if row['deadline']:
            dl_format = ' %a %d.%m %H:%M'
            dl = row['deadline'].astimezone(DEF_TZ).strftime(dl_format)
            reps_text += f'<b>Срок:</b> <code>{dl}</code>\n'

        reps_text += f'<b>Действия:</b>  /act_{row["id"]}\n'
        reps_text += u'-' * 16 + '\n\n'

    update.message.bot.send_message(chat_id=chat.id, text=reps_text,
                                    parse_mode=ParseMode.HTML,
                                    disable_web_page_preview=True,
                                    disable_notification=True)


def _row_sort_key(row):
    """Sort tasks by marked flag and deadline"""
    # Sort works in ascending order
    # To show marked tasks first m_key must be False
    m_key = False if row['marked'] else True
    dl_key = row['deadline']
    if not dl_key:  # If deadline is None
        dl_key = datetime.max
        tz = pytz.timezone('UTC')
        dl_key = tz.localize(dl_key)
    return m_key, dl_key
