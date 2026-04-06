import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(debug=False):
    """
    Configure logging for the entire bot.

    Args:
        debug (bool): If True, set console handler to DEBUG level.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Formatter with detailed context
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )

    # Console handler (level based on debug flag)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (always INFO, rotates at 50 MB, keeps 10 backups)
    file_handler = RotatingFileHandler(
        'bot.log', maxBytes=50 * 1024 * 1024, backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Set log levels for third-party libraries
    third_party_level = logging.INFO if not debug else logging.DEBUG
    logging.getLogger('discord').setLevel(third_party_level)
    logging.getLogger('discord.http').setLevel(third_party_level)
    logging.getLogger('asyncpg').setLevel(third_party_level)
    logging.getLogger('boto3').setLevel(third_party_level)
    logging.getLogger('botocore').setLevel(third_party_level)

    # Hook for uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

    return logger


def get_logger(name):
    """
    Return a logger instance for the given module name.

    Usage: logger = get_logger(__name__)
    """
    return logging.getLogger(name)