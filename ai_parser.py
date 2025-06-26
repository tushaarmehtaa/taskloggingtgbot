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
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        system_prompt = f"""
        You are a task management AI. Analyze the user's message and return JSON with the appropriate actions.

        Current date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        User's pending tasks:
        {numbered_tasks_str}

        IMPORTANT - Task Number to ID Mapping:
        {task_mapping_str}

        **RULES:**
        1. For task completion by number (e.g., "done 1", "complete 2", "finished 3"), use the TASK ID from the mapping above, NOT the display number.
        2. For task completion by description (e.g., "completed the presentation"), match against task titles.
        3. For task creation, extract title, due_date, priority, and reminder_at.
        4. For task queries, set query to "list_tasks".
        5. Assume "today" for times without explicit dates (e.g., "10am" = "today 10:00:00").
        6. Set priority based on urgency:
           - "urgent": Critical deadlines, emergencies, time-sensitive tasks
           - "high": Important tasks with near deadlines, work priorities
           - "medium": Regular tasks, moderate importance (default)
           - "low": Wellness tasks (breaks, water, exercise), optional tasks

        **Examples:**
        - "done 1" → Look up Task ID for display #1 from mapping → {{"completions": [{{"id": ACTUAL_TASK_ID}}]}}
        - "complete task 3" → Look up Task ID for display #3 from mapping → {{"completions": [{{"id": ACTUAL_TASK_ID}}]}}
        - "finished the presentation" → {{"completions": [{{"id": matching_task_id}}]}}
        - "pay rent by tomorrow 5pm" → {{"creations": [{{"title": "Pay rent", "due_date": "tomorrow 17:00:00", "priority": "high"}}]}}
        - "take a break in 30 minutes" → {{"creations": [{{"title": "Take a break", "due_date": "today +30min", "priority": "low"}}]}}

        **JSON Structure:**
        {{
          "query": null,
          "creations": [
            {{
              "title": "Task title",
              "due_date": "YYYY-MM-DD HH:MM:SS",
              "reminder_at": "YYYY-MM-DD HH:MM:SS", 
              "priority": "medium"
            }}
          ],
          "completions": [
            {{"id": task_id}}
          ],
          "deletions": [
            {{"id": task_id}}
          ]
        }}

        User message: "{text}"

        Return only valid JSON. CRITICAL: Use the correct Task ID from the mapping, not the display number.
        """
        message = await self.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2000,
            temperature=0.1,
            system=system_prompt,
            messages=[
                {"role": "user", "content": text}
            ]
        )
        content = message.content[0].text.strip()
        logger.debug(f"Raw AI response for task management:\n{content}")
        
        task_actions = {
            "query": None,
            "creations": [],
            "completions": [],
            "deletions": []
        }

        try:
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
            json_str = ""
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)

            if json_str:
                parsed_json = json.loads(json_str)
                task_actions["query"] = parsed_json.get("query")
                
                creations = parsed_json.get("creations", [])
                if creations:
                    task_actions["creations"] = self._validate_and_process_tasks(creations)

                completions = parsed_json.get("completions", [])
                if completions:
                    task_actions["completions"] = completions

                deletions = parsed_json.get("deletions", [])
                if deletions:
                    task_actions["deletions"] = deletions

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing AI response for task management: {e}\nContent: {content}", exc_info=True)
            return { "query": None, "creations": [], "completions": [], "deletions": [] }
            
        return task_actions
    
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
            model="claude-3-5-sonnet-20240620",
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
