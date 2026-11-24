import hashlib
import json
import os
import re
from calendar import monthrange
from datetime import datetime
from urllib.parse import quote, urlsplit

from dotenv import load_dotenv
from requests.exceptions import HTTPError
from fGOaria import AriaClient, Field

from nmrguf.db.sqlite_db import get_project_value, update_project
from nmrguf.logs_metadata import custom_value, validate_metadata

load_dotenv()


def _is_permission_error(error):
    if isinstance(error, HTTPError) and error.response is not None:
        return error.response.status_code == 403
    return bool(re.search(r'\b403\b|\bforbidden\b|\bpermission denied\b|\bdo not have permission\b',
                          str(error), re.IGNORECASE))


def _record_url(template, **values):
    if not template or '{record_id}' not in template:
        raise ValueError('Set ARIA_RECORD_URL_TEMPLATE to a record-specific URL containing '
                         '{record_id}; see .env.template')
    try:
        url = template.format(**{k: quote(str(v), safe='') for k, v in values.items()})
    except (KeyError, ValueError) as error:
        raise ValueError('Invalid ARIA_RECORD_URL_TEMPLATE placeholder') from error
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        raise ValueError('ARIA_RECORD_URL_TEMPLATE must be an absolute HTTP(S) URL')
    return url


def send_metadata(project_name, visit_id):
    """Deposit one JSON_LOGS graph without changing the source data in LOGS.

    A saved receipt lets a retry reuse a known bucket, record or field.
    """
    print(f'FandanGO will send metadata for {project_name} project to ARIA...')
    receipt = {}
    try:
        path = get_project_value(project_name, 'experiment_metadata_path', '')
        if not path or not os.path.isfile(path):
            raise ValueError('Experiment metadata is missing; run generate-experiment-metadata first')
        with open(path) as file:
            payload = json.load(file)
        validate_metadata(payload)
        if len(payload['projects']) != 1:
            raise ValueError('Deposition requires exactly one LOGS project')
        project = payload['projects'][0]
        pid, vid = custom_value(project, 'PID'), custom_value(project, 'VID')
        if not pid or not vid:
            raise ValueError('LOGS project must contain PID and VID custom values')
        visit_id = int(visit_id)
        if int(vid) != visit_id:
            raise ValueError(f'LOGS project VID {vid} does not match requested ARIA visit {visit_id}')

        # Preserve optional Excel analysis inside the same JSON field.
        library_path = get_project_value(project_name, 'filtered_library_metadata_path', '')
        if library_path:
            with open(library_path) as file:
                payload['libraryAnalysis'] = json.load(file)

        template = os.getenv('ARIA_RECORD_URL_TEMPLATE', '')
        if template:
            _record_url(template, pid=pid, visit_id=visit_id, bucket_id='bucket',
                        record_id='record', field_id='field')
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        endpoint = os.getenv('ARIA_GQL_' + os.getenv('DEV', 'LOCAL'))
        previous = json.loads(get_project_value(project_name, 'aria_deposition_receipt', '{}'))
        if (previous.get('fingerprint') == fingerprint
                and previous.get('visit_id') == visit_id
                and previous.get('endpoint') == endpoint):
            receipt = previous
        else:
            receipt = {'fingerprint': fingerprint, 'visit_id': visit_id, 'endpoint': endpoint}
        # Older receipts may include progress from the former LOGS write-back.
        receipt.pop('backlinked_dataset_ids', None)

        def save_receipt():
            update_project(project_name, 'aria_deposition_receipt', json.dumps(receipt))

        if not receipt.get('field_id'):
            print('Connecting to ARIA...')
            aria = AriaClient(True)
            aria.login()
            visit = aria.new_data_manager(visit_id, 'visit', False)
            if not receipt.get('bucket_id'):
                today = datetime.today()
                year = today.year + 3
                embargo = today.replace(year=year, day=min(today.day, monthrange(year, today.month)[1]))
                bucket = visit.create_bucket(embargo.strftime('%Y-%m-%d'))
                if not bucket.id:
                    raise ValueError('ARIA did not return a bucket ID')
                receipt['bucket_id'] = bucket.id
                save_receipt()
            if not receipt.get('record_id'):
                record = visit.create_record(receipt['bucket_id'], 'LOGS')
                if not record.id:
                    raise ValueError('ARIA did not return a record ID')
                receipt['record_id'] = record.id
                save_receipt()
            payload['aria'] = {k: receipt[k] for k in ('visit_id', 'bucket_id', 'record_id')}
            field = Field(receipt['record_id'], 'JSON_LOGS', payload)
            visit.push(field)
            if not field.id:
                raise ValueError('ARIA did not confirm the metadata field ID; '
                                 'inspect the record before retrying')
            receipt['field_id'] = field.id
            save_receipt()

        if template:
            receipt['record_url'] = _record_url(
                template, pid=pid, visit_id=visit_id, bucket_id=receipt['bucket_id'],
                record_id=receipt['record_id'], field_id=receipt['field_id'])
        else:
            receipt.pop('record_url', None)
        save_receipt()
        print('Metadata uploaded to ARIA. Source data in LOGS was not changed.')
        return True, receipt
    except Exception as error:
        message = str(error)
        if _is_permission_error(error):
            message = (f'ARIA denied permission to upload metadata to visit {visit_id}. '
                       'Use an account with edit access to this visit, choose a visit you can edit, '
                       'or ask an ARIA administrator to grant access.')
        info = {'error': message}
        if receipt.get('record_id'):
            info['record_id'] = receipt['record_id']
            info['metadata_uploaded'] = bool(receipt.get('field_id'))
            info['retry'] = ('Retry the same command with unchanged metadata to resume '
                             'using the saved deposition receipt.')
        return False, info


def perform_action(args):
    success, info = send_metadata(args['name'], args['visit_id'])
    return {'success': success, 'info': info}
