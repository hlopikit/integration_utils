from integration_utils.its_utils.app_logger.classes.base_logger import BaseLogger


class MuteLogger(BaseLogger):
    # Немой регистратор логов.
    # Используется для заглушки ilogger через settings.

    def log(self, log_level, log_type, message=None):
        pass
