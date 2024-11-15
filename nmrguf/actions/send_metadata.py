from nmrguf.db.sqlite_db import get_project_metadata, get_experiment_metadata_path, get_filtered_library_metadata_path
from datetime import datetime
from dotenv import load_dotenv
import json
from fGOaria import AriaClient, Bucket, Field

load_dotenv()

def send_metadata(project_name, visit_id):
    """
    Function that sends FandanGO project info to ARIA

    Args:
        project_name (str): FandanGO project name
        visit_id (int): ARIA visit ID

    Returns:
        success (bool): if everything went ok or not
        info (dict): bucket, record and field ARIA data
    """

    print(f'FandanGO will send metadata for {project_name} project to ARIA...')
    success = True
    info = None

    try:
        experiment_metadata_path = get_experiment_metadata_path(project_name)
        filtered_library_metadata_path = get_filtered_library_metadata_path(project_name)

        aria = AriaClient(True)
        aria.login()
        today = datetime.today()
        visit = aria.new_data_manager(int(visit_id), 'visit', True)
        embargo_date = datetime(today.year + 3, today.month, today.day).strftime('%Y-%m-%d')
        bucket = visit.create_bucket(embargo_date)

        # experiment metadata
        with open(experiment_metadata_path, 'r') as file:
            experiment_metadata = json.load(file)

        for dataset in experiment_metadata['Datasets']:
            record = visit.create_record(bucket.id, 'TestSchema')
            field = Field(record.id, 'TestFieldType', dataset)
            visit.push(field)
            if not isinstance(field, Field):
                success = False

        for sample in experiment_metadata['Samples']:
            record = visit.create_record(bucket.id, 'TestSchema')
            field = Field(record.id, 'TestFieldType', sample)
            visit.push(field)
            if not isinstance(field, Field):
                success = False


        # filtered library data
        with open(filtered_library_metadata_path, 'r') as file:
            filtered_library_metadata = json.load(file)

        for mix in filtered_library_metadata:
            for key in mix.keys():
                record = visit.create_record(bucket.id, 'TestSchema')
                field = Field(record.id, 'TestFieldType', mix[key])
                visit.push(field)
                if not isinstance(field, Field):
                    success = False

    except Exception as e:
        success = False
        info = e

    if success:
        print(f'Successfully sent metadata for project {project_name} to ARIA!')
        info = {'bucket': bucket.__dict__}

    return success, info


def perform_action(args):
    success, info = send_metadata(args['name'], args['visit_id'])
    results = {'success': success, 'info': info}
    return results
