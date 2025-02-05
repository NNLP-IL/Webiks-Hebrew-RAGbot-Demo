import logging
import threading
import time
from datetime import datetime, timezone
from config import CONVERSATIONS_INDEX


def get_current_index_name():
    """
      Returns the current index name based on the week number.
      Returns:
          str: The current index name.
      """
    week_num = datetime.now(timezone.utc).isocalendar()[1]
    return f"{CONVERSATIONS_INDEX}_{week_num}"


class InteractionsModel:
    """
       A class to manage interactions and save them to Elasticsearch.
       Every interaction (question or rating) is saved to an index named after the current week number.
       The class uses a queue ("poll queue") to store interactions.
       Attributes:
           queue (list): A list to store interactions.
           t (threading.Thread): A thread for polling the queue.
           poll_queue (bool): A flag to control the polling of the queue.
           es_client (Elasticsearch): An Elasticsearch client instance.
       Methods:
           __init__(es_client): Initializes the InteractionsModel instance.
           start_poll(): Starts the polling thread.
           handle_queue(): Handles the interactions queue.
           create_index(): Creates an Elasticsearch index if it does not exist.
           do_save_interaction(interaction): Saves an interaction to Elasticsearch.
           save_interaction(interaction): Adds an interaction to the queue and starts polling if not already started.
       """
    queue = []
    t = None
    poll_queue = False


    def __init__(self, es_client):
        """
        Initializes the InteractionsModel instance.
        Args:
            es_client (Elasticsearch): An Elasticsearch client instance.
        """
        self.es_client = es_client
        self.create_index()
        self.start_poll()


    def start_poll(self):
        """
          Starts the polling thread.
          """
        self.poll_queue = True
        self.t = threading.Thread(target=self.handle_queue)
        self.t.start()


    def handle_queue(self):
        """
       Handles the interactions queue.
       """
        logging.info("Handling queue")
        while True and self.poll_queue:
            if len(self.queue) == 0:
                time.sleep(1)
                continue
            interaction = self.queue.pop(0)
            if interaction['interaction_type'] == 'rating':
                exists = self.es_client.count(index=get_current_index_name(),
                                              body={"query": {"match": {"conversation_id":
                                                                            interaction['conversation_id']}}})
                if exists['count'] == 0:
                    continue
            self.do_save_interaction(interaction)


    def create_index(self):
        """
          Creates an Elasticsearch index if it does not exist.
          """
        index_name = get_current_index_name()
        if not self.es_client.indices.exists(index=index_name):
            self.es_client.indices.create(index=index_name)
            logging.debug("Index created ${index_name}")
        else:
            logging.debug("Index exists")


    def do_save_interaction(self, interaction):
        """
       Saves an interaction to Elasticsearch.

       Args:
           interaction (dict): The interaction to save.
       """

        interaction['timestamp'] = datetime.now(timezone.utc).isoformat()

        if not self.es_client.indices.exists(index=get_current_index_name()):
            self.create_index()
        logging.debug("Saving interaction", interaction)
        self.es_client.index(index=get_current_index_name(), body=interaction)


    def save_interaction(self, interaction):
        """
          Adds an interaction to the queue and starts polling if not already started.
          Args:
              interaction (dict): The interaction to save.
          """
        logging.debug("saving interaction in type", interaction['interaction_type'])
        if not self.poll_queue:
            self.start_poll()
        self.queue.append(interaction)


singleton = None


def factory(es_client=None):
    global singleton
    if singleton is None:
        singleton = InteractionsModel(es_client)
    return singleton
