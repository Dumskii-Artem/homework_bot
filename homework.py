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

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
homework_keys = ['homework_name', 'status']

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missing = []

    if not PRACTICUM_TOKEN:
        missing.append('PRACTICUM_TOKEN')
    if not TELEGRAM_TOKEN:
        missing.append('TELEGRAM_TOKEN')
    if not TELEGRAM_CHAT_ID:
        missing.append('TELEGRAM_CHAT_ID')

    if missing:
        message = f'Отсутствуют обязательные переменные: {", ".join(missing)}'
        logger.critical(message)
        raise ValueError(message)


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Отправлено сообщение {message}')
    except Exception as error:
        logger.error(f'Ошибка отправки сообщения {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp},
            timeout=5
        )
    except requests.exceptions.RequestException as error:
        logger.error(f'Эндпоинт недоступен: {error}')
        raise RuntimeError(f"Ошибка при проверке эндпоинта: {error}")

    if response.status_code != 200:
        message = f'Эндпоинт ответил с кодом: {response.status_code}'
        logger.error(message)
        raise requests.exceptions.HTTPError(message)

    answer = response.json()
    return answer


def check_response(response):
    """Проверяет ответ API на соответствие документации из урока."""
    if not isinstance(response, dict):
        raise TypeError(f'В ответе {type(response)} вместо словаря')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'В ответе "homewokrs" {type(homeworks)} вместо списка'
        )
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    for key in homework_keys:
        if key not in homework:
            raise KeyError(f'В ответе нет ключа "{key}"')

    status = homework['status']
    homework_name = homework['homework_name']

    if status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    raise ValueError(f'Неизвестный статус {status}')


def main():
    """Запуск и работа бота."""
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    if send_message(bot, parse_status(homework)):
                        last_error_message = None
                        timestamp = response.get('current_date', timestamp)
            else:
                logger.debug('Статус не изменился')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error_message:
                if send_message(bot, message):
                    last_error_message = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s, %(levelname)s, %(message)s, %(name)s'
        ),
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'{__file__}.log'),
        ]
    )
    main()
