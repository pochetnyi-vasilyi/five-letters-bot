"""
Телеграм-бот для поиска русских слов из 5 букв.
Помогает решать игру "Пять букв" (Wordle на русском).
"""

import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Логгер для действий пользователей
user_logger = logging.getLogger("user_actions")
user_logger.setLevel(logging.INFO)

# Путь к файлу логов (можно переопределить через переменную окружения)
LOG_DIR = os.environ.get("LOG_DIR", os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(LOG_DIR, "user_actions.log")

# Файловый обработчик для логов пользователей
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
user_logger.addHandler(file_handler)

# Состояния диалога
REQUIRED, EXCLUDED, REQUIRED_POSITIONS, EXCLUDED_POSITIONS = range(4)

# Загрузка словаря
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICTIONARY_PATH = os.path.join(SCRIPT_DIR, "rus.txt")

with open(DICTIONARY_PATH, 'r', encoding='utf-8') as f:
    DICTIONARY = {line.strip() for line in f if line.strip()}


def generate_real_words(required_chars=None, excluded_chars=None,
                        required_positions=None, excluded_positions=None):
    """
    Поиск слов в словаре по заданным критериям.

    Args:
        required_chars: Буквы, которые обязательно должны быть в слове
        excluded_chars: Буквы, которых не должно быть в слове
        required_positions: Словарь {позиция: буква} для точных позиций
        excluded_positions: Словарь {позиция: буквы} для исключённых позиций

    Returns:
        Список найденных слов
    """
    required_chars = required_chars or ""
    excluded_chars = excluded_chars or ""
    required_positions = required_positions or {}
    excluded_positions = excluded_positions or {}

    real_words = []

    for word in DICTIONARY:
        if len(word) != 5:
            continue

        # Проверяем наличие обязательных символов
        if not all(char in word for char in required_chars):
            continue

        # Проверяем отсутствие исключённых символов
        if any(char in word for char in excluded_chars):
            continue

        # Проверяем позиции для обязательных символов
        if not all(word[pos - 1] == char for pos, char in required_positions.items()):
            continue

        # Проверяем исключённые позиции
        if any(word[pos - 1] in chars for pos, chars in excluded_positions.items()):
            continue

        real_words.append(word)

    return real_words


def is_russian_letter(c: str) -> bool:
    """Проверяет, является ли символ русской буквой."""
    return 'а' <= c <= 'я' or c == 'ё'


def validate_letters_input(text: str) -> tuple[bool, str]:
    """
    Валидация ввода букв (обязательных или исключённых).

    Returns:
        (is_valid, error_message)
    """
    if text == "-":
        return True, ""

    # Проверяем на наличие цифр
    if any(c.isdigit() for c in text):
        return False, "⚠️ Цифры не допускаются при вводе букв."

    # Проверяем на наличие английских букв
    if any('a' <= c <= 'z' for c in text):
        return False, "⚠️ Обнаружены английские буквы. Используйте только русские буквы."

    # Проверяем, есть ли хотя бы одна русская буква
    russian_letters = [c for c in text if is_russian_letter(c)]
    if not russian_letters:
        return False, "⚠️ Не найдено русских букв. Введите русские буквы или `-` если их нет."

    return True, ""


def validate_positions_input(text: str, single_char_only: bool = False) -> tuple[bool, str, dict]:
    """
    Валидация и парсинг ввода позиций.

    Args:
        text: Строка с позициями
        single_char_only: Если True, допускается только одна буква на позицию (для известных позиций)

    Returns:
        (is_valid, error_message, parsed_positions)
    """
    if text.strip() == "-":
        return True, "", {}

    text = text.lower().strip()

    # Проверяем на английские буквы
    if any('a' <= c <= 'z' for c in text):
        return False, "⚠️ Обнаружены английские буквы. Используйте только русские буквы.", {}

    # Поддержка формата "1а 3б" или "1:а 3:б" или "1=а, 3=б"
    parts = text.replace(",", " ").replace(":", "").replace("=", "").split()

    if not parts:
        return False, "⚠️ Не удалось распознать ввод. Используйте формат: `1а 3б`", {}

    result = {}
    errors = []

    for part in parts:
        if not part:
            continue

        # Извлекаем номер позиции и буквы
        pos_str = ""
        chars = ""
        for i, c in enumerate(part):
            if c.isdigit():
                pos_str += c
            else:
                chars = part[i:]
                break

        # Проверка на несколько цифр подряд (например, "12а")
        if len(pos_str) > 1:
            errors.append(f"• `{part}`: несколько цифр подряд. Разделяйте пробелами: `1а 2б`")
            continue

        # Проверка на отсутствие цифры
        if not pos_str:
            errors.append(f"• `{part}`: не указан номер позиции (1-5)")
            continue

        # Проверка на отсутствие букв
        if not chars:
            errors.append(f"• `{part}`: не указаны буквы после номера позиции")
            continue

        pos = int(pos_str)

        # Проверка диапазона позиции
        if pos < 1 or pos > 5:
            errors.append(f"• `{part}`: позиция должна быть от 1 до 5")
            continue

        # Проверка, что буквы русские
        russian_chars = "".join(c for c in chars if is_russian_letter(c))
        if not russian_chars:
            errors.append(f"• `{part}`: не найдено русских букв")
            continue

        # Проверка на одну букву (для известных позиций)
        if single_char_only and len(russian_chars) > 1:
            errors.append(f"• `{part}`: для известной позиции укажите только одну букву")
            continue

        result[pos] = russian_chars

    if errors:
        error_msg = "⚠️ Ошибки в вводе:\n" + "\n".join(errors)
        return False, error_msg, {}

    if not result:
        return False, "⚠️ Не удалось распознать ни одной позиции. Используйте формат: `1а 3б`", {}

    return True, "", result


def get_user_info(update: Update) -> str:
    """Получает информацию о пользователе для логирования."""
    user = update.effective_user
    if user:
        username = f"@{user.username}" if user.username else "no_username"
        return f"user_id={user.id} | username={username} | name={user.full_name}"
    return "unknown_user"


def log_user_action(update: Update, action: str, details: str = "") -> None:
    """Логирует действие пользователя."""
    user_info = get_user_info(update)
    if details:
        user_logger.info(f"{user_info} | action={action} | {details}")
    else:
        user_logger.info(f"{user_info} | action={action}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога."""
    log_user_action(update, "start")

    await update.message.reply_text(
        "🔤 *Помощник для игры «Пять букв»*\n\n"
        "Я помогу найти слова по вашим подсказкам.\n\n"
        "Введите *обязательные буквы* (которые есть в слове):\n"
        "Например: `ре` или `-` если таких нет",
        parse_mode="Markdown"
    )

    # Очищаем контекст
    context.user_data.clear()

    return REQUIRED


async def get_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение обязательных букв."""
    text = update.message.text.lower().strip()

    # Валидация ввода
    is_valid, error_msg = validate_letters_input(text)
    if not is_valid:
        log_user_action(update, "invalid_input", f"stage=required | input={text}")
        await update.message.reply_text(
            f"{error_msg}\n\nВведите *обязательные буквы* ещё раз:",
            parse_mode="Markdown"
        )
        return REQUIRED

    if text == "-":
        context.user_data["required"] = ""
    else:
        # Оставляем только русские буквы
        context.user_data["required"] = "".join(c for c in text if is_russian_letter(c))

    log_user_action(update, "required", f"value={context.user_data['required'] or '-'}")

    await update.message.reply_text(
        "Введите *исключённые буквы* (которых точно нет в слове):\n"
        "Например: `хокспитлавк` или `-` если таких нет",
        parse_mode="Markdown"
    )

    return EXCLUDED


async def get_excluded(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение исключённых букв."""
    text = update.message.text.lower().strip()

    # Валидация ввода
    is_valid, error_msg = validate_letters_input(text)
    if not is_valid:
        log_user_action(update, "invalid_input", f"stage=excluded | input={text}")
        await update.message.reply_text(
            f"{error_msg}\n\nВведите *исключённые буквы* ещё раз:",
            parse_mode="Markdown"
        )
        return EXCLUDED

    if text == "-":
        context.user_data["excluded"] = ""
    else:
        context.user_data["excluded"] = "".join(c for c in text if is_russian_letter(c))

    # Проверка на конфликт с обязательными буквами
    required = context.user_data.get("required", "")
    excluded = context.user_data["excluded"]
    conflicting = set(required) & set(excluded)

    if conflicting:
        conflicting_str = ", ".join(f"'{c}'" for c in sorted(conflicting))
        log_user_action(update, "invalid_input", f"stage=excluded | conflict={conflicting_str}")
        await update.message.reply_text(
            f"⚠️ Буквы {conflicting_str} указаны и в обязательных, и в исключённых.\n"
            "Это несовместимые требования.\n\n"
            "Введите *исключённые буквы* ещё раз:",
            parse_mode="Markdown"
        )
        return EXCLUDED

    log_user_action(update, "excluded", f"value={context.user_data['excluded'] or '-'}")

    await update.message.reply_text(
        "Введите *известные позиции букв* (зелёные буквы):\n"
        "Формат: `3р` означает, что на 3-й позиции буква 'р'\n"
        "Можно несколько: `1а 3р 5т`\n"
        "Или `-` если позиции неизвестны",
        parse_mode="Markdown"
    )

    return REQUIRED_POSITIONS


async def get_required_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение обязательных позиций."""
    text = update.message.text.strip()

    # Валидация и парсинг ввода (только одна буква на позицию)
    is_valid, error_msg, positions = validate_positions_input(text, single_char_only=True)
    if not is_valid:
        log_user_action(update, "invalid_input", f"stage=required_positions | input={text}")
        await update.message.reply_text(
            f"{error_msg}\n\nВведите *известные позиции* ещё раз:",
            parse_mode="Markdown"
        )
        return REQUIRED_POSITIONS

    context.user_data["required_positions"] = {k: v for k, v in positions.items() if v}

    # Проверка на конфликт с исключёнными буквами
    excluded = context.user_data.get("excluded", "")
    position_letters = set(context.user_data["required_positions"].values())
    conflicting = position_letters & set(excluded)

    if conflicting:
        conflicting_str = ", ".join(f"'{c}'" for c in sorted(conflicting))
        log_user_action(update, "invalid_input", f"stage=required_positions | conflict_with_excluded={conflicting_str}")
        await update.message.reply_text(
            f"⚠️ Буквы {conflicting_str} указаны в исключённых, но теперь указаны в известных позициях.\n"
            "Это несовместимые требования.\n\n"
            "Введите *известные позиции* ещё раз:",
            parse_mode="Markdown"
        )
        return REQUIRED_POSITIONS

    pos_str = " ".join(f"{k}{v}" for k, v in sorted(context.user_data["required_positions"].items())) or "-"
    log_user_action(update, "required_positions", f"value={pos_str}")

    await update.message.reply_text(
        "Введите *исключённые позиции* (жёлтые буквы - буква есть, но не на этом месте):\n"
        "Формат: `4е` означает, что на 4-й позиции НЕ буква 'е'\n"
        "Можно несколько букв на позицию: `2ае 4ет`\n"
        "Или `-` если таких нет",
        parse_mode="Markdown"
    )

    return EXCLUDED_POSITIONS


async def get_excluded_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение исключённых позиций и выполнение поиска."""
    text = update.message.text.strip()

    # Валидация и парсинг ввода
    is_valid, error_msg, excluded_positions = validate_positions_input(text)
    if not is_valid:
        log_user_action(update, "invalid_input", f"stage=excluded_positions | input={text}")
        await update.message.reply_text(
            f"{error_msg}\n\nВведите *исключённые позиции* ещё раз:",
            parse_mode="Markdown"
        )
        return EXCLUDED_POSITIONS

    # Проверка на конфликт с известными позициями (одна буква на одной позиции)
    required_positions = context.user_data.get("required_positions", {})
    position_conflicts = []
    for pos, excl_chars in excluded_positions.items():
        if pos in required_positions and required_positions[pos] in excl_chars:
            position_conflicts.append(f"позиция {pos}: буква '{required_positions[pos]}'")

    if position_conflicts:
        conflicts_str = ", ".join(position_conflicts)
        log_user_action(update, "invalid_input", f"stage=excluded_positions | position_conflict={conflicts_str}")
        await update.message.reply_text(
            f"⚠️ Конфликт позиций: {conflicts_str}.\n"
            "Одна и та же буква не может быть одновременно на позиции и исключена с неё.\n\n"
            "Введите *исключённые позиции* ещё раз:",
            parse_mode="Markdown"
        )
        return EXCLUDED_POSITIONS

    # Проверка: обязательная буква не должна быть исключена со всех позиций
    required = context.user_data.get("required", "")
    for req_char in required:
        # Считаем, с скольких позиций эта буква исключена
        excluded_from_positions = sum(1 for chars in excluded_positions.values() if req_char in chars)
        # Также учитываем позиции, где уже стоит другая буква
        occupied_positions = sum(1 for pos, char in required_positions.items() if char != req_char)
        # Если буква исключена со всех оставшихся позиций — конфликт
        if excluded_from_positions + occupied_positions >= 5:
            log_user_action(update, "invalid_input", f"stage=excluded_positions | char_excluded_everywhere={req_char}")
            await update.message.reply_text(
                f"⚠️ Буква '{req_char}' указана как обязательная, но исключена со всех возможных позиций.\n"
                "Это несовместимые требования.\n\n"
                "Введите *исключённые позиции* ещё раз:",
                parse_mode="Markdown"
            )
            return EXCLUDED_POSITIONS

    context.user_data["excluded_positions"] = excluded_positions

    excl_pos_str = " ".join(f"{k}{v}" for k, v in sorted(excluded_positions.items())) or "-"
    log_user_action(update, "excluded_positions", f"value={excl_pos_str}")

    # Выполняем поиск
    required = context.user_data.get("required", "")
    excluded = context.user_data.get("excluded", "")
    required_positions = context.user_data.get("required_positions", {})

    found_words = generate_real_words(
        required_chars=required,
        excluded_chars=excluded,
        required_positions=required_positions,
        excluded_positions=excluded_positions
    )

    # Логируем результат поиска
    log_user_action(update, "search_complete", f"found={len(found_words)}")

    # Формируем ответ
    if found_words:
        if len(found_words) <= 50:
            words_text = ", ".join(found_words)
            message = f"🎯 *Найдено слов: {len(found_words)}*\n\n{words_text}"
        else:
            # Показываем первые 50 слов
            words_text = ", ".join(found_words[:50])
            message = (
                f"🎯 *Найдено слов: {len(found_words)}*\n\n"
                f"Первые 50: {words_text}\n\n"
                f"_...и ещё {len(found_words) - 50} слов_"
            )
    else:
        message = "😔 Слова не найдены. Попробуйте другие критерии."

    # Показываем использованные критерии
    criteria = "\n\n📋 *Ваши критерии:*\n"
    criteria += f"• Обязательные буквы: `{required or '-'}`\n"
    criteria += f"• Исключённые буквы: `{excluded or '-'}`\n"

    if required_positions:
        pos_str = " ".join(f"{k}{v}" for k, v in sorted(required_positions.items()))
        criteria += f"• Известные позиции: `{pos_str}`\n"
    else:
        criteria += "• Известные позиции: `-`\n"

    if excluded_positions:
        pos_str = " ".join(f"{k}{v}" for k, v in sorted(excluded_positions.items()))
        criteria += f"• Исключённые позиции: `{pos_str}`\n"
    else:
        criteria += "• Исключённые позиции: `-`\n"

    await update.message.reply_text(
        message + criteria + "\nДля нового поиска нажмите /start",
        parse_mode="Markdown"
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога."""
    log_user_action(update, "cancel")

    await update.message.reply_text(
        "Поиск отменён. Для нового поиска нажмите /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Справка по использованию бота."""
    log_user_action(update, "help")

    help_text = """
🔤 *Помощник для игры «Пять букв»*

*Как пользоваться:*
1. Нажмите /start
2. Введите буквы, которые есть в слове (жёлтые + зелёные)
3. Введите буквы, которых нет в слове (серые)
4. Укажите известные позиции (зелёные буквы)
5. Укажите, на каких позициях НЕ стоят известные буквы (жёлтые)

*Формат позиций:*
• `3р` - на 3-й позиции буква 'р'
• `1а 3р 5т` - несколько позиций
• `2ае` - на 2-й позиции НЕ буквы 'а' и 'е'

*Команды:*
• /start - начать новый поиск
• /help - эта справка
• /cancel - отменить текущий поиск
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")


def main() -> None:
    """Запуск бота."""
    # Загружаем переменные из .env
    load_dotenv()

    # Получаем токен из переменной окружения
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.error("Не задан TELEGRAM_BOT_TOKEN!")
        print("Ошибка: установите переменную окружения TELEGRAM_BOT_TOKEN")
        print("Пример: set TELEGRAM_BOT_TOKEN=ваш_токен")
        return

    # Создаём приложение
    application = Application.builder().token(token).build()

    # Добавляем обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REQUIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_required)],
            EXCLUDED: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_excluded)],
            REQUIRED_POSITIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_required_positions)],
            EXCLUDED_POSITIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_excluded_positions)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))

    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
