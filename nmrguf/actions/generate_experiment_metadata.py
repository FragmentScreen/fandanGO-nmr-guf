import configparser
import json
import logging
import os
import tempfile

from dotenv import load_dotenv
from LOGS import LOGS
from LOGS.Entities import DatasetRequestParameter, ProjectRequestParameter

from nmrguf.db.sqlite_db import update_project
from nmrguf.logs_metadata import build_metadata

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'plugin.cfg'))
metadata_output_path = config.get(section='METADATA', option='OUTPUT_PATH')
load_dotenv()


def generate_experiment_metadata(project_name, logs_project_id):
    """Export a complete LOGS graph, preserving custom fields and sample links."""
    print(f'FandanGO will create metadata for FandanGO project {project_name} '
          f'from LOGS for project with id {logs_project_id}...')
    temporary_path = None
    try:
        logs = LOGS(url=os.getenv('LOGS_URL'), apiKey=os.getenv('API_KEY'))
        project_id = int(logs_project_id)
        projects = logs.projects(ProjectRequestParameter(ids=[project_id])).toList()
        if len(projects) != 1 or projects[0].id != project_id:
            raise ValueError(f'LOGS project {project_id} was not found')
        datasets = logs.datasets(DatasetRequestParameter(projectIds=[project_id])).toList()
        data = build_metadata(logs, projects, datasets)

        # Do not replace a previous usable export with a partial graph or JSON.
        os.makedirs(metadata_output_path, exist_ok=True)
        experiment_metadata_path = os.path.join(
            metadata_output_path, f'{project_name}_experiment_metadata.json')
        with tempfile.NamedTemporaryFile(mode='w', dir=metadata_output_path,
                                         suffix='.json', delete=False) as metadata_file:
            temporary_path = metadata_file.name
            json.dump(data, metadata_file, indent=4, allow_nan=False)
        os.replace(temporary_path, experiment_metadata_path)
        temporary_path = None
        update_project(project_name, 'experiment_metadata_path', experiment_metadata_path)
        quality = data['dataQuality']
        if quality['issues']:
            logging.warning('LOGS export has %s data-quality issue(s); see dataQuality in %s',
                            len(quality['issues']), experiment_metadata_path)
        return True, {'experiment_metadata_path': experiment_metadata_path,
                      'complete': quality['complete'], 'issue_count': len(quality['issues'])}
    except Exception as error:
        return False, {'error': f'LOGS metadata could not be generated: {error}'}
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def perform_action(args):
    success, info = generate_experiment_metadata(args['name'], args['logs_project_id'])
    return {'success': success, 'info': info}
