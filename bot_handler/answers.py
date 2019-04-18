import db_connector


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
    msg_text = update.message.text.lstrip('/add ')
    try:
        handler.add_task(chat_id, creator_id, msg_text)
    except RuntimeError:
        update.message.reply_text('Извините, не получилось.')
    update.message.reply_text('Задание успешно добавлено.')


def echo(update, context):
    """Echo the user message."""
    update.message.reply_text(update.message.text)
