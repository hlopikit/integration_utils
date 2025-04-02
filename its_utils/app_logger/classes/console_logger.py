from integration_utils.its_utils.app_logger.classes.base_logger import BaseLogger


class ConsoleLogger(BaseLogger):
    # Консольный регистратор логов.
    # Делает print логов в консоль.

    def log(self, log_level, log_type, message=None):
        from logging import getLevelName
        print("{}: {} => {}".format(getLevelName(log_level), log_type, message))
