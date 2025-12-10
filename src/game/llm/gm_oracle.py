from src.game.models import Entity, Action, ActionType, ActionPlan, GameState, RollType, RollSpec, StateChange
from src.game.llm.prompts import GMPrompts
from src.game.llm.exceptions import JSONExtractionError, ActionPlanParseError, ValidationFailedError
from src.game.llm.client import OllamaClient
import json
import re
import logging
from pydantic import ValidationError
from enum import Enum


logger = logging.getLogger(__name__)


class GMOracle:
    """
    LLM interface for the Dungeon Master.
    Handles interpretation of intents into structured ActionPlans.
    """
    
    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client


    def interpret_action(
        self, 
        intent_text: str, 
        context: GameState
    ) -> ActionPlan | None:
        """
        Ask the DM to interpret a player's intent.
        Returns a structured ActionPlan or None if action is invalid.
        """
        prompt = GMPrompts.INTERPRETATION_PROMPT.format(context=context, intent=intent_text)
        
        # Request structured output from LLM
        response = self.llm.generate(
            prompt,
            response_format=ActionPlan  # Pydantic model for structured output
        )
        
        return self._parse_action_plan(response)


    def explain_invalid_action(self, intent: str, context: GameState) -> str:
        """Generate a DM explanation for why an action can't be done"""
        prompt = GMPrompts.EXPLAIN_INVALID_ACTION.format(intent=intent,summary=context.summary())
        
        return self.llm.generate(prompt)


    def describe_reaction(
        self,
        triggering_action: Action,
        entity: Entity
    ) -> str:
        """Generate the intent text for an entity's reaction"""
        prompt = GMPrompts.DESCRIBE_REACTION.format(entity=entity,triggering_action=triggering_action)
        
        return self.llm.generate(prompt)


    def _extract_json_from_response(self, response: str) -> dict:
        """
        Extract JSON from an LLM response that may contain surrounding text.
        
        Handles common LLM output patterns:
        - Pure JSON
        - JSON wrapped in markdown code blocks
        - JSON with preamble/postamble text
        """
        response = response.strip()
        
        # Try 1: Direct JSON parse (cleanest case)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try 2: Extract from markdown code blocks
        # Handles ```json ... ``` or ``` ... ```
        code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, response, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        
        # Try 3: Find JSON object by matching braces
        # Look for outermost { ... }
        brace_depth = 0
        start_idx = None
        
        for i, char in enumerate(response):
            if char == '{':
                if brace_depth == 0:
                    start_idx = i
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
                if brace_depth == 0 and start_idx is not None:
                    try:
                        return json.loads(response[start_idx:i + 1])
                    except json.JSONDecodeError:
                        start_idx = None
                        continue
        
        raise JSONExtractionError(
            f"Could not extract valid JSON from response. "
            f"Response preview: {response[:200]}..."
        )


    def _normalize_enum_value(self, value: str, enum_class: type[Enum]) -> str:
        """
        Normalize enum string values to match expected format.
        Handles case insensitivity and common variations.
        """
        value_lower = value.lower().strip()
        
        # Check direct match first
        for member in enum_class:
            if member.value == value_lower:
                return member.value
            if member.name.lower() == value_lower:
                return member.value
        
        # Handle common variations
        # e.g., "ATTACK_ROLL" -> "attack_roll", "attack" -> "attack_roll" for RollType
        if enum_class == RollType:
            roll_type_aliases = {
                "attack": "attack_roll",
                "damage": "damage_roll",
                "save": "save_roll",
                "saving": "save_roll",
                "saving_throw": "save_roll",
                "check": "check_roll",
                "ability_check": "check_roll",
                "skill_check": "check_roll",
            }
            if value_lower in roll_type_aliases:
                return roll_type_aliases[value_lower]
        
        return value_lower


    def _parse_state_change(self, data: dict) -> StateChange:
        """Parse a single StateChange from dict data."""
        return StateChange(
            target_id=str(data.get("target_id", "")),
            attribute=str(data.get("attribute", "")),
            operation=str(data.get("operation", "set")),
            value=data.get("value")
        )


    def _parse_roll_outcomes(self, data: dict) -> dict[str, list[StateChange]]:
        """Parse roll outcomes dictionary."""
        outcomes = {}
        
        for key in ["SUCCESS", "FAILURE", "success", "failure"]:
            normalized_key = key.upper()
            if key in data:
                changes = data[key]
                if isinstance(changes, list):
                    outcomes[normalized_key] = [
                        self._parse_state_change(sc) if isinstance(sc, dict) else sc
                        for sc in changes
                    ]
                else:
                    outcomes[normalized_key] = []
        
        # Ensure both keys exist
        if "SUCCESS" not in outcomes:
            outcomes["SUCCESS"] = []
        if "FAILURE" not in outcomes:
            outcomes["FAILURE"] = []
        
        return outcomes


    def _parse_roll_spec(self, data: dict) -> RollSpec:
        """Parse a single RollSpec from dict data."""
        roll_type_raw = data.get("type", "check_roll")
        roll_type_normalized = self._normalize_enum_value(roll_type_raw, RollType)
        
        return RollSpec(
            made_by=str(data.get("made_by", "")),
            type=RollType(roll_type_normalized),
            dice=str(data.get("dice", "1d20")),
            threshold=int(data.get("threshold", 10)),
            advantage=bool(data.get("advantage", False)),
            disadvantage=bool(data.get("disadvantage", False)),
            outcomes=self._parse_roll_outcomes(data.get("outcomes", {})),
            explanation=str(data.get("explanation", ""))
        )


    def _parse_conditional_rolls(self, data: dict) -> dict[int, list[RollSpec]]:
        """
        Parse conditional rolls dictionary.
        Handles both string and int keys (JSON only has string keys).
        """
        result = {}
        
        for key, rolls in data.items():
            try:
                int_key = int(key)
            except (ValueError, TypeError):
                logger.warning(f"Invalid conditional roll key: {key}, skipping")
                continue
            
            if isinstance(rolls, list):
                result[int_key] = [
                    self._parse_roll_spec(r) if isinstance(r, dict) else r
                    for r in rolls
                ]
        
        return result


    def _parse_action_plan(self, llm_response: str) -> ActionPlan:
        """
        Parse an LLM response into an ActionPlan object.
        
        Args:
            llm_response: Raw string response from the LLM containing JSON-formatted
                        action plan data. May include surrounding text or markdown.
        
        Returns:
            ActionPlan: Validated ActionPlan object ready for game engine processing.
        
        Raises:
            JSONExtractionError: If no valid JSON could be extracted from response.
            ValidationFailedError: If extracted JSON doesn't conform to ActionPlan schema.
            ActionPlanParseError: For other parsing failures.
        
        Example:
            >>> response = '''
            ... Here's the action plan:
            ... ```json
            ... {
            ...     "action_type": "attack",
            ...     "actor_id": "player_1",
            ...     "target_ids": ["goblin_1"],
            ...     "required_rolls": [{
            ...         "made_by": "player_1",
            ...         "type": "attack_roll",
            ...         "dice": "1d20+5",
            ...         "threshold": 13,
            ...         "advantage": false,
            ...         "disadvantage": false,
            ...         "outcomes": {"SUCCESS": [], "FAILURE": []},
            ...         "explanation": "Melee attack against goblin"
            ...     }],
            ...     "narrative_context": "You swing your sword at the goblin."
            ... }
            ... ```
            ... '''
            >>> plan = parse_action_plan(response)
            >>> plan.action_type
            <ActionType.ATTACK: 'attack'>
        """
        # Step 1: Extract JSON from response
        try:
            data = self._extract_json_from_response(llm_response)
        except JSONExtractionError:
            raise
        except Exception as e:
            raise JSONExtractionError(f"Unexpected error extracting JSON: {e}")
        
        # Step 2: Normalize and parse fields
        try:
            # Parse action_type
            action_type_raw = data.get("action_type", "other")
            action_type_normalized = self._normalize_enum_value(action_type_raw, ActionType)
            
            # Parse required_rolls
            required_rolls_raw = data.get("required_rolls", [])
            required_rolls = [
                self._parse_roll_spec(r) if isinstance(r, dict) else r
                for r in required_rolls_raw
            ]
            
            # Parse conditional_rolls
            conditional_rolls = self._parse_conditional_rolls(
                data.get("conditional_rolls", {})
            )
            
            # Build ActionPlan
            action_plan = ActionPlan(
                action_type=ActionType(action_type_normalized),
                actor_id=str(data.get("actor_id", "")),
                target_ids=[str(t) for t in data.get("target_ids", [])],
                required_rolls=required_rolls,
                conditional_rolls=conditional_rolls,
                potential_reactions=[str(r) for r in data.get("potential_reactions", [])],
                narrative_context=str(data.get("narrative_context", ""))
            )
            
            return action_plan
            
        except ValidationError as e:
            raise ValidationFailedError(f"ActionPlan validation failed: {e}")
        except Exception as e:
            raise ActionPlanParseError(f"Failed to parse ActionPlan: {e}")