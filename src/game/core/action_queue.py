from src.game.models import Action
from collections import deque

class ActionQueue:
    """
    Priority queue for actions. Reactions (high priority) process before 
    regular actions. FIFO within same priority level.
    """
    
    def __init__(self):
        self._queues: dict[int, deque[Action]] = {}
        self._priorities = []  # Sorted list of active priorities
    
    def enqueue(self, action: Action):
        """Add action at its priority level"""
        if action.priority not in self._queues:
            self._queues[action.priority] = deque()
            self._priorities = sorted(self._queues.keys(), reverse=True)
        self._queues[action.priority].append(action)
    
    def enqueue_reaction(self, action: Action):
        """Convenience: enqueue with elevated priority"""
        action.priority = 100  # Reactions always process first
        self.enqueue(action)
    
    def dequeue(self) -> Action | None:
        """Get next action (highest priority first)"""
        for priority in self._priorities:
            queue = self._queues[priority]
            if queue:
                return queue.popleft()
        return None
    
    def is_empty(self) -> bool:
        return all(len(q) == 0 for q in self._queues.values())
    
    def peek(self) -> Action | None:
        """Look at next action without removing"""
        for priority in self._priorities:
            queue = self._queues[priority]
            if queue:
                return queue[0]
        return None