import hashlib
import json
import os
import re
from calendar import monthrange
from copy import deepcopy
from datetime import datetime
from urllib.parse import quote, urlsplit

from dotenv import load_dotenv
from LOGS import LOGS
from requests.exceptions import HTTPError, JSONDecodeError as ResponseJSONError
from fGOaria import AriaClient, Field
from fGOaria.classes.data_manager import DataManager

from nmrguf.db.sqlite_db import get_project_value, update_project
from nmrguf.logs_metadata import custom_value, validate_metadata
from nmrguf.logs_backlinks import backlink_dataset, write_backlink

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


def _verify_aria_types(visit):
    response = visit.client.gql_query(
        'query { fieldTypesItems { type } '
        'recordSchemaTypesItems { type } }', {})
    data = response.get('data') or {}
    for key, expected in (('fieldTypesItems', 'JSON_LOGS'), ('recordSchemaTypesItems', 'LOGS')):
        if not any(item.get('type') == expected for item in data.get(key) or []):
            raise ValueError(f'ARIA does not advertise {expected}; install/register '
                             'the ddapi-record-logs handler before depositing metadata')


def _recover_field(visit, record_id, payload):
    matches = []
    for field in visit.client.pull_fields(record_id):
        if field.get('type') != 'JSON_LOGS':
            continue
        content = field.get('content')
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except ValueError:
                continue
        if content == payload and field.get('id'):
            matches.append(field['id'])
    if len(matches) > 1:
        raise ValueError('Multiple matching JSON_LOGS fields exist; inspect the ARIA record')
    return matches[0] if matches else None


class _RetryingFieldUpload(DataManager):
    """Use the SDK retry policy without re-encoding or duplicating a field."""

    def __init__(self, manager, payload):
        self.manager = manager
        self.payload = deepcopy(payload)
        self.attempted = False

    def push(self, field):
        if self.attempted:
            field_id = _recover_field(self.manager, field.record_id, self.payload)
            if field_id is not None:
                field.id = field_id
                self.manager.fields[field_id] = field
                return
        self.attempted = True
        # ARIA 2.2.6 serializes Field.content in place, even on failed requests.
        field.content = deepcopy(self.payload)
        self.manager.push(field)


