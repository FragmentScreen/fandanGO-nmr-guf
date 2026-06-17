import json
import os
import traceback
from datetime import datetime
from dotenv import load_dotenv
from fGOaria import AriaClient, Field
from nmrguf.db.sqlite_db import get_project_value

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
        experiment_metadata_path = get_project_value(project_name, "experiment_metadata_path", "")
        os.makedirs(os.path.dirname(experiment_metadata_path), exist_ok=True)

        filtered_library_metadata_path = get_project_value(project_name, "filtered_library_metadata_path", "")
        if filtered_library_metadata_path:
            os.makedirs(os.path.dirname(filtered_library_metadata_path), exist_ok=True)


        print('Connecting to ARIA...')
        aria = AriaClient(True)
        aria.login()
        print('✓ Connected to ARIA')

        print(f'Getting visit {visit_id}...')
        visit = aria.new_data_manager(int(visit_id), 'visit', True)
        print(f'✓ Got visit {visit_id}')

        today = datetime.today()
        embargo_date = datetime(today.year + 3, today.month, today.day).strftime('%Y-%m-%d')

        print(f'Creating bucket embargoed until {embargo_date}...')
        bucket = visit.create_bucket(embargo_date)
        print(f'✓ Created bucket {bucket.id}')

        print('Creating record...')
        record = visit.create_record(bucket.id, 'LOGS')
        print(f'✓ Created record {record.id}')

        if not os.path.exists(experiment_metadata_path):
            raise Exception(f'Experiment metadata not found at {experiment_metadata_path}')

        # experiment metadata
        with open(experiment_metadata_path, 'r') as file:
            experiment_metadata = json.load(file)

        for dataset in experiment_metadata['Datasets']:
            print(f'Sending experiment dataset {dataset["Automatic Name"]} ...')
            field = Field(record.id, 'JSON_LOGS_Dataset', dataset)
            # print(field.__dict__)
            visit.push_safe_cli(field)
            print(f'✓ Experiment dataset field {dataset["Automatic Name"]} created')
            if not isinstance(field, Field):
                success = False

        for sample in experiment_metadata['Samples']:
            print(f'Sending experiment sample {sample["Sample Name"]} ...')
            field = Field(record.id, 'JSON_LOGS_Sample', sample)
            # print(field.__dict__)
            visit.push_safe_cli(field)
            print(f'✓ Experiment sample field {sample["Sample Name"]} created')
            if not isinstance(field, Field):
                success = False

        # filtered library data
        if filtered_library_metadata_path:
            with open(filtered_library_metadata_path, 'r') as file:
                filtered_library_metadata = json.load(file)

            for mix in filtered_library_metadata:
                for key in mix.keys():
                    print(f'Sending filtered library mix {key} ...')
                    field = Field(record.id, 'JSON_LOGS_Mix', mix[key])
                    # print(field.__dict__)
                    visit.push_safe_cli(field)
                    print(f'✓ Filtered library mix field {key} created')
                    if not isinstance(field, Field):
                        success = False

    except Exception as e:
        success = False
        info = { 'error': str(e) }
        # if os.getenv('DEV') == 'LOCAL':
        print(traceback.format_exc())

    if success:
        print(f'Successfully sent metadata for project {project_name} to ARIA!')
        info = {'bucket': bucket.__dict__}

    return success, info


def perform_action(args):
    success, info = send_metadata(args['name'], args['visit_id'])
    results = {'success': success, 'info': info}
    return results
