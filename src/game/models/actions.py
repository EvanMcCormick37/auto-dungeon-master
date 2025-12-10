from typing import List, TypedDict
from pydantic import BaseModel
from enum import Enum

# ========================================================================================
# ACTIONS: These are formal intentions to alter state, and are stored in a separate Action queue.
# ========================================================================================
class Intent:                                   # Anything that wants to happen, described in natural language. The DM translates it into an ActionPlan which resolves mechanically.
    owner_id: str
    text: str
class StateChange(BaseModel):                   # An actual change to state
    """A discrete change to game state"""
    target_id: str             # Entity/item being changed
    attribute: str             # What's changing ("hp", "position", "inventory")
    operation: str             # "set", "add", "remove", "append"
    value: any                 # The new value or delta
class ActionType(Enum):
    ATTACK = "attack"           # Combat attack
    CAST = "cast"               # Cast a spell
    SKILL = "skill"             # Skill check (stealth, perception, etc.)
    INTERACT = "interact"       # Interact with object/environment
    MOVE = "move"               # Movement
    SAY = "say"                 # Social interaction
    OTHER = "other"             # Free actions (drop item, etc.)
class RollType(Enum):
    """Types of dice rolls"""
    ATTACK = "attack_roll"                  # d20 + modifiers vs AC
    DAMAGE = "damage_roll"                  # Weapon/spell damage dice
    SAVE = "save_roll"                      # Saving throw (d20 vs DC)
    CHECK = "check_roll"                    # Ability/skill check (d20 vs DC)
# ============================================================
# ROLL STRUCTURES
# ============================================================
class RollOutcome(Enum):
    # CRITICAL_SUCCESS = "critical_success"
    SUCCESS = "success"
    FAILURE = "failure"
    # CRITICAL_FAILURE = "critical_failure"
class RollOutcomes(TypedDict):
    SUCCESS: List[StateChange]
    FAILURE: List[StateChange]
class RollSpec(BaseModel):
    made_by: str                            # Who is making the roll
    type: RollType                          # What type of roll is being made
    dice: str                               # Dice formula, e.g. 3d4+2, 1d20+INT
    threshold: int                          # The target value the diceroll must match or beat
    advantage: bool                         # Advantage?
    disadvantage: bool                      # Disadvantage?
    outcomes: RollOutcomes
    explanation: str                        # Why the roll is being made (for LLM)
class RollResult(BaseModel):
    """Result of rolling a RollSpec"""
    spec: RollSpec                          # Spec which generated this result
    result: int
    outcome: RollOutcome
    state_changes: List[StateChange]
class ResolutionStatus(Enum):
    """Current state of an action's resolution"""
    PENDING = "pending"                     # Waiting to be processed
    AWAITING_ROLL = "awaiting_roll"         # Need a dice roll
    AWAITING_DECISION = "awaiting_decision" # Need DM to interpret outcome
    RESOLVED = "resolved"                   # Complete
    CANCELLED = "cancelled"                 # Invalidated by something
# ============================================================
# ACTION & RESOLUTION
# ============================================================
class ActionPlan(BaseModel):
    """
    The DM's interpretation of what an action requires.
    This is the CONTRACT between LLM interpretation and mechanical execution.
    """
    action_type: ActionType
    actor_id: str                           # Who's doing this
    target_ids: List[str] = []              # Who/what is affected
    
    # The sequence of rolls needed (in order)
    required_rolls: List[RollSpec] = []
    
    # Conditional follow-up rolls based on previous roll success
    # Key: index of the roll that must succeed, Value: rolls to add if it does
    conditional_rolls: dict[int, List[RollSpec]] = {}
    
    # Potential reactions this might trigger
    potential_reactions: List[str] = []     # Entity IDs that might react
    
    # DM's notes for narration context
    narrative_context: str = ""

class Resolution(BaseModel):
    """
    The evolving state of resolving a single action.
    This tracks progress through the ActionPlan.
    """
    action_plan: ActionPlan
    status: ResolutionStatus = ResolutionStatus.PENDING
    
    # Track roll results as they happen
    roll_results: List[RollResult] = []
    current_roll_index: int = 0
    
    # Accumulated state changes to apply when resolved
    pending_state_changes: List[StateChange] = []
    
    # Narration fragments collected during resolution
    narration_fragments: List[str] = []
    
    # Reactions that got triggered
    triggered_reactions: List['Action'] = []

class Action(BaseModel):
    """A complete action waiting to be resolved"""
    id: str
    owner_id: str                    # Who initiated this
    intent_text: str                 # Original natural language
    priority: int = 0                # Higher = process first (for reactions)
    
    # Set after DM interprets the intent
    plan: ActionPlan | None
    resolution: Resolution | None
