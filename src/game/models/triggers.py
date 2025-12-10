from enum import Enum
from typing import List, Set, Any
from pydantic import BaseModel
from abc import ABC, abstractmethod
from src.game.models.actions import StateChange, RollSpec, RollType, Action, ActionPlan, ActionType
from src.game.models.state import GameState, Entity

# ============================================================
# TRIGGER EVENT TYPES
# ============================================================

class TriggerEvent(Enum):
    """What kind of game event can wake up a trigger?"""
    
    # Action-based triggers
    ACTION_ATTEMPTED = "action_attempted"    # Before resolution (can interrupt)
    ACTION_RESOLVED = "action_resolved"     # After resolution (reactions)
    
    # Movement triggers
    ENTER = "enter"      # Entity enters a room/area
    EXIT = "exit"       # Entity leaves
    APPROACH = "approach"            # Entity gets close to something
    
    # State-change triggers  
    STATE_CHANGED = "state_changed"       # Generic state change occurred
    THRESHOLD_CROSSED = "threshold_crossed"   # HP dropped below 50%, etc.
    ITEM_ACQUIRED = "item_acquired"             # Something picked up
    ITEM_USED = "item_used"                     # Something used/consumed
    
    # Perception triggers
    PERCEPTION_CHECK = "perception_check"    # Player actively looking/listening
    PASSIVE_PERCEPTION = "passive_perception"  # Automatic awareness check
    
    # Time triggers
    TIME_ELAPSED = "time_elapsed"        # X turns have passed
    ROUND_START = "round_start"         # Combat round beginning
    ROUND_END = "round_end"           # Combat round ending

class TriggerContext(BaseModel):
    """Context passed to triggers during evaluation"""
    actor_id: str                          # Who did something
    event_type: TriggerEvent               # What kind of event
    state: GameState                     # Current game state
    current_turn: int                      # For cooldown tracking
    triggering_action: Action | None  # The action that caused this
    
    class Config:
        arbitrary_types_allowed = True
# ============================================================
# CONDITIONS (Predicates)
# ============================================================

class Condition(BaseModel, ABC):
    """
    Abstract base for trigger conditions.
    Conditions are pure predicates—they check state but don't modify it.
    """
    
    @abstractmethod
    def evaluate(self, context: TriggerContext) -> bool:
        """Return True if this condition is met"""
        pass
    
    @abstractmethod
    def describe(self) -> str:
        """Human-readable description for DM narration"""
        pass


class AttributeCondition(Condition):
    """Check if an entity's attribute meets a threshold"""
    entity_id: str
    attribute: str
    operator: str  # ">=", "<=", "==", "!=", ">", "<"
    value: Any
    
    def evaluate(self, ctx: TriggerContext) -> bool:
        entity = ctx.state.get_entity(self.entity_id)
        if not entity:
            return False
        actual = getattr(entity, self.attribute, None)
        if actual is None:
            return False
        
        ops = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
        }
        return ops[self.operator](actual, self.value)
    
    def describe(self) -> str:
        return f"{self.entity_id}.{self.attribute} {self.operator} {self.value}"


class ProximityCondition(Condition):
    """Check if actor is near a location or entity"""
    target_id: str  # Location or entity ID
    max_distance: int = 1  # In grid squares/zones
    
    def evaluate(self, ctx: TriggerContext) -> bool:
        return ctx.state.distance_between(ctx.actor_id, self.target_id) <= self.max_distance
    
    def describe(self) -> str:
        return f"within {self.max_distance} of {self.target_id}"


class ActionTypeCondition(Condition):
    """Check if the triggering action is of a specific type"""
    action_types: Set[ActionType]
    
    def evaluate(self, ctx: TriggerContext) -> bool:
        if ctx.triggering_action is None:
            return False
        return ctx.triggering_action.plan.action_type in self.action_types
    
    def describe(self) -> str:
        return f"action is one of {self.action_types}"


