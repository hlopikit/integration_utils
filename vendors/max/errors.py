class MaxApiError(Exception):
    def __init__(self, message: str, status_code=None, error_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response_data = response_data

