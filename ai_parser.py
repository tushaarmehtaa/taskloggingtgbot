from anthropic import AsyncAnthropic
import json
import re
import logging
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from typing import List, Dict, Optional
from database import Task
import os
from dotenv import load_dotenv

# Explicitly load .env file from the project root
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger(__name__)

class AITaskParser:
    def __init__(self):
        self.anthropic_client = AsyncAnthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    async def manage_tasks(self, text: str, user_context: List[Task] = []) -> Dict:
        """
        Parse natural language to create, complete, delete, or query tasks, and ask for clarification when needed.
        """
        # Filter only pending tasks and sort them
        pending_tasks = [task for task in user_context if task.status == 'pending']
        pending_tasks.sort(key=lambda t: (t.due_date is None, t.due_date, {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}.get(t.priority, 4)))
        
        # Create numbered list with clear mapping
        numbered_tasks_str = "\n".join([f'{i}. {task.title} (Task ID: {task.id})' for i, task in enumerate(pending_tasks, 1)]) or "No pending tasks."
        
        # Create mapping for AI to understand
        task_mapping = {str(i): task.id for i, task in enumerate(pending_tasks, 1)}
        task_mapping_str = "\n".join([f"Display #{i} = Task ID {task.id}" for i, task in enumerate(pending_tasks, 1)]) or "No task mappings."
        
        now = datetime.now()
        current_time_str = now.strftime('%Y-%m-%d %H:%M:%S')
        tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')

        system_prompt = f"""
        You are a friendly, intelligent, and time-aware AI assistant for managing a to-do list. Your primary goal is to understand the user's request, correct any errors, and respond with a single, valid JSON object that represents the necessary actions.

        **CRITICAL CONTEXT**:
        - **Current Time**: `{current_time_str}`. All relative times (e.g., "in 5 minutes", "tonight", "in 30 seconds") MUST be calculated based on this exact time. Do not guess.

        **Core Capabilities**:
        1.  **Smart Correction**: The user's message may be a raw transcription from a voice note and contain phonetic or spelling errors. You must intelligently correct these mistakes before processing the command.
        2.  **Time-Aware Task Management**: You can create, complete, update, and list tasks. All dates and times must be calculated relative to the current time provided above.
        3.  **Conversational Handling**: You can handle simple greetings and general questions.

        **User's Current Tasks**:
        {numbered_tasks_str}

        **Task ID Mapping (for updates/completions)**:
        {task_mapping_str}

        **JSON Response Structure**:
        Respond with a JSON object containing one or more of the following fields:
        - `creations`: A list of new tasks to be created. Each task must have a `title`, `due_date` (in '%Y-%m-%d %H:%M:%S' format), `reminder_at` (same as due_date), and `priority`.
        - `completions`: A list of tasks to be marked as complete. Each must have the `id` of the task.
        - `updates`: A list of tasks to be updated. Each must have the `id` of the task and a `fields_to_update` dictionary.
        - `general_query`: For questions like "help" or "what can you do?". Respond with a well-formatted, user-friendly guide using Telegram's `Markdown` format. CRITICAL: Use single asterisks for bold (e.g., *bold text*), not double asterisks.
        - `greeting`: For simple greetings like "hey", "hello", "hi". Provide a friendly `response`.

        **Examples**:
        - User: "remind me to call mom at 3pm tomorrow"
          JSON: {{"creations": [{{"title": "Call mom", "due_date": "{tomorrow} 15:00:00", "reminder_at": "{tomorrow} 15:00:00", "priority": "medium"}}]}}
        - User: "remind me to take a break in 30 seconds" (Current time is {current_time_str})
          JSON: {{"creations": [{{"title": "Take a break", "due_date": "{(now + timedelta(seconds=30)).strftime('%Y-%m-%d %H:%M:%S')}", "reminder_at": "{(now + timedelta(seconds=30)).strftime('%Y-%m-%d %H:%M:%S')}", "priority": "medium"}}]}}
        - User: "Go play jirutsu at 8pm" -> (You correct this to "Go play jujutsu at 8pm")
          JSON: {{"creations": [{{"title": "Go play jujutsu", "due_date": "{now.strftime('%Y-%m-%d')} 20:00:00", "reminder_at": "{now.strftime('%Y-%m-%d')} 20:00:00", "priority": "medium"}}]}}
        - User: "done 2"
          JSON: {{"completions": [{{"id": {task_mapping.get('2')}}}]}}
        - User: "all tasks are done for today" or "mark all tasks complete" or "everything is done"
          JSON: {{"completions": [{{"id": task_id}} for task_id in [{', '.join([str(task.id) for task in user_context if task.status == 'pending'])}]]}}
        - User: "what can you do?"
          JSON: {{"intent": "general_query", "response": "I'm your AI assistant for managing your to-do list! Here's what I can help you with:\n\n*Task Management:*\n- Create new tasks with reminders (e.g., 'remind me to call mom at 3pm tomorrow')\n- Mark tasks as complete (e.g., 'done 2' to complete task #2)\n- Update existing tasks\n- Show your current task list\n\n*Smart Features:*\n- I understand relative time (like 'in 5 minutes', 'tonight', 'tomorrow')\n- I can correct spelling and voice transcription errors\n\n*How to Use:*\n- Just tell me what you want to do naturally\n- Say 'show my tasks' to see everything\n- Use 'done [number]' to complete tasks"}}
        - User: "hey"
          JSON: {{"intent": "greeting", "response": "Hello! How can I help you today?"}}

        If the user's request is unclear or doesn't fit any of the above actions, return an empty JSON object: {{}}.
        """
        message = await self.anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            temperature=0.1,
            system=system_prompt,
            messages=[
                {"role": "user", "content": text}
            ]
        )
        content = message.content[0].text.strip()
        logger.debug(f"Raw AI response for task management:\n{content}")
        
        try:
            # Find the JSON block, whether it's in a markdown code block or not
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed_json = json.loads(json_str)
                
                # Directly return the parsed JSON. The bot logic can handle the structure.
                return parsed_json
            else:
                logger.warning(f"No JSON object found in AI response: {content}")
                return {}

        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from AI response: {content}")
            return {}
        except Exception as e:
            logger.error(f"An unexpected error occurred during task parsing: {e}")
            return {}
    
    def _validate_and_process_tasks(self, tasks_data: List[Dict]) -> List[Dict]:
        """
        Validate and process the extracted tasks
        """
        processed_tasks = []
        
        for task in tasks_data:
            try:
                processed_task = {
                    'title': task.get('title', '').strip(),
                    'description': task.get('description', '').strip(),
                    'due_date': None,
                    'priority': task.get('priority', 'medium').lower(),
                    'estimated_duration': task.get('estimated_duration'),
                    'reminder_at': None
                }

                due_date_str = task.get('due_date')
                if due_date_str:
                    try:
                        processed_task['due_date'] = date_parser.parse(due_date_str)
                    except ValueError:
                        logger.warning(f"Could not parse due_date: {due_date_str}")

                reminder_at_str = task.get('reminder_at')
                if reminder_at_str:
                    try:
                        processed_task['reminder_at'] = date_parser.parse(reminder_at_str)
                    except ValueError:
                        logger.warning(f"Could not parse reminder_at: {reminder_at_str}")
                
                if processed_task['priority'] not in ['low', 'medium', 'high', 'urgent']:
                    processed_task['priority'] = 'medium'
                
                if processed_task['title']:  # Only add if title exists
                    processed_tasks.append(processed_task)
                    
            except Exception as e:
                logger.error(f"Error processing task: {e}")
                continue
        
        return processed_tasks
    
        
    async def generate_smart_response(self, user_message: str, actions: Dict, all_tasks: List[Task]) -> str:
        """
        Generate an intelligent, context-aware response based on the actions taken.
        """
        has_actions = actions.get("creations") or actions.get("completions") or actions.get("deletions")

        if has_actions:
            # --- Task-Oriented Response ---
            summary_lines = []
            if actions.get("creations"):
                summary_lines.append(f"Added {len(actions['creations'])} new task(s).")
            if actions.get("completions"):
                summary_lines.append(f"Marked {len(actions['completions'])} task(s) as complete.")
            if actions.get("deletions"):
                summary_lines.append(f"Removed {len(actions['deletions'])} task(s).")
            action_summary = " ".join(summary_lines)

            pending_tasks_count = len([task for task in all_tasks if task.status == 'pending'])
            
            system_prompt = f"""
            You are a professional AI assistant. Your purpose is to confirm actions clearly and concisely.

            Your Persona: Direct, efficient, and professional. No cheerleading, no emojis.

            Context: The user has just managed their tasks. Confirm the action taken.

            - User's message: "{user_message}"
            - Actions taken: {action_summary}
            - Pending tasks: {pending_tasks_count}

            Guidelines:
            - State the outcome directly (e.g., "Task list updated.", "Task created.").
            - Keep the response to a single, short sentence.
            - Do not add conversational filler.

            Example Responses:
            - "Done."
            - "Acknowledged. Task created."
            - "Task list updated. 2 tasks completed."

            Now, craft a professional response confirming the action.
            """
            user_prompt = "Provide a professional summary of the changes."

        else:
            # --- Conversational Response ---
            system_prompt = f"""
            You are a professional AI assistant. The user has sent a message that is not a task. Respond directly and professionally.

            Your Persona:
            - **Direct & Efficient:** Get to the point.
            - **Task-Focused:** Your goal is to manage tasks.

            Example Scenarios:
            - User: "hey" or "hello"
            - Good Response: "Ready for instructions."

            - User: "thanks!"
            - Good Response: "Acknowledged."

            - User: "you're cool"
            - Good Response: "My purpose is to assist you efficiently."

            Now, provide a direct, professional response.
            """
            user_prompt = user_message

        message = await self.anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            temperature=0.2,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        return message.content[0].text.strip()