class TargetCondition(Condition):
    """Check if a specific entity is the target of an action"""
    entity_id: str
    
    def evaluate(self, ctx: TriggerContext) -> bool:
        if ctx.triggering_action is None:
            return False
        return self.entity_id in ctx.triggering_action.plan.target_ids
    
    def describe(self) -> str:
        return f"{self.entity_id} is targeted"


class HasItemCondition(Condition):
    """Check if an entity has a specific item"""
    entity_id: str
    item_id: str
    
    def evaluate(self, ctx: TriggerContext) -> bool:
        entity = ctx.state.get_entity(self.entity_id)
        return entity and self.item_id in entity.inventory
    
    def describe(self) -> str:
        return f"{self.entity_id} has {self.item_id}"


class CompositeCondition(Condition):
    """Combine multiple conditions with AND/OR logic"""
    conditions: List[Condition]
    operator: str = "AND"  # "AND" or "OR"
    
    def evaluate(self, ctx: TriggerContext) -> bool:
        if self.operator == "AND":
            return all(c.evaluate(ctx) for c in self.conditions)
        else:
            return any(c.evaluate(ctx) for c in self.conditions)
    
    def describe(self) -> str:
        joiner = " AND " if self.operator == "AND" else " OR "
        return f"({joiner.join(c.describe() for c in self.conditions)})"


# ============================================================
# CHECKS (Optional skill/ability gates)
# ============================================================

class TriggerCheck(BaseModel):
    """
    An optional skill check required for a trigger to fully activate.
    Unlike Conditions (which are binary), Checks involve dice.
    """
    check_type: str              # "perception", "investigation", "stealth", etc.
    dc: int                      # Difficulty class
    attribute: str               # "WIS", "INT", "DEX", etc.
    
    # Who makes this check?
    checker: str = "actor"       # "actor" (triggering entity) or specific entity_id
    
    # Can passive scores trigger this?
    allow_passive: bool = True
    passive_modifier: int = 0    # Bonus/penalty to passive checks
    
    # What happens on failure?
    reveal_on_failure: bool = False  # Does failure reveal something exists?
    failure_hint: str | None  # "You sense something is off..."

    def to_roll_spec(self, actor: Entity) -> RollSpec:
        """Convert to a RollSpec for the resolution engine"""
        modifier = actor.get_skill_modifier(self.check_type)
        return RollSpec(
            roll_type=RollType.CHECK,
            dice=f"1d20+{modifier}",
            dc=self.dc,
            reason=f"{self.check_type.title()} check"
        )


# ============================================================
# EFFECTS (What happens when triggered)
# ============================================================

class TriggerEffect(BaseModel, ABC):
    """What happens when a trigger activates"""
    
    @abstractmethod
    def to_actions(self, ctx: TriggerContext) -> List[Action]:
        """Generate the actions this effect produces"""
        pass


class SpawnActionEffect(TriggerEffect):
    """Queue an action as if an entity performed it"""
    actor_id: str
    intent_template: str  # Can include {variables}
    priority: int = 50    # Higher than normal (0) but lower than reactions (100)
    
    def to_actions(self, ctx: TriggerContext) -> List[Action]:
        # Interpolate template with context
        intent = self.intent_template.format(
            actor=ctx.actor_id,
            target=ctx.triggering_action.plan.target_ids[0] if ctx.triggering_action else None,
            location=ctx.state.get_entity_location(ctx.actor_id)
        )
        return [Action(
            id=f"triggered_{self.actor_id}_{id(self)}",
            owner_id=self.actor_id,
            intent_text=intent,
            priority=self.priority
        )]


