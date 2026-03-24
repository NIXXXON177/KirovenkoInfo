# Donatov.net Monitoring Bot

Telegram-бот для мониторинга изменений на сайте Donatov.net (игры, категории, товары).

## Быстрый старт

### Локально (для разработки)

```bash
# Установить зависимости
pip install -r requirements.txt

# Установить переменные окружения
cp .env.example .env
# Отредактируйте .env с вашим BOT_TOKEN и CHAT_IDS

# Запустить бота
python run_bot.py
```

### На сервере (production)

```bash
# Установить как systemd сервис
sudo cp donatov-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start donatov-bot
sudo systemctl enable donatov-bot

# Проверить статус
sudo systemctl status donatov-bot

# Просмотреть логи
sudo journalctl -u donatov-bot -f
```

Подробная инструкция в [DEPLOY.md](DEPLOY.md)

## Возможности

- 🎮 Отслеживание игр (добавление/удаление)
- 📂 Отслеживание категорий (добавление/удаление)
- 📦 Отслеживание товаров (добавление/удаление/изменение цены)
- 🔔 Автоматические уведомления в Telegram
- 📊 Интерактивное меню с кнопками
- 📝 Подробное логирование
- 🔄 Работа 24/7 на сервере

## Команды бота

- `/start` - главное меню
- `/status` - текущий статус
- `/games` - список всех игр
- `/game ID` - информация об игре
- `/help` - справка по командам

## Структура проекта

```
.
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py           # Основная логика бота и команды
│   ├── donatov.py        # Парсинг сайта
│   ├── config.py         # Конфигурация
│   ├── state_store.py    # Хранилище статуса
│   ├── diff_events.py    # Генерация событий об изменениях
│   ├── games_ui.py       # UI для списка игр
│   ├── db_config.py      # Конфигурация БД
│   └── db_loader.py      # Загрузчик данных из БД
├── data/
│   └── state.json        # Сохраненное состояние
├── run_bot.py            # Точка входа
├── requirements.txt      # Зависимости Python
├── donatov-bot.service   # systemd сервис
├── DEPLOY.md            # Инструкция развертывания
└── README.md            # Этот файл
```

## Переменные окружения

Создайте файл `.env`:

```bash
# Telegram
BOT_TOKEN=your_bot_token_here
CHAT_IDS=123456789,987654321

# Сайт
BASE_URL=https://donatov.net
DATA_SOURCE=site  # site или database

# Путь к хранилищу состояния
STATE_PATH=./data/state.json

# Логирование
LOG_LEVEL=INFO

# Опционально для БД
# SQLALCHEMY_URL=postgresql://user:pass@localhost/db
```

## Требования

- Python 3.11+
- aiogram 3.7+
- aiohttp 3.9+
- python-dotenv
- sqlalchemy (если используется БД)

## Развертывание на сервере

1. Клонируйте репозиторий
2. Установите зависимости в venv
3. Скопируйте и отредактируйте `.env`
4. Следуйте инструкциям в [DEPLOY.md](DEPLOY.md)

## Логирование

Все события логируются через systemd journal:

```bash
# Просмотр логов
sudo journalctl -u donatov-bot -f

# История за день
sudo journalctl -u donatov-bot --since today

# Только ошибки
sudo journalctl -u donatov-bot -p err
```

## Автор

NIXXXON177

## Лицензия

MIT
