# Установка бота как systemd сервиса

Это инструкция по запуску бота на сервере так, чтобы он работал постоянно, даже после закрытия SSH.

## Предусловия

- Linux сервер (Ubuntu/Debian)
- SSH доступ с правами sudo
- Python 3.11+
- Проект расположен в `/opt/KirovenkoInfo`

## Пошаговая установка

### 1. Загрузите файл сервиса на сервер

Скопируйте `donatov-bot.service` в системную директорию:

```bash
sudo cp donatov-bot.service /etc/systemd/system/
```

### 2. Проверьте пути в сервисе

Если ваш проект в другой директории, отредактируйте файл:

```bash
sudo nano /etc/systemd/system/donatov-bot.service
```

Измените эти строки на правильные пути:

- `WorkingDirectory=/opt/KirovenkoInfo`
- `ExecStart=/opt/KirovenkoInfo/venv/bin/python -u /opt/KirovenkoInfo/run_bot.py`

### 3. Перезагрузите systemd кэш

```bash
sudo systemctl daemon-reload
```

### 4. Запустите сервис

```bash
sudo systemctl start donatov-bot
```

### 5. Проверьте статус

```bash
sudo systemctl status donatov-bot
```

### 6. Включите автозапуск при перезагрузке сервера

```bash
sudo systemctl enable donatov-bot
```

## Команды управления

```bash
# Проверить статус
sudo systemctl status donatov-bot

# Остановить бота
sudo systemctl stop donatov-bot

# Перезагрузить бота
sudo systemctl restart donatov-bot

# Просмотреть логи (последние 50 строк)
sudo journalctl -u donatov-bot -n 50

# Просмотреть логи в реальном времени
sudo journalctl -u donatov-bot -f

# Проверить, включен ли автозапуск
sudo systemctl is-enabled donatov-bot
```

## Примеры логирования

### Просмотр всех логов за сегодня

```bash
sudo journalctl -u donatov-bot --since today
```

### Просмотр логов за последний час

```bash
sudo journalctl -u donatov-bot --since "1 hour ago"
```

### Просмотр только ошибок

```bash
sudo journalctl -u donatov-bot -p err
```

### Экспортировать логи в файл

```bash
sudo journalctl -u donatov-bot > bot_logs.txt
```

## Устранение проблем

### Ошибка: "Service failed to start"

Проверьте статус:

```bash
sudo systemctl status donatov-bot -l
```

Посмотрите подробные логи:

```bash
sudo journalctl -u donatov-bot -n 100
```

### Бот не получает сообщения

Проверьте переменные окружения в файле `.env`:

```bash
cat /opt/KirovenkoInfo/.env
```

Убедитесь, что `BOT_TOKEN` и `CHAT_IDS` установлены.

### Бот потребляет много памяти

Перезагрузите сервис:

```bash
sudo systemctl restart donatov-bot
```

## Настройка логов

Если хотите сохранять логи в файл, замените в `donatov-bot.service`:

```ini
StandardOutput=journal
StandardError=journal
```

на:

```ini
StandardOutput=file:/opt/KirovenkoInfo/logs/bot.log
StandardError=file:/opt/KirovenkoInfo/logs/bot.log
```

И создайте директорию:

```bash
sudo mkdir -p /opt/KirovenkoInfo/logs
sudo chown nobody:nogroup /opt/KirovenkoInfo/logs
```

## Автоматическое резервное копирование логов

Можно добавить ротацию логов через `logrotate`:

```bash
sudo nano /etc/logrotate.d/donatov-bot
```

Добавьте:

```
/opt/KirovenkoInfo/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 nobody nogroup
}
```

---

**После этого бот будет работать 24/7 на сервере!** ✅