def send_metadata(project_name, visit_id, incomplete_policy='reject', write_back_logs=False):
    """Deposit one JSON_LOGS graph; source updates require explicit opt-in.

    A saved receipt lets a retry reuse a known bucket, record or field.
    """
    print(f'FandanGO will send metadata for {project_name} project to ARIA...')
    receipt = {}
    service = 'ARIA'
    try:
        if incomplete_policy not in ('reject', 'preserve'):
            raise ValueError('incomplete_policy must be reject or preserve')
        path = get_project_value(project_name, 'experiment_metadata_path', '')
        if not path or not os.path.isfile(path):
            raise ValueError('Experiment metadata is missing; run generate-experiment-metadata first')
        with open(path) as file:
            payload = json.load(file)
        quality = validate_metadata(payload, allow_incomplete=incomplete_policy == 'preserve')
        payload['dataQuality'] = quality
        if len(payload['projects']) != 1:
            raise ValueError('Deposition requires exactly one LOGS project')
        project = payload['projects'][0]
        pid, vid = custom_value(project, 'PID'), custom_value(project, 'VID')
        if not pid or not vid:
            raise ValueError('LOGS project must contain PID and VID custom values')
        visit_id = int(visit_id)
        if int(vid) != visit_id:
            raise ValueError(f'LOGS project VID {vid} does not match requested ARIA visit {visit_id}')

        # Preserve both available analysis products without changing Excel parsing.
        for key, output in (('library_metadata_path', 'analyzedMetadata'),
                            ('filtered_library_metadata_path', 'libraryAnalysis')):
            analysis_path = get_project_value(project_name, key, '')
            if analysis_path:
                with open(analysis_path) as file:
                    payload[output] = json.load(file)
                if not isinstance(payload[output], (dict, list)):
                    raise ValueError(f'{key} must contain a JSON object or array')

        template = os.getenv('ARIA_RECORD_URL_TEMPLATE', '')
        if write_back_logs and not template:
            raise ValueError('LOGS write-back requires ARIA_RECORD_URL_TEMPLATE')
        if template:
            _record_url(template, pid=pid, visit_id=visit_id, bucket_id='bucket',
                        record_id='record', field_id='field')
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        endpoint = os.getenv('ARIA_GQL_' + os.getenv('DEV', 'LOCAL'))
        previous = json.loads(get_project_value(project_name, 'aria_deposition_receipt', '{}'))
        if (previous.get('fingerprint') == fingerprint
                and previous.get('visit_id') == visit_id
                and previous.get('endpoint') == endpoint):
            receipt = previous
        else:
            receipt = {'fingerprint': fingerprint, 'visit_id': visit_id, 'endpoint': endpoint}
        receipt.setdefault('backlinked_dataset_ids', [])

        def save_receipt():
            update_project(project_name, 'aria_deposition_receipt', json.dumps(receipt))

        logs = None
        if write_back_logs:
            service = 'LOGS'
            logs = LOGS(url=os.getenv('LOGS_URL'), apiKey=os.getenv('API_KEY'))
            for dataset in payload['datasets']:
                if dataset['id'] not in receipt['backlinked_dataset_ids']:
                    backlink_dataset(logs, dataset, receipt.get('record_url'))
        service = 'ARIA'
        if receipt.get('pending_creation'):
            raise ValueError('An ARIA creation response was not confirmed. Inspect the '
                             'remote bucket/record before retrying; refusing to create a duplicate')
        if not receipt.get('field_id'):
            print('Connecting to ARIA...')
            aria = AriaClient(True)
            aria.login()
            visit = aria.new_data_manager(visit_id, 'visit', False)
            _verify_aria_types(visit)
            existing_record = bool(receipt.get('record_id'))
            if not receipt.get('bucket_id'):
                today = datetime.today()
                year = today.year + 3
                embargo = today.replace(year=year, day=min(today.day, monthrange(year, today.month)[1]))
                receipt['pending_creation'] = 'bucket'
                save_receipt()
                bucket = visit.create_bucket(embargo.strftime('%Y-%m-%d'))
                if not bucket.id:
                    raise ValueError('ARIA did not return a bucket ID')
                receipt['bucket_id'] = bucket.id
                receipt.pop('pending_creation', None)
                save_receipt()
            if not receipt.get('record_id'):
                receipt['pending_creation'] = 'record'
                save_receipt()
                record = visit.create_record(receipt['bucket_id'], 'LOGS')
                if not record.id:
                    raise ValueError('ARIA did not return a record ID')
                receipt['record_id'] = record.id
                receipt.pop('pending_creation', None)
                save_receipt()
            payload['aria'] = {k: receipt[k] for k in ('visit_id', 'bucket_id', 'record_id')}
            # Recover an accepted field if the prior HTTP response/receipt was lost.
            field_id = _recover_field(visit, receipt['record_id'], payload) if existing_record else None
            if field_id is None:
                field = Field(receipt['record_id'], 'JSON_LOGS', payload)
                uploader = _RetryingFieldUpload(visit, payload)
                uploader.push_safe_cli(field)
                if not field.id:
                    raise ValueError('ARIA did not confirm the metadata field ID; '
                                     'inspect the record before retrying')
                field_id = field.id
            receipt['field_id'] = field_id
            save_receipt()

        if template:
            receipt['record_url'] = _record_url(
                template, pid=pid, visit_id=visit_id, bucket_id=receipt['bucket_id'],
                record_id=receipt['record_id'], field_id=receipt['field_id'])
        else:
            receipt.pop('record_url', None)
        save_receipt()
        if write_back_logs:
            service = 'LOGS'
            for dataset in payload['datasets']:
                if dataset['id'] in receipt['backlinked_dataset_ids']:
                    continue
                write_backlink(logs, dataset, receipt['record_url'])
                receipt['backlinked_dataset_ids'].append(dataset['id'])
                save_receipt()
            print('Metadata uploaded to ARIA and dataset backlinks saved in LOGS.')
        else:
            print('Metadata uploaded to ARIA. Source data in LOGS was not changed.')
        receipt['write_back_requested'] = write_back_logs
        receipt['data_quality'] = quality
        save_receipt()
        return True, receipt
    except Exception as error:
        message = str(error)
        if isinstance(error, ResponseJSONError):
            message = ('ARIA returned a non-JSON HTTP response. Check the GraphQL/API '
                       'server logs, request-size limits and endpoint configuration.')
        elif service == 'LOGS' and (isinstance(error, PermissionError) or _is_permission_error(error)):
            message = f'LOGS write-back denied: {error}'
        elif _is_permission_error(error):
            message = (f'ARIA denied permission to upload metadata to visit {visit_id}. '
                       'Use an account with edit access to this visit, choose a visit you can edit, '
                       'or ask an ARIA administrator to grant access.')
        if receipt.get('pending_creation') and _is_permission_error(error):
            receipt.pop('pending_creation', None)
            update_project(project_name, 'aria_deposition_receipt', json.dumps(receipt))
        info = {'error': message}
        if receipt.get('record_id'):
            info['record_id'] = receipt['record_id']
            info['metadata_uploaded'] = bool(receipt.get('field_id'))
            info['write_back_complete'] = len(receipt.get('backlinked_dataset_ids', []))
            if not receipt.get('pending_creation'):
                info['retry'] = ('Retry the same command with unchanged metadata to resume '
                                 'using the saved deposition receipt.')
        return False, info


def perform_action(args):
    success, info = send_metadata(args['name'], args['visit_id'],
                                  args.get('incomplete_policy') or 'reject',
                                  args.get('write_back_logs') == 'yes')
    return {'success': success, 'info': info}
