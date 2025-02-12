import pytest
from unittest.mock import Mock, patch
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types import CompletionUsage
from datetime import datetime
import sys
import os
import builtins
import importlib
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app/src')))

project_root = Path(__file__).parent.parent
fake_config_path = project_root / "example-conf.json"


class GPTClientSetup:
    @staticmethod
    def setup():
        with patch.dict(os.environ, {"DOCUMENT_DEFINITION_CONFIG": str(fake_config_path)}), \
                patch.object(builtins, "open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "{\"identifier_field\": \"doc_id\", \"saved_fields\": {\"title\": \"text\", \"doc_id\": \"integer\", \"link\": \"text\", \"content\": \"text\"}, \"field_for_llm\": \"content\", \"model_name\": \"Webiks_Hebrew_RAGbot_KolZchut_QA_Embedder_v1.0\", \"field_to_embed\": \"content\"}"
            gpt_client_module = importlib.import_module("gpt_client")
            return (
                importlib.import_module("saved_config").Configs,
                importlib.import_module("webiks_hebrew_ragbot.llm_client").LLMClient,
                gpt_client_module.GPTClient,
                gpt_client_module.get_mock_answer,
                gpt_client_module.llms_client_factory
            )


Configs, LLMClient, GPTClient, get_mock_answer, llms_client_factory = GPTClientSetup.setup()


def create_mock_chat_completion(content: str = "Test response") -> ChatCompletion:
    """
    Creates a mock ChatCompletion response with the proper Choice structure
    """
    mock_message = ChatCompletionMessage(
        content=content,
        role="assistant",
        function_call=None,
        tool_calls=None
    )
    mock_choice = {
        "finish_reason": "stop",
        "index": 0,
        "message": mock_message,
        "logprobs": None
    }

    mock_usage = CompletionUsage(
        completion_tokens=10,
        prompt_tokens=20,
        total_tokens=30
    )
    return ChatCompletion(
        id="test_id",
        choices=[mock_choice],
        created=int(datetime.now().timestamp()),
        model="gpt-3.5-turbo",
        object="chat.completion",
        usage=mock_usage,
        system_fingerprint=None
    )


@pytest.fixture
def mock_openai_client():
    class MockOpenAI:
        def __init__(self):
            self.chat = Mock()
            self.chat.completions = Mock()
            mock_response = create_mock_chat_completion("Test response")
            self.chat.completions.create = Mock(return_value=mock_response)

    return MockOpenAI()


@pytest.fixture
def config_class():
    mock_config = {
        "model": "gpt-3.5-turbo",
        "temperature": "0.7",
        "system_prompt": "You are a helpful assistant",
        "user_prompt": "Please answer the following question"
    }
    mock_configs = Mock(spec=Configs)
    mock_configs.get_config.return_value = mock_config
    return mock_configs


@pytest.fixture
def gpt_client(mock_openai_client, config_class):
    with patch('os.getenv') as mock_getenv:
        mock_getenv.return_value = "test_api_key"
        client = GPTClient(config_class)
        client.oai_client = mock_openai_client
        client.field_for_answer = "content"
        return client


def test_gpt_client_initialization(gpt_client):
    """Test GPTClient initialization"""
    assert isinstance(gpt_client, LLMClient)
    assert gpt_client.is_mock_client == False
    assert hasattr(gpt_client, 'oai_client')
    assert hasattr(gpt_client, 'configs_class')


def test_create_body(gpt_client):
    """Test create_body method"""
    query = "מה השעה?"
    top_k_docs = [
        {"content": "Document 1 content"},
        {"content": "Document 2 content"}
    ]

    body = gpt_client.create_body(query, top_k_docs)

    assert "שאלה: מה השעה?" in body
    assert "מסמך 1: Document 1 content" in body
    assert "מסמך 2: Document 2 content" in body


def test_answer_normal_mode(gpt_client):
    """Test answer method in normal (non-mock) mode"""
    query = "test question"
    top_k_docs = [{"content": "test document"}]

    answer, elapsed, tokens = gpt_client.answer(query, top_k_docs)

    assert answer == "Test response"
    assert isinstance(elapsed, float)
    assert tokens == 10
    assert gpt_client.oai_client.chat.completions.create.called


def test_answer_mock_mode():
    """Test answer method in mock mode"""
    with patch('os.getenv') as mock_getenv:
        def mock_getenv_func(key, default=None):
            if key == 'IS_MOCK_GPT_CLIENT':
                return "true"
            return "test_api_key"

        mock_getenv.side_effect = mock_getenv_func

        client = GPTClient(Mock(spec=Configs))
        query = "test question"
        top_k_docs = [{"content": "test document"}]

        answer, elapsed, tokens = client.answer(query, top_k_docs)

        assert "Mock answer with docs" in answer
        assert elapsed == 0.0
        assert tokens == 0


def test_get_mock_answer():
    """Test get_mock_answer function"""
    top_k_docs = [{"content": "test document"}]
    answer, elapsed, tokens = get_mock_answer(top_k_docs)

    assert isinstance(answer, str)
    assert "Mock answer with docs" in answer
    assert elapsed == 0.0
    assert tokens == 0


def test_llms_client_factory_singleton(config_class):
    """Test that llms_client_factory maintains singleton pattern"""
    with patch('os.getenv') as mock_getenv:
        mock_getenv.return_value = "test_api_key"
        global llms_client
        llms_client = None
        client1 = llms_client_factory(config_class)
        client2 = llms_client_factory(config_class)

        assert client1 is client2
        assert isinstance(client1, GPTClient)


@pytest.mark.parametrize("top_k_docs,expected_contains", [
    ([{"content": "doc1"}], "doc1"),
    ([{"content": "doc1"}, {"content": "doc2"}], "doc2"),
    ([], "")
])
def test_create_body_with_different_docs(gpt_client, top_k_docs, expected_contains):
    """Test create_body with different numbers of documents"""
    query = "test"
    body = gpt_client.create_body(query, top_k_docs)

    if expected_contains:
        assert expected_contains in body
    assert "שאלה: test" in body
