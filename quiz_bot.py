import os
import logging
from pathlib import Path
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from quiz_data import QUESTIONS, RESULT_SEALS

from dotenv import load_dotenv

load_dotenv()

# ─── Настройка ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN_QUIZ")
IMG_DIR = Path("img")
TOTAL_QUESTIONS = len(QUESTIONS)


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def init_quiz(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.update({
        "active": True,
        "current_q": 0,
        "scores": defaultdict(int),
        "answered_message_ids": [],   # id сообщений с вопросами (чтобы убирать кнопки)
    })


def build_answer_keyboard(q_index: int, answers: list) -> InlineKeyboardMarkup:
    """Кнопки с вариантами ответа (каждый ответ — отдельная строка)."""
    rows = [
        [InlineKeyboardButton(a["text"], callback_data=f"q{q_index}_a{i}")]
        for i, a in enumerate(answers)
    ]
    return InlineKeyboardMarkup(rows)


def get_result_seal(scores: dict) -> str:
    """Возвращает ключ вида-победителя по максимуму очков."""
    if not scores:
        return "нерпа"
    return max(scores, key=scores.get)


# ─── Отправка вопроса ─────────────────────────────────────────────────────────

async def send_question(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    bot,
) -> None:
    q_index = context.user_data["current_q"]
    q = QUESTIONS[q_index]
    keyboard = build_answer_keyboard(q_index, q["answers"])

    msg = await bot.send_message(
        chat_id=chat_id,
        text=(
            f"{q['emoji']} <b>Вопрос {q_index + 1} из {TOTAL_QUESTIONS}</b>\n\n"
            f"{q['text']}"
        ),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    context.user_data["answered_message_ids"].append(msg.message_id)


# ─── Хэндлеры ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🦭 <b>Привет! Я помогу узнать, какой ты тюлень!</b>\n\n"
        "Тест состоит из 13 вопросов. Отвечай честно — тюлени всё чувствуют 🔮\n\n"
        "Нажми /quiz, чтобы начать!",
        parse_mode="HTML",
    )


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    init_quiz(context)
    await update.message.reply_text(
        "🎯 <b>Тест начинается!</b>\n\nОтвечай на вопросы — в конце узнаешь, какой ты тюлень 🦭",
        parse_mode="HTML",
    )
    await send_question(update.effective_chat.id, context, update.get_bot())


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    # Игнорируем если тест не активен
    if not context.user_data.get("active"):
        await query.message.reply_text(
            "Тест уже завершён или ещё не начат. Нажми /quiz, чтобы пройти! 🦭"
        )
        return

    data = query.data  # вид: "q{q_index}_a{a_index}"
    try:
        q_index_str, a_index_str = data.split("_")
        q_index = int(q_index_str[1:])
        a_index = int(a_index_str[1:])
    except (ValueError, IndexError):
        return

    # Проверяем что это ответ на текущий вопрос (защита от двойного нажатия)
    if q_index != context.user_data["current_q"]:
        return

    # Убираем клавиатуру с вопроса
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Начисляем очки
    answer = QUESTIONS[q_index]["answers"][a_index]
    for seal, pts in answer["scores"].items():
        context.user_data["scores"][seal] += pts

    # Переходим к следующему вопросу
    context.user_data["current_q"] += 1
    chat_id = query.message.chat_id
    bot = query.get_bot()

    if context.user_data["current_q"] < TOTAL_QUESTIONS:
        await send_question(chat_id, context, bot)
    else:
        await show_result(chat_id, context, bot)


async def show_result(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    bot,
) -> None:
    """Показываем итоговый результат с фото."""
    context.user_data["active"] = False

    scores = context.user_data["scores"]
    winner = get_result_seal(scores)
    seal_data = RESULT_SEALS[winner]

    photo_path = IMG_DIR / seal_data["photo_folder"] / "1.jpg"

    await bot.send_message(
        chat_id=chat_id,
        text="⏳ Подсчитываю результаты...",
    )

    caption = (
        f"🎉 <b>Результаты теста!</b>\n\n"
        f"Ты — <b>{seal_data['display']}</b>\n\n"
        f"{seal_data['info']}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Пройти ещё раз: /quiz"
    )

    try:
        with open(photo_path, "rb") as photo:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode="HTML",
            )
    except FileNotFoundError:
        # Если фото не нашлось — просто текст
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
        )

    # Удаляем сообщение "Подсчитываю..."
    # (оно было предпоследним — не критично если не удалится)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 <b>Команды бота:</b>\n\n"
        "/start — приветствие\n"
        "/quiz — начать тест\n"
        "/help — эта справка",
        parse_mode="HTML",
    )


# ─── Запуск ───────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern=r"^q\d+_a\d+$"))

    logger.info("Квиз-бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
