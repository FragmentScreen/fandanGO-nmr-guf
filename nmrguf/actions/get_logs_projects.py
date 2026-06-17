import configparser
import json
import os
import traceback
from typing import List, Optional
from dotenv import load_dotenv
from LOGS import LOGS
from LOGS.Entities import Project, ProjectRequestParameter
from nmrguf.db.sqlite_db import get_project_value, update_project


config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'plugin.cfg'))
metadata_output_path = config.get(section='METADATA', option='OUTPUT_PATH')

load_dotenv()

logs_url = os.getenv('LOGS_URL')
api_key = os.getenv('API_KEY')


def get_project_ids(project_name: str, type_id: Optional[int] = None):
    """
    Find projects given a type ID

    Args:
        project_name (str): name of the fandanGO project
        type_id (str): search term
    Returns:
        success (bool): if everything went ok or not
        info (dict): info metadata path
    """

    success = False
    info = None

    try:
        logs = LOGS(url=logs_url, apiKey=api_key)

        type_ids = []
        if type_id is None:
            print('Searching for projects from saved type IDs...')
            db_type_ids = get_project_value(project_name, "logs_project_types", "")
            type_ids = json.loads(db_type_ids)
        else:
            print(f'Searching for projects of type {type_id} from LOGS ...')
            type_ids = [type_id]

        projects = fetch_projects(logs, type_ids)
        project_ids = [p.id for p in projects]

        update_project(project_name, 'logs_project_ids', json.dumps(project_ids))

        success = len(project_ids) > 0
        info = { 'logs_project_ids': project_ids }

    except Exception:
        success = False
        info = { 'error': '... LOGS projects could not be found for provided type ID(s).' }
        if os.getenv('DEV') == 'LOCAL':
            print(traceback.format_exc())

    return success, info


def fetch_projects(logs_session: LOGS, type_ids: list[int]) -> List[Project]:
    return logs_session.projects(ProjectRequestParameter(customTypeIds=type_ids)).toList()


def perform_action(args):
    success, info = get_project_ids(args['name'], args['logs_type_id'] if 'logs_type_id' in args else None)
    results = {'success': success, 'info': info}
    return results
