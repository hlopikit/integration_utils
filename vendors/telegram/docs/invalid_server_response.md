Описание
Transport `integration_utils.vendors.telegram.utils.request.Request` обрабатывает HTTP-ответы прокси Telegram и разбирает JSON body.
Где используется: все Telegram-боты проекта, которые ходят через `integration_utils.vendors.telegram.Bot`.

Что изменено
Если прокси или upstream возвращает пустой body, HTML-страницу ошибки или другой не-JSON ответ, `_parse` теперь поднимает `NetworkError('Invalid server response')`.
При разборе неуспешного HTTP-статуса `_request_wrapper` больше не выпускает наружу общий `TelegramError` из `_parse`, а приводит сообщение к `Invalid server response`.

Зачем
Такой ответ означает сбой transport/proxy-слоя, а не ошибку Telegram Bot API и не ошибку бизнес-логики бота.
После этой правки polling в `its_utils.app_telegram_bot` обрабатывает такой кейс как временную сетевую проблему и не роняет cron.
