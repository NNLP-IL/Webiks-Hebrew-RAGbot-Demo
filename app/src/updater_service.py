from typing import List, Dict
import logging
import os
from webiks_hebrew_ragbot.engine import Engine
from elasticsearch import Elasticsearch
from webiks_hebrew_ragbot.document import document_definition_factory
# Constants
index_name = os.getenv("UPDATES_INDEX", "updates")
UPDATES_DOC_ID = "1"  # Unique document ID to store update metadata
document_definition =document_definition_factory()


class UpdaterService:
    """
    A service for managing updates to documents stored in Elasticsearch.
    This includes adding documents to a queue for processing, removing documents,
    finding documents, and handling independent or immediate updates.

    Attributes:
        es_client (Elasticsearch): The Elasticsearch client instance.
        engine (Engine): The engine used to update document data.
    """
    def __init__(self, es_client: Elasticsearch, engine: Engine):
        """
        Initializes the UpdaterService.

        Args:
            es_client (Elasticsearch): Elasticsearch client for document management.
            engine (Engine): Engine for parsing and updating document data.

        Creates the index if it doesn't exist and initializes it with default metadata.
        """
        self.es_client = es_client
        self.engine = engine
        self.docs_index = os.getenv("ES_EMBEDDING_INDEX", "embedded_fusion")
        if not self.es_client.indices.exists(index=index_name):
            self.es_client.indices.create(index=index_name)
            self.es_client.index(
                index=index_name,
                id=UPDATES_DOC_ID,
                body={
                    "doc_ids_queue": [],
                    "doc_ids_failed": [],
                    "lock": ""
                }
            )
            logging.info(f"Index created {index_name}")
        else:
            logging.info("Index exists")


    def add_to_queue(self, doc_id: str):
        """
        Adds a document ID to the update queue if not already present.

        Args:
            doc_id (str): The document ID to be queued.
        """
        logging.info(f"Update requested for page {doc_id}")
        self.es_client.update(index=index_name, id=UPDATES_DOC_ID, script={
            "source": "if(ctx._source.doc_ids_queue.contains(params.doc_id)) { return } ctx._source.doc_ids_queue.add(params.doc_id)",
            "lang": "painless",
            "params": {"doc_id": doc_id}
        })


    def remove_doc(self, doc_id: str) -> bool:
        """
        Removes a document with the specified ID from Elasticsearch.

        Args:
            doc_id (str): The document ID to remove.

        Returns:
            bool: True if the document was deleted, False otherwise.
        """
        docs_index = os.getenv("ES_EMBEDDING_INDEX", "embedded_fusion")
        query = {
            "query": {
                "match": {
                    "doc_id": doc_id
                }
            }
        }

        es_response = self.es_client.delete_by_query(index=f"{docs_index}*", body=query)
        deleted_count = es_response.get('deleted', 0)
        return deleted_count > 0


    def remove_nth_doc(self, doc_id: str, n: int) -> bool:
        """
        Removes the nth (zero-based index) document with the specified ID from Elasticsearch using a query.

        Args:
            doc_id (str): The document ID to remove.
            n (int): The zero-based occurrence index of the document to delete.

        Returns:
            bool: True if the document was deleted, False otherwise.
        """
        query = {
            "query": {
                "match": {
                    "doc_id": doc_id
                }
            },
            "size": n + 1,
        }

        es_response = self.es_client.search(index=f"{self.docs_index}*", body=query)
        hits = es_response.get("hits", {}).get("hits", [])

        if len(hits) <= n:
            return False

        delete_query = {
            "query": {
                "match": {
                    "_id": hits[n]["_id"]
                }
            }
        }
        delete_response = self.es_client.delete_by_query(index=f"{self.docs_index}*", body=delete_query)

        deleted_count = delete_response.get("deleted", 0)
        return deleted_count > 0


    def find_doc(self, doc_id: str):
        """
        Finds a document with the specified ID in Elasticsearch.

        Args:
            doc_id (str): The document ID to search for.

        Returns:
            list or None: A list of matched documents or None if no documents were found.
        """
        docs_index = os.getenv("ES_EMBEDDING_INDEX", "embedded_fusion")
        query = {
            "_source": {
                "excludes": ["*vector*"]
            },
            "query": {
                "match": {
                    document_definition.identifier: doc_id
                }
            }
        }

        es_response = self.es_client.search(index=f"{docs_index}*", body=query)
        hits = es_response.get('hits', {}).get('hits', [])
        return hits if hits else None


    def copy_to_indices(self, documents:List[Dict]):
        """
        This function receives a list of documents to insert to elastic. deletes the existing indices, and create new ones
        Parameters
        ----------
        documents (List of dicts): contains the documents you are going to insert the elastic
        """
        self.delete_indices(document_definition.identifier)
        self.engine.create_paragraphs(documents)


    def delete_indices(self, indices_name: str):
        """
        Deletes all the indices which starting with the parameter received
        Parameters
        ----------
        indices_name(str): the start of the indices you are applying to remove name
        Returns
        -------
        Boolean value if passed or failed during the deletion.
        """
        try:
            indices_to_delete = self.es_client.indices.get(index=f'{self.docs_index}*')  # Corrected
            if not indices_to_delete:
                logging.info(f"No indices found that start with {indices_name}.")
                return False

            for index in indices_to_delete:
                try:
                    delete_response = self.es_client.indices.delete(index=index)
                    if delete_response.get('acknowledged', False):
                        logging.info(f"Successfully deleted index: {index}")
                    else:
                        logging.error(f"Failed to delete index: {index}. Response: {delete_response}")
                except Exception as e:
                    logging.error(f"Error deleting index {index}: {e}")

            return True

        except Exception as e:
            logging.error(f"Error while fetching indices or deleting: {e}")
            return False


def handle_update_exception( e: Exception, doc_id: str) -> dict:
    """
    Handles exceptions during document updates.

    Args:
        e (Exception): The exception raised.
        doc_id (str): The document ID associated with the error.

    Returns:
        dict: An error object containing details about the exception.
    """
    err_obj = {
        "error": str(e),
        "page_id": doc_id
    }
    logging.error(f"Error during update: {err_obj}")
    return err_obj


# Global instance for the UpdaterService
updater_service = None


def updater_factory(es_client: Elasticsearch, engine: Engine) -> UpdaterService:
    """
    Factory function to create a singleton instance of UpdaterService.

    Args:
        es_client (Elasticsearch): Elasticsearch client for document management.
        engine (Engine): Engine for parsing and updating document data.

    Returns:
        UpdaterService: The singleton instance of UpdaterService.
    """
    global updater_service
    if updater_service is None:
        updater_service = UpdaterService(es_client, engine)
    return updater_service
