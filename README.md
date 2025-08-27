# Kwork Auto Offer Bot

Telegram-бот для мониторинга новых заказов на бирже Kwork и быстрого отправления шаблонных откликов. Реализован с использованием **aiogram 3**, **Playwright** и **IMAP**-триггеров.

## Возможности
* Подписка на новые заказы по фильтрам (ключевые слова, категория, бюджет, язык).
* Push-уведомления в Telegram с инлайн-кнопками для быстрого отклика.
* Автоматическое заполнение формы отклика через Playwright.
* Резервный канал событий через e-mail.
* Дедупликация, ночной режим, анти-бот-детектор, JSON-логи.

## Быстрый старт

### 1. Установка зависимостей
```bash
git clone https://github.com/yourname/kwork-auto-offer.git
cd kwork-auto-offer
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install  # установка браузеров
```

### 2. Настройка конфигурации
```bash
cp .env.example .env
# Отредактируйте .env файл:
# - TELEGRAM_TOKEN - токен вашего бота
# - ADMIN_IDS - ваш Telegram ID
# - KWORK_LOGIN - email для входа в Kwork
# - KWORK_PASSWORD - пароль для входа в Kwork
```

### 3. Запуск
```bash
python main.py
```

## Команды бота

### Основные команды
- `/start` - регистрация и справка
- `/help` - список всех команд
- `/status` - состояние бота и статистика

### Авторизация
- `/login` - инструкции по авторизации в Kwork
- `/logout` - удалить сессию

### Фильтры
- `/filters` - показать активные фильтры
- `/addfilter <json>` - добавить фильтр
- `/delfilter <name>` - удалить фильтр

### Шаблоны
- `/templates` - список шаблонов
- `/settpl <name> <text>` - создать шаблон
- `/deltpl <name>` - удалить шаблон

## Примеры использования

### Добавление фильтра
```json
/addfilter {
  "name": "design_ru",
  "keywords_any": ["логотип", "брендинг", "фирменный стиль"],
  "keywords_not": ["3d", "архитектура"],
  "categories": ["Дизайн"],
  "lang": ["ru"],
  "budget_min": 1500,
  "budget_max": 20000,
  "min_words": 10
}
```

### Создание шаблона
```
/settpl tpl1 Здравствуйте! Готов взяться за задачу «{title}». Опыт — 6+ лет, кейсы: {my_portfolio_url}. Предлагаю: оценка {price} ₽, срок {eta_days} дн.
```

## Структура проекта
```
bot/        # Telegram-бот (aiogram)
scraper/    # Playwright-скрапер
mail/       # IMAP-listener
storage/    # Работа с БД и сессиями
config/     # Примеры фильтров и шаблонов
```

## Переменные окружения

| Переменная | Описание | Пример |
|------------|----------|--------|
| `TELEGRAM_TOKEN` | Токен Telegram бота | `1234567890:ABCdef...` |
| `ADMIN_IDS` | ID администраторов | `123456789,987654321` |
| `KWORK_LOGIN` | Email для входа в Kwork | `user@example.com` |
| `KWORK_PASSWORD` | Пароль для входа в Kwork | `mypassword` |
| `DB_PATH` | Путь к SQLite базе | `data/db.sqlite3` |
| `PLAYWRIGHT_HEADLESS` | Запуск браузера в фоне | `true` |
| `BASE_SCAN_INTERVAL_SEC` | Интервал сканирования | `45` |

## Безопасность

- Пароли и сессии шифруются с помощью Fernet
- Никакие секреты не сохраняются в открытом виде
- Используется этичный поллинг с джиттером
- Детекция капчи и автоматическая пауза

## Логирование

Логи выводятся в консоль в формате:
```
2024-01-01 12:00:00 | INFO | 🔍 Scanning for new orders...
2024-01-01 12:00:05 | INFO | 📊 Found 15 orders
2024-01-01 12:00:06 | INFO | 🎉 Found 2 new orders!
```

## Устранение неполадок

### Бот не отвечает
1. Проверьте `TELEGRAM_TOKEN` в `.env`
2. Убедитесь, что бот добавлен в чат
3. Проверьте `ADMIN_IDS` в `.env`

### Скрапер не работает
1. Проверьте `KWORK_LOGIN` и `KWORK_PASSWORD`
2. Убедитесь, что Playwright установлен: `playwright install`
3. Проверьте интернет-соединение

### Ошибки парсинга
1. Kwork мог изменить разметку страницы
2. Обновите селекторы в `scraper/kwork_scraper.py`
3. Проверьте логи на наличие ошибок

## Разработка

### Установка для разработки
```bash
pip install -e .[develop]
```

### Запуск тестов
```bash
pytest tests/
```

### Линтинг
```bash
black .
isort .
mypy .
```

## Лицензия

MIT License
