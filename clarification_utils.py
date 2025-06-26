"""
Simplified clarification utilities using pattern matching instead of AI.
"""
import re
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

class SimpleClarificationHandler:
    
    # Patterns that indicate vague timing
    VAGUE_TIME_PATTERNS = [
        r'\bsometime today\b',
        r'\blater today\b', 
        r'\blater\b',
        r'\bsoon\b',
        r'\bin a bit\b',
        r'\bin a while\b',
        r'\bthis afternoon\b',
        r'\bthis evening\b',
        r'\btoday\b(?!\s+at|\s+\d)',  # "today" without specific time
    ]
    
    # Common time slots for buttons
    TIME_SLOTS = [
        ("9:00 AM", "09:00"),
        ("10:00 AM", "10:00"), 
        ("11:00 AM", "11:00"),
        ("12:00 PM", "12:00"),
        ("1:00 PM", "13:00"),
        ("2:00 PM", "14:00"),
        ("3:00 PM", "15:00"),
        ("4:00 PM", "16:00"),
        ("5:00 PM", "17:00"),
        ("6:00 PM", "18:00"),
        ("7:00 PM", "19:00"),
        ("8:00 PM", "20:00"),
    ]
    
    def needs_clarification(self, text: str) -> bool:
        """Check if text contains vague time references that need clarification."""
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in self.VAGUE_TIME_PATTERNS)
    
    def extract_task_action_and_object(self, text: str) -> Tuple[str, str]:
        """Extract the action and object from task text using simple patterns."""
        text_clean = text.lower().strip()
        
        # Remove vague time phrases to get core task
        for pattern in self.VAGUE_TIME_PATTERNS:
            text_clean = re.sub(pattern, '', text_clean).strip()
        
        # Common action patterns
        action_patterns = [
            (r'^(pay|send money to|transfer to)\s+(.+)', 'Pay', 2),
            (r'^(call|phone|ring)\s+(.+)', 'Call', 2),
            (r'^(email|send email to|write to)\s+(.+)', 'Email', 2),
            (r'^(meet|meeting with)\s+(.+)', 'Meet with', 2),
            (r'^(buy|purchase|get)\s+(.+)', 'Buy', 2),
            (r'^(remind me to|reminder to)\s+(.+)', 'Reminder', 2),
            (r'^(finish|complete|do)\s+(.+)', 'Finish', 2),
        ]
        
        for pattern, action_prefix, group_num in action_patterns:
            match = re.search(pattern, text_clean)
            if match:
                object_part = match.group(group_num).strip()
                return action_prefix, object_part
        
        # Fallback: try to extract meaningful parts
        words = text_clean.split()
        if len(words) >= 2:
            action = words[0].capitalize()
            object_part = ' '.join(words[1:])
            return action, object_part
        
        return "Task", text_clean
    
    def create_task_title(self, action: str, object_part: str) -> str:
        """Create a proper task title from action and object."""
        if not object_part:
            return action
        
        # Clean up object part
        object_clean = object_part.strip()
        
        # Handle special cases
        if action.lower() == 'pay' and object_clean:
            return f"Pay {object_clean.title()}"
        elif action.lower() == 'call' and object_clean:
            return f"Call {object_clean.title()}"
        elif action.lower() == 'email' and object_clean:
            return f"Email {object_clean.title()}"
        else:
            return f"{action} {object_clean}"
    
    def create_task_with_time(self, original_text: str, selected_time: str) -> Dict:
        """Create a complete task object with the selected time."""
        action, object_part = self.extract_task_action_and_object(original_text)
        title = self.create_task_title(action, object_part)
        
        # Parse selected time (format: "HH:MM")
        today = datetime.now().strftime('%Y-%m-%d')
        due_date = f"{today} {selected_time}:00"
        
        # Determine priority based on action
        priority = "medium"
        if action.lower() in ['pay', 'transfer', 'send money']:
            priority = "high"
        elif any(word in original_text.lower() for word in ['break', 'water', 'exercise', 'rest']):
            priority = "low"
        
        return {
            "title": title,
            "due_date": due_date,
            "reminder_at": due_date,
            "priority": priority
        }
