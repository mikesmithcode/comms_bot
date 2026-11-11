# CommsBot

A standalone, asynchronous Telegram integration package designed for Python agent loops and lab automation workflows. It features strict chat locking, automatic session persistence via JSON, non-blocking `/help` command generation, priority command interruption, and robust helper methods for sharing web links and image assets.

---

## Prerequisites & Telegram Setup

### 1. Download Telegram
To use CommsBot, you will need a Telegram account and the app installed on your device:
* **Mobile (iOS / Android):** Download from the [Official Telegram Mobile Apps Page](https://telegram.org/apps) or your device's app store.
* **Desktop (Windows / macOS / Linux):** Download the native desktop client from [Telegram Desktop](https://desktop.telegram.org/).

### 2. Get Your Telegram Bot API Key
To connect your bot to Telegram, you need an API token from BotFather:
1. Open Telegram and search for the official **[BotFather](https://t.me/botfather)** user (look for the verified blue checkmark).
2. Start a chat and send the command:
   ```text
   /newbot
---

## Features

* **Strict Chat Locking:** Automatically binds to the first incoming authorized chat ID and saves it to a local configuration file, ignoring stray messages from other chats.
* **Startup Handshake:** Tests connectivity on initialization with a status message, automatically resetting the chat session if the connection fails so users can easily re-establish contact.
* **Non-Blocking Execution:** Internal commands like `/help` execute instantly in the background without locking or cluttering your main agent message queue.
* **Priority Interrupts:** Intercepts high-priority commands (such as `/stop`) to cancel active asynchronous tasks immediately.
* **Rich Outbound Media:** Dedicated helper methods (`send_msg`, `send_link`, and `send_image`) for publishing text updates, markdown-formatted web server view links, and local/remote image assets.

---

## Project Structure

```text
comms_bot/
├── src/
│   └── comms_bot/
│       ├── __init__.py
│       └── bot.py
├── bot.json
├── .env
├── test_interactive.py
├── README.md
└── pyproject.toml
```

## Installation in a uv Project

Add comms_bot as a local dependency in your project's pyproject.toml or install it directly using uv:

```Bash
uv add git+https://github.com/mikesmithcode/comms_bot.git
```

## Configuration

1. Environment Variables (.env)
Create a .env file in your workspace root and insert the API token you received from BotFather:

Code snippet
TELEGRAM_API_KEY="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
2. Command Schema & State (bot.json)
Create a bot.json file in your workspace root. This file manages your bot's username, definitions for standard and priority commands, and automatically persists your active chat_id when the bot locks onto a conversation.

Example bot.json:
JSON
{
    "bot_username": "MyAgentBot",
    "chat_id": null,
    "priority_commands": [
        {
            "command": "/stop",
            "description": "Immediately interrupts and cancels the currently active agent task.",
            "args": []
        }
    ],
    "standard_commands": [
        {
            "command": "/start",
            "description": "Initializes a session with the bot and establishes the connection.",
            "args": []
        },
        {
            "command": "/p",
            "description": "Sends a direct text prompt to the agent runtime for processing.",
            "args": [
                {
                    "name": "text",
                    "type": "string",
                    "required": true,
                    "description": "The primary prompt or query text for the agent."
                }
            ]
        }
    ]
}

## Examples & Templates

To help you get started quickly, the repository includes ready-to-use template files:

* **`bot.json`**: A baseline configuration file defining your bot's command schemas and state. Copy or rename this in your project root and fill in your bot's username.
* **`test_interactive.py`**: A complete test harness utilising `aioconsole` to let you chat with your bot directly from your terminal while it polls Telegram in the background.
