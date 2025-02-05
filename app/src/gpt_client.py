import os
import time
import re
from bs4 import BeautifulSoup
from webiks_hebrew_ragbot.llm_client import LLMClient
from openai import OpenAI
from saved_config import Configs


def parse_hebrew_text(characters):
    """
      Parses Hebrew text, separating words and punctuation.
      Args:
          characters (str): The input text to parse.
      Returns:
          list: A list of parsed words and punctuation.
      """
    parsed_text = []
    temp_word = []

    for char in characters:
        if char.isalpha() or char == ' ':
            temp_word.append(char)
        else:
            if temp_word:
                # Join the collected characters to form a word
                parsed_text.append(''.join(temp_word).strip())
                temp_word = []
            # Add the punctuation or special character separately
            if char.strip():
                parsed_text.append(char)

    # Add any remaining word
    if temp_word:
        parsed_text.append(''.join(temp_word).strip())

    # Join the parsed text into a single string and split by specific punctuation or spaces
    result = ''.join(parsed_text).split(', ')

    return result

def clean_text(input_text):
    """
   Cleans the input text to include only Hebrew characters, numbers, and specified punctuation.
   Args:
       input_text (str): The input text to clean.
   Returns:
       str: The cleaned text.
   """
    """Clean the text to include only Hebrew characters, numbers, and specified punctuation."""
    soup = BeautifulSoup(input_text, 'html.parser')
    text = soup.get_text(separator='\n')

    cleaned_text = re.sub(
        r'[^\u0590-\u05FFa-zA-Z0-9\s.,!?"\'():;״׳;@:\-()_=+%/\n]+',
        '',
        ' '.join(text.split())
    )

    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return cleaned_text


class GPTClient(LLMClient):
    """
   A client for interacting with the OpenAI GPT model.
   Attributes:
       oai_client (OpenAI): The OpenAI client instance.
       configs_class (Configs): The configuration class instance.
       answer (function): The function to get the GPT answer.
       is_mock_client (bool): Flag indicating if the client is a mock client.
   Methods:
       create_body(query, top_k_docs): Creates the request body for the GPT model.
       filter_docs(html_string): Strips headers from the HTML string based on banned headers and returns the filtered HTML.
       get_gpt_answer(query, top_k_docs): Gets the GPT answer for the given query and documents.
       get_mock_answer(query, top_k_docs): Gets a mock answer for the given query and documents.
   """
    def __init__(self, config_class: Configs):
        """
       Initializes the GPTClient instance.
       Args:
           config_class (Configs): The configuration class instance.
       """
        super().__init__()
        self.oai_client = OpenAI(api_key=os.getenv('OAI_API_KEY'))
        self.configs_class = config_class
        self.is_mock_client = os.getenv('IS_MOCK_GPT_CLIENT', "false").lower() == "true"


    def create_body(self, query, top_k_docs):
        """
         Creates the request body for the GPT model.
         Args:
             query (str): The query string.
             top_k_docs (list): The list of top documents.
         Returns:
             str: The request body.
         """
        identifier = "מסמך"
        body = {'שאלה': query} | {f'{identifier} {i + 1}': top_k_docs[i][self.field_for_answer] for i in range(len(top_k_docs))}
        body = '\n'.join([f'{k}: {d}' for k, d in body.items()])
        return body


    def answer(self, query, top_k_docs):
        """
         Gets the GPT answer for the given query and documents.
         Args:
             query (str): The query string.
             top_k_docs (list): The list of top documents.
         Returns:
             tuple: The GPT answer, elapsed time, and token usage.
         """
        if self.is_mock_client:
            return get_mock_answer(top_k_docs)
        before_gpt = time.perf_counter()
        current_config = self.configs_class.get_config()
        response = self.oai_client.chat.completions.create(
            model=current_config["model"],
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": current_config["system_prompt"]
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": current_config['user_prompt'] + "\n" + self.create_body(query, top_k_docs)
                        }
                    ]
                }
            ],
            temperature=float(current_config["temperature"]),
            max_tokens=512,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        usage = response.usage
        tokens = usage.completion_tokens
        answer = response.choices[0].message.content
        after_gpt = time.perf_counter()
        elapsed = round(after_gpt - before_gpt, 4)
        return answer, elapsed, tokens


def get_mock_answer(top_k_docs):
    """
           Gets a mock answer for the given query and documents.
           Args:
               query (str): The query string.
               top_k_docs (list): The list of top documents.
           Returns:
               tuple: The mock answer, elapsed time, and token usage.
           """
    return f"Mock answer with docs___{top_k_docs}", 0.0, 0


llms_client = None


def llms_client_factory(configs_class: Configs):
    """
       Factory function to create and return a singleton instance of GPTClient.
       Args:
           configs_class (Configs): The configuration class instance.
       Returns:
           GPTClient: The singleton instance of GPTClient.
       """
    global llms_client
    if llms_client is None:
        llms_client = GPTClient(configs_class)
    return llms_client
