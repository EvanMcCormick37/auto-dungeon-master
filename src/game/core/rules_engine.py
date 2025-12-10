import re
import random
from typing import Dict
from src.game.models import RollResult, RollOutcome, RollSpec

# ============================================================
# RULES ENGINE
# ============================================================

class RulesEngine:
    """
    Central logic for resolving game mechanics, dice rolls, 
    and calculating outcomes.
    """

    def calculate_modifier(self, attribute_value: int) -> int:
        """
        Calculates standard D&D style modifier: (val - 10) // 2
        e.g., 10 -> 0, 12 -> +1, 8 -> -1
        """
        return (attribute_value - 10) // 2

    def roll_dice(self, formula: str, context: Dict[str, int] = None) -> int:
        """
        Parses a dice string (e.g., '1d20+5', '2d6', '1d20+STR') and rolls it.
        
        Args:
            formula: The dice string.
            context: A dictionary mapping attribute names (STR, DEX) to their *modifiers*.
                     Used if the formula contains non-numeric modifiers.
        """
        # Regex to match XdY followed optionally by +Z or -Z (where Z is number or string)
        # Group 1: Num Dice, Group 2: Die Sides, Group 3: Modifier (optional)
        pattern = r"(\d+)d(\d+)([+-]\w+)?"
        match = re.fullmatch(pattern, formula.strip())

        if not match:
            raise ValueError(f"Invalid dice formula format: {formula}")

        num_dice = int(match.group(1))
        die_sides = int(match.group(2))
        modifier_str = match.group(3)

        # 1. Roll the dice
        total = 0
        for _ in range(num_dice):
            total += random.randint(1, die_sides)

        # 2. Add modifier if it exists
        if modifier_str:
            sign = 1 if modifier_str[0] == '+' else -1
            value_part = modifier_str[1:]

            if value_part.isdigit():
                # Static number (e.g., +5)
                mod_value = int(value_part)
            else:
                # Attribute reference (e.g., +STR)
                if context is None:
                    raise ValueError(f"Formula requires context for attribute '{value_part}' but none provided.")
                
                # Check if key exists (case-insensitive handling recommended elsewhere, assuming strict here)
                key = value_part.upper() 
                if key not in context:
                    # Fallback or error? For now, 0 if missing to prevent crash, but logging would be good.
                    mod_value = 0 
                else:
                    mod_value = context[key]
            
            total += (sign * mod_value)

        return total

    def roll_with_advantage(self, formula: str, context: Dict[str, int] = None) -> int:
        """Rolls twice and takes the higher result."""
        r1 = self.roll_dice(formula, context)
        r2 = self.roll_dice(formula, context)
        return max(r1, r2)

    def roll_with_disadvantage(self, formula: str, context: Dict[str, int] = None) -> int:
        """Rolls twice and takes the lower result."""
        r1 = self.roll_dice(formula, context)
        r2 = self.roll_dice(formula, context)
        return min(r1, r2)

    def execute_roll(self, spec: RollSpec) -> RollResult:
        """
        Executes a full roll specification:
        1. Determines roll method (normal, adv, disadv)
        2. Calculates result
        3. Compares to threshold
        4. Returns structured result with state changes
        """
        
        # Handle Advantage/Disadvantage cancellation
        has_adv = spec.advantage and not spec.disadvantage
        has_dis = spec.disadvantage and not spec.advantage

        if has_adv:
            total = self.roll_with_advantage(spec.dice, spec.context)
        elif has_dis:
            total = self.roll_with_disadvantage(spec.dice, spec.context)
        else:
            # Standard roll (or if both adv and dis exist, they cancel out)
            total = self.roll_dice(spec.dice, spec.context)

        # Determine Outcome
        # Note: In standard 5e, meeting the DC is a success.
        if total >= spec.threshold:
            outcome = RollOutcome.SUCCESS
            changes = spec.outcomes.get("SUCCESS", [])
        else:
            outcome = RollOutcome.FAILURE
            changes = spec.outcomes.get("FAILURE", [])

        return RollResult(
            spec=spec,
            result=total,
            outcome=outcome,
            state_changes=changes
        )