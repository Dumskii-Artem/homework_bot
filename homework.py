import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv(dotenv_path='.env')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

API_TIMEOUT = 5
RETRY_PERIOD = 600

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

logger = logging.getLogger(__name__)

ANSWER_INSTEAD_DICT = 'В ответе API вместо словаря {}'
ANSWER_HAVNT_HOMEWORKS = 'В ответе API нет ключа "homeworks"'
HOMEWORKS_INSTEAD_LIST = 'В ответе "homewokrs" вместо списка {}'
MISSED_TOKENS = 'Отсутствуют обязательные переменные: {}'
MESSAGE_SENT_OK = 'Отправлено сообщение {}'
MESSAGE_SENT_ERROR = 'При отправке сообщения "{}" произошла ошибка {}'
NEW_STATUS = 'Изменился статус проверки работы "{}". {}'
NO_KEY_IN_ANSWER = 'В ответе нет ключа "{}"'
PROGRAM_ERROR = 'Сбой в работе программы: {}'
SAME_STATUS = 'Статус не изменился'
UNKNOWN_STATUS = 'Неизвестный статус {}'

REQUEST_PARAMETERS = (
    '\nПараметры запроса: url={url}, headers={headers}, params={params}'
)
ENDPOINT_CHECK_ERROR = ('Произошла ошибка запроса: {}.' + REQUEST_PARAMETERS)
ENDPOINT_ANSWER_CODE = ('Ошибка ответа: {}.' + REQUEST_PARAMETERS)
API_DATA_ERROR = ('Ключ ответ API: "{}", Значение: {}.' + REQUEST_PARAMETERS)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missing_tokens = [token for token in TOKENS if not globals().get(token)]
    if missing_tokens:
        message = MISSED_TOKENS.format(missing_tokens)
        logger.critical(message)
        raise ValueError(message)


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(MESSAGE_SENT_OK.format(message))
    except Exception as error:
        logger.error(
            MESSAGE_SENT_ERROR.format(message, error),
            exc_info=True
        )


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
        'timeout': API_TIMEOUT,
    }
    try:
        response = requests.get(**request_params)
    except Exception as error:
        raise ConnectionError(
            ENDPOINT_CHECK_ERROR.format(error, **request_params)
        )

    if response.status_code != requests.codes.ok:
        raise ValueError(ENDPOINT_ANSWER_CODE.format(
            response.status_code,
            **request_params
        ))

    answer = response.json()
    for error_key in ['code', 'error']:
        if error_key in answer:
            raise ValueError(
                API_DATA_ERROR.format(
                    error_key,
                    answer[error_key],
                    **request_params
                )
            )
    return answer


def check_response(response):
    """Проверяет ответ API на соответствие документации из урока."""
    if not isinstance(response, dict):
        raise TypeError(ANSWER_INSTEAD_DICT.format(type(response)))
    if 'homeworks' not in response:
        raise KeyError(ANSWER_HAVNT_HOMEWORKS)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(HOMEWORKS_INSTEAD_LIST.format(type(homeworks)))
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    for key in ['homework_name', 'status']:
        if key not in homework:
            raise KeyError(NO_KEY_IN_ANSWER.format(key))

    status = homework['status']
    if status in HOMEWORK_VERDICTS:
        return NEW_STATUS.format(
            homework['homework_name'],
            HOMEWORK_VERDICTS[status]
        )
    raise ValueError(UNKNOWN_STATUS.format(status))


def main():
    """Запуск и работа бота."""
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
                last_error_message = None
                timestamp = response.get('current_date', timestamp)
            else:
                logger.debug(SAME_STATUS)
        except Exception as error:
            message = PROGRAM_ERROR.format(error)
            logger.error(message)
            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s, %(levelname)s, %(message)s,'
            ' %(name)s, %(funcName)s, %(lineno)d'
        ),
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'{__file__}.log'),
        ]
    )
    main()
