import os
import json
from dotenv import load_dotenv
import asyncio
from typing import Optional, Dict, Any, Set
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest
from telegram.ext import ApplicationBuilder



class CommsBot:
    def __init__(self, config_path="bot.json"):
        load_dotenv()
        BOT_TOKEN = os.getenv("TELEGRAM_API_KEY") or ""
        # Inside your CommsBot __init__ or start method where ApplicationBuilder is called:
        request_config = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0,
        )

        self.app = (
            ApplicationBuilder()
            .token(BOT_TOKEN)
            .request(request_config)
            .build()
        )
        
        self.config_path = config_path        
        self.message_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.config = self._load_config()
        
        # Track the currently running agent task so it can be cancelled
        self.active_agent_task: Optional[asyncio.Task] = None

        self.app.add_handler(
            MessageHandler(filters.ALL & (~filters.StatusUpdate.ALL), self._handle_incoming)
        )

    def _load_config(self) -> dict:
        """Loads JSON config and maps properties into structured instance attributes."""
        self.bot_username: Optional[str] = None
        self.priority_cmds: Dict[str, Dict[str, Any]] = {}
        self.standard_cmds: Dict[str, Dict[str, Any]] = {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                self.bot_username = data.get("bot_username")
                self.chat_id: Optional[int] = data.get("chat_id")
                
                for item in data.get("priority_commands", []):
                    cmd = item.get("command")
                    if cmd:
                        self.priority_cmds[cmd] = {
                            "description": item.get("description", ""),
                            "args": item.get("args", [])
                        }
                
                for item in data.get("standard_commands", []):
                    cmd = item.get("command")
                    if cmd:
                        self.standard_cmds[cmd] = {
                            "description": item.get("description", ""),
                            "args": item.get("args", [])
                        }
                return data
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

    def _save_chat_id_to_json(self, chat_id: Optional[int]):
        """Persists the chat_id directly into the JSON configuration file."""
        self.chat_id = chat_id
        try:
            # Read current file contents to preserve other keys
            data = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            data["chat_id"] = chat_id
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"⚠️ Failed to save chat_id to config file: {e}")

    def _generate_help_text(self, command_query: Optional[str] = None) -> str:
        """Generates formatted help messages for all commands or a specific command."""
        all_cmds = {**self.standard_cmds, **self.priority_cmds}

        if command_query:
            if not command_query.startswith("/"):
                command_query = "/" + command_query

            if command_query in all_cmds:
                cmd_info = all_cmds[command_query]
                help_msg = f"📖 **Command: {command_query}**\n\n"
                help_msg += f"• **Description:** {cmd_info['description']}\n\n"
                
                args = cmd_info.get("args", [])
                if args:
                    help_msg += "• **Arguments:**\n"
                    for arg in args:
                        req_str = "required" if arg.get("required") else "optional"
                        help_msg += f"  - `{arg.get('name')}` ({arg.get('type')}, {req_str}): {arg.get('description')}\n"
                else:
                    help_msg += "• **Arguments:** None\n"
                return help_msg
            else:
                general_help = self._generate_help_text(None)
                return f"❌ Command `{command_query}` does not exist.\n\n" + general_help

        help_msg = "🤖 **Available Bot Commands:**\nUse `/help <command>` for detailed info on a specific command.\n\n"
        
        if self.standard_cmds:
            help_msg += "**Standard Commands:**\n"
            for cmd, info in self.standard_cmds.items():
                help_msg += f"• `{cmd}` - {info['description']}\n"
            help_msg += "\n"

        if self.priority_cmds:
            help_msg += "**Priority / Interrupt Commands:**\n"
            for cmd, info in self.priority_cmds.items():
                help_msg += f"• `{cmd}` - {info['description']}\n"

        return help_msg

    async def _handle_incoming(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        chat = update.message.chat
        chat_id = chat.id
        chat_type = chat.type
        user = update.effective_user
        text = update.message.text

        # If no chat_id is stored yet, lock onto this one and save it to json
        if self.chat_id is None:
            self._save_chat_id_to_json(chat_id)
            print(f"🔒 Locked onto new chat ID: {chat_id} and saved to {self.config_path}")
        elif self.chat_id != chat_id:
            return  # Ignore stray chats

        if not self.bot_username and context.bot.username:
            self.bot_username = context.bot.username

        processed_text = text
        is_addressed = False

        if processed_text.strip().startswith("/"):
            is_addressed = True
        elif self.bot_username:
            mention_str = f"@{self.bot_username.lower()}"
            if mention_str in processed_text.lower():
                is_addressed = True
                processed_text = processed_text.lower().replace(mention_str, "").strip()

        if not is_addressed:
            return

        stripped_text = processed_text.strip()
        if not stripped_text.startswith("/"):
            return

        # Handle built-in /help command non-blockingly via a background task
        if stripped_text.startswith("/help"):
            parts = stripped_text.split(maxsplit=1)
            sub_command = parts[1] if len(parts) > 1 else None
            help_response = self._generate_help_text(sub_command)
            
            asyncio.create_task(self.send_msg(help_response))
            return

        is_priority = any(stripped_text.lower().startswith(cmd) for cmd in self.priority_commands)

        message_packet = {
            "chat_id": chat_id,
            "user_id": user.id if user else None,
            "username": user.username or user.first_name if user else "Unknown",
            "text": stripped_text,
            "chat_type": chat_type,
            "is_priority": is_priority
        }

        if is_priority:
            if self.active_agent_task and not self.active_agent_task.done():
                self.active_agent_task.cancel()
            await self.message_queue.put(message_packet)
        else:
            await self.message_queue.put(message_packet)

    async def start(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        # Re-initialization check: Test connection if a chat_id was previously saved
        if self.chat_id is not None:
            try:
                print(f"🔄 Testing connection to saved chat ID ({self.chat_id})...")
                await self.app.bot.send_message(chat_id=self.chat_id, text=f"{self.bot_username} connected and waiting...")
                print("✅ Connection test successful.")
            except Exception as e:
                print(f"⚠️ Connection test failed ({e}). Resetting chat_id.")
                self._save_chat_id_to_json(None)
                print("📌 Please send a command or message to the bot on Telegram to re-establish chat connection.")
        else:
            print("📌 No chat_id found. Please send a command or message to the bot on Telegram to establish a chat connection.")

    async def stop(self):
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()

    async def send_msg(self, msg: str):
        if self.chat_id is None:
            raise ValueError("Cannot send message: chat_id has not been established yet.")
        await self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="Markdown")

    async def get_msg(self) -> Dict[str, Any]:
        return await self.message_queue.get()

    async def send_link(self, url: str, title: str, description: Optional[str] = None):
        """Sends a robustly formatted web link with a title and optional description."""
        if self.chat_id is None:
            raise ValueError("Cannot send message: chat_id has not been established yet.")
        
        # Build a clean markdown message format
        msg = f"🔗 **{title}**\n"
        if description:
            msg += f"_{description}_\n"
        msg += f"\n[Access Link]({url})"
        
        await self.app.bot.send_message(
            chat_id=self.chat_id, 
            text=msg, 
            parse_mode="Markdown",
            disable_web_page_preview=False # Allows Telegram to show rich metadata preview card if desired
        )
