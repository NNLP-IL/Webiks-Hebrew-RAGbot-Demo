from dotenv import load_dotenv
import os

load_dotenv()
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
CONVERSATIONS_INDEX = os.getenv("CONVERSATIONS_INDEX", "conversations")
STATIC_DIR = os.getenv("STATIC_DIR")
SAVED_CONFIGURATIONS = os.getenv("CONFIG_INDEX", "saved_configurations")
CONFIG_CACHE_PERIOD_SECS = int(os.getenv("CONFIG_CACHE_PERIOD_SECS", '600'))
PATH_TO_ES_INITIAL_VALUES=os.getenv("PATH_TO_ES_INITIAL_VALUES", "../../Webiks_Hebrew_RAGbot_KolZchut_Paragraphs_Corpus_v1.0.json")
CODE_VERSION = os.getenv("CODE_VERSION")
