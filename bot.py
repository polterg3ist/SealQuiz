import os
import random
import logging
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from seals_data import SEALS, SEAL_NAMES

from dotenv import load_dotenv

load_dotenv()

# ─── Настройка ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
IMG_DIR = Path("img")          # папка с изображениями рядом с bot.py
QUESTIONS_PER_GAME = 10        # сколько видов показываем за игру (≤ 18)
OPTIONS_COUNT = 6              # вариантов ответа


# ─── Вспомогательные функции ──────────────────────────────────────────────────

def get_photo_path(species: str, number: int) -> Path:
    """Вернёт путь к фото number (1/2/3) для данного вида."""
    folder = SEALS[species]["folder"]
    return IMG_DIR / folder / f"{number}.jpg"


def build_options_keyboard(correct: str, all_names: list[str]) -> InlineKeyboardMarkup:
    """6 кнопок с вариантами ответа (1 правильный + 5 случайных)."""
    wrong = [n for n in all_names if n != correct]
    options = random.sample(wrong, OPTIONS_COUNT - 1) + [correct]
    random.shuffle(options)

    # По 2 кнопки в ряд
    rows = []
    for i in range(0, OPTIONS_COUNT, 2):
        row = [
            InlineKeyboardButton(options[i].capitalize(), callback_data=options[i]),
            InlineKeyboardButton(options[i + 1].capitalize(), callback_data=options[i + 1]),
        ]
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def result_comment(correct_count: int, total: int, score: int) -> str:
    """Итоговый комментарий в зависимости от результата."""
    ratio = correct_count / total
    if ratio == 1.0:
        return (
            "🏆 <b>Легендарный тюленевед!</b>\n"
            "Ты угадал абсолютно всех тюленей — такой результат встречается редко! "
            "Ты настоящий эксперт по ластоногим. Тюлени тебя определённо уважают 🦭✨"
        )
    elif ratio >= 0.8:
        return (
            "🥇 <b>Отличный результат!</b>\n"
            "Ты великолепно разбираешься в тюленях! Совсем немного до совершенства — "
            "ещё пара тренировок, и ты станешь настоящим экспертом 💪"
        )
    elif ratio >= 0.6:
        return (
            "🥈 <b>Хороший результат!</b>\n"
            "Ты знаешь тюленей лучше большинства людей! Есть куда расти — "
            "повтори игру и закрепи знания 📚"
        )
    elif ratio >= 0.4:
        return (
            "🥉 <b>Неплохое начало!</b>\n"
            "Кое-каких тюленей ты точно запомнил. Потренируйся ещё — "
            "и результат обязательно улучшится! 🔁"
        )
    else:
        return (
            "📖 <b>Тюлени — это целая наука!</b>\n"
            "Пока тюлени оказались хитрее 😄 Но не расстраивайся — "
            "теперь ты узнал о них гораздо больше. Сыграй ещё раз и удиви всех! 🚀"
        )


# ─── Инициализация состояния игры ────────────────────────────────────────────

