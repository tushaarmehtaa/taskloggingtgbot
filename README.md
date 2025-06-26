# AI Productivity Assistant Bot 🤖

A smart Telegram bot that helps you manage tasks and boost productivity using natural language processing and AI.

## Features ✨

- **Natural Language Task Parsing**: Tell the bot about your tasks in plain English
- **Smart Scheduling**: AI-powered prioritization based on deadlines and importance
- **Task Management**: Create, track, and manage your tasks effortlessly
- **Intelligent Responses**: Get personalized productivity advice and suggestions
- **Database Storage**: All your tasks and conversations are saved locally

## Quick Start 🚀

### 1. Setup Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

### 2. Get Your Bot Token

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Use `/newbot` command and follow instructions
3. Copy the bot token to your `.env` file

### 3. Get Anthropic API Key

1. Sign up at [Anthropic](https://console.anthropic.com/)
2. Go to the API Keys section in your Account Settings.
3. Create a new API key and add it to your `.env` file.

### 4. Run the Bot

```bash
python3 ai_assistant_bot.py
```

## Usage Examples 💬

### Adding Tasks
Just talk naturally to the bot:

```
"Hey, I need to finish my marketing assignment by Friday, write 3 blog posts by next week, and prepare for a meeting tomorrow at 2 PM"
```

The bot will automatically:
- Extract individual tasks
- Parse deadlines and priorities
- Store them in your task list
- Provide intelligent scheduling suggestions

### Commands
- `/start` - Welcome message and introduction
- `/help` - Show available commands
- `/tasks` - View your current task list

## Project Structure 📁

```
gymloggingtgbot/
├── ai_assistant_bot.py    # Main bot application
├── ai_parser.py           # AI task parsing logic
├── database.py            # Database models and setup
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
├── .env.example          # Environment template
└── README.md             # This file
```

## Next Steps 🔮

Future enhancements planned:
- [ ] Calendar integration (Google Calendar)
- [ ] Voice message processing
- [ ] Task completion reminders
- [ ] Weekly productivity reports
- [ ] Team collaboration features

## Support 💡

If you encounter any issues:
1. Make sure all environment variables are set correctly
2. Check that your OpenAI API key has sufficient credits
3. Ensure your bot token is valid and active

Happy productivity! 🎯
