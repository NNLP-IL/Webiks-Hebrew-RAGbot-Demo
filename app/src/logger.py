import logging
import os


def setup_logging():
    """
      Set up logging configuration.
      This function sets up the logging configuration based on the `LOG_LEVEL` environment variable.
      If the `LOG_LEVEL` is not set or is invalid, it defaults to `WARNING`.
      The log format is: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
      Returns:
          logging.Logger: Configured logger instance with the name "megi_fastapi".
      """
    log_level = os.getenv('LOG_LEVEL', 'WARNING').upper()

    # Map string log levels to logging constants
    log_level_mapping = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    # Default to WARNING if the log level is not in the mapping
    level = log_level_mapping.get(log_level, logging.WARNING)

    logging.basicConfig(level=level,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("megi_fastapi")
    return logger
