class LocalSettingsClass:
    def __init__(self,
                 portal_domain,
                 app_domain,
                 app_name,
                 salt,
                 secret_key,
                 application_bitrix_client_id,
                 application_bitrix_client_secret,
                 application_index_path,
                 application_token=None,  # токен для верификации событий
                 ):

        self.portal_domain = portal_domain
        self.app_domain = app_domain
        self.app_name = app_name
        self.salt = salt
        self.secret_key = secret_key
        self.application_bitrix_client_id = application_bitrix_client_id
        self.application_bitrix_client_secret = application_bitrix_client_secret
        self.application_index_path = application_index_path
        self.application_token = application_token

