import logging
from datetime import datetime, timedelta
from config import SAVED_CONFIGURATIONS, CONFIG_CACHE_PERIOD_SECS


system_prompt_seed = """
 אתה צ'אטבוט שתוכנן לענות על שאלות בנושא זכויות על סמך טקסטים שאתה מקבל. מטרתך העיקרית היא לספק מידע אמין, מדויק ונכון המבוסס אך ורק על הטקסט שניתן לך. אתה לא תומך בשיחה מתמשכת

כדי לענות על השאלה, פעל לפי ההוראות הבאות בקפידה:

חוקים חשובים שיש לפעול לפיהם:
אל תוסיף מידע, פרשנויות או דוגמאות שאינן מופיעות בטקסט המקורי.
"""
seed_config = {
    "model": "gpt-4o-2024-08-06",
    "num_of_pages": "3",
    "temperature": "0.5",
    "user_prompt": "ענה על השאלות בהתבסס על המידע שקיבלת.",
    "system_prompt": system_prompt_seed,
    "version": 1
}




class Configs:
    """
       A class to manage configurations stored in Elasticsearch.
       Attributes:
           current_config (dict): The current configuration.
           last_updated (datetime): The last time the configuration was updated.
           es_client (Elasticsearch): The Elasticsearch client instance.
       Methods:
           __init__(es_client):
               Initializes the Configs instance with the given Elasticsearch client.
           create_index(index_name=SAVED_CONFIGURATIONS):
               Creates an index in Elasticsearch if it does not exist.
           get_config():
               Retrieves the latest configuration from Elasticsearch.
           set_config(config=None):
               Sets a new configuration in Elasticsearch.
           organize_config(config: dict[str, str or int]):
               Organizes and updates the configuration with a new version and timestamp.
       """
    current_config=None
    last_updated=None


    def __init__(self, es_client):
        """
         Initializes the Configs instance with the given Elasticsearch client.
         Args:
             es_client (Elasticsearch): The Elasticsearch client instance.
         """
        self.es_client = es_client
        self.create_index(SAVED_CONFIGURATIONS)
        self.current_config = self.get_config()
        self.last_updated = datetime.now()


    def create_index(self, index_name=SAVED_CONFIGURATIONS):
        """
       Creates an index in Elasticsearch if it does not exist.
       Args:
           index_name (str): The name of the index to create. Defaults to SAVED_CONFIGURATIONS.
       """
        if not self.es_client.indices.exists(index=index_name):
            self.es_client.indices.create(index=index_name)
            logging.debug("Index created")
        else:
            logging.debug("Index exists")


    def get_config(self):
        """
           Retrieves the latest configuration from Elasticsearch.
           Returns:
               dict: The latest configuration.
           """
        if self.es_client.count(index=SAVED_CONFIGURATIONS)["count"] == 0:
            self.es_client.index(
                index=SAVED_CONFIGURATIONS,
                body=seed_config
            )
            return seed_config
        if self.current_config and self.last_updated:
            time_diff = timedelta(seconds=(datetime.now().__sub__(self.last_updated)).total_seconds())
            if time_diff.total_seconds() < CONFIG_CACHE_PERIOD_SECS:
                return self.current_config

        last_config = self.es_client.search(
            index=SAVED_CONFIGURATIONS,
            sort=[
                {"version": {"order": "desc"}}
            ]
        )["hits"]["hits"][0]["_source"]
        if last_config is None:
            return None
        self.current_config = last_config
        self.last_updated = datetime.now()
        return last_config


    def set_config(self, config=None):
        """
        Sets a new configuration in Elasticsearch.
        Args:
            config (dict, optional): The new configuration to set. Defaults to None.
        """
        organized_config = self.organize_config(config)
        self.es_client.index(
            index=SAVED_CONFIGURATIONS,
            body=organized_config
        )
        self.current_config = organized_config
        self.last_updated = datetime.now()


    def organize_config(self, config: dict[str, str or int]):
        """
        Organizes and updates the configuration with a new version and timestamp.
        Args:
            config (dict): The configuration to organize.
        Returns:
            dict: The organized configuration.
        """
        existing_config = self.get_config()
        new_conf = {**existing_config, **config, "version": int(existing_config.get("version", '0')) + 1, "timestamp": datetime.now().isoformat()}
        for key in seed_config.keys():
            if key not in new_conf:
                new_conf[key] = seed_config[key]
        return new_conf


#global value
singleton = None


def factory(es_client=None):
    global singleton
    if singleton is None:
        singleton = Configs(es_client)
    return singleton
