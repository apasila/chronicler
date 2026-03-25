import json
import pytest
from unittest.mock import patch
from chronicler.llm.classifier import EntryClassifier
from chronicler.config.settings import Config, ModelsConfig, GroqConfig
from chronicler.core.differ import DiffResult

MOCK_LLM_RESPONSE = {
    "change_type": "feature",
    "subtype": "api_change",
    "confidence": 0.92,
    "summary": "Added POST login endpoint with JWT generation",
    "impact": "high",
    "affected_functions": ["login", "generate_token"],
    "affected_components": None,
    "tags": ["auth", "api", "jwt"],
}

@pytest.fixture
def mock_config():
    config = Config()
    config.models = ModelsConfig(tier="cloud",
                                  workhorse="groq/llama-3.3-70b-versatile",
                                  premium="groq/llama-3.3-70b-versatile")
    config.groq = GroqConfig(api_key="test-key")
    return config

@pytest.fixture
def sample_diff():
    return DiffResult(
        file_path="/project/api/auth.py", relative_path="api/auth.py",
        diff_text="+def login(u, p):\n+    return generate_token(u)",
        lines_added=2, lines_removed=0, is_new_file=False,
        is_deleted=False, language="python",
    )

def test_classify_returns_change_info(mock_config, sample_diff):
    classifier = EntryClassifier(config=mock_config)
    with patch("chronicler.llm.client.LLMClient.complete") as mock_complete:
        mock_complete.return_value = (json.dumps(MOCK_LLM_RESPONSE), 850, 420)
        change_info, llm_info = classifier.classify(
            diff=sample_diff, project_name="test",
            framework="fastapi", recent_context=[],
        )
    assert change_info.type == "feature"
    assert change_info.subtype == "api_change"
    assert change_info.confidence == 0.92
    assert llm_info.tokens_used == 850

def test_classify_falls_back_on_invalid_type(mock_config, sample_diff):
    bad = dict(MOCK_LLM_RESPONSE, change_type="totally_invalid")
    classifier = EntryClassifier(config=mock_config)
    with patch("chronicler.llm.client.LLMClient.complete") as mock_complete:
        mock_complete.return_value = (json.dumps(bad), 800, 400)
        change_info, _ = classifier.classify(
            diff=sample_diff, project_name="test",
            framework=None, recent_context=[],
        )
    assert change_info.type == "experiment"  # fallback
