import logging

from telethon import TelegramClient, events
from telethon.sessions import StringSession

import config
from database import Database

logger = logging.getLogger("userbot")

db = Database(config.DB_PATH)


class UserBotManager:
    def __init__(self):
        self.client: TelegramClient | None = None
        self.monitoring = False
        self._phone = None
        self._phone_code_hash = None
        self._session_str = config.SESSION_STRING

    def _new_client(self) -> TelegramClient:
        return TelegramClient(StringSession(self._session_str), config.API_ID, config.API_HASH)

    async def ensure_connected(self):
        if self.client is None:
            self.client = self._new_client()
        if not self.client.is_connected():
            await self.client.connect()

    async def is_authorized(self) -> bool:
        await self.ensure_connected()
        return await self.client.is_user_authorized()

    def get_session_string(self):
        return self._session_str

    # ---------- Логин ----------

    async def send_code(self, phone: str):
        self.client = self._new_client()
        await self.client.connect()
        result = await self.client.send_code_request(phone)
        self._phone = phone
        self._phone_code_hash = result.phone_code_hash

    async def submit_code(self, code: str):
        # Может выбросить SessionPasswordNeededError / PhoneCodeInvalidError —
        # ловим их на уровне бота
        await self.client.sign_in(
            phone=self._phone, code=code, phone_code_hash=self._phone_code_hash
        )
        self._session_str = self.client.session.save()

    async def submit_password(self, password: str):
        await self.client.sign_in(password=password)
        self._session_str = self.client.session.save()

    async def logout(self):
        """Выход из аккаунта: завершает сессию Telegram и сбрасывает локальное состояние."""
        self.monitoring = False
        if self.client is not None:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                await self.client.log_out()
            except Exception as e:
                logger.warning("Ошибка при выходе из аккаунта: %s", e)
        self.client = None
        self._session_str = ""
        self._phone = None
        self._phone_code_hash = None

    # ---------- Работа с чатами ----------

    async def resolve_chat(self, identifier: str):
        """identifier: ссылка t.me/..., @username или числовой ID чата (-100...)"""
        await self.ensure_connected()
        identifier = identifier.strip()
        try:
            if identifier.lstrip("-").isdigit():
                entity = await self.client.get_entity(int(identifier))
            else:
                entity = await self.client.get_entity(identifier)
        except Exception as e:
            raise RuntimeError(f"Не удалось найти чат: {e}")
        return entity

    # ---------- Мониторинг ----------

    async def start_monitoring(self):
        if self.monitoring:
            return
        await self.ensure_connected()
        if not await self.client.is_user_authorized():
            raise RuntimeError("Аккаунт не авторизован. Сначала выполните вход.")

        groups = db.list_groups()
        chat_ids = [g[0] for g in groups]
        if not chat_ids:
            raise RuntimeError("Нет добавленных групп. Сначала добавьте хотя бы одну.")

        # NewMessage-события Telethon приходят только "вживую", с момента
        # подписки на них — то есть мониторинг всегда стартует с последнего
        # сообщения, а не с начала истории чата.
        @self.client.on(events.NewMessage(chats=chat_ids))
        async def handler(event):
            await self._handle_message(event)

        self.monitoring = True
        logger.info("Мониторинг запущен для %s чатов", len(chat_ids))

    async def _handle_message(self, event):
        try:
            sender = await event.get_sender()
        except Exception:
            return
        if sender is None or getattr(sender, "bot", False):
            return

        user_id = sender.id
        if db.user_exists(user_id):
            return  # уже в базе — пропускаем

        # Определяем топик форума, если сообщение из группы с темами
        topic_id = None
        reply_to = event.message.reply_to
        if reply_to is not None and getattr(reply_to, "forum_topic", False):
            topic_id = (
                getattr(reply_to, "reply_to_top_id", None)
                or getattr(reply_to, "reply_to_msg_id", None)
            )

        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, "title", None) or str(event.chat_id)
        except Exception:
            chat_title = str(event.chat_id)

        db.add_employee(
            user_id=user_id,
            username=getattr(sender, "username", None),
            first_name=getattr(sender, "first_name", None),
            last_name=getattr(sender, "last_name", None),
            source_chat_id=event.chat_id,
            source_chat_title=chat_title,
            topic_id=topic_id,
        )
        logger.info(
            "Новый сотрудник: id=%s username=%s чат=%s топик=%s",
            user_id, sender.username, chat_title, topic_id,
        )


userbot_manager = UserBotManager()
