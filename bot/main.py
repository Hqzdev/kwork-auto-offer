"""Main Telegram bot module."""

import asyncio
import json
import os
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

from storage.database import Database

load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = os.getenv("DB_PATH", "data/db.sqlite3")

# Initialize bot and database
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
db = Database(DB_PATH)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command."""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещен. Обратитесь к администратору.")
        return
    
    # Add user as admin
    await db.add_admin(user_id)
    
    await message.answer(
        "🤖 **Kwork Auto Offer Bot**\n\n"
        "Бот для мониторинга новых заказов на Kwork и быстрого отправления откликов.\n\n"
        "**Основные команды:**\n"
        "/help - список всех команд\n"
        "/status - текущее состояние\n"
        "/login - авторизация в Kwork\n"
        "/filters - управление фильтрами\n"
        "/templates - управление шаблонами\n\n"
        "Используйте /help для подробной справки."
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Handle /help command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    help_text = """
📋 **Список команд:**

**Основные:**
/start - регистрация и справка
/help - эта справка
/status - состояние бота и статистика

**Авторизация:**
/login - авторизация в Kwork
/logout - удалить сессию

**Фильтры:**
/filters - показать активные фильтры
/addfilter <json> - добавить фильтр
/delfilter <name> - удалить фильтр

**Шаблоны:**
/templates - список шаблонов
/settpl <name> <text> - создать шаблон
/deltpl <name> - удалить шаблон

**Настройки:**
/interval <sec> - интервал опроса
/quiet <on|off> - ночной режим
/blacklist - управление черным списком
/setproxy <url> - настройка прокси
/captchamode <on|off> - режим капчи

**Тестирование:**
/test - тестовый прогон

**Пример фильтра:**
```json
{
  "name": "design_ru",
  "keywords_any": ["логотип", "брендинг"],
  "categories": ["Дизайн"],
  "budget_min": 1000,
  "budget_max": 50000
}
```
"""
    await message.answer(help_text)


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Handle /status command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    # Get basic stats
    filters = await db.get_filters()
    templates = await db.get_templates()
    
    status_text = f"""
📊 **Статус бота:**

**Фильтры:** {len(filters)} активных
**Шаблоны:** {len(templates)} создано
**Сессия:** {'✅' if await db.get_session('kwork_session') else '❌'}

**Последние действия:**
- Мониторинг: {'🟢 Активен' if len(filters) > 0 else '🔴 Остановлен'}
- Последний скан: {'Недавно' if len(filters) > 0 else 'Нет данных'}

**Настройки:**
- Интервал: {await db.get_setting('scan_interval') or '45 сек'}
- Тихий режим: {await db.get_setting('quiet_mode') or 'Выключен'}
"""
    
    await message.answer(status_text)


@dp.message(Command("filters"))
async def cmd_filters(message: types.Message):
    """Handle /filters command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    filters = await db.get_filters()
    
    if not filters:
        await message.answer("📝 Фильтры не настроены.\n\nИспользуйте /addfilter для добавления.")
        return
    
    filters_text = "📋 **Активные фильтры:**\n\n"
    for i, filter_data in enumerate(filters, 1):
        filters_text += f"{i}. **{filter_data['name']}**\n"
        if 'keywords_any' in filter_data:
            filters_text += f"   Ключевые слова: {', '.join(filter_data['keywords_any'])}\n"
        if 'budget_min' in filter_data and 'budget_max' in filter_data:
            filters_text += f"   Бюджет: {filter_data['budget_min']}-{filter_data['budget_max']} ₽\n"
        filters_text += "\n"
    
    await message.answer(filters_text)


@dp.message(Command("addfilter"))
async def cmd_addfilter(message: types.Message):
    """Handle /addfilter command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    # Extract JSON from command
    text = message.text.replace("/addfilter", "").strip()
    
    if not text:
        await message.answer(
            "❌ Укажите JSON фильтра.\n\n"
            "Пример:\n"
            "/addfilter {\"name\": \"design\", \"keywords_any\": [\"логотип\"]}"
        )
        return
    
    try:
        filter_data = json.loads(text)
        if "name" not in filter_data:
            await message.answer("❌ Фильтр должен содержать поле 'name'")
            return
        
        await db.save_filter(filter_data["name"], filter_data)
        await message.answer(f"✅ Фильтр '{filter_data['name']}' сохранен!")
        
    except json.JSONDecodeError:
        await message.answer("❌ Неверный формат JSON")


@dp.message(Command("delfilter"))
async def cmd_delfilter(message: types.Message):
    """Handle /delfilter command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    filter_name = message.text.replace("/delfilter", "").strip()
    
    if not filter_name:
        await message.answer("❌ Укажите имя фильтра для удаления.")
        return
    
    await db.delete_filter(filter_name)
    await message.answer(f"✅ Фильтр '{filter_name}' удален!")


@dp.message(Command("templates"))
async def cmd_templates(message: types.Message):
    """Handle /templates command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    templates = await db.get_templates()
    
    if not templates:
        await message.answer("📝 Шаблоны не созданы.\n\nИспользуйте /settpl для добавления.")
        return
    
    templates_text = "📋 **Шаблоны откликов:**\n\n"
    for name, text in templates.items():
        preview = text[:100] + "..." if len(text) > 100 else text
        templates_text += f"**{name}:**\n{preview}\n\n"
    
    await message.answer(templates_text)


@dp.message(Command("settpl"))
async def cmd_settemplate(message: types.Message):
    """Handle /settpl command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    # Extract template name and text
    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        await message.answer(
            "❌ Укажите имя и текст шаблона.\n\n"
            "Пример:\n"
            "/settpl tpl1 Здравствуйте! Готов взяться за задачу..."
        )
        return
    
    template_name = parts[1]
    template_text = parts[2]
    
    await db.save_template(template_name, template_text)
    await message.answer(f"✅ Шаблон '{template_name}' сохранен!")


@dp.message(Command("deltpl"))
async def cmd_deltemplate(message: types.Message):
    """Handle /deltpl command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    template_name = message.text.replace("/deltpl", "").strip()
    
    if not template_name:
        await message.answer("❌ Укажите имя шаблона для удаления.")
        return
    
    await db.delete_template(template_name)
    await message.answer(f"✅ Шаблон '{template_name}' удален!")


@dp.message(Command("login"))
async def cmd_login(message: types.Message):
    """Handle /login command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    await message.answer(
        "🔐 **Авторизация в Kwork**\n\n"
        "Для авторизации используйте команду:\n"
        "/login_kwork <email> <password>\n\n"
        "⚠️ Внимание: пароль будет зашифрован и сохранен локально."
    )


@dp.message(Command("logout"))
async def cmd_logout(message: types.Message):
    """Handle /logout command."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен.")
        return
    
    await db.delete_session("kwork_session")
    await message.answer("✅ Сессия удалена!")


async def main():
    """Main function."""
    # Initialize database
    await db.init()
    
    # Add default admin if specified
    if ADMIN_IDS:
        for admin_id in ADMIN_IDS:
            await db.add_admin(admin_id)
    
    print("🤖 Starting Kwork Auto Offer Bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
