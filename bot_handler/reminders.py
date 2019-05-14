import html
import re
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, \
    ReplyKeyboardRemove
from telegram.ext import ConversationHandler
from telegram_calendar_keyboard import calendar_keyboard

import db_connector
import logger
from bot_handler.response import DEF_TZ, ParseMode, CHOOSING_REMIND_DATE, \
    TYPING_REMIND_TIME

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
            return ConversationHandler.END

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
        task_id = user_data['task id']
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
            return ConversationHandler.END

        success = handler.create_reminder(task_id, user_id, date_time)

    except (ValueError, AttributeError, ConnectionError):
        update.message.reply_text(_ERR_MSG, disable_notification=True)
        return ConversationHandler.END

    if success:
        msg = 'Напоминание успешно установлено'
        update.message.reply_text(msg, disable_notification=True)
    else:
        update.message.reply_text(_ERR_MSG, disable_notification=True)

    return ConversationHandler.END


def send_reminders(context):
    """ Sends messages with task reminders """
    try:
        handler = db_connector.DataBaseConnector()
        reminders = handler.get_reminders()
    except (ValueError, ConnectionError) as err:
        logger.get_logger(__name__).warning(
            'Unable to fetch reminders', err)
        return

    rems_to_close = list()
    for rem in reminders:
        try:
            task_mark = u'[\U0001F514]'
            resp_text = f'{task_mark} {html.escape(rem["task_text"])}\n'
            if rem['deadline']:
                dl_format = ' %a %d.%m'
                if rem['deadline'].second == 0:  # if time is not default
                    dl_format += ' %H:%M'
                dl = rem['deadline'].astimezone(DEF_TZ).strftime(dl_format)
                resp_text += f'<b>Срок:</b> <code>{dl}</code>'

            ret_data = f'pr:{rem["task_id"]}'
            keyboard = [[InlineKeyboardButton("Отложить",
                                              callback_data=ret_data),
                         InlineKeyboardButton("Закрыть",
                                              callback_data=CLOSE_MSG)]]
            markup = InlineKeyboardMarkup(keyboard)

            context.message = context.bot.send_message(
                 chat_id=rem['user_id'], text=resp_text,
                 reply_markup=markup,
                 parse_mode=ParseMode.HTML,
                 disable_web_page_preview=True)
            rems_to_close.append(rem['id'])
        except (ValueError, ConnectionError, KeyError) as err:
            logger.get_logger(__name__).warning(
                'Unable to process reminder', err)
    try:
        handler.close_reminders(rems_to_close)
    except (ValueError, ConnectionError) as err:
        logger.get_logger(__name__).warning('Unable to close reminders', err)


def reset_btn(update, context):
    try:
        data = update.callback_query.data
        task_id = int(data[data.find(':') + 1:])
        context.user_data['task id'] = task_id
        context.bot.answer_callback_query(update.callback_query.id)
        update.message = update.callback_query.message
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
        return add_reminder(update, context)
    except (ValueError, KeyError, AttributeError) as err:
        logger.get_logger(__name__).warning('Unable to reset reminder', err)
        return ConversationHandler.END


def close_btn(update, context):
    try:
        update.message = update.callback_query.message
        update.message.bot.delete_message(update.message.chat.id,
                                          update.message.message_id)
    except (ValueError, AttributeError) as err:
        logger.get_logger(__name__).warning('Unable to remove message', err)
