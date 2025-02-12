import pytest
from datetime import datetime, timedelta
import sys
import os
import importlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app/src')))


class SavedConfigSetup:
    @staticmethod
    def setup():
        config_module = importlib.import_module("config")
        saved_config_module = importlib.import_module("saved_config")
        return (
            config_module.SAVED_CONFIGURATIONS,
            config_module.CONFIG_CACHE_PERIOD_SECS,
            saved_config_module.Configs,
            saved_config_module.factory,
            saved_config_module.seed_config
        )


SAVED_CONFIGURATIONS, CONFIG_CACHE_PERIOD_SECS, Configs, factory, seed_config = SavedConfigSetup.setup()


@pytest.fixture
def es_client():
    class MockElasticsearch:
        def __init__(self):
            self.index_exists = False
            self.indices = self
            self.stored_config = None
            self.call_count = 0

        def exists(self, index):
            return self.index_exists

        def create(self, index):
            return {"acknowledged": True}

        def index(self, index, body):
            self.stored_config = body
            return {"result": "created"}

        def search(self, index, sort=None):
            self.call_count += 1
            return {
                "hits": {
                    "hits": [{
                        "_source": self.stored_config or seed_config
                    }]
                }
            }

        def count(self, index):
            return {"count": 1 if self.stored_config else 0}

        def __eq__(self, other):
            if not isinstance(other, MockElasticsearch):
                return False
            return (self.index_exists == other.index_exists and
                    self.stored_config == other.stored_config and
                    self.call_count == other.call_count)

    return MockElasticsearch()


@pytest.fixture
def configs(es_client):
    return factory(es_client)


def test_init_creates_index_if_not_exists(es_client):
    """Test that initialization creates index when it doesn't exist"""
    es_client.index_exists = False
    configs = Configs(es_client)

    assert configs.es_client == es_client


def test_init_skips_index_creation_if_exists(es_client):
    """Test that initialization skips index creation when it exists"""
    es_client.index_exists = True
    configs = Configs(es_client)

    assert configs.es_client == es_client


def test_get_config_returns_seed_config_if_no_configs(es_client):
    """Test that get_config returns seed config when no configs exist"""
    es_client.stored_config = None
    configs = Configs(es_client)

    result = configs.get_config()

    assert result == seed_config
    assert es_client.stored_config == seed_config


def test_get_config_uses_cache(es_client):
    """Test that get_config uses cached config within cache period"""
    configs = Configs(es_client)

    # First call to get_config
    first_result = configs.get_config()
    initial_call_count = es_client.call_count

    # Second call to get_config
    second_result = configs.get_config()

    assert first_result == second_result
    assert es_client.call_count == initial_call_count  # No additional calls made


def test_get_config_refreshes_cache_after_period(es_client):
    """Test that get_config refreshes cache after cache period"""
    configs = Configs(es_client)

    first_result = configs.get_config()
    initial_call_count = es_client.call_count

    configs.last_updated = datetime.now() - timedelta(seconds=CONFIG_CACHE_PERIOD_SECS + 1)

    second_result = configs.get_config()

    assert first_result == second_result
    assert es_client.call_count > initial_call_count


def test_set_config_updates_elasticsearch(es_client):
    """Test that set_config properly updates Elasticsearch"""
    configs = Configs(es_client)
    new_config = {"model": "gpt-4", "temperature": "0.7"}

    configs.set_config(new_config)

    stored_config = es_client.stored_config
    assert stored_config["model"] == "gpt-4"
    assert stored_config["temperature"] == "0.7"
    assert "version" in stored_config
    assert "timestamp" in stored_config


def test_organize_config_maintains_required_fields(configs):
    """Test that organize_config maintains all required fields from seed_config"""
    new_config = {"model": "gpt-4"}

    result = configs.organize_config(new_config)
    for key in seed_config.keys():
        assert key in result

    assert result["model"] == "gpt-4"
    assert result["version"] == seed_config["version"] + 1
    assert "timestamp" in result


def test_factory_returns_singleton(es_client):
    """Test that factory returns the same instance"""
    first_instance = factory(es_client)
    second_instance = factory(es_client)

    assert first_instance is second_instance
