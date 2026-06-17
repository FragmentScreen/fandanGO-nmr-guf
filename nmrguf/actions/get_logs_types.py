import configparser
import os
import json
import sys
import traceback
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from nmrguf.db.sqlite_db import update_project
from LOGS import LOGS
from LOGS.Entities import CustomType, CustomTypeRequestParameter

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'plugin.cfg'))
metadata_output_path = config.get(section='METADATA', option='OUTPUT_PATH')

load_dotenv()

logs_url = os.getenv('LOGS_URL')
api_key = os.getenv('API_KEY')


def get_custom_types(project_name: str, search_term: Optional[str] = None):
    """
    Find custom types based on search term

    Args:
        project_name (str): name of the fandanGO project
        search_term (str): search term
    Returns:
        success (bool): if everything went ok or not
        info (dict): info metadata path
    """

    print(f'Searching for types including term {search_term} from LOGS ...')
    success = False
    info = {}

    try:
        logs = LOGS(url=logs_url, apiKey=api_key)

        types = fetch_custom_types(logs, search_term if search_term else '')
        type_ids = [t.id for t in types]

        update_project(project_name, 'logs_project_types', json.dumps(type_ids))

        success = len(type_ids) > 0
        info = { 'logs_type_ids': type_ids }

    except Exception:
        success = False
        info = { 'error': f'... LOGS project types could not be found for search term ({search_term}).' }
        if os.getenv('DEV') == 'LOCAL':
            print(traceback.format_exc())

    return success, info


def fetch_custom_types(logs_session: LOGS, search_term: str) -> List[CustomType]:
    return logs_session.customTypes(CustomTypeRequestParameter(searchTerm=search_term.lower())).toList()


def perform_action(args):
    success, info = get_custom_types(args['name'], args['search_term'] if 'search_term' in args else None)
    results = {'success': success, 'info': info}
    return results
