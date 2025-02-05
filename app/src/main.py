import config  # keep it first
from typing import List
import logging
import uuid
import uvicorn
from http import HTTPStatus
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from utils import convert_kolzchut_paragraphs_corpus_to_json, create_or_update_doc
from pydantic import BaseModel
from webiks_hebrew_ragbot.engine import engine_factory
import get_es_client
import interactions_model
import saved_config
from gpt_client import llms_client_factory
from logger import setup_logging
from updater_service import updater_factory

setup_logging()
es_client = get_es_client.factory()
app = FastAPI()
configs = saved_config.factory(es_client)
gpt_client = llms_client_factory(configs)
engine = engine_factory(gpt_client, es_client)
updater_service = updater_factory(es_client, engine)
interactions_model = interactions_model.factory(es_client)

origins = ['http://localhost:5000']

code_version = config.CODE_VERSION

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchQuery(BaseModel):
    query: str
    asked_from: str


class Document(BaseModel):
    """
    Represents a document with necessary attributes.

    Attributes:
        doc_id (int): Unique identifier for the document.
        title (str): The title of the document.
        link (str): URL or reference link for the document.
        content (str): The main content of the document.
    """
    doc_id: int
    title: str
    link: str
    content: str


class DocumentRequest(BaseModel):
    """
    Represents a request payload for creating or updating documents.

    Attributes:
        operation (str): The type of operation - "create" or "update".
        documents (List[Document]): A list of documents to be created or updated.
    """
    operation: str
    documents: List[Document]

@app.get("/health")
async def health():
    """
    Health check endpoint.
    Logs access to the health check endpoint and returns a status code of 200.
    Returns:
        int: HTTP status code 200.
    """
    logging.info("Health check endpoint accessed")
    return HTTPStatus.OK


@app.get("/get_config")
async def get_conf():
    """
    Retrieve the current configuration.
    Returns:
        dict: Current configuration settings.
    """
    return configs.get_config()


@app.post("/set_config")
async def set_conf(params: dict):
    """
    Set a new configuration.
    Args:
        params (dict): Dictionary containing configuration parameters.
    Returns:
        int: HTTP status code 200.
    """
    data = {k: v for k, v in {
        "model": params.get("model"),
        "num_of_pages": params.get("num_of_pages"),
        "temperature": params.get("temperature"),
        "user_prompt": params.get("user_prompt"),
        "system_prompt": params.get("system_prompt"),
    }.items() if v is not None}
    configs.set_config(data)
    return HTTPStatus.OK


@app.post("/search")
async def search(params: SearchQuery):
    """
    Perform a search query.
    Args:
        params (SearchQuery): Parameters for the search query.
    Returns:
        dict: Result of the search operation.
    """
    try:
        conversation_id = str(uuid.uuid4())
        current_config = configs.get_config()
        answer = (engine.answer_query(params.query, int(current_config["num_of_pages"]), current_config["model"]))
        llm_ans = answer[1]
        config_version = current_config["version"]
        docs = [
            {
                "id": item["doc_id"],
                "title": item["title"],
                "link": item["link"],
                "content": item["content"],
            } for item in answer[0]
        ]
        result = {
            "conversation_id": conversation_id,
            "interaction_type": "search",
            "llm_result": llm_ans,
            "docs": docs,
            "config_version": config_version,
            "code_version": code_version,
            "question": params.query,
            "asked_from": params.asked_from,
            "metadata": {
                "llm_model": answer[2]["llm_model"],
                "llm_time": answer[2]["llm_time"],
                "retrieval_time": answer[2]["retrieval_time"],
                "tokens": answer[2]["tokens"]
            }
        }
        interactions_model.save_interaction(result)

        logging.debug(f"Search performed with query: {params.query}")
        logging.debug(f"Generated conversation_id: {conversation_id}")

        return result
    except Exception as e:
        logging.error(f"Error during search: {e}")

@app.get("/initialize_elastic_from_json")
async def initialize_elastic_from_json():
    """
    Deletes all the indices and creates them from the json
    Returns
    -------
    Status code
    """
    try:
        documents = convert_kolzchut_paragraphs_corpus_to_json(config.PATH_TO_ES_INITIAL_VALUES)
        updater_service.copy_to_indices(documents)
        return Response(status_code=HTTPStatus.CREATED)

    except Exception as e:
        logging.error(f"Error during initialize: {str(e)}")
        status_code = getattr(e, 'status_code', HTTPStatus.INTERNAL_SERVER_ERROR)
        return Response(status_code=status_code)


@app.post("/operate_docs")
async def operate_docs(request: DocumentRequest):
    """
      Handles document operations by creating or updating documents.

      Args:
          request (DocumentRequest): The request containing the operation type
                                     ("create" or "update") and a list of documents.

      Returns:
          Response:
              - 200 OK if the operation is successful.
              - 422 Unprocessable Entity if the operation type is invalid or
                if documents have mismatched `doc_id`s.
              - Other status codes as returned by `create_or_update_doc`.

      Behavior:
          - If `operation` is `"create"`, the function adds new documents.
          - If `operation` is `"update"`, it updates existing documents.
          - If an invalid `operation` is provided, the function returns HTTP 422.
          - If all documents do not have the same `doc_id`, it returns HTTP 422.
          - The status code returned by `create_or_update_doc` is used as the response.
    """
    operation = request.operation.lower()
    if operation not in {"create", "update"}:
        return Response(status_code=HTTPStatus.UNPROCESSABLE_ENTITY)

    doc_ids = {doc.doc_id for doc in request.documents}

    if len(doc_ids) > 1:
        return Response(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content="All documents must have the same doc_id")

    delete_existing = operation == "update"
    return Response(status_code=create_or_update_doc(request.documents, delete_existing, engine.update_docs))


@app.delete("/delete_doc")
async def delete_doc(doc_id: str, obj_id: str):
    """
    Delete document by its ID.

    Args:
        doc_id (str): Document ID to delete.
        obj_id (str): The index of the document to delete.

    Returns:
        Response: HTTP response with status code indicating success or failure.
    """
    try:
        try:
            n = int(obj_id) - 1  # Coming as BASE 1 - setting to BASE 0
        except ValueError:
            return Response(status_code=HTTPStatus.BAD_REQUEST, content="Invalid id: must be an integer.")

        is_deleted = updater_service.remove_nth_doc(doc_id, n)
        if is_deleted:
            return Response(status_code=HTTPStatus.OK)
        else:
            return Response(status_code=HTTPStatus.NOT_FOUND)
    except Exception as e:
        logging.error(f"Error during deletion for doc_id {doc_id}: {str(e)}")
        status_code = getattr(e, 'status_code', HTTPStatus.INTERNAL_SERVER_ERROR)
        return Response(status_code=status_code)


@app.get("/get_doc")
async def get_doc(doc_id: str):
    """
    Retrieve a document by its ID.
    Args:
        doc_id (str): Document ID to retrieve.
    Returns:
        dict: The document details if found.
    """
    try:
        return updater_service.find_doc(doc_id)
    except Exception as e:
        logging.error(f"Error during retrieval for doc_id {doc_id}: {str(e)}")
        status_code = getattr(e, 'status_code', HTTPStatus.INTERNAL_SERVER_ERROR)
        return Response(status_code=status_code)


app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=int(config.PORT))
