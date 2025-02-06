import os
import time
import logging
import requests
from dotenv import load_dotenv
from telebot import TeleBot

# Загружаем переменные окружения
load_dotenv()

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


# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logging.critical('Отсутствует обязательная переменная окружения.')
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except Exception as e:
        logging.error(f'Ошибка при отправке сообщения: {e}')


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != 200:
            logging.error(f'Ошибка: API вернул код {response.status_code}')
            raise Exception(f'Ошибка: API вернул код {response.status_code}')
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f'Ошибка при запросе к API: {e}')
        return None


def check_response(response):
    """Проверяет ответ API на наличие ожидаемых ключей."""
    if not isinstance(response, dict):
        logging.error('Ответ API не является словарем.')
        raise TypeError('Ответ API не является словарем.')

    if 'homeworks' not in response or 'current_date' not in response:
        logging.error('Отсутствуют ожидаемые ключи в ответе API.')
        raise KeyError('Отсутствуют ожидаемые ключи в ответе API.')

    if not isinstance(response['homeworks'], list):
        logging.error('Ключ `homeworks` должен содержать список.')
        raise TypeError('Ключ `homeworks` должен содержать список.')

    return response['homeworks']


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ `homework_name` в ответе API.')

    homework_name = homework['homework_name']
    status = homework.get('status')

    if status not in HOMEWORK_VERDICTS:
        logging.error(f'Неожиданный статус домашней работы: {status}')
        raise ValueError(f'Неожиданный статус: {status}')

    return (
        f'Изменился статус проверки работы "{homework_name}". '
        f'{HOMEWORK_VERDICTS[status]}'
    )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            if response is None:
                time.sleep(RETRY_PERIOD)
                continue

            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            else:
                logging.debug('Нет новых статусов.')

            timestamp = response['current_date']
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
