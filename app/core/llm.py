"""
Single factory for the local LLM client.

All components obtain the model through `get_llm()` so that the model name and
decoding parameters can be switched at run time (e.g. by the evaluation harness)
and are identical for JUDICATA and for every baseline.
"""
from functools import lru_cache
from typing import Optional

from langchain_community.chat_models import ChatOllama

from app.core.config import settings


@lru_cache(maxsize=16)
def _client(model: str, base_url: str, temperature: float, num_predict: int, seed: Optional[int]):
    kwargs = dict(base_url=base_url, model=model, temperature=temperature, num_predict=num_predict)
    if seed is not None:
        try:
            return ChatOllama(seed=seed, **kwargs)
        except Exception:  # older langchain-community without `seed`
            pass
    return ChatOllama(**kwargs)


def get_llm(temperature: Optional[float] = None, num_predict: Optional[int] = None):
    return _client(
        settings.ollama_model,
        settings.ollama_base_url,
        settings.ollama_temperature if temperature is None else temperature,
        settings.ollama_max_tokens if num_predict is None else num_predict,
        getattr(settings, "llm_seed", None),
    )


async def generate(prompt: str, temperature: Optional[float] = None, num_predict: Optional[int] = None) -> str:
    resp = await get_llm(temperature, num_predict).ainvoke(prompt)
    return (resp.content if hasattr(resp, "content") else str(resp)).strip()
