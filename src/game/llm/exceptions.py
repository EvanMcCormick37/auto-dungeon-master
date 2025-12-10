# ============================================================
# PARSING EXCEPTIONS
# ============================================================

class ActionPlanParseError(Exception):
    """Base exception for ActionPlan parsing errors"""
    pass


class JSONExtractionError(ActionPlanParseError):
    """Could not extract JSON from LLM response"""
    pass


class ValidationFailedError(ActionPlanParseError):
    """JSON was extracted but failed Pydantic validation"""
    pass