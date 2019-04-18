import logging


def get_logger(name):
    """Set stderr StreamHandler logger with specified name"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=log_format, level=logging.INFO)
    logger = logging.getLogger(name)
    return logger
