import sys
import os
import pytest
from unittest.mock import Mock, patch
from elasticsearch import Elasticsearch
import builtins
import importlib
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app/src')))

project_root = Path(__file__).parent.parent
fake_config_path = project_root / "example-conf.json"


class UpdaterServiceSetup:
    @staticmethod
    def setup():
        with patch.dict(os.environ, {"DOCUMENT_DEFINITION_CONFIG": str(fake_config_path)}), \
                patch.object(builtins, "open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "{\"identifier_field\": \"doc_id\", \"saved_fields\": {\"title\": \"text\", \"doc_id\": \"integer\", \"link\": \"text\", \"content\": \"text\"}, \"field_for_llm\": \"content\", \"model_name\": \"Webiks_Hebrew_RAGbot_KolZchut_QA_Embedder_v1.0\", \"field_to_embed\": \"content\"}"
            updater_service_module = importlib.import_module("updater_service")
            return (
                importlib.import_module("webiks_hebrew_ragbot.engine").Engine,
                updater_service_module.UpdaterService,
                updater_service_module.updater_factory,
                updater_service_module.handle_update_exception
            )


Engine, UpdaterService, updater_factory, handle_update_exception = UpdaterServiceSetup.setup()


@pytest.fixture
def mock_es_client():
    client = Mock(spec=Elasticsearch)

    client.indices = Mock()

    client.indices.exists.return_value = False
    client.indices.create.return_value = {"acknowledged": True}
    client.index.return_value = {"result": "created"}

    return client


@pytest.fixture
def mock_engine():
    """Fixture for mocked Engine"""
    return Mock(spec=Engine)


@pytest.fixture
def updater_service(mock_es_client, mock_engine):
    """Fixture for UpdaterService instance"""
    return UpdaterService(mock_es_client, mock_engine)


class TestUpdaterService:
    def test_init_create_new_index(self, mock_es_client, mock_engine):
        """Test initialization when index doesn't exist"""
        mock_es_client.indices.exists.return_value = False
        service = UpdaterService(mock_es_client, mock_engine)

        mock_es_client.indices.create.assert_called_once()
        mock_es_client.index.assert_called_once_with(
            index="updates",
            id="1",
            body={
                "doc_ids_queue": [],
                "doc_ids_failed": [],
                "lock": ""
            }
        )

    def test_init_existing_index(self, mock_es_client, mock_engine):
        """Test initialization when index already exists"""
        mock_es_client.indices.exists.return_value = True
        service = UpdaterService(mock_es_client, mock_engine)

        mock_es_client.indices.create.assert_not_called()
        mock_es_client.index.assert_not_called()

    def test_add_to_queue(self, updater_service):
        """Test adding document to queue"""
        doc_id = "test_doc"
        updater_service.add_to_queue(doc_id)

        updater_service.es_client.update.assert_called_once()
        call_args = updater_service.es_client.update.call_args[1]
        assert call_args["index"] == "updates"
        assert call_args["id"] == "1"
        assert "script" in call_args
        assert call_args["script"]["params"]["doc_id"] == doc_id

    def test_remove_doc(self, updater_service):
        """Test removing document"""
        doc_id = "test_doc"
        updater_service.es_client.delete_by_query.return_value = {"deleted": 1}

        result = updater_service.remove_doc(doc_id)

        assert result is True
        updater_service.es_client.delete_by_query.assert_called_once()

    def test_remove_doc_not_found(self, updater_service):
        """Test removing non-existent document"""
        doc_id = "test_doc"
        updater_service.es_client.delete_by_query.return_value = {"deleted": 0}

        result = updater_service.remove_doc(doc_id)

        assert result is False

    def test_remove_nth_doc(self, updater_service):
        """Test removing nth occurrence of document"""
        doc_id = "test_doc"
        n = 1
        mock_hits = {
            "hits": {
                "hits": [
                    {"_id": "1"},
                    {"_id": "2"},
                    {"_id": "3"}
                ]
            }
        }
        updater_service.es_client.search.return_value = mock_hits
        updater_service.es_client.delete_by_query.return_value = {"deleted": 1}

        result = updater_service.remove_nth_doc(doc_id, n)

        assert result is True
        updater_service.es_client.delete_by_query.assert_called_once()

    def test_remove_nth_doc_out_of_range(self, updater_service):
        """Test removing nth occurrence when n is out of range"""
        doc_id = "test_doc"
        n = 5
        mock_hits = {
            "hits": {
                "hits": [
                    {"_id": "1"},
                    {"_id": "2"}
                ]
            }
        }
        updater_service.es_client.search.return_value = mock_hits

        result = updater_service.remove_nth_doc(doc_id, n)

        assert result is False
        updater_service.es_client.delete_by_query.assert_not_called()

    def test_find_doc(self, updater_service):
        """Test finding document"""
        doc_id = "test_doc"
        mock_hits = {
            "hits": {
                "hits": [{"_id": "1", "source": {}}]
            }
        }
        updater_service.es_client.search.return_value = mock_hits

        result = updater_service.find_doc(doc_id)

        assert result == mock_hits["hits"]["hits"]
        updater_service.es_client.search.assert_called_once()

    def test_find_doc_not_found(self, updater_service):
        """Test finding non-existent document"""
        doc_id = "test_doc"
        mock_hits = {"hits": {"hits": []}}
        updater_service.es_client.search.return_value = mock_hits

        result = updater_service.find_doc(doc_id)

        assert result is None

    def test_copy_to_indices(self, updater_service):
        """Test copying documents to indices"""
        documents = [{"id": "1"}, {"id": "2"}]
        updater_service.delete_indices = Mock()

        with patch("updater_service.document_definition.identifier", "test_identifier"):
            updater_service.copy_to_indices(documents)

        updater_service.delete_indices.assert_called_once_with("test_identifier")
        updater_service.engine.create_paragraphs.assert_called_once_with(documents)

    def test_delete_indices(self, updater_service):
        """Test deleting indices"""
        indices = {"index1": {}, "index2": {}}
        updater_service.es_client.indices.get.return_value = indices
        updater_service.es_client.indices.delete.return_value = {"acknowledged": True}

        result = updater_service.delete_indices("test")

        assert result is True
        assert updater_service.es_client.indices.delete.call_count == len(indices)

    def test_delete_indices_no_indices(self, updater_service):
        """Test deleting indices when none exist"""
        updater_service.es_client.indices.get.return_value = {}

        result = updater_service.delete_indices("test")

        assert result is False
        updater_service.es_client.indices.delete.assert_not_called()


class TestUpdaterFactory:
    def test_updater_factory_singleton(self, mock_es_client, mock_engine):
        """Test updater factory creates singleton instance"""
        service1 = updater_factory(mock_es_client, mock_engine)
        service2 = updater_factory(mock_es_client, mock_engine)

        assert service1 is service2


def test_handle_update_exception():
    """Test exception handling function"""
    test_exception = Exception("Test error")
    doc_id = "test_doc"

    result = handle_update_exception(test_exception, doc_id)

    assert result == {
        "error": "Test error",
        "page_id": doc_id
    }
