import pytz
import db_connector
import re
from datetime import datetime, timezone
from telegram import (ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove,
                      ForceReply, TelegramError, InlineKeyboardButton,
                      InlineKeyboardMarkup)
from telegram.ext import ConversationHandler
import html
from telegram_calendar_keyboard import calendar_keyboard

import logger


DEF_TZ = pytz.timezone('Europe/Moscow')
_ERR_MSG = 'Извините, произошла ошибка'
_LOGGER = logger.get_logger(__name__)

CHOOSING_COMMAND, CHOOSING_DL_DATE, CHOOSING_REMIND_DATE, \
    TYPING_REMIND_TIME, TYPING_DL_TIME, TYPING_TASK = range(6)


def _get_task_id(text):
    """Return string representing first decimal number in text"""
    id_str = re.search('[0-9]+', text)
    id_str = id_str.group(0) if id_str else ''
    return id_str


def _clean_msg(update, context, keys=('rem msg',)):
    for key in keys:
        if key not in context.chat_data:
            continue
        while context.chat_data[key]:
            try:
                msg_id = context.chat_data[key].pop()
                update.message.bot.delete_message(update.message.chat.id, msg_id)
            except TelegramError:
                pass
            except (ValueError, KeyError, AttributeError):
                _LOGGER.exception(f'Unable to delete message')


def end_conversation(update, context):
    _clean_msg(update, context)
    context.user_data.clear()
    return ConversationHandler.END


def start(update, context):
    """Send a message when the command /start is issued."""
    msg = ('Добро пожаловать в Task-O-bot.\n'
           'Для получения справки вызовите команду /help')
    update.message.reply_text(msg, disable_notification=True)


def help_msg(update, context):
    """Send a message when the command /help is issued."""
    msg = ('Я могу помочь вам управлять задачами, '
           'а также присылать уведомления о них в указанное Вами время.\n\n'
           '<b>Для корректной работы требуется запустить '
           'личную беседу со мной</b>\n\n'
           '<b>Доступные команды:</b>\n'
           '/add - создать новое задание\n'
           '(в личной беседе можно просто написать текстовое сообщение)\n'
           '/list - список всех заданий\n'
           '/free - список заданий без исполнителя\n'
           '/my - список задач, взятых на исполнение\n'
           '(доступна в личной беседе, отображает задачи со всех чатов)\n'
           '/rem - список напоминаний (только в личной беседе)\n'
           )
    update.message.reply_text(msg, parse_mode=ParseMode.HTML,
                              disable_notification=True)


def new_task(update, context):
    """Initiate task creation process"""
    update.message.reply_text(
        'Введите текст задачи', disable_notification=True,
        reply_markup=ForceReply(selective=True))
    return TYPING_TASK


def add_task(update, context):
    """Adds new task to the list"""
    chat_id = update.message.chat.id
    creator_id = update.message.from_user.id
    msg_text = update.message.text.strip()
    if not msg_text:
        update.message.reply_text('Вы не можете добавить пустое задание')
        return end_conversation(update, context)
    try:
        handler = db_connector.DataBaseConnector()
        task_id = handler.add_task(chat_id, creator_id, msg_text)
        context.user_data['task id'] = task_id
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
        _LOGGER.exception('Unable to add task')
        return end_conversation(update, context)
    update.message.reply_text('Задание успешно добавлено.\n'
                              f'Управление доступно по команде /act_{task_id}')
    return act_task(update, context, newly_created=True)


