import configparser
import os
from nmrguf.db.sqlite_db import update_project
import json
from dotenv import load_dotenv
from LOGS import LOGS

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.yaml'))
logs_path = config['LOGS'].get('PROJECTS_PATH')

load_dotenv()

logs_url = os.getenv("LOGS_URL")
api_key = os.getenv("API_KEY")


def generate_metadata_data(project_name, logs_dataset_id):
    """
    Function that generates metadata for a FandanGO project

    Args:
        project_name (str): FandanGO project name
        logs_dataset_id (str): LOGS dataset id
    Returns:
        success (bool): if everything went ok or not
        info (dict): info metadata path
    """

    print(f'FandanGO will retrieve metadata from LOGS for dataset {logs_dataset_id}...')
    success = False
    info = None

    logs = LOGS(url=logs_url, apiKey=api_key)
    try:
        dataset = logs.dataset(id=logs_dataset_id)
        sample = {'sample_name': dataset.sample.name,
                  'method': dataset.method.name,
                  'experiment_name': dataset.experiment.name}
        sample_metadata_path = os.path.join(logs_path, logs_dataset_id, 'sample.json')
        with open(sample_metadata_path, 'w') as sample_file:
            sample_file.write(json.dumps(sample))
        success = True
        update_project(project_name, 'sample_metadata_path', sample_metadata_path)
        info = {'sample_metadata_path': sample_metadata_path}

    except:
        info = (f'... LOGS metadata could not be retrieved for dataset with id ({logs_dataset_id}).')

    return success, info


def perform_action(args):
    success, info = generate_metadata_data(args['name'], args['logs_dataset_id'])
    results = {'success': success, 'info': info}
    return results
