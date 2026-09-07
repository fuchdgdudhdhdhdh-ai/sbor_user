import logging
import os

from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
from userbot import userbot_manager, db

logger = logging.getLogger("bot")

# Состояния диалогов
PHONE, CODE, PASSWORD, WAIT_GROUP = range(4)


def is_owner(user_id: int) -> bool:
    return user_id in config.OWNER_IDS


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Войти в аккаунт", callback_data="login")],
        [InlineKeyboardButton("➕ Добавить группу", callback_data="add_group")],
        [InlineKeyboardButton("📋 Список групп", callback_data="list_groups")],
        [InlineKeyboardButton("▶️ Запустить мониторинг", callback_data="start_monitor")],
        [InlineKeyboardButton("📥 Скачать базу (CSV)", callback_data="export_db")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
    ])


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())


# ---------- Простые действия (без диалога) ----------

async def simple_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_owner(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return
    await query.answer()

    if query.data == "list_groups":
        groups = db.list_groups()
        if not groups:
            text = "Пока нет добавленных групп."
        else:
            text = "\n".join(f"• {title or chat_id} (id: `{chat_id}`)" for chat_id, title, _ in groups)
        await query.message.reply_text(text, parse_mode="Markdown")

    elif query.data == "start_monitor":
        try:
            await userbot_manager.start_monitoring()
            await query.message.reply_text(
                "Мониторинг запущен ✅\nБот смотрит только новые сообщения, "
                "с момента запуска (историю чата не сканирует)."
            )
        except Exception as e:
            await query.message.reply_text(f"Ошибка: {e}")

    elif query.data == "export_db":
        path = "employees_export.csv"
        db.export_csv(path)
        if os.path.getsize(path) == 0 or db.count_employees() == 0:
            await query.message.reply_text("База пока пуста.")
        else:
            with open(path, "rb") as f:
                await query.message.reply_document(document=f, filename="employees.csv")

    elif query.data == "stats":
        count = db.count_employees()
        groups = db.list_groups()
        monitoring_status = "включён ▶️" if userbot_manager.monitoring else "выключен ⏸"
        await query.message.reply_text(
            f"Сотрудников в базе: {count}\n"
            f"Групп на мониторинге: {len(groups)}\n"
            f"Статус мониторинга: {monitoring_status}"
        )


# ---------- Диалог логина ----------

async def login_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_owner(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    await query.message.reply_text("Введите номер телефона в международном формате, например +79991234567:")
    return PHONE


async def login_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    try:
        await userbot_manager.send_code(phone)
    except Exception as e:
        await update.message.reply_text(f"Не удалось отправить код: {e}")
        return ConversationHandler.END
    await update.message.reply_text("Введите код, который пришёл в Telegram:")
    return CODE


async def login_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().replace(" ", "")
    try:
        await userbot_manager.submit_code(code)
    except SessionPasswordNeededError:
        await update.message.reply_text("На аккаунте включена двухфакторная аутентификация.\nВведите пароль 2FA:")
        return PASSWORD
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        await update.message.reply_text("Код неверный или устарел. Начните заново: /start")
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Ошибка входа: {e}")
        return ConversationHandler.END

    await _send_login_success(update)
    return ConversationHandler.END


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    try:
        await userbot_manager.submit_password(password)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return ConversationHandler.END

    await _send_login_success(update)
    return ConversationHandler.END


async def _send_login_success(update: Update):
    session_str = userbot_manager.get_session_string()
    await update.message.reply_text(
        "Вход выполнен успешно ✅\n\n"
        "Чтобы не логиниться заново после каждого перезапуска сервиса на Render, "
        "скопируйте эту строку и сохраните её в переменную окружения SESSION_STRING "
        "в настройках вашего сервиса (Environment):\n\n"
        f"`{session_str}`",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ---------- Диалог добавления группы ----------

async def add_group_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_owner(query.from_user.id):
        await query.answer("Доступ запрещён", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    if not await userbot_manager.is_authorized():
        await query.message.reply_text("Сначала выполните вход в аккаунт (кнопка «Войти в аккаунт»).")
        return ConversationHandler.END
    await query.message.reply_text(
        "Отправьте ссылку на группу (https://t.me/...), @username "
        "или числовой ID чата (например -1001234567890).\n"
        "Можно отправить несколько групп — по одной сообщением."
    )
    return WAIT_GROUP


async def add_group_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        entity = await userbot_manager.resolve_chat(text)
    except Exception as e:
        await update.message.reply_text(f"{e}\nПопробуйте ещё раз или /cancel")
        return WAIT_GROUP

    title = getattr(entity, "title", None) or getattr(entity, "username", None) or str(entity.id)
    db.add_group(entity.id, title)
    await update.message.reply_text(
        f"Группа добавлена: {title} (id={entity.id})\n"
        f"Отправьте следующую группу или /done чтобы закончить."
    )
    return WAIT_GROUP


async def add_group_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Готово.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


def build_application() -> Application:
    application = Application.builder().token(config.BOT_TOKEN).build()

    login_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(login_entry, pattern="^login$")],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    add_group_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_group_entry, pattern="^add_group$")],
        states={
            WAIT_GROUP: [
                CommandHandler("done", add_group_done),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_group_receive),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(login_conv)
    application.add_handler(add_group_conv)
    application.add_handler(
        CallbackQueryHandler(simple_menu_handler, pattern="^(list_groups|start_monitor|export_db|stats)$")
    )

    return application
