from integration_utils.iu_logger.classes.base_logger import BaseLogger


class ConsoleLogger(BaseLogger):
    # Консольный регистратор логов.
    # Делает print логов в консоль.

    def log(self, log_level, log_type, message=None, tag=None):
        from logging import getLevelName
        print(f"{getLevelName(log_level)}: {f'{tag}:' if tag else ''}{log_type} => {message}")
