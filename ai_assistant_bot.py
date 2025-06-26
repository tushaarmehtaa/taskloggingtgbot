import os
import logging
import hashlib
import os
import random
import speech_recognition as sr
from datetime import datetime, timedelta
from typing import List
from dateutil import parser as date_parser
from pydub import AudioSegment

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from dotenv import load_dotenv

from database import get_db, Task, create_tables
from ai_parser import AITaskParser
from clarification_utils import SimpleClarificationHandler

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AIAssistantBot:
    def __init__(self):
        self.ai_parser = AITaskParser()
        self.clarification_handler = SimpleClarificationHandler()
        self.scheduler = AsyncIOScheduler()
        self.application = None
        self.main_user_id = None  # Store user ID for proactive messages

        # Wellness suggestions
        self.wellness_suggestions = [
            "💧 Remember to drink some water!",
            "🚶‍♀️ Time for a short walk to stretch your legs.",
            "🧘 Take a moment to breathe deeply.",
            "👀 Look away from the screen for 20 seconds to rest your eyes.",
            "💪 A quick stretch can do wonders!"
        ]

        # Create database tables
        create_tables()

        # Set up logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)

    async def post_init(self, application):
        """Initialize components that need the event loop to be running."""
        self.scheduler.start()
        self.logger.info("Scheduler started.")

        # Schedule wellness task cleanup every 30 minutes
        self.scheduler.add_job(
            self.cleanup_expired_wellness_tasks,
            'interval',
            minutes=30,
            id='wellness_cleanup'
        )

        # Schedule proactive wellness messages every 4 hours
        self.scheduler.add_job(
            self.send_proactive_wellness_suggestion,
            'interval',
            hours=1,
            id='proactive_wellness'
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        self.main_user_id = update.effective_user.id
        self.logger.info(f"User {self.main_user_id} started the bot. Storing user ID for proactive messages.")

        welcome_message = (
            "🤖 *AI Task Assistant*\n\n"
            "I can help you manage tasks using natural language!\n\n"
            "*Examples:*\n"
            "• 'Add task to call mom at 3pm'\n"
            "• 'Pay John sometime today'\n"
            "• 'Show my tasks'\n"
            "• 'Done 1' (mark task 1 complete)\n\n"
            "Just tell me what you need to do!"
        )
        await update.message.reply_text(welcome_message, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user text messages by passing them to the processing function."""
        await self._process_text(update, context, update.message.text)

    async def _process_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text_to_process: str):
        """A shared function to process text from both text and voice messages."""
        user_id = update.effective_user.id
        self.logger.info(f"[Processing] User {user_id}: '{text_to_process}'")

        thinking_message = await update.message.reply_text("🧠 Thinking...")
        db = next(get_db())
        try:
            all_user_tasks = db.query(Task).filter(Task.user_id == user_id).all()
            result = await self.ai_parser.manage_tasks(text_to_process, all_user_tasks)

            # Handle conversational intents first
            if result.get('intent') in ['general_query', 'greeting']:
                response = result.get('response', "Hello! How can I help?")
                await thinking_message.edit_text(response, parse_mode='Markdown')
                return

            # If AI parser returned empty results and text has vague time patterns, try clarification
            if not result and self.clarification_handler.needs_clarification(text_to_process):
                await thinking_message.delete()
                await self._ask_for_time_clarification(update, text_to_process)
                return

            action_taken = False
            if result.get('completions'):
                action_taken = True
                completed_tasks = []
                for completion in result['completions']:
                    task_id = completion['id']
                    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
                    if task:
                        task.status = 'completed'
                        completed_tasks.append(f"✅ {task.title}")
                        self.logger.info(f"Completed task: {task.title}")

                if completed_tasks:
                    db.commit()
                    await self.show_tasks(update, context, completed_tasks)
                    return

            if result.get('creations'):
                action_taken = True
                for creation in result['creations']:
                    try:
                        # Parse the date string into a datetime object
                        due_date = None
                        reminder_at = None
                        if creation.get('due_date'):
                            due_date = date_parser.parse(creation['due_date'])
                        if creation.get('reminder_at'):
                            reminder_at = date_parser.parse(creation['reminder_at'])

                        new_task = Task(
                            user_id=user_id,
                            title=creation['title'],
                            due_date=due_date,
                            reminder_at=reminder_at,
                            priority=creation.get('priority', 'medium'),
                            status='pending'
                        )
                        db.add(new_task)
                        db.flush()  # Get the ID
                        
                        # Schedule reminder if needed
                        if new_task.reminder_at:
                            self._schedule_reminder(new_task)
                        
                        self.logger.info(f"Created task: {new_task.title} (ID: {new_task.id})")
                    except Exception as e:
                        self.logger.error(f"Error creating task: {e}")
                        continue

                db.commit()
                await self.show_tasks(update, context)
                return

            if result.get('updates'):
                action_taken = True
                for update_item in result['updates']:
                    task_id = update_item['id']
                    fields = update_item['fields_to_update']
                    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
                    if task:
                        for field, value in fields.items():
                            if hasattr(task, field):
                                if field in ['due_date', 'reminder_at'] and value:
                                    try:
                                        setattr(task, field, date_parser.parse(value))
                                    except:
                                        self.logger.error(f"Failed to parse date: {value}")
                                        continue
                                else:
                                    setattr(task, field, value)
                        self.logger.info(f"Updated task: {task.title}")

                db.commit()
                await self.show_tasks(update, context)
                return

            # If no actions were taken, show current tasks or provide help
            if not action_taken:
                if not result:
                    await thinking_message.edit_text("I'm not sure how to help. Try creating a task or asking for your 'tasks'.")
                else:
                    await self.show_tasks(update, context)

        except Exception as e:
            self.logger.error(f"Error in _process_text: {e}", exc_info=True)
            await thinking_message.edit_text("Sorry, I encountered an error processing your request.")
        finally:
            db.close()

    async def _ask_for_time_clarification(self, update: Update, original_message: str):
        """Ask for time clarification using inline buttons."""
        action, object_part = self.clarification_handler.extract_task_action_and_object(original_message)
        task_preview = self.clarification_handler.create_task_title(action, object_part)

        # Use a truncated hash to stay within Telegram's 64-byte callback_data limit
        message_hash = hashlib.sha256(original_message.encode()).hexdigest()[:16]

        # Create inline keyboard with time options
        keyboard = []
        time_slots = self.clarification_handler.TIME_SLOTS

        # Create rows of 4 buttons each
        for i in range(0, len(time_slots), 4):
            row = []
            for j in range(4):
                if i + j < len(time_slots):
                    display_time, actual_time = time_slots[i + j]
                    callback_data = f"time_{actual_time}_{message_hash}"
                    row.append(InlineKeyboardButton(display_time, callback_data=callback_data))
            keyboard.append(row)

        # Add custom time option
        keyboard.append([InlineKeyboardButton("📝 Custom Time", callback_data=f"custom_{message_hash}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Store the original message in a class variable for callback access
        if not hasattr(self, 'pending_clarifications'):
            self.pending_clarifications = {}
        self.pending_clarifications[message_hash] = original_message

        question = f"What time would you like to *{task_preview.lower()}*?"
        await update.message.reply_text(
            question,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_time_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle time selection from inline buttons."""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        user_id = update.effective_user.id
        
        if callback_data.startswith('time_'):
            # Extract time and message hash
            parts = callback_data.split('_')
            selected_time = parts[1]  # HH:MM format
            message_hash = parts[2]
            
            # Get original message
            original_message = self.pending_clarifications.get(message_hash)
            
            if not original_message:
                await query.edit_message_text("Sorry, I lost track of your original request. Please try again.")
                return
            
            # Create task with selected time
            task_data = self.clarification_handler.create_task_with_time(original_message, selected_time)
            
            # Save to database
            db = next(get_db())
            try:
                new_task = Task(
                    user_id=user_id,
                    title=task_data['title'],
                    due_date=datetime.strptime(task_data['due_date'], '%Y-%m-%d %H:%M:%S'),
                    reminder_at=datetime.strptime(task_data['reminder_at'], '%Y-%m-%d %H:%M:%S'),
                    priority=task_data['priority'],
                    status='pending'
                )
                db.add(new_task)
                db.commit()
                
                # Schedule reminder
                await self._schedule_reminder(new_task)
                
                # Clean up pending clarification
                del self.pending_clarifications[message_hash]
                
                # Confirm task creation
                time_display = datetime.strptime(selected_time, '%H:%M').strftime('%I:%M %p')
                confirmation = f"✅ Task created: *{task_data['title']}* at {time_display}"
                await query.edit_message_text(confirmation, parse_mode='Markdown')
                
                self.logger.info(f"[Clarification] Created task '{task_data['title']}' for user {user_id}")
                
            except Exception as e:
                self.logger.error(f"Error creating task from clarification: {e}")
                await query.edit_message_text("Sorry, there was an error creating your task. Please try again.")
            finally:
                db.close()
        
        elif callback_data.startswith('custom_'):
            # Handle custom time input
            message_hash = callback_data.split('_')[1]
            await query.edit_message_text(
                "Please type your preferred time (e.g., '2:30 PM', '14:30', 'in 2 hours'):"
            )
             # Note: This would require additional conversation handling for custom times
            # For now, we'll keep it simple with predefined slots

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages by transcribing them and processing the text."""
        self.logger.info("Received voice message.")
        processing_message = await update.message.reply_text("🎤 Processing voice note...")

        try:
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            
            temp_dir = "temp_audio"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            oga_path = os.path.join(temp_dir, f"{update.message.voice.file_id}.oga")
            wav_path = os.path.join(temp_dir, f"{update.message.voice.file_id}.wav")

            await voice_file.download_to_drive(oga_path)

            audio = AudioSegment.from_ogg(oga_path)
            audio.export(wav_path, format="wav")

            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            
            transcribed_text = recognizer.recognize_google(audio_data)
            self.logger.info(f"Transcription: '{transcribed_text}'")

            os.remove(oga_path)
            os.remove(wav_path)

            # Delete the 'processing' message and call the shared text processor
            await processing_message.delete()
            await self._process_text(update, context, transcribed_text)

        except sr.UnknownValueError:
            self.logger.warning("Google Speech Recognition could not understand audio")
            await processing_message.edit_text("Sorry, I couldn't understand what you said. Please try again.")
        except sr.RequestError as e:
            self.logger.error(f"Could not request results from Google Speech Recognition service; {e}")
            await processing_message.edit_text("Sorry, my speech recognition service is down.")
        except Exception as e:
            self.logger.error(f"Error processing voice message: {e}", exc_info=True)
            await processing_message.edit_text("An unexpected error occurred while processing your voice note.")

    async def show_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE, completed_tasks: List[str] = None):
        """Show user's tasks in a formatted list. Can also show a completion message."""
        user_id = update.effective_user.id
        db = next(get_db())
        try:
            # Centralized sorting logic
            pending_tasks = db.query(Task).filter(Task.user_id == user_id, Task.status == 'pending').all()
            pending_tasks.sort(key=lambda t: (t.due_date is None, t.due_date, {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}.get(t.priority, 4)))

            message = ""
            if completed_tasks:
                if len(completed_tasks) == 1:
                    message += f"🎉 Great job! Completed: *{completed_tasks[0]}*\n\n"
                else:
                    message += f"🎉 Great job! Completed {len(completed_tasks)} tasks.\n\n"

            if not pending_tasks:
                message += "🎊 **All tasks completed! You're all caught up!**" if completed_tasks else "You have no pending tasks. Add one by sending me a message!"
                await update.message.reply_text(message, parse_mode='Markdown')
                return

            message += "📋 **Your Remaining Tasks:**\n\n" if completed_tasks else "📋 **Your Tasks:**\n\n"
            for i, task in enumerate(pending_tasks, 1):
                due_str = f" - Due: {task.due_date.strftime('%I:%M %p')}" if task.due_date else ""
                
                priority_indicators = {
                    "urgent": "🔴 **URGENT**",
                    "high": "🟠 **HIGH**", 
                    "medium": "🟡",
                    "low": "🟢"
                }
                priority_display = priority_indicators.get(task.priority, "⚪")
                
                message += f"{i}. {priority_display} {task.title}{due_str}\n"

            message += f"\n_Total: {len(pending_tasks)} pending tasks_"
            message += f"\n\n💡 *Tip: Say 'done 1' to complete task #1*"
            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            self.logger.error(f"Error in show_tasks: {e}")
            await update.message.reply_text("An error occurred while fetching your tasks.")
        finally:
            db.close()

    async def _schedule_reminder(self, task: Task):
        if task.reminder_at and task.reminder_at > datetime.now() and not task.reminder_sent:
            trigger = DateTrigger(run_date=task.reminder_at)
            job_id = f"task_reminder_{task.id}"
            self.scheduler.add_job(
                self.send_reminder,
                trigger=trigger,
                args=[task.user_id, task.id],
                id=job_id,
                replace_existing=True
            )
            self.logger.info(f"Successfully scheduled reminder for task {task.id} (Job ID: {job_id}) at {task.reminder_at}")
        else:
            self.logger.info(f"Did not schedule reminder for task {task.id}. Reason: No reminder time, reminder in past, or already sent.")

    async def send_reminder(self, user_id: int, task_id: int):
        db = next(get_db())
        try:
            task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
            if task and task.status == 'pending':
                reminder_message = f"🔔 **Reminder: Time to start your task!**\n\n" \
                                   f"**Task:** {task.title}"
                if task.due_date:
                    reminder_message += f"\n**Due:** {task.due_date.strftime('%a, %b %d, %I:%M %p')}"

                await self.application.bot.send_message(chat_id=user_id, text=reminder_message, parse_mode='Markdown')
                task.reminder_sent = True
                db.commit()
                self.logger.info(f"Successfully sent reminder for task {task_id} to user {user_id}")
            elif task:
                self.logger.warning(f"Skipped sending reminder for task {task_id} as its status is '{task.status}'.")
        except Exception as e:
            self.logger.error(f"Failed to send reminder for task {task_id}: {e}", exc_info=True)
        finally:
            db.close()

    async def cleanup_expired_wellness_tasks(self):
        """Auto-complete expired wellness tasks (breaks, water, exercise, etc.)."""
        db = next(get_db())
        try:
            now = datetime.now()
            wellness_keywords = ['break', 'water', 'exercise', 'walk', 'stretch', 'rest', 'breathe', 'drink', 'hydrate']
            
            # Find expired wellness tasks - be more aggressive with break tasks
            expired_wellness_tasks = db.query(Task).filter(
                Task.status == 'pending',
                Task.due_date < now  # Any overdue task
            ).all()
            
            completed_count = 0
            # Filter by wellness keywords in title
            for task in expired_wellness_tasks:
                if any(keyword in task.title.lower() for keyword in wellness_keywords):
                    # For break tasks, auto-complete immediately when overdue
                    if 'break' in task.title.lower():
                        task.status = 'completed'
                        completed_count += 1
                        self.logger.info(f"Auto-completed expired break task: {task.title}")
                    # For other wellness tasks, give 15 min grace period and check priority
                    elif task.due_date < now - timedelta(minutes=15) and task.priority == 'low':
                        task.status = 'completed'
                        completed_count += 1
                        self.logger.info(f"Auto-completed expired wellness task: {task.title}")
            
            if completed_count > 0:
                db.commit()
                self.logger.info(f"Auto-completed {completed_count} expired wellness tasks")
            
        except Exception as e:
            self.logger.error(f"Error in wellness task cleanup: {e}")
        finally:
            db.close()

    async def send_proactive_wellness_suggestion(self):
        """Periodically send a random wellness suggestion to the user."""
        if self.main_user_id:
            try:
                suggestion = random.choice(self.wellness_suggestions)
                await self.application.bot.send_message(chat_id=self.main_user_id, text=suggestion)
                self.logger.info(f"Sent proactive wellness suggestion to user {self.main_user_id}: {suggestion}")
            except Exception as e:
                self.logger.error(f"Failed to send proactive wellness suggestion: {e}", exc_info=True)
        else:
            self.logger.info("Skipping proactive wellness suggestion: user ID not set yet.")

    def run(self):
        """Set up and run the bot."""
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            self.logger.critical("❌ TELEGRAM_BOT_TOKEN not found!")
            raise ValueError("TELEGRAM_BOT_TOKEN is required.")

        self.application = Application.builder().token(token).post_init(self.post_init).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("tasks", self.show_tasks))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_time_selection))

        self.logger.info("🤖 AI Assistant Bot is starting...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = AIAssistantBot()
    bot.run()
