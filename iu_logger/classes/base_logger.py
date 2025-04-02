from integration_utils.iu_logger.constants import log_levels


class BaseLogger:
    # Корневой класс регистратора логов.

    def log(self, log_level, log_type, message=None):
        raise NotImplementedError()

    def debug(self, log_type, message=None):
        return self.log(log_levels.DEBUG, log_type, message)

    def info(self, log_type, message=None):
        return self.log(log_levels.INFO, log_type, message)

    def warning(self, log_type, message=None):
        return self.log(log_levels.WARNING, log_type, message)

    def error(self, log_type, message=None):
        return self.log(log_levels.ERROR, log_type, message)

    def critical(self, log_type, message=None):
        return self.log(log_levels.CRITICAL, log_type, message)