def init_game(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сбрасываем данные игры в user_data."""
    species_order = random.sample(SEAL_NAMES, QUESTIONS_PER_GAME)
    context.user_data.update({
        "playing": True,
        "species_order": species_order,   # список видов на эту игру
        "current_index": 0,               # текущий вопрос (индекс в species_order)
        "attempt": 1,                     # 1 = первая попытка, 2 = вторая
        "score": 0,
        "correct_count": 0,
        "total": QUESTIONS_PER_GAME,
    })


# ─── Хэндлеры ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🦭 <b>Добро пожаловать в «Угадай тюленя»!</b>\n\n"
        "Я покажу тебе фотографию тюленя и 6 вариантов ответа.\n\n"
        "🟢 Угадал с первого раза → <b>+5 очков</b>\n"
        "🟡 Угадал со второй попытки → <b>+2 очка</b>\n"
        "🔴 Не угадал → <b>0 очков</b>\n\n"
        f"В каждой игре {QUESTIONS_PER_GAME} вопросов. Удачи!\n\n"
        "Нажми /play, чтобы начать 🎮",
        parse_mode="HTML",
    )


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинаем новую игру."""
    init_game(context)
    await update.message.reply_text(
        "🎮 Игра началась! Смотри внимательно и выбирай ответ 👇",
        parse_mode="HTML",
    )
    await send_question(update.effective_chat.id, context, update.get_bot())


async def send_question(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    bot,
) -> None:
    """Отправляем вопрос (фото + клавиатура)."""
    ud = context.user_data
    idx = ud["current_index"]
    species = ud["species_order"][idx]
    q_num = idx + 1
    total = ud["total"]

    photo_path = get_photo_path(species, 1)

    keyboard = build_options_keyboard(species, SEAL_NAMES)

    with open(photo_path, "rb") as photo:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=(
                f"❓ <b>Вопрос {q_num} из {total}</b>\n\n"
                "Какой вид тюленя изображён на фото?\n"
                "Выбери один из вариантов 👇"
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатываем нажатие кнопки с ответом."""
    query = update.callback_query
    await query.answer()

    # Игра не запущена
    if not context.user_data.get("playing"):
        await query.message.reply_text(
            "Игра ещё не начата. Нажми /play, чтобы стартовать! 🎮"
        )
        return

    ud = context.user_data
    chosen = query.data
    idx = ud["current_index"]
    species = ud["species_order"][idx]
    attempt = ud["attempt"]
    correct = chosen == species
    chat_id = query.message.chat_id
    bot = query.get_bot()

    # Убираем клавиатуру с предыдущего сообщения
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # ── Первая попытка ──────────────────────────────────────────────────────
    if attempt == 1:
        if correct:
            ud["score"] += 5
            ud["correct_count"] += 1
            await query.message.reply_text(
                f"✅ <b>Правильно!</b> Это {species.capitalize()}!\n"
                "Ты получаешь <b>+5 очков</b> 🌟",
                parse_mode="HTML",
            )
            await send_info_and_next(chat_id, context, bot, species)
        else:
            ud["attempt"] = 2
            await query.message.reply_text(
                f"❌ <b>Неверно!</b> Это был не {chosen.capitalize()}...\n\n"
                "Смотри ещё внимательнее — вот ещё <b>два фото</b> этого же вида! 👀",
                parse_mode="HTML",
            )
            # Показываем фото 2 и 3
            photos = []
            for num in (2, 3):
                with open(get_photo_path(species, num), "rb") as f:
                    photos.append(InputMediaPhoto(media=f.read()))
            await bot.send_media_group(chat_id=chat_id, media=photos)

            # Новая клавиатура (те же варианты, перемешаны заново)
            keyboard = build_options_keyboard(species, SEAL_NAMES)
            await bot.send_message(
                chat_id=chat_id,
                text="Попробуй угадать ещё раз 👇",
                reply_markup=keyboard,
                parse_mode="HTML",
            )

    # ── Вторая попытка ──────────────────────────────────────────────────────
    else:
        if correct:
            ud["score"] += 2
            ud["correct_count"] += 1
            await query.message.reply_text(
                f"✅ <b>Правильно!</b> Это {species.capitalize()}!\n"
                "Со второй попытки — <b>+2 очка</b> 👏",
                parse_mode="HTML",
            )
        else:
            await query.message.reply_text(
                f"❌ <b>Не угадал...</b>\n"
                f"Это был <b>{species.capitalize()}</b>. Очков не начислено 😔",
                parse_mode="HTML",
            )
        await send_info_and_next(chat_id, context, bot, species)


async def send_info_and_next(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    bot,
    species: str,
) -> None:
    """Показываем информацию о виде, затем следующий вопрос или итог."""
    ud = context.user_data
    info_text = SEALS[species]["info"]

    await bot.send_message(
        chat_id=chat_id,
        text=f"📖 <b>Интересно знать:</b>\n\n{info_text}",
        parse_mode="HTML",
    )

    ud["current_index"] += 1
    ud["attempt"] = 1

    if ud["current_index"] < ud["total"]:
        await bot.send_message(chat_id=chat_id, text="➡️ Следующий вопрос!")
        await send_question(chat_id, context, bot)
    else:
        await finish_game(chat_id, context, bot)


async def finish_game(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    bot,
) -> None:
    """Итоги игры."""
    ud = context.user_data
    score = ud["score"]
    correct = ud["correct_count"]
    total = ud["total"]
    max_score = total * 5

    ud["playing"] = False

    comment = result_comment(correct, total, score)

    await bot.send_message(
        chat_id=chat_id,
        text=(
            "🏁 <b>Игра окончена!</b>\n\n"
            f"🦭 Угадано видов: <b>{correct} из {total}</b>\n"
            f"⭐ Набрано очков: <b>{score} из {max_score}</b>\n\n"
            f"{comment}\n\n"
            "Сыграй ещё раз: /play\n"
            "Главное меню: /start"
        ),
        parse_mode="HTML",
    )


async def score_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показываем текущий счёт во время игры."""
    ud = context.user_data
    if not ud.get("playing"):
        await update.message.reply_text(
            "Сейчас нет активной игры. Нажми /play, чтобы начать!"
        )
        return
    idx = ud["current_index"]
    total = ud["total"]
    score = ud["score"]
    await update.message.reply_text(
        f"📊 <b>Текущий счёт</b>\n\n"
        f"Вопрос: {idx + 1} из {total}\n"
        f"Очки: {score}",
        parse_mode="HTML",
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 <b>Команды бота:</b>\n\n"
        "/start — приветствие и правила\n"
        "/play — начать новую игру\n"
        "/score — текущий счёт\n"
        "/help — эта справка",
        parse_mode="HTML",
    )


# ─── Запуск ───────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("score", score_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_answer))

    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
