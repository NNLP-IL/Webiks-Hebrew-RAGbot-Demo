import logging
import os
from elasticsearch import Elasticsearch


class EsClient(Elasticsearch):
    """
   A custom Elasticsearch client that supports both managed and local Elasticsearch instances.
   Attributes:
   Methods:
       __getattribute__(name): Overrides the default method to modify index attributes and return custom attributes.
   """


    def __init__(self):
        """
        Initializes the EsClient instance.
        If the CLOUD_ES_ID environment variable is set, it connects to a managed Elasticsearch instance using the
        cloud ID and API key. Otherwise, it connects to a local Elasticsearch instance using the scheme, host, and port
        specified in the environment variables.
        """
        cloud_es_id = os.getenv("CLOUD_ES_ID")
        if cloud_es_id is not None:
            super().__init__(
                cloud_id=cloud_es_id,
                api_key=os.getenv("CLOUD_ES_API_KEY")
            )
            logging.debug("Connected to managed ES")
        else:
            logging.debug("Waiting for local ES...")
            super().__init__(os.getenv("DOCKER_ES_SCHEME") + "://" + os.getenv("DOCKER_ES_HOST") + ":" + os.getenv("DOCKER_ES_PORT"))
            logging.debug("Connected to local ES")


singleton_es_client = None


def factory():
    """
   Factory function to create and return a singleton instance of EsClient.
   Returns:
       EsClient: The singleton instance of EsClient.
   """
    global singleton_es_client
    if singleton_es_client is None:
        singleton_es_client = EsClient()
    return singleton_es_client
