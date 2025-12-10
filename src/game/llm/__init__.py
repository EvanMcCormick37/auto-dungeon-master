from src.game.llm.client import OllamaClient
from src.game.llm.gm_oracle import GMOracle
from src.game.llm.narrator_oracle import NarratorOracle

llm_client = OllamaClient()
gm_oracle = GMOracle(llm_client)
narrator_oracle = NarratorOracle(llm_client)

__all__ = [
    'llm_client',
    'gm_oracle',
    'narrator_oracle',
    'OllamaClient',
    'GMOracle',
    'NarratorOracle'
]