def close_task(update, context):
    """Mark the task as closed"""
    handler = db_connector.DataBaseConnector()
    user_id = update.message.from_user.id
    user_data = context.user_data
    if 'chat id' in user_data:
        chat_id = user_data['chat id']
    else:
        chat_id = update.message.chat.id
    try:
        admin = user_id in update.message.bot.get_chat_administrators(chat_id)
    except TelegramError:
        admin = False
    try:
        task_id = user_data['task id']
        success = handler.close_task(task_id, chat_id, user_id, admin)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
        _LOGGER.exception('Unable to close task')
        return end_conversation(update, context)
    if not success:
        update.message.reply_text('Вы не можете закрыть эту задачу',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Задача успешно закрыта',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    return end_conversation(update, context)


def update_deadline(update, context):
    """Updates task deadline"""
    handler = db_connector.DataBaseConnector()
    user_id = update.message.from_user.id
    user_data = context.user_data
    try:
        task_id = user_data['task id']
        task_info = handler.task_info(task_id)

        success = (task_info['creator_id'] == user_id
                   or user_id in task_info['workers']
                   or not task_info['workers'])
    except (ValueError, ConnectionError, KeyError):
        update.message.reply_text(_ERR_MSG, disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
        _LOGGER.exception('Unable to update deadline')
        return end_conversation(update, context)

    if not success:
        update.message.reply_text('Вы не можете установить срок этому заданию',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text(
            'Пожалуйста, выберите дату',
            reply_markup=calendar_keyboard.create_calendar())
        return CHOOSING_DL_DATE


def deadline_cal_handler(update, context):
    selected, full_date, update.message = \
        calendar_keyboard.process_calendar_selection(update, context)

    if selected:
        user_data = context.user_data
        if 'chat id' in user_data:
            chat_id = user_data['chat id']
        else:
            chat_id = update.message.chat.id

        user_id = update.callback_query.from_user.id

        full_date = full_date.replace(hour=23, minute=59, second=59)
        full_date = DEF_TZ.localize(full_date)
        try:
            handler = db_connector.DataBaseConnector()
            task_id = user_data['task id']
            success = handler.set_deadline(task_id, chat_id, user_id, full_date)
            del user_data['task id']
        except (ValueError, ConnectionError, KeyError):
            update.message.reply_text(_ERR_MSG, disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
            _LOGGER.exception('Unable to add task')
            return end_conversation(update, context)

        if not success:
            msg = 'Вы не можете установить срок этому заданию'
            update.message.reply_text(msg, disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
            return end_conversation(update, context)
        else:
            user_data['deadline'] = full_date
            user_data['dl task'] = task_id
            update.message.bot.delete_message(update.message.chat.id,
                                              update.message.message_id)
            user_name = update.callback_query.from_user.username
            msg = (f'@{user_name}, Вы выбрали дату ' 
                   f'{full_date.strftime("%d/%m/%Y")}\n'
                   'Для уточнения времени отправьте его в формате "hh:mm" '
                   'в ответном сообщении')
            update.message.bot.sendMessage(
                update.message.chat.id, msg, disable_notification=True,
                reply_markup=ForceReply(selective=True)
            )
            return TYPING_DL_TIME


def get_dl_time(update, context):
    user_data = context.user_data
    try:
        handler = db_connector.DataBaseConnector()
        chat_id = user_data['chat id']
        user_id = update.message.from_user.id
        task_id = user_data['dl task']
        due_date = user_data['deadline']
        try:
            time = re.search(r'\d{1,2}:\d{2}', update.message.text).group()
            hours = int(time[:time.find(':')].strip())
            minutes = int(time[time.find(':') + 1:].strip())
            due_date = due_date.replace(hour=hours, minute=minutes, second=0,
                                        tzinfo=None)
        except (ValueError, AttributeError):
            msg = 'Извините, введенное Вами время не соответствует формату'
            update.message.reply_text(msg, disable_notification=True)
            return end_conversation(update, context)

        due_date = DEF_TZ.localize(due_date)

        success = handler.set_deadline(task_id, chat_id, user_id, due_date)
        if not success:
            update.message.reply_text(
                'Вы не можете установить срок этому заданию.',
                disable_notification=True)
        else:
            update.message.reply_text('Время выполнения установлено',
                                      disable_notification=True)

    except (ValueError, ConnectionError, AttributeError):
        update.message.reply_text(_ERR_MSG, disable_notification=True)
        _LOGGER.exception('Unable to process task deadline time')
    return end_conversation(update, context)


def _compile_list(rows, chat, bot, for_user=False):
    """
    Creates list of task pages for the chat
    :raises TelegramError if some chat does not exist
    :raises Value error if rows are corrupted
    :returns List of strings with task info
    """
    lines_lim = 20
    line_len = 30
    task_lst = ['']
    cur_lines = 0
    for row in (sorted(rows, key=_row_sort_key)):
        task_chat_id = row['chat_id'] if 'chat_id' in row else chat.id
        resp_text = ''
        task_lines = 0
        task_mark = u'<b>[ ! ]</b> ' if row['marked'] else u'\u25b8 '
        resp_text += f'{task_mark} {html.escape(row["task_text"])}\n\n'
        task_lines += len(resp_text) // line_len
        task_lines += 1 if len(resp_text) % line_len else 0
        if for_user:
            try:
                task_chat = bot.get_chat(task_chat_id)
                if task_chat.title:
                    resp_text += f'<b>Чат:</b> {task_chat.title}\n'
                    task_lines += 1
            except TelegramError:
                _LOGGER.exception('Could not get chat info')

        # Parse workers list
        if row['workers']:
            workers = ''
            for w_id in row['workers']:
                try:
                    w_info = chat.get_member(w_id)
                    f_name = w_info['user']['first_name']
                    l_name = w_info['user']['last_name']
                    username = w_info['user']['username']
                    tg_link = f'https://t.me/{username}'
                    workers += f'<a href="{tg_link}">{l_name} {f_name}</a>\n'
                except TelegramError:  # Worker is no longer in this chat
                    try:
                        handler = db_connector.DataBaseConnector()
                        handler.rem_worker(row['id'], task_chat_id, w_id)
                    except (ValueError, ConnectionError):
                        _LOGGER.exception('Could not remove invalid worker')
            if workers:
                resp_text += f'<b>Исполнитель:</b> {workers}'
                task_lines += 1

        # Localize UTC time
        if row['deadline']:
            dl_format = ' %a %d.%m'
            today = datetime.now(timezone.utc).astimezone(DEF_TZ)
            if today.year != row['deadline'].year:
                dl_format += '.%Y'
            if row['deadline'].second == 0:  # if time is not default
                dl_format += '.%H:%M'
            dl = row['deadline'].astimezone(DEF_TZ).strftime(dl_format)
            resp_text += f'<b>Срок:</b> <code>{dl}</code>\n'
            task_lines += 1

        resp_text += f'<b>Действия:</b>  /act_{row["id"]}\n'
        resp_text += u'-' * 16 + '\n\n'
        task_lines += 2

        if cur_lines and cur_lines + task_lines > lines_lim:
            task_lst.append(resp_text)
            cur_lines = task_lines
        else:
            task_lst[-1] += resp_text
            cur_lines += task_lines
    return task_lst


def get_list(update, context, for_user=False, free_only=False):
    """Sends the task list"""
    chat = update.message.chat
    user_id = update.message.from_user.id

    if for_user and user_id != chat.id:
        msg = 'Список Ваших задач доступен в личном диалоге'
        update.message.reply_text(msg)
        return

    try:
        handler = db_connector.DataBaseConnector()
        if for_user:
            rows = handler.get_user_tasks(user_id)
        else:
            rows = handler.get_tasks(chat.id, free_only=free_only)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True)
        _LOGGER.exception('Unable to get list of tasks')
        return

    if not rows:
        resp_text = 'Ваш список задач пуст!'
        update.message.bot.send_message(chat_id=chat.id, text=resp_text,
                                        disable_notification=True)
        return

    tasks_lst = _compile_list(rows, chat, update.message.bot, for_user=for_user)
    context.chat_data['pages'] = tasks_lst
    context.chat_data['page ind'] = 0
    if len(tasks_lst) > 1:
        r_nav = 'nav:r'
        r_text = '>>'
    else:
        r_nav = 'nav:-'
        r_text = '  '
    cl_nav = 'nav:cl'
    keyboard = [[InlineKeyboardButton('  ', callback_data='-'),
                 InlineKeyboardButton('Закрыть', callback_data=cl_nav),
                 InlineKeyboardButton(r_text, callback_data=r_nav)]]
    markup = InlineKeyboardMarkup(keyboard)
    _clean_msg(update, context, keys=('rem lst', ))
    msg = update.message.bot.send_message(
        chat_id=chat.id, text=tasks_lst[0], parse_mode=ParseMode.HTML,
        disable_web_page_preview=True, disable_notification=True,
        reply_markup=markup
    )
    context.chat_data['rem lst'] = {msg.message_id}


def list_nav(update, context):
    """Parse callback from tasks list and flip pages"""
    data = update.callback_query.data
    try:
        command = data[data.find(':') + 1:]
    except IndexError:
        context.bot.answer_callback_query(update.callback_query.id)
        _LOGGER.exception('Invalid callback data')
        return
    update.message = update.callback_query.message

    r_nav = 'nav:r'
    r_text = '>>'
    l_nav = 'nav:l'
    l_text = '<<'
    cl_nav = 'nav:cl'
    cl_text = 'Закрыть'
    alter = False

    if command == 'cl':
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
        if 'pages' in context.chat_data:
            del context.chat_data['pages']
        if 'page ind' in context.chat_data:
            del context.chat_data['page ind']
        return

    try:
        pages = context.chat_data['pages']
        page_ind = context.chat_data['page ind']
        total = len(pages)
    except (KeyError, ValueError):
        context.bot.answer_callback_query(update.callback_query.id)
        _LOGGER.exception('Invalid callback data')
        return

    if command == 'l' and page_ind > 0:
        if page_ind == 1:
            l_nav = 'nav:-'
            l_text = '  '
        alter = True
        page_ind -= 1

    elif command == 'r' and page_ind < total - 1:
        if page_ind == total - 2:
            r_nav = 'nav:-'
            r_text = '  '
        alter = True
        page_ind += 1

    context.bot.answer_callback_query(update.callback_query.id)
    if alter:
        keyboard = [[InlineKeyboardButton(l_text, callback_data=l_nav),
                     InlineKeyboardButton(cl_text, callback_data=cl_nav),
                     InlineKeyboardButton(r_text, callback_data=r_nav)]]
        markup = InlineKeyboardMarkup(keyboard)
        context.chat_data['page ind'] = page_ind
        update.message.bot.edit_message_text(
            text=pages[page_ind], chat_id=update.message.chat.id,
            message_id=update.message.message_id, parse_mode=ParseMode.HTML,
            disable_web_page_preview=True, disable_notification=True,
            reply_markup=markup
        )


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
    user_id = update.message.from_user.id
    user_data = context.user_data
    if 'chat id' in user_data:
        chat_id = user_data['chat id']
    else:
        chat_id = update.message.chat.id
    try:
        handler = db_connector.DataBaseConnector()
        task_id = user_data['task id']
        success = handler.assign_task(task_id, chat_id, user_id, [user_id])
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
        _LOGGER.exception('Unable to add worker')
        return end_conversation(update, context)

    if not success:
        update.message.reply_text('Вы не можете взять это задание',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Задание захвачено',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    return end_conversation(update, context)


def ret_task(update, context):
    """Return task to the vacant pool"""
    user_data = context.user_data
    if 'chat id' in user_data:
        chat_id = user_data['chat id']
    else:
        chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    try:
        handler = db_connector.DataBaseConnector()
        task_id = user_data['task id']
        success = handler.rem_worker(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
        _LOGGER.exception('Unable to return task to the vacant pool')
        return end_conversation(update, context)

    if not success:
        update.message.reply_text('Вы не можете вернуть это задание',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Вы отказались от задания',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    return end_conversation(update, context)


def rem_deadline(update, context):
    """Removes task deadline"""
    user_data = context.user_data
    if 'chat id' in user_data:
        chat_id = user_data['chat id']
    else:
        chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    try:
        task_id = user_data['task id']
        handler = db_connector.DataBaseConnector()
        success = handler.set_deadline(task_id, chat_id, user_id)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
        _LOGGER.exception('Unable to remove task deadline')
        return end_conversation(update, context)
    if not success:
        update.message.reply_text(
            'Вы не можете изменить срок выполнения этого задания',
            disable_notification=True, reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Срок выполнения отменен',
                                  disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
    return end_conversation(update, context)


def done(update, context):
    """Finish act conversation"""
    msg = update.message.reply_text(u'\u2800', disable_notification=True,
                                    reply_markup=ReplyKeyboardRemove())
    update.message.bot.delete_message(update.message.chat.id, msg.message_id)
    return end_conversation(update, context)


def set_marked_status(update, context):
    user_data = context.user_data
    if 'chat id' in user_data:
        chat_id = user_data['chat id']
    else:
        chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    try:
        task_id = user_data['task id']
        handler = db_connector.DataBaseConnector()
        marked = not handler.task_info(task_id)['marked']
        success = handler.set_marked_status(task_id, chat_id, user_id, marked)
    except (ValueError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True,
                                  reply_markup=ReplyKeyboardRemove())
        _LOGGER.exception('Unable to update task marked status')
        return end_conversation(update, context)
    if not success:
        if marked:
            update.message.reply_text('Вы не можете отметить это задание',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text('Вы не можете снять отметку '
                                      'этого задания',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
    else:
        if marked:
            update.message.reply_text('Отметка успешно добавлена',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text('Отметка успешно удалена',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
    return end_conversation(update, context)


def act_task(update, context, newly_created=False):
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    user_data = context.user_data
    try:
        text_task_id = _get_task_id(update.message.text)
        if text_task_id and not newly_created:
            task_id = int(text_task_id)
            user_data['task id'] = task_id
        else:
            task_id = user_data['task id']
        task_info = handler.task_info(task_id)
        user_data['chat id'] = task_info['chat_id']
        task_chat = update.message.bot.get_chat(task_info['chat_id'])

        if task_chat.id != chat_id and user_id not in task_info['workers']:
            update.message.reply_text('Вы не можете управлять этим заданием',
                                      disable_notification=True,
                                      reply_markup=ReplyKeyboardRemove())
            return end_conversation(update, context)

        if task_chat.type == 'private':
            is_admin = False
        else:
            is_admin = user_id in [
                admin.user.id for admin in
                update.message.bot.get_chat_administrators(task_info['chat_id'])
            ]
        buttons = [[]]
        cols = 0
        if (user_id in task_info['workers'] or is_admin
                or task_info['chat_id'] == chat_id and not task_info['workers']
                or task_info['creator_id'] == user_id):
            buttons[-1] += ['Закрыть задачу']
            cols += 1

        if user_id in task_info['workers']:
            cols += 1
            buttons[-1] += ['Отказаться']

        elif task_info['chat_id'] == chat_id and not task_info['workers']:
            if not cols % 2:
                buttons.append([])
            cols += 1
            buttons[-1] += ['Взять']

        if task_info['creator_id'] == user_id or is_admin:
            if task_info['deadline']:
                buttons.append([])
                buttons[-1] += ['Изменить срок']
                buttons[-1] += ['Удалить срок']
                cols = 0
            else:
                if not cols % 2:
                    buttons.append([])
                buttons[-1] += ['Установить срок']
                cols += 1

            if not cols % 2:
                buttons.append([])
            if task_info['marked']:
                buttons[-1] += ['Снять отметку']
            else:
                buttons[-1] += ['Отметить']
            cols += 1

        if not cols % 2:
            buttons.append([])
        buttons[-1] += ['Создать напоминание']

        buttons.append([])
        buttons[-1] += ['Покинуть меню']

        markup = ReplyKeyboardMarkup(buttons,
                                     selective=True,
                                     resize_keyboard=True,
                                     one_time_keyboard=True)
        if newly_created:
            msg = 'Вы можете выбрать действие для этой задачи'
        else:
            msg = 'Выберите действие с задачей'

    except (ValueError, ConnectionError, TelegramError, KeyError):
        update.message.reply_text(_ERR_MSG, disable_notification=True)
        log_msg = 'Unable to create task action menu'
        _LOGGER.exception(log_msg)
        return end_conversation(update, context)

    update.message.reply_text(msg, reply_markup=markup,
                              disable_notification=True)
    return CHOOSING_COMMAND
