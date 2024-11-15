import configparser
import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from nmrguf.db.sqlite_db import update_project
from LOGS import LOGS
from LOGS.Entities import (
    DatasetRequestParameter,
    ProjectRequestParameter,
    SampleRequestParameter,
)

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.yaml'))
metadata_output_path = config['METADATA'].get('OUTPUT_PATH')

load_dotenv()

logs_url = os.getenv('LOGS_URL')
api_key = os.getenv('API_KEY')


def generate_experiment_metadata(project_name, logs_project_id):
    """
    Function that generates metadata for a FandanGO project based on LOGS information

    Args:
        project_name (str): FandanGO project name
        logs_project_id (int): LOGS project id
    Returns:
        success (bool): if everything went ok or not
        info (dict): info metadata path
    """

    print(f'FandanGO will create metadata for FandanGO project {project_name} from LOGS for project with id {logs_project_id}...')
    success = False
    info = None

    try:
        logs = LOGS(url=logs_url, apiKey=api_key)

        projects = fetch_projects(logs, logs_project_id)
        project_ids = [p.id for p in projects]

        samples = fetch_samples(logs, project_ids)
        sample_ids = [s.id for s in samples]

        datasets = fetch_datasets(logs, project_ids, sample_ids)

        all_data = {
            'Project': [process_project_data(p) for p in projects],
            'Datasets': [process_dataset_data(d) for d in datasets],
            'Samples': [process_sample_data(s) for s in samples],
        }

        experiment_metadata_path = os.path.join(metadata_output_path, f'{project_name}_experiment_metadata.json')
        with open(experiment_metadata_path, 'w') as metadata_file:
            json.dump(all_data, metadata_file, indent=4)
        success = True
        update_project(project_name, 'experiment_metadata_path', experiment_metadata_path)
        info = {'experiment_metadata_path': experiment_metadata_path}

    except:
        info = (f'... LOGS metadata could not be retrieved for project with id ({logs_project_id}).')
        success = False

    return success, info


def extract_json_field(data: Any, path: List[Any], default=None) -> Any:
    """
    Extract nested JSON fields, handling dictionaries and lists in the path.
    Args:
        data (Any): The JSON-like data structure (dict or list)
        path (List[Any]): The keys or indices to navigate
        default (Any): The value to return if the path is invalid
    Returns:
        Any: The extracted value or the default if the path is invalid
    """
    try:
        for key in path:
            if isinstance(data, list) and isinstance(key, int):
                data = data[key]
            elif isinstance(data, dict):
                data = data.get(key, default)
            else:
                return default
        return data
    except (IndexError, TypeError):
        return default


def fetch_projects(logs_session, project_id: int) -> List[Dict[str, Any]]:
    """Fetch project details."""
    return logs_session.projects(ProjectRequestParameter(ids=[project_id])).toList()


def fetch_samples(logs_session, logproject_ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch sample details."""
    return logs_session.samples(SampleRequestParameter(projectIds=logproject_ids)).toList()


def fetch_datasets(logs_session, project_ids: List[int], sample_ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch dataset details."""
    project_datasets = logs_session.datasets(DatasetRequestParameter(projectIds=project_ids)).toList()
    sample_datasets = logs_session.datasets(DatasetRequestParameter(sampleIds=sample_ids)).toList()
    return project_datasets + sample_datasets


def process_project_data(project: Any) -> Dict[str, Any]:
    """Process and format project data."""
    data = json.loads(project.toJson())
    slack = project._slack or {}

    return {
        'Created On': data.get('createdOn'),
        'Project ID': data.get('id'),
        'Project Name': data.get('name'),
        'Project Notes': data.get('notes'),
        'Owner Name': extract_json_field(data, ['owner', 'name']),
        'Dataset Count': extract_json_field(data, ['relations', 'datasets', 'count'], 0),
        'Sample Count': extract_json_field(data, ['relations', 'samples', 'count'], 0),
        'Project UID': data.get('uid'),
        'Custom Type': extract_json_field(slack, ['customType', 'name']),
        'Custom Values': {
            item['name']: item['value']
            for item in slack.get('customValues', [{}])[0].get('content', [])
        },
    }


def process_dataset_data(dataset: Any) -> Dict[str, Any]:
    """Process and format dataset data."""
    dataset.fetchFull()
    data = json.loads(dataset.toJson())
    params = json.loads(str(dataset.parameters).replace("'", "\""))

    return {
        'Acquisition Date': data.get('acquisitionDate'),
        'Automatic Name': data.get('automaticName'),
        'Claimed': data.get('claimed'),
        'Created On': data.get('createdOn'),
        'Format ID': extract_json_field(data, ['format', 'id']),
        'Format Name': extract_json_field(data, ['format', 'name']),
        'Record ID': data.get('id'),
        'Instrument Name': extract_json_field(data, ['instrument', 'name']),
        'Method Name': extract_json_field(data, ['method', 'name']),
        'Record Name': data.get('name'),
        'Notes': data.get('notes'),
        'Operator Name': extract_json_field(data, ['operators', 0, 'name']),
        'Project ID': extract_json_field(data, ['projects', 0, 'id']),
        'Project Name': extract_json_field(data, ['projects', 0, 'name']),
        'Project UID': extract_json_field(data, ['projects', 0, 'uid']),
        'Source': data.get('source'),
        'Source Base Directory': data.get('sourceBaseDirectory'),
        'Source Relative Directory': data.get('sourceRelativeDirectory'),
        'UID': data.get('uid'),
        'Parameters': params,
    }


def process_sample_data(sample: Any) -> Dict[str, Any]:
    """Process and format sample data."""
    data = json.loads(sample.toJson())

    return {
        'Created On': data.get('createdOn'),
        'Custom Type ID': extract_json_field(data, ['customType', 'id']),
        'Custom Type Name': extract_json_field(data, ['customType', 'name']),
        'Custom Type UID': extract_json_field(data, ['customType', 'uid']),
        'Sample ID': data.get('id'),
        'Sample Name': data.get('name'),
        'Sample Notes': data.get('notes'),
        'Prepared By Name': extract_json_field(data, ['preparedBy', 0, 'name']),
        'Sample UID': data.get('uid'),
        'Target Info': {
            item['name']: item['value']
            for item in extract_json_field(data, ['customValues', 0, 'content'], [])
        },
        'Buffer Info': {
            item['name']: item['value']
            for item in extract_json_field(data, ['customValues', 1, 'content'], [])
        },
    }


def perform_action(args):
    success, info = generate_experiment_metadata(args['name'], args['logs_project_id'])
    results = {'success': success, 'info': info}
    return results
