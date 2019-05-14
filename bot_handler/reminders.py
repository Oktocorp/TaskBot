import html
import re
from datetime import datetime, timezone

from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardRemove, ParseMode)
from telegram_calendar_keyboard import calendar_keyboard

import db_connector
import logger
from bot_handler.response import DEF_TZ, CHOOSING_REMIND_DATE, \
    TYPING_REMIND_TIME, end_conversation

#  callback data on close message button
CLOSE_MSG = 'rem_msg'
_ERR_MSG = 'Извините, операция не удалась'


def add_reminder(update, context):
    update.message.bot.send_message(
        update.message.chat.id, 'Пожалуйста, выберите дату',
        disable_notification=True,
        reply_markup=calendar_keyboard.create_calendar())
    return CHOOSING_REMIND_DATE


def reminder_cal_handler(update, context):
    selected, full_date, update.message = \
        calendar_keyboard.process_calendar_selection(update, context)
    if selected:
        today = datetime.now(timezone.utc).astimezone(DEF_TZ)
        if today.date() > full_date.date():
            msg = 'Дата неверна'
            update.message.bot.sendMessage(
                update.message.chat.id, msg,
                reply_markup=ReplyKeyboardRemove(selective=True))
            return end_conversation(context)

        context.user_data['datetime'] = full_date
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
        msg = (f'Вы выбрали дату {full_date.strftime("%d/%m/%Y")}\n'
               'Введите время в формате \"hh:mm\"\n')
        update.message.bot.sendMessage(
            update.message.chat.id, msg,
            reply_markup=ReplyKeyboardRemove(selective=True))
        return TYPING_REMIND_TIME


def get_rem_time(update, context):
    user_data = context.user_data
    user_id = update.message.from_user.id
    handler = db_connector.DataBaseConnector()
    try:
        time = re.search(r'\d{1,2}:\d{2}', update.message.text).group()

        date_time = user_data['datetime']
        hours = int(time[:time.find(':')].strip())
        minutes = int(time[time.find(':') + 1:].strip())

        date_time = date_time.replace(hour=hours, minute=minutes, second=0,
                                      tzinfo=None)
        date_time = DEF_TZ.localize(date_time)
        now = datetime.now(timezone.utc)
        if now > date_time:
            msg = 'Введенное время уже прошло'
            update.message.bot.sendMessage(
                update.message.chat.id, msg,
                reply_markup=ReplyKeyboardRemove(selective=True))
            return end_conversation(context)

        if 'reset' in user_data:
            rem_id = user_data['rem id']
            success = handler.reset_reminder(rem_id, user_id, date_time)
        else:
            task_id = user_data['task id']
            success = handler.create_reminder(task_id, user_id, date_time)

    except (ValueError, AttributeError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True)
        return end_conversation(context)

    if success:
        msg = 'Напоминание успешно установлено'
        update.message.reply_text(msg, disable_notification=True)
    else:
        update.message.reply_text(_ERR_MSG, disable_notification=True)

    return end_conversation(context)


def _compile_rem(rem, cancel_rem=True, show_dl=False, show_dt=False):
    """
    Create reminder message text and buttons markup

    :param rem: reminder Dict
    :param cancel_rem: Initiate callback btn to cancel reminder
    :param show_dl: Display task deadline
    :param show_dt: Display reminder trigger datetime
    :raises: ValueError if fields contain incorrect data
    :raises: KeyError if required key do not exist
    """
    task_mark = u'[\U0001F514]'
    resp_text = f'{task_mark} {html.escape(rem["task_text"])}\n'
    if show_dl and rem['deadline']:
        dl_format = ' %a %d.%m'
        if rem['deadline'].second == 0:  # if time is not default
            dl_format += ' %H:%M'
        dl = rem['deadline'].astimezone(DEF_TZ).strftime(dl_format)
        resp_text += f'<b>Срок выполнения:</b> <code>{dl}</code>'

    if show_dt:
        today = datetime.now(timezone.utc).astimezone(DEF_TZ)
        dt = rem['datetime'].astimezone(DEF_TZ)
        dt_format = '%H:%M'
        if today.date() != dt.date():
            dt_format = '%a %d.%m ' + dt_format
        dt = dt.strftime(dt_format)
        resp_text += f'<code>{dt}</code>'

    ret_data = f'pr:{rem["id"]}'
    if cancel_rem:
        close_data = f'cr:{rem["id"]}'
        close_btn = 'Отменить'
    else:
        close_data = CLOSE_MSG
        close_btn = 'Закрыть'
    keyboard = [[InlineKeyboardButton('Отложить', callback_data=ret_data),
                 InlineKeyboardButton(close_btn, callback_data=close_data)]]
    markup = InlineKeyboardMarkup(keyboard)
    return resp_text, markup


