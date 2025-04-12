import copy
import logging
import os
import sys
import time
from math import trunc

import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv(dotenv_path='.env')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600

# эти константы нужны для прохождения тестов
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

YP_REQUEST_PARAMS = dict(
    url='https://practicum.yandex.ru/api/user_api/homework_statuses/',
    headers=HEADERS,
    params={'from_date':None},   #добавим перед запросом
    timeout=5,
)

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
MESSAGE_SENT_ERROR = ('При отправке сообщения "{message}"'
                     ' произошла ошибка {error}')
NEW_STATUS = 'Изменился статус проверки работы "{name}". {verdict}'
NO_KEY_IN_ANSWER = 'В ответе нет ключа "{}"'
PROGRAM_ERROR = 'Сбой в работе программы: {}'
SAME_STATUS = 'Статус не изменился'
UNKNOWN_STATUS = 'Неизвестный статус {}'

REQUEST_PARAMETERS = (
    'Параметры запроса: url={url}, headers={headers}, params={params}'
)
ENDPOINT_CHECK_ERROR = ('Произошла ошибка запроса: {error}. '
                        + REQUEST_PARAMETERS)
ENDPOINT_ANSWER_CODE = 'Ошибка ответа: {code}. ' + REQUEST_PARAMETERS
API_DATA_ERROR = ('Ключ ответ API: "{key}", Значение: {answer}. '
                  + REQUEST_PARAMETERS)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missing_tokens = [token for token in TOKENS if not globals().get(token)]
    if not missing_tokens:
        return
    message = MISSED_TOKENS.format(missing_tokens)
    logger.critical(message)
    raise ValueError(message)


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(MESSAGE_SENT_OK.format(message))
        return True
    except Exception as error:
        logger.error( MESSAGE_SENT_ERROR.format(message=message, error=error),
            exc_info=True
        )
        return False


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    request_params = copy.deepcopy(YP_REQUEST_PARAMS)
    request_params['params']['from_date'] = timestamp
    try:
        response = requests.get(**request_params)
    except requests.RequestException as error:
        raise ConnectionError(
            ENDPOINT_CHECK_ERROR.format( error=error, **request_params)
        )

    if response.status_code != requests.codes.ok:
        raise RuntimeError(ENDPOINT_ANSWER_CODE.format(
            code=response.status_code,
            **request_params
        ))

    answer = response.json()
    for error_key in ['code', 'error']:
        if error_key in answer:
            raise RuntimeError(
                API_DATA_ERROR.format(
                    key=error_key,
                    answer=answer[error_key],
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
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(UNKNOWN_STATUS.format(status))
    return NEW_STATUS.format(
        name=homework['homework_name'],
        verdict=HOMEWORK_VERDICTS[status]
    )


def main():
    """Запуск и работа бота."""
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = None

    first_time=True

    while True:

        if first_time:
            first_time = False
        else:
            time.sleep(RETRY_PERIOD)

        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug(SAME_STATUS)
                continue
            if send_message(bot, parse_status(homeworks[0])):
                last_error_message = None
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = PROGRAM_ERROR.format(error)
            logger.error(message)
            if message != last_error_message:
                if send_message(bot, message):
                    last_error_message = message


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(funcName)s:%(lineno)d, %(asctime)s,'
            ' %(levelname)s, %(message)s, %(name)s'
        ),
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'{__file__}.log'),
        ]
    )
    main()
