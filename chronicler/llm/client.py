from __future__ import annotations
import time
import litellm
from chronicler.config.settings import Config


def get_model_for_task(task: str, config: Config) -> str:
    return {
        "entry_classifier":   config.models.workhorse,
        "session_summarizer": config.models.workhorse,
        "map_updater":        config.models.workhorse,
        "handoff_generator":  config.models.premium,
    }[task]


class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        if config.groq.api_key:
            import os
            os.environ["GROQ_API_KEY"] = config.groq.api_key

    def complete(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> tuple[str, int, int]:
        """Returns (response_text, tokens_used, processing_ms)."""
        model = get_model_for_task(task, self.config)
        start = time.time()
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return text, tokens, elapsed_ms
