import pytest
from unittest.mock import patch, Mock, MagicMock, ANY
import builtins
import importlib
import os
from pathlib import Path
from fastapi.testclient import TestClient
import sys
import json
from http import HTTPStatus

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app/src')))

project_root = Path(__file__).parent.parent
fake_config_path = project_root / "example-conf.json"

mock_saved_configurations = {
    "identifier_field": "doc_id",
    "saved_fields": {
        "title": "text",
        "doc_id": "integer",
        "link": "text",
        "content": "text"
    },
    "field_for_llm": "content",
    "model_name": "Webiks_Hebrew_RAGbot_KolZchut_QA_Embedder_v1.0",
    "field_to_embed": "content"
}

atrifacts_folder_path = str(Path(__file__).parent.parent / "app" / "artifacts")


class MainSetup:
    @staticmethod
    def setup(mocker):
        with patch.dict(os.environ, {"DOCUMENT_DEFINITION_CONFIG": str(fake_config_path)}), \
                patch('webiks_hebrew_ragbot.config.MODEL_LOCATION', atrifacts_folder_path), \
                patch.object(builtins, "open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "{\"identifier_field\": \"doc_id\", \"saved_fields\": {\"title\": \"text\", \"doc_id\": \"integer\", \"link\": \"text\", \"content\": \"text\"}, \"field_for_llm\": \"content\", \"model_name\": \"Webiks_Hebrew_RAGbot_KolZchut_QA_Embedder_v1.0\", \"field_to_embed\": \"content\"}"
            mock_llm_client = mocker.patch('webiks_hebrew_ragbot.llm_client.LLMClient')
            mock_llm_client_instance = mock_llm_client.return_value
            mock_es_model_instance = mock_es_client()
            with patch('get_es_client.factory', return_value=mock_es_client()), \
                    patch('saved_config.Configs.get_config', return_value=mock_saved_configurations), \
                    patch('webiks_hebrew_ragbot.engine.engine_factory', return_value=MagicMock()):
                main_module = importlib.import_module("main")
                app = main_module.app
                engine = MagicMock()
                return app, engine, mock_es_model_instance, mock_llm_client_instance


def mock_es_client():
    """Create a mock Elasticsearch client"""
    mock_client = Mock()
    mock_client.indices.exists.return_value = True
    mock_client.indices.create = Mock()
    mock_client.index = Mock()
    mock_client.count.return_value = {'count': 1}
    return mock_client


@pytest.fixture(scope="function")
def mock_dependencies(mocker):
    app, engine, mock_es_model_instance, mock_llm_client_instance = MainSetup.setup(mocker)

    client = TestClient(app)

    return client, engine, mock_es_model_instance, mock_llm_client_instance


def test_healthcheck(mock_dependencies):
    """
    Health Check.
    Parameters
    ----------
    mock_dependencies

    Returns
    -------
    Status code, 200 if server is live.
    """
    client, engine, mock_es_model_instance, mock_llm_client_instance = mock_dependencies

    response = client.get("/health")

    assert response.status_code == HTTPStatus.OK


def test_get_conf(mock_dependencies):
    client, engine, mock_es_model_instance, mock_llm_client_instance = mock_dependencies

    response = client.get("/get_config")
    response_json = json.loads(response.content)
    assert response_json == mock_saved_configurations


def test_set_conf(mock_dependencies, mocker):
    client, engine, mock_es_model_instance, mock_llm_client_instance = mock_dependencies
    mock_set_config = mocker.patch("main.configs.set_config")

    new_config = {
        "model": "gpt-4o-2024-08-06",
        "num_of_pages": "3",
        "temperature": "0.5",
        "user_prompt": "זהו טסט, אם אתה רואה את זה בקוד סימן שה Mocker לא עובד :(",
        "system_prompt": "זהו טסט, אם אתה רואה את זה בקוד סימן שה Mocker לא עובד :(",
    }

    response = client.post("/set_config", json=new_config)

    assert response.status_code == HTTPStatus.OK
    mock_set_config.assert_called_once_with(new_config)


def test_search(mock_dependencies, mocker):
    client, engine, mock_es_model_instance, mock_llm_client_instance = mock_dependencies

    mocker.patch('uuid.uuid4', return_value='some-uuid-generated-by-uuid4')

    mock_config = {
        "version": "config_version",
        "num_of_pages": 3,
        "model": "some-model"
    }
    mock_get_config = mocker.patch('main.configs.get_config', return_value=mock_config)

    mocker.patch('main.code_version', 'code_version')

    mock_query = {
        "query": "שאלה לדוגמא",
        "asked_from": "test"
    }

    mock_engine_answer = (
        [
            {
                'last_update': '2025-02-11T17:15:55.092530',
                'doc_id': 1,
                'title': 'כותרת לדוגמה',
                'content': 'זהו תוכן לדוגמה בעברית',
                'link': 'https://example.com/sample',
                'content_Webiks_Hebrew_RAGbot_KolZchut_QA_Embedder_v1.0_vectors': [0.021454483, -0.016907433],
                '_len_': 6
            },
            {
                'last_update': '2025-02-11T17:15:55.092530',
                'doc_id': 2,
                'title': 'כותרת לדוגמה',
                'content': 'זהו תוכן לדוגמה בעברית מסםר 2',
                'link': 'https://example.com/sample',
                'content_Webiks_Hebrew_RAGbot_KolZchut_QA_Embedder_v1.0_vectors': [0.021454483, -0.016907433],
                '_len_': 6
            },
            {
                'last_update': '2025-02-11T17:15:55.092530',
                'doc_id': 3,
                'title': 'כותרת לדוגמה',
                'content': 'זהו תוכן לדוגמה בעברית מסםר 3',
                'link': 'https://example.com/sample',
                'content_Webiks_Hebrew_RAGbot_KolZchut_QA_Embedder_v1.0_vectors': [0.021454483, -0.016907433],
                '_len_': 6
            },
        ],
        "שאלה לדוגמא",
        {
            'llm_model': 'gpt-4o-2024-08-06',
            'llm_time': 11.0133,
            'retrieval_time': 2.2592,
            'tokens': 381,
            '_len_': 4
        }
    )

    mock_answer_query = mocker.patch('main.engine.answer_query', return_value=mock_engine_answer)

    mock_save_interaction = mocker.patch('main.interactions_model.save_interaction')

    expected_result = {
        "conversation_id": "some-uuid-generated-by-uuid4",
        "interaction_type": "search",
        "llm_result": "שאלה לדוגמא",
        "docs": [
            {
                "id": 1,
                "title": "כותרת לדוגמה",
                "link": "https://example.com/sample",
                "content": "זהו תוכן לדוגמה בעברית"
            },
            {
                "id": 2,
                "title": "כותרת לדוגמה",
                "link": "https://example.com/sample",
                "content": "זהו תוכן לדוגמה בעברית מסםר 2"
            },
            {
                "id": 3,
                "title": "כותרת לדוגמה",
                "link": "https://example.com/sample",
                "content": "זהו תוכן לדוגמה בעברית מסםר 3"
            }
        ],
        "config_version": "config_version",
        "code_version": "code_version",
        "question": "שאלה לדוגמא",
        "asked_from": "test",
        "metadata": {
            "llm_model": "gpt-4o-2024-08-06",
            "llm_time": 11.0133,
            "retrieval_time": 2.2592,
            "tokens": 381
        }
    }

    response = client.post("/search", json=mock_query)
    assert response.status_code == 200

    json_response = response.json()
    assert json_response == expected_result

    mock_get_config.assert_called_once()
    mock_answer_query.assert_called_once_with(
        "שאלה לדוגמא",
        3,
        "some-model"
    )
    mock_save_interaction.assert_called_once_with(expected_result)


def test_operate_docs(mock_dependencies, mocker):
    client, engine, mock_es_model_instance, mock_llm_client_instance = mock_dependencies

    mock_create_or_update = mocker.patch('main.create_or_update_doc', return_value=HTTPStatus.CREATED)

    create_request = {
        "operation": "create",
        "documents": [
            {
                "doc_id": 1,
                "title": "Sample Document",
                "link": "https://example.com/document",
                "content": "This is the content of the sample document."
            }
        ]
    }

    response = client.post("/operate_docs", json=create_request)
    assert response.status_code == HTTPStatus.CREATED

    mock_create_or_update.assert_called_once_with(
        ANY,
        False,
        ANY
    )
    actual_call_args = mock_create_or_update.call_args[0]
    actual_docs = actual_call_args[0]
    assert len(actual_docs) == 1
    assert actual_docs[0].doc_id == 1
    assert actual_docs[0].title == "Sample Document"
    assert actual_docs[0].link == "https://example.com/document"
    assert actual_docs[0].content == "This is the content of the sample document."

    mock_create_or_update.reset_mock()

    invalid_request = {
        "operation": "invalid",
        "documents": [
            {
                "doc_id": 1,
                "title": "Test Document",
                "link": "https://example.com/test",
                "content": "Test content"
            }
        ]
    }

    response = client.post("/operate_docs", json=invalid_request)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert not mock_create_or_update.called
    mismatched_request = {
        "operation": "create",
        "documents": [
            {
                "doc_id": 1,
                "title": "Document 1",
                "link": "https://example.com/doc1",
                "content": "Content 1"
            },
            {
                "doc_id": 2,
                "title": "Document 2",
                "link": "https://example.com/doc2",
                "content": "Content 2"
            }
        ]
    }

    response = client.post("/operate_docs", json=mismatched_request)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.content == b"All documents must have the same doc_id"
    assert not mock_create_or_update.called


def test_operate_docs_error(mock_dependencies, mocker):
    client, engine, mock_es_model_instance, mock_llm_client_instance = mock_dependencies
    mocker.patch(
        'main.create_or_update_doc',
        return_value=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    request = {
        "operation": "create",
        "documents": [
            {
                "doc_id": 1,
                "title": "Test Document",
                "link": "https://example.com/test",
                "content": "Test content"
            }
        ]
    }

    response = client.post("/operate_docs", json=request)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