def send_reminders(context):
    """ Sends messages with task reminders """
    try:
        handler = db_connector.DataBaseConnector()
        reminders = handler.get_overdue_reminders()
    except (ValueError, ConnectionError) as err:
        logger.get_logger(__name__).warning(
            'Unable to fetch reminders', err)
        return

    rems_to_close = list()
    for rem in reminders:
        try:
            resp_text, markup = _compile_rem(rem, cancel_rem=False, show_dl=True)
            context.message = context.bot.send_message(
                 chat_id=rem['user_id'], text=resp_text,
                 reply_markup=markup, parse_mode=ParseMode.HTML)
            rems_to_close.append(rem['id'])
        except (ValueError, ConnectionError, KeyError) as err:
            logger.get_logger(__name__).warning(
                'Unable to process reminder', err)
    try:
        handler.close_reminders(rems_to_close)
    except (ValueError, ConnectionError) as err:
        logger.get_logger(__name__).warning('Unable to close reminders', err)


def reset_reminder(update, context):
    try:
        data = update.callback_query.data
        rem_id = int(data[data.find(':') + 1:])
        context.user_data['rem id'] = rem_id
        context.user_data['reset'] = True
        context.bot.answer_callback_query(update.callback_query.id)
        update.message = update.callback_query.message
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
        return add_reminder(update, context)
    except (ValueError, KeyError, AttributeError) as err:
        logger.get_logger(__name__).warning('Unable to reset reminder', err)
        return end_conversation(context)


def remove_reminder(update, context):
    try:
        data = update.callback_query.data
        rem_id = int(data[data.find(':') + 1:])
        handler = db_connector.DataBaseConnector()
        handler.close_reminders([rem_id])
        update.message = update.callback_query.message
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
    except (ValueError, AttributeError) as err:
        logger.get_logger(__name__).warning('Unable to close reminder', err)


def remove_msg(update, context):
    try:
        update.message = update.callback_query.message
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
    except (ValueError, AttributeError) as err:
        logger.get_logger(__name__).warning('Unable to remove message', err)


def get_list(update, context):
    """Sends user's reminders list"""
    chat = update.message.chat
    user_id = update.message.from_user.id
    try:
        handler = db_connector.DataBaseConnector()
        rems = handler.get_user_reminders(user_id)
        rems.sort(key=lambda x: x['datetime'])
    except (ValueError, ConnectionError, KeyError):
        update.message.reply_text(_ERR_MSG)
        return

    if not rems:
        reps_text = 'У вас отсутствуют предстоящие напоминания!'
        update.message.bot.send_message(chat_id=chat.id, text=reps_text)
        return

    for rem in rems:
        try:
            resp_text, markup = _compile_rem(rem, show_dt=True)
            context.message = context.bot.send_message(
                chat_id=rem['user_id'], text=resp_text,
                reply_markup=markup, parse_mode=ParseMode.HTML)
        except (ValueError, ConnectionError, KeyError) as err:
            logger.get_logger(__name__).warning(
                'Unable to process reminder', err)
