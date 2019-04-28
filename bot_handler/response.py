import pytz
import db_connector
import re
from datetime import datetime
from telegram import ParseMode
import html
from telegram_calendar_keyboard import calendar_keyboard
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply
from telegram.ext import ConversationHandler

from telegram import ReplyMarkup

_DEF_TZ = pytz.timezone('Europe/Moscow')
_ERR_MSG = 'Извините, произошла ошибка'
CHOOSING, TYPING_REPLY, TYPING_CHOICE = range(3)
buttons = ReplyKeyboardMarkup([["Закрыть"],
                               ["Взять"],
                               ["Установить/изменить срок"],
                               ["Удалить срок"],
                               ["Отмена"]],
                              selective=True, one_time_keyboard=True)

# reply_keyboard = [['Age', 'Favourite colour'],
#                   ['Number of siblings', 'Something else...'],
#                   ['Done']]
# markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)


class ForceReplyAndReplyKeyboardRemove(ReplyMarkup):

    def __init__(self, force_reply=True, selective=False, **kwargs):
        # Required
        self.remove_keyboard = True
        self.force_reply = bool(force_reply)
        # Optionals
        self.selective = bool(selective)


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
        user_data = context.user_data
        if 'task id' in user_data:
            task_id = user_data['task id']
        else:
            task_id = int(_get_task_id(msg_text))
        success = handler.close_task(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return
    if not success:
        update.message.reply_text('Вы не можете закрыть это задание.',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Задание успешно закрыто.',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    user_data = context.user_data
    if 'task id' in user_data:
        del user_data['task id']
    user_data.clear()
    return ConversationHandler.END


def update_deadline(update, context):
    """Updates task deadline"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    # remove leading command
    msg_text = _rem_command(update.message.text)

    try:
        user_data = context.user_data
        if 'task id' in user_data:
            task_id = user_data['task id']
        else:
            task_id = int(_get_task_id(msg_text))
        due_date = datetime(2019, 5, 30, 12, 30, 0)
        due_date = _DEF_TZ.localize(due_date)
        success = handler.set_deadline(task_id, chat_id, user_id, due_date)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return
    if not success:
        update.message.reply_text('Вы не можете установить срок этому заданию.',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text(f'Пожалуйста, выберите дату для задания {task_id}',
                                  reply_markup=calendar_keyboard.create_calendar())
    user_data = context.user_data
    if 'task id' in user_data:
        del user_data['task id']
    user_data.clear()
    return ConversationHandler.END


def inline_calendar_handler(update, context):
    selected, full_date, update.message = calendar_keyboard.process_calendar_selection(update, context)

    if selected:
        update.message.reply_text(f'Вы выбрали {full_date.strftime("%d/%m/%Y")}\n',
                                  reply_markup=ReplyKeyboardRemove())

    handler = db_connector.DataBaseConnector()
    update.message.bot.delete_message(update.message.chat.id, update.message.message_id)

    task_id = re.sub('Пожалуйста, выберите дату для задания ', '', update.message.text, 1)
    chat_id = update.message.chat.id
    user_id = update.callback_query.from_user.id #update._effective_user.id #need to be fixed

    year = int(full_date.strftime("%Y"))
    month = int(full_date.strftime("%m"))
    date = int(full_date.strftime("%d"))
    due_date = datetime(year, month, date, 12, 0, 0)
    due_date = _DEF_TZ.localize(due_date)

    try:
        success = handler.set_deadline(task_id, chat_id, user_id, due_date)
    except (ValueError, ConnectionError):
        update.message.reply_text('Извините, не получилось.',
                                  reply_markup=ReplyKeyboardRemove())
        return
    if not success:
        update.message.reply_text('Вы не можете установить срок этому заданию.',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Срок выполнения установлен.',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())

    update.message.reply_text(f'Вы выбрали {full_date.strftime("%d/%m/%Y")}\n' +
                              f'Введите /time \'время дедлайна\'(hh:mm:ss) ' +
                              f'для задачи {task_id}', reply_markup=ForceReplyAndReplyKeyboardRemove())


def get_time(update, context):
    if (update.message.reply_to_message.text.find('Введите /time \'время дедлайна\'(hh:mm:ss) для задачи ') != -1):
        handler = db_connector.DataBaseConnector()
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        # remove leading command
        time = re.sub('/time ', '', update.message.text, 1)
        task_id = update.message.reply_to_message.text[update.message.reply_to_message.text.find('\n') + 52:]

        date = int(update.message.reply_to_message.text[11:13])
        month = int(update.message.reply_to_message.text[14:16])
        year = int(update.message.reply_to_message.text[17:21])

        hours = time[:time.find(':')].strip()
        minutes = time[time.find(':') + 1:time.find(':', time.find(':') + 1)].strip()
        seconds = time[time.find(':', time.find(':') + 1) + 1:].strip()

        try:
            if (hours.isdigit() and minutes.isdigit() and seconds.isdigit()):
                due_date = datetime(year, month, date, int(hours), int(minutes), int(seconds))
                due_date = _DEF_TZ.localize(due_date)
            else:
                due_date = datetime(year, month, date, 12, 0, 0)
                due_date = _DEF_TZ.localize(due_date)

            success = handler.set_deadline(task_id, chat_id, user_id, due_date)

            if not success:
                update.message.reply_text('Вы не можете установить срок этому заданию.')
            else:
                update.message.reply_text('Срок выполнения установлен.')

        except (ValueError, ConnectionError):
            update.message.reply_text('Извините, не получилось.')
            return
    else:
        update.message.reply_text('Извините, не получилось.')


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
        user_data = context.user_data
        if 'task id' in user_data:
            task_id = user_data['task id']
        else:
            task_id = int(_get_task_id(msg_text))
        success = handler.assign_task(task_id, chat_id, user_id, [user_id])
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return

    if not success:
        update.message.reply_text('Вы не можете взять это задание.',
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Задание захвачено.',
                                  reply_markup=ReplyKeyboardRemove())
    user_data = context.user_data
    if 'task id' in user_data:
        del user_data['task id']
    user_data.clear()
    return ConversationHandler.END


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
        user_data = context.user_data
        if 'task id' in user_data:
            task_id = user_data['task id']
        else:
            task_id = int(_get_task_id(msg_text))
        success = handler.set_deadline(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return
    if not success:
        update.message.reply_text('Вы не можете отменить срок выполнения '
                                  'этого задания.',
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Срок выполнения отменен.',
                                  reply_markup=ReplyKeyboardRemove())
    user_data = context.user_data
    if 'task id' in user_data:
        del user_data['task id']
    user_data.clear()
    return ConversationHandler.END


def done(update, context):
    user_data = context.user_data
    if 'task id' in user_data:
        del user_data['task id']
    user_data.clear()
    # ReplyKeyboardRemove()
    return ConversationHandler.END


# def custom_choice(update, context):
#     update.message.reply_text('Alright, please send me the category first, '
#                               'for example "Most impressive skill"')
#
#     return TYPING_CHOICE
#
#
# def received_information(update, context):
#     user_data = context.user_data
#     text = update.message.text
#     category = user_data['choice']
#     user_data[category] = text
#     del user_data['choice']
#
#     update.message.reply_text("Neat! Just so you know, this is what you already told me:"
#                               "{}"
#                               "You can tell me more, or change your opinion on something.".format(
#                                   facts_to_str(user_data)), reply_markup=markup)
#
#     return CHOOSING
#
#
# def facts_to_str(user_data):
#     facts = list()
#
#     for key, value in user_data.items():
#         facts.append('{} - {}'.format(key, value))
#
#     return "\n".join(facts).join(['\n', '\n'])
#
#
# def regular_choice(update, context):
#     text = update.message.text
#     context.user_data['choice'] = text
#     update.message.reply_text(
#         'Your {}? Yes, I would love to hear about that!'.format(text.lower()))
#
#     return TYPING_REPLY


def act_task(update, context):
    msg_text = _rem_command(update.message.text)
    try:
        task_id = int(_get_task_id(msg_text))
        context.user_data['task id'] = task_id
        update.message.reply_text("Выберите действие с задачей",
                                  reply_markup=buttons)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return

    return CHOOSING


# def regular_choice(update, context):
#     text = update.message.text
#     context.user_data['choice'] = text
#
#     return TYPING_REPLY


