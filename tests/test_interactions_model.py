import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import os
import sys
import importlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app/src')))


class IMSetup:
    @staticmethod
    def setup():
        interaction_model_import = importlib.import_module("interactions_model")
        return (
            interaction_model_import.InteractionsModel,
            interaction_model_import.factory,
            interaction_model_import.get_current_index_name
        )


InteractionsModel, factory, get_current_index_name = IMSetup.setup()


@pytest.fixture
def mock_es_client():
    """Create a mock Elasticsearch client"""
    mock_client = Mock()
    mock_client.indices.exists.return_value = True
    mock_client.indices.create = Mock()
    mock_client.index = Mock()
    mock_client.count.return_value = {'count': 1}
    return mock_client


@pytest.fixture
def interactions_model(mock_es_client):
    """Create an InteractionsModel instance with mocked ES client"""
    with patch('threading.Thread'):
        model = InteractionsModel(mock_es_client)
        global singleton
        singleton = None
        mock_es_client.indices.exists.reset_mock()
        mock_es_client.indices.create.reset_mock()
        return model


class TestStartPoll:
    def test_start_poll_creates_thread(self, interactions_model):
        """Test that start_poll creates and starts a thread"""
        with patch('threading.Thread') as mock_thread:
            interactions_model.poll_queue = False
            interactions_model.start_poll()

            mock_thread.assert_called_once_with(target=interactions_model.handle_queue)
            mock_thread.return_value.start.assert_called_once()
            assert interactions_model.poll_queue == True

    def test_start_poll_sets_thread_attribute(self, interactions_model):
        """Test that start_poll sets the thread attribute"""
        with patch('threading.Thread') as mock_thread:
            interactions_model.poll_queue = False
            interactions_model.start_poll()
            assert interactions_model.t == mock_thread.return_value


class TestHandleQueue:
    @patch('time.sleep')
    def test_handle_queue_empty(self, mock_sleep, interactions_model):
        """Test handle_queue behavior with empty queue"""
        interactions_model.poll_queue = True

        def stop_after_one_sleep(*args):
            interactions_model.poll_queue = False

        mock_sleep.side_effect = stop_after_one_sleep
        interactions_model.handle_queue()

        mock_sleep.assert_called_once_with(1)
        interactions_model.es_client.index.assert_not_called()

    def test_handle_queue_processes_question(self, interactions_model):
        """Test handle_queue processes a question interaction"""
        test_interaction = {
            'interaction_type': 'question',
            'content': 'test question'
        }
        interactions_model.queue.append(test_interaction)
        interactions_model.poll_queue = True

        def stop_after_one_sleep(*args):
            interactions_model.poll_queue = False

        with patch('time.sleep', side_effect=stop_after_one_sleep):
            interactions_model.handle_queue()

        interactions_model.es_client.index.assert_called_once()
        assert len(interactions_model.queue) == 0


class TestCreateIndex:
    def test_create_index_new(self, interactions_model):
        """Test create_index when index doesn't exist"""
        index_name = get_current_index_name()
        interactions_model.es_client.indices.exists.return_value = False

        with patch('logging.debug') as mock_debug:
            interactions_model.create_index()

        interactions_model.es_client.indices.exists.assert_called_once_with(index=index_name)
        interactions_model.es_client.indices.create.assert_called_once_with(index=index_name)
        mock_debug.assert_called_once()

    def test_create_index_exists(self, interactions_model):
        """Test create_index when index already exists"""
        index_name = get_current_index_name()
        interactions_model.es_client.indices.exists.return_value = True

        with patch('logging.debug') as mock_debug:
            interactions_model.create_index()

        interactions_model.es_client.indices.exists.assert_called_once_with(index=index_name)
        interactions_model.es_client.indices.create.assert_not_called()
        mock_debug.assert_called_once()


class TestDoSaveInteraction:
    def test_do_save_interaction_adds_timestamp(self, interactions_model):
        """Test do_save_interaction adds timestamp to interaction"""
        test_interaction = {'type': 'test'}

        interactions_model.es_client.indices.exists.return_value = True
        interactions_model.do_save_interaction(test_interaction)

        call_args = interactions_model.es_client.index.call_args[1]
        assert 'timestamp' in call_args['body']
        assert isinstance(datetime.fromisoformat(call_args['body']['timestamp']), datetime)


class TestSaveInteraction:
    def test_save_interaction_starts_polling(self, interactions_model):
        """Test save_interaction starts polling if not already started"""
        interactions_model.poll_queue = False
        test_interaction = {'interaction_type': 'test'}

        with patch('threading.Thread') as mock_thread:
            interactions_model.save_interaction(test_interaction)

            mock_thread.assert_called_once()
            assert interactions_model.poll_queue == True

    def test_save_interaction_adds_to_queue(self, interactions_model):
        """Test save_interaction adds interaction to queue"""
        test_interaction = {'interaction_type': 'test'}
        initial_queue_length = len(interactions_model.queue)

        interactions_model.save_interaction(test_interaction)

        assert len(interactions_model.queue) == initial_queue_length + 1
        assert interactions_model.queue[-1] == test_interaction

    def test_save_interaction_with_polling_active(self, interactions_model):
        """Test save_interaction when polling is already active"""
        interactions_model.poll_queue = True
        test_interaction = {'interaction_type': 'test'}

        with patch('threading.Thread') as mock_thread:
            interactions_model.save_interaction(test_interaction)

            mock_thread.assert_not_called()
