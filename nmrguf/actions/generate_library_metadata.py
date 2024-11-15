import configparser
import os
import json
from nmrguf.db.sqlite_db import update_project, get_library_metadata_path, get_experiment_metadata_path

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.yaml'))
metadata_output_path = config['METADATA'].get('OUTPUT_PATH')


def generate_library_metadata(project_name):
    """
    Function that creates filtered library metadata for a FandanGO project

    Args:
        project_name (str): FandanGO project name
    Returns:
        success (bool): if everything went ok or not
        info (dict): info metadata path
    """

    print(f'FandanGO will filter library metadata for FandanGO project {project_name}...')
    success = False
    info = None

    try:
        library_metadata_path = get_library_metadata_path(project_name)
        experiment_metadata_path = get_experiment_metadata_path(project_name)
        mixes = generate_mix_list(experiment_metadata_path)
        filtered_json = filter_json(mixes, library_metadata_path)

        filtered_library_metadata_path = os.path.join(metadata_output_path, f'{project_name}_filtered_analyzed_metadata.json')

        with open(filtered_library_metadata_path, 'w') as metadata_file:
            json.dump(filtered_json, metadata_file, indent=4)
        success = True
        update_project(project_name, 'filtered_library_metadata_path', filtered_library_metadata_path)
        info = {'filtered_library_metadata_path': filtered_library_metadata_path}

    except Exception as e:
        info = (f'... Something went wrong: {e}')
        success = False

    return success, info


def filter_json(mix_list, file_path):
    with open(file_path) as f:
        data = json.load(f)

    filtered_mixes = [mix for mix in data if any(mix_key in mix_list for mix_key in mix.keys())]

    return filtered_mixes


def generate_mix_list(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    mixes = set()

    for dataset in data['Datasets']:
        mix_name = dataset['Automatic Name'].split('/')[0]
        mixes.add(mix_name)

    return mixes


def perform_action(args):
    success, info = generate_library_metadata(args['name'])
    results = {'success': success, 'info': info}
    return results
