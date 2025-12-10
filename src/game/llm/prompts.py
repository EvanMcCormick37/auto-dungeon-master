from enum import Enum

class GMPrompts(str, Enum):
    EXPLAIN_INVALID_ACTION = """The player tried to: "{intent}"
But this isn't possible because of the current situation:
{summary}

Respond in-character as a Dungeon Master explaining why they can't do this.
Be helpful and suggest alternatives if appropriate.
Keep it brief (2-3 sentences)."""
    DESCRIBE_REACTION = """An entity is reacting to the player's action.

ENTITY: {entity.name} ({entity.type})
- Disposition: {entity.disposition}
- Current HP: {entity.hp}/{entity.max_hp}

PLAYER'S ACTION: {triggering_action.intent_text}
OUTCOME: {"Success" if triggering_action.resolution.roll_results[-1].success else "Failure"}

What does {entity.name} do in response? Describe their reaction as a simple action intent.
Example: "The goblin snarls and swings its rusty scimitar at the player"

Respond with just the action description, nothing else."""
    INTERPRETATION_PROMPT = """You are the Dungeon Master. Interpret the player's intended action
and determine what dice rolls are required to resolve it.

CURRENT SITUATION:
- Location: {context.location.description}
- Player: {context.player.name}, {context.player.hp}/{context.player.max_hp} HP
- Nearby entities: {[e.name for e in context.entities]}
- Player's equipment: {context.player.equipped}

PLAYER'S ACTION: "{intent}"

Determine:
1. What type of action is this? (ATTACK, CAST, SKILL, INTERACT, MOVE, DIALOGUE, FREE)
2. Who/what is the target?
3. What rolls are needed? For each roll, specify:
   - Roll type (ATTACK, DAMAGE, SAVE, CHECK)
   - Dice formula (e.g., "1d20+5")
   - Target DC or AC
   - Any advantage/disadvantage
4. Are there conditional rolls? (e.g., "if attack hits, roll damage")
5. What entities might react to this action?
6. What state changes occur on success vs failure?

If this action is impossible or doesn't make sense, respond with INVALID and explain why.

Respond in the following JSON format:
{{
    "valid": true/false,
    "invalid_reason": "..." (only if invalid),
    "action_type": "...",
    "actor_id": "player",
    "target_ids": [...],
    "required_rolls": [
        {{
            "roll_type": "ATTACK",
            "dice": "1d20+5",
            "target_ac": 13,
            "reason": "Sword attack against Goblin"
        }}
    ],
    "conditional_rolls": {{
        "0": [  // If roll at index 0 succeeds
            {{
                "roll_type": "DAMAGE",
                "dice": "1d8+3",
                "reason": "Longsword damage"
            }}
        ]
    }},
    "potential_reactions": ["goblin_1"],  // Entity IDs
    "on_success": [
        {{"target_id": "goblin_1", "attribute": "hp", "operation": "add", "value": -8}}
    ],
    "on_failure": [],
    "narrative_context": "Player swings their longsword at the goblin"
}}
"""