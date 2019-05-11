import pytz
import db_connector
import re
from datetime import datetime
from telegram import (ParseMode, ReplyKeyboardMarkup,
                      ReplyKeyboardRemove, ReplyMarkup, ForceReply)
import html
from telegram_calendar_keyboard import calendar_keyboard
from telegram.ext import ConversationHandler

_DEF_TZ = pytz.timezone('Europe/Moscow')
_ERR_MSG = 'Извините, произошла ошибка'
CHOOSING, TYPING_REPLY, TYPING_CHOICE = range(3)


class ForceReplyAndRemKeyboard(ReplyMarkup):

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
        task_info = handler.task_info(task_id, chat_id)

        success = (not task_info['closed'] and task_info['chat_id'] == chat_id
                   and task_info['creator_id'] == user_id
                   or user_id in task_info['workers'])
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return
    if not success:
        update.message.reply_text('Вы не можете установить срок этому заданию.',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text(f'Пожалуйста, выберите дату для задания ' +
                                  f'{task_id}',
                                  reply_markup=calendar_keyboard.create_calendar())
    user_data = context.user_data
    if 'task id' in user_data:
        del user_data['task id']
    user_data.clear()
    return ConversationHandler.END


def inline_calendar_handler(update, context):
    selected, full_date, update.message = calendar_keyboard.\
        process_calendar_selection(update, context)

    if selected:
        update.message.reply_text(f'Вы выбрали '+
                                  f'{full_date.strftime("%d/%m/%Y")}\n',
                                  reply_markup=ReplyKeyboardRemove())

        handler = db_connector.DataBaseConnector()
        chat_id = update.message.chat.id
        user_id = update.callback_query.from_user.id

        task_id = re.sub('Пожалуйста, выберите дату для задания ',
                         '', update.message.text, 1)

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
            update.message.reply_text('Вы не можете установить ' +
                                      'срок этому заданию.',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text('Срок выполнения установлен.',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())

        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
        user_name = update.callback_query.from_user.username
        msg = (f'@{user_name} Вы выбрали {full_date.strftime("%d/%m/%Y")}\n'
               f'Введите время дедлайна(hh:mm)\n' +
               f'для задачи {task_id}')
        update.message.bot.sendMessage(update.message.chat.id, msg,
                                       reply_markup=ForceReplyAndRemKeyboard(selective=True))


def get_time(update, context):
    try:
        reply_msg_text = update.message.reply_to_message.text
        if reply_msg_text.find('Введите время дедлайна(hh:mm)') != -1:
            handler = db_connector.DataBaseConnector()
            chat_id = update.message.chat.id
            user_id = update.message.from_user.id

            time = re.sub(' *', '', update.message.text, 1)

            task_id = int(re.sub('для задачи ', '',
                        reply_msg_text[reply_msg_text.rfind('\n') + 1:], 1))
            task_info = handler.task_info(task_id, chat_id)

            year = int(task_info['deadline'].strftime("%Y"))
            month = int(task_info['deadline'].strftime("%m"))
            date = int(task_info['deadline'].strftime("%d"))

            hours = int(time[:time.find(':')].strip())
            minutes = int(time[time.find(':') + 1:].strip())

            try:
                due_date = datetime(year, month, date, hours, minutes, 0)
                due_date = _DEF_TZ.localize(due_date)

                success = handler.set_deadline(task_id, chat_id, user_id,
                                               due_date)

                if not success:
                    update.message.reply_text('Вы не можете установить время ' +
                                              'этому заданию.')
                else:
                    update.message.reply_text('Время выполнения установлено.')

            except (ValueError, ConnectionError):
                update.message.reply_text('Извините, не получилось.')
                return
        else:
            update.message.reply_text('Извините, не получилось.')
            return
    except (ValueError, ConnectionError):
        return


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
        user_data = context.user_data
        if 'task id' in user_data:
            task_id = user_data['task id']
        else:
            task_id = int(_get_task_id(msg_text))
        success = handler.rem_worker(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return

    if not success:
        update.message.reply_text('Вы не можете вернуть это задание.',
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Вы отказались от задания.',
                                  reply_markup=ReplyKeyboardRemove())
    user_data = context.user_data
    if 'task id' in user_data:
        del user_data['task id']
    user_data.clear()
    return ConversationHandler.END


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
    """Finish act conversation"""
    msg = update.message.reply_text('Принято', disable_notification=True,
                                    reply_markup=ReplyKeyboardRemove())
    update.message.bot.delete_message(update.message.chat.id,
                                      msg.message_id)
    context.user_data.clear()
    return ConversationHandler.END


def act_task(update, context):
    handler = db_connector.DataBaseConnector()
    msg_text = _rem_command(update.message.text)
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    try:
        task_id = int(_get_task_id(msg_text))
        context.user_data['task id'] = task_id
        task_info = handler.task_info(task_id, chat_id)
        buttons = []
        if user_id == task_info['creator_id']:
            buttons += [["Закрыть"]]
            if task_info['marked']:
                buttons += [["Снять отметку"]]
            else:
                buttons += [["Отметить"]]
            if task_info['deadline']:
                buttons += [["Удалить срок"]]
            else:
                buttons += [["Установить/изменить срок"]]
        if user_id in task_info['workers']:
            buttons += [["Отказаться"]]
        else:
            buttons += [["Взять"]]
        buttons += [["Отмена"]]
        markup = ReplyKeyboardMarkup(buttons,
                                     selective=True,
                                     one_time_keyboard=True,
                                     resize_keyboard=False)
        update.message.reply_text("Выберите действие с задачей",
                                  reply_markup=markup)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return

    return CHOOSING


def set_marked_status(update, context):
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
        marked = not handler.task_info(task_id, chat_id)['marked']
        success = handler.set_marked_status(task_id, chat_id, user_id, marked)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG)
        return
    if not success:
        if marked:
            update.message.reply_text('Вы не можете отметить это задание.',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text('Вы не можете снять отметку у этого задания.',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
    else:
        if marked:
            update.message.reply_text('Отметка успешно добавлена.',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text('Отметка успешно удалена.',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
    user_data = context.user_data
    if 'task id' in user_data:
        del user_data['task id']
    user_data.clear()
    return ConversationHandler.END

