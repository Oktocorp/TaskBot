import pytz
import db_connector
import re
from datetime import datetime
from telegram import ParseMode
import html
from telegram_calendar_keyboard import calendar_keyboard
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import MessageHandler, Filters, Updater
import os


_DEF_TZ = pytz.timezone('Europe/Moscow')
_ERR_MSG = 'Извините, произошла ошибка'


def _rem_command(text):
    """Remove '/command' from text"""
    return re.sub('/[a-zA-Z_]+', '', text, 1)


def _get_task_id(text):
    """Return string representing first decimal number in text"""
    id_str = re.search('(?:[^_ ])[0-9]*', text)
    id_str = id_str.group(0) if id_str else ''
    return id_str


# todo: Adequate start message
def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Greetings from DeltaSquad!',
                              disable_notification=True)


def help_msg(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('HELP IS ON ITS WAY!!!',
                              disable_notification=True)


def add_task(update, context):
    """Adds new task to the list"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    creator_id = update.message.from_user.id
    msg_text = _rem_command(update.message.text)
    if not msg_text:
        update.message.reply_text('Вы не можете добавить пустое задание.')
        return
    try:
        handler.add_task(chat_id, creator_id, msg_text)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return
    update.message.reply_text('Задание успешно добавлено.')


# todo: Allow admin to close and modify any task
def close_task(update, context):
    """Mark the task as closed"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    # remove leading command
    msg_text = _rem_command(update.message.text)
    try:
        task_id = int(_get_task_id(msg_text))
        success = handler.close_task(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
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
    msg_text = _rem_command(update.message.text)

    # todo: Get real datetime
    due_date = datetime(2019, 5, 30, 12, 30, 0)
    due_date = _DEF_TZ.localize(due_date)
    try:
        task_id = int(_get_task_id(msg_text))
        success = handler.set_deadline(task_id, chat_id, user_id, due_date)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
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
        update.message.reply_text(_ERR_MSG)
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

            reps_text += f'<b>Исполнитель:</b> {workers}'

        # todo: strip date or year if possible
        # Localize UTC time
        if row['deadline']:
            dl_format = ' %a %d.%m %H:%M'
            dl = row['deadline'].astimezone(_DEF_TZ).strftime(dl_format)
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


def take_task(update, context):
    """Assign task to the current user"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    msg_text = _rem_command(update.message.text)
    try:
        task_id = int(_get_task_id(msg_text))
        success = handler.assign_task(task_id, chat_id, user_id, [user_id])
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return

    if not success:
        update.message.reply_text('Вы не можете взять это задание.')
    else:
        update.message.reply_text('Задание захвачено.')


def ret_task(update, context):
    """Return task to the vacant pool"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    msg_text = _rem_command(update.message.text)
    try:
        task_id = int(_get_task_id(msg_text))
        success = handler.rem_worker(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return

    if not success:
        update.message.reply_text('Вы не можете вернуть это задание.')
    else:
        update.message.reply_text('Вы отказались от задания.')


def rem_deadline(update, context):
    """Removes task deadline"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    # remove leading command
    msg_text = _rem_command(update.message.text)
    try:
        task_id = int(_get_task_id(msg_text))
        success = handler.set_deadline(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return
    if not success:
        update.message.reply_text('Вы не можете отменить срок выполнения '
                                  'этого задания.')
    else:
        update.message.reply_text('Срок выполнения отменен.')


def ask_choice(update, context):
    choice = update.message.text
    context.user_data['choice'] = choice
    update.message.reply_text(
        'Your {}? Yes, I would love to hear about that!'.format(choice.lower()))
    print(context.user_data)

# TODO: do something with reply
def act_task(update, context):
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    msg_text = _rem_command(update.message.text)
    try:
        task_id = int(_get_task_id(msg_text))
        buttons = ReplyKeyboardMarkup([["Закрыть"], ["Взять"]], selective=True, one_time_keyboard=True)
        update.message.reply_text("Выберите действие с задачей",
                                  disable_notification=True, reply_markup=buttons)

        token = os.environ['BOT_TOKEN']
        updater = Updater(token, use_context=True)

        dp = updater.dispatcher
        dp.add_handler(MessageHandler(Filters.text, ask_choice, pass_user_data=True))
        # print(context.user_data)
        choice = context.user_data['choice']
        if choice == "Закрыть":
            success = handler.close_task(task_id, chat_id, user_id)
            if not success:
                update.message.reply_text('Вы не можете закрыть это задание.',
                                          disable_notification=True)
            else:
                update.message.reply_text('Задание успешно закрыто.',
                                          disable_notification=True)
        elif choice == "Взять":
            success = handler.assign_task(task_id, chat_id, user_id, [user_id])
            if not success:
                update.message.reply_text('Вы не можете взять это задание.')
            else:
                update.message.reply_text('Задание захвачено.')
    except (ValueError, ConnectionError):
            update.message.reply_text(_ERR_MSG)

