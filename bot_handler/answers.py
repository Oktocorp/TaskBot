import db_connector
import re


def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Greetings from DeltaSquad!')


def help_ans(update, context):
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
    except RuntimeError:
        update.message.reply_text('Извините, не получилось.')
    update.message.reply_text('Задание успешно добавлено.')


def get_list(update, context):
    """Adds new task to the list"""
    handler = db_connector.DataBaseConnector()
    chat_id = update.message.chat.id
    try:
        rows = handler.get_tasks(chat_id)
    except RuntimeError:
        update.message.reply_text('Извините, не получилось.')
        return

    if not rows:
        lst_text = 'Ваш список задач пуст!'
        update.message.bot.send_message(chat_id=chat_id, text=lst_text)
        return

    lst_text = ''
    # todo: sort by deadline and pin marked to the top
    for i, row in enumerate(reversed(rows)):
        lst_text += f'{i + 1}) {row["task_text"]}\n'
    update.message.bot.send_message(chat_id=chat_id, text=lst_text)


def echo(update, context):
    """Echo the user message."""
    update.message.reply_text(update.message.text)