class StateChangeEffect(TriggerEffect):
    """Directly modify state without going through action resolution"""
    changes: List[StateChange]
    
    def to_actions(self, ctx: TriggerContext) -> List[Action]:
        # This is a "pseudo-action" that just applies state changes
        # We wrap it so it goes through the normal flow
        action = Action(
            id=f"state_change_{id(self)}",
            owner_id="system",
            intent_text="[System state change]",
            priority=200  # Highest priority—happens immediately
        )
        # Pre-populate the plan so DM doesn't need to interpret
        action.plan = ActionPlan(
            action_type=ActionType.OTHER,
            actor_id="system",
            required_rolls=[],
            on_success=self.changes,
            narrative_context="triggered effect"
        )
        return [action]


class RevealEffect(TriggerEffect):
    """Reveal a hidden entity/object to the player"""
    entity_id: str
    revelation_text: str  # What the player perceives
    
    def to_actions(self, ctx: TriggerContext) -> List[Action]:
        return [Action(
            id=f"reveal_{self.entity_id}",
            owner_id="system",
            intent_text=f"[Reveal: {self.revelation_text}]",
            priority=150
        )]


class CompositeEffect(TriggerEffect):
    """Multiple effects that all fire together"""
    effects: List[TriggerEffect]
    
    def to_actions(self, ctx: TriggerContext) -> List[Action]:
        actions = []
        for effect in self.effects:
            actions.extend(effect.to_actions(ctx))
        return actions


# ============================================================
# THE TRIGGER ITSELF
# ============================================================

class Trigger(BaseModel):
    """
    A dormant action-generator that activates under specific circumstances.
    
    This is the clean replacement for your Requirement class.
    """
    id: str
    name: str                              # "Pit Trap", "Hidden Assassin", etc.
    description: str                       # For DM/debug purposes
    
    # WHEN does this trigger wake up?
    trigger_events: Set[TriggerEvent]      # What events cause evaluation
    
    # WHERE is this trigger active?
    location_id: str | None      # None = anywhere
    attached_to: str | None      # Entity ID if attached to something
    
    # WHAT conditions must be met?
    conditions: List[Condition] = []       # All must pass (implicit AND)
    
    # OPTIONAL: Skill check gate
    check: TriggerCheck | None   # If present, must pass to activate
    
    # WHAT happens when triggered?
    effect: TriggerEffect
    
    # Lifecycle management
    single_use: bool = True                # Remove after triggering?
    enabled: bool = True                   # Can be disabled temporarily
    cooldown_turns: int = 0                # Turns before can trigger again
    last_triggered_turn: int = -999        # Track cooldown
    
    def evaluate(self, ctx: TriggerContext) -> 'TriggerEvaluation':
        """
        Evaluate whether this trigger should activate.
        Returns an evaluation result with all the details.
        """
        # Check if enabled and not on cooldown
        if not self.enabled:
            return TriggerEvaluation(trigger=self, activated=False, reason="disabled")
        
        if ctx.current_turn - self.last_triggered_turn < self.cooldown_turns:
            return TriggerEvaluation(trigger=self, activated=False, reason="on cooldown")
        
        # Check location constraint
        if self.location_id and ctx.state.get_entity_location(ctx.actor_id) != self.location_id:
            return TriggerEvaluation(trigger=self, activated=False, reason="wrong location")
        
        # Evaluate all conditions
        for condition in self.conditions:
            if not condition.evaluate(ctx):
                return TriggerEvaluation(
                    trigger=self, 
                    activated=False, 
                    reason=f"condition failed: {condition.describe()}"
                )
        
        # All conditions passed!
        # If there's a check, we need to signal that a roll is required
        if self.check:
            return TriggerEvaluation(
                trigger=self,
                activated=False,  # Not yet—pending check
                pending_check=self.check,
                reason="awaiting check"
            )
        
        # No check needed, trigger activates
        return TriggerEvaluation(trigger=self, activated=True)


class TriggerEvaluation(BaseModel):
    """Result of evaluating a trigger"""
    trigger: Trigger
    activated: bool
    pending_check: TriggerCheck | None
    reason: str = ""