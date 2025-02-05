from typing import List, Dict
import pandas as pd
from http import HTTPStatus
import logging

def convert_kolzchut_paragraphs_corpus_to_json(path: str) -> List[Dict]:
    """
    Reads a JSON file and converts it into a list of dictionaries,
    while removing the 'license' field if it exists.

    Args:
        path (str): Path to the JSON file.

    Returns:
        List[Dict]: List of dictionaries without the 'license' field.
    """
    df = pd.read_json(path)
    if 'license' in df.columns:
        df = df.drop(columns=['license'])

    return df.to_dict(orient='records')


def create_or_update_doc(documents, delete_existing,update_docs_function):
    try:
        documents_dicts = [doc.model_dump() for doc in documents]

        update_docs_function(documents_dicts, delete_existing)
        return HTTPStatus.CREATED
    except Exception as e:
        logging.error(f"Error during create or update until: {str(e)}")
        return HTTPStatus.BAD_REQUEST
