# Project Documentation

This document provides a detailed explanation of the code files in this project, as well as a section for documenting problems and solutions.

## File Explanations

### `ai_assistant_bot.py`

This is the main entry point for the Telegram bot. It handles the bot's lifecycle, including:

- **Initialization**: Sets up the AI parser, clarification handler, and scheduler.
- **Command Handling**: Defines handlers for commands like `/start` and `/tasks`.
- **Message Handling**: Processes incoming user messages, using the AI parser to understand user intent.
- **Clarification**: Asks for clarification when user messages are vague (e.g., "remind me later").
- **Task Management**: Shows, creates, and completes tasks based on user input.
- **Reminders**: Schedules and sends reminders for tasks.

### `my_bot.py`

This file contains a simple Telegram bot that echoes user messages. It appears to be a basic example or a starting point for the project. 

**Note**: This file contains a hardcoded Telegram bot token, which is a security risk. It is recommended to remove this file or store the token securely in an environment variable.

### `ai_parser.py`

This file is responsible for parsing user messages to identify tasks and other actions. It uses the Anthropic API to:

- **Understand Natural Language**: Processes user messages to extract tasks, completions, and other commands.
- **Generate Smart Responses**: Creates context-aware responses based on the actions taken.
- **Manage Tasks**: Provides a structured output (JSON) that the main bot can use to manage tasks.

### `clarification_utils.py`

This file provides a `SimpleClarificationHandler` class that helps in handling vague user messages. It uses regular expressions to:

- **Detect Vague Time References**: Identifies phrases like "later today" or "sometime this afternoon".
- **Create Structured Task Objects**: Helps in creating structured task objects with the necessary information.

### `database.py`

This file defines the database schema and provides functions for interacting with the database. It uses SQLAlchemy to:

- **Define Tables**: Defines the `Task`, `Conversation`, and `UserProfile` tables.
- **Create Database Session**: Provides a `get_db` function to create a database session.
- **Create Tables**: Provides a `create_tables` function to create the database tables.

### `.gitignore`

This file specifies which files and directories should be ignored by Git.

### `.env.example`

This file is an example of the environment variables required for the project. It should be copied to a `.env` file and filled with the actual values.

### `requirements.txt`

This file lists the Python dependencies required for the project.

## Improvement Log

This section documents key improvements and solutions implemented during the project's development.

---

**Issue**: Hardcoded Telegram bot token in `my_bot.py`.
**Resolution**: The hardcoded token was replaced with a secure method of loading it from an environment variable (`TELEGRAM_BOT_TOKEN_MY_BOT`). This prevents accidental exposure of sensitive credentials.
**Status**: Resolved.

---

**Issue**: Handling vague user inputs for task creation (e.g., "remind me to call John later").
**Resolution**: The `clarification_utils.py` file was created to handle such cases. It uses regular expressions to detect vague time references and prompts the user for clarification by providing specific time options. This ensures that tasks are created with a clear due date.
**Status**: Implemented.

---

**Issue**: Managing asynchronous operations, such as sending task reminders at a specific time, without blocking the main application.
**Resolution**: The `apscheduler` library was integrated to handle asynchronous task scheduling. The `AIAssistantBot` schedules reminders using `AsyncIOScheduler`, which runs in the background and sends reminders at the appropriate time without interrupting the bot's ability to handle other user requests.
**Status**: Implemented.

---

**Issue**: Ensuring the AI model has enough context to accurately manage tasks (e.g., completing the correct task when a user says "done 1").
**Resolution**: The `ai_parser.py` file was designed to provide the AI model with a numbered list of the user's pending tasks. This context allows the model to map natural language inputs like "done 1" to the correct task ID, ensuring that the right task is marked as complete.
**Status**: Implemented.

---

**Issue**: Auto-completing recurring or expired wellness tasks (e.g., "take a break," "drink water") to prevent them from cluttering the task list.
**Resolution**: A cleanup function (`cleanup_expired_wellness_tasks`) was implemented in `ai_assistant_bot.py`. This function is scheduled to run periodically and automatically marks expired wellness tasks as complete, keeping the user's task list relevant and up-to-date.
**Status**: Implemented.
