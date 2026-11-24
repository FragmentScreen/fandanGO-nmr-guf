"""Lossless, read-only LOGS metadata graph export.

Sample references use the API's dataType, not a section index or field label.
Shared samples are stored once; IDs/UIDs connect the graph, including cycles.
"""

from copy import deepcopy

from LOGS.Entities import SampleRequestParameter

SCHEMA_VERSION = 2
COCKTAIL_SIZES = {30: 1, 11: 4, 10: 12}


def custom_fields(entity):
    """Yield fields from every custom-value section, retaining API ordering."""
    def walk(items):
        for item in items or []:
            if item.get('type') == 'CustomField':
                yield item
            elif 'content' in item:
                yield from walk(item['content'])

    yield from walk(entity.get('customValues'))


def custom_value(entity, name):
    values = [f.get('value') for f in custom_fields(entity) if f.get('name') == name]
    populated = [v for v in values if v is not None and v != '']
    if len(populated) > 1:
        raise ValueError(f"Ambiguous {name} fields in LOGS entity {entity.get('id')}")
    return populated[0] if populated else None


def sample_references(entity):
    for field in custom_fields(entity):
        if field.get('dataType') not in ('Sample', 'SampleArray'):
            continue
        value = field.get('value')
        if value is None:
            continue
        values = value if isinstance(value, list) else [value]
        for ref in values:
            if not isinstance(ref, dict) or not ref.get('id'):
                raise ValueError(f"Invalid sample reference in LOGS field {field.get('name')}")
            yield {
                'fieldId': field.get('id'),
                'fieldName': field.get('name'),
                'sampleId': ref['id'],
                'sampleUid': ref.get('uid'),
            }


def serialize_entity(entity, dataset=False):
    entity.fetch()
    if dataset:
        entity.fetchFull()
    data = deepcopy(entity.toDict())
    # Keep the data and type identity, without repeating the type's field schema.
    custom_type = data.get('customType') or {}
    data['customType'] = {k: custom_type.get(k) for k in ('id', 'name', 'uid')}
    data['url'] = entity.getUIUrl()
    data['sampleReferences'] = list(sample_references(data))
    _validate_identity(data)
    return data


def _validate_identity(entity):
    for key in ('id', 'name', 'uid', 'url'):
        if not entity.get(key):
            raise ValueError(f"LOGS entity {entity.get('id')} is missing {key}")
    for key in ('id', 'name', 'uid'):
        if not (entity.get('customType') or {}).get(key):
            raise ValueError(f"LOGS entity {entity.get('id')} is missing customType.{key}")


def build_metadata(logs, projects, datasets):
    """Resolve all referenced samples, including those outside the project."""
    result = {
        'schemaVersion': SCHEMA_VERSION,
        'projects': [serialize_entity(p) for p in projects],
        'datasets': [serialize_entity(d, dataset=True) for d in datasets],
        'samples': [],
    }
    resolved = {}
    pending = [r for e in result['projects'] + result['datasets']
               for r in e['sampleReferences']]
    while pending:
        ref = pending.pop(0)
        sample_id = ref['sampleId']
        if sample_id not in resolved:
            found = logs.samples(SampleRequestParameter(ids=[sample_id])).toList()
            if len(found) != 1 or found[0].id != sample_id:
                raise ValueError(f'Cannot resolve LOGS sample {sample_id}; export is incomplete')
            data = serialize_entity(found[0])
            resolved[sample_id] = data
            pending.extend(data['sampleReferences'])
        if ref.get('sampleUid') and ref['sampleUid'] != resolved[sample_id]['uid']:
            raise ValueError(f'UID mismatch for LOGS sample {sample_id}')
    result['samples'] = list(resolved.values())
    validate_metadata(result)
    return result


def validate_metadata(data):
    """Reject old flattened exports and dangling references before deposition."""
    if not isinstance(data, dict) or data.get('schemaVersion') != SCHEMA_VERSION:
        raise ValueError('Regenerate experiment metadata with generate-experiment-metadata; '
                         'a complete LOGS hierarchy (schemaVersion 2) is required')
    for key in ('projects', 'datasets', 'samples'):
        if not isinstance(data.get(key), list):
            raise ValueError(f'Metadata is missing the {key} list')
        ids = set()
        for entity in data[key]:
            _validate_identity(entity)
            if entity['id'] in ids:
                raise ValueError(f"Duplicate {key} ID {entity['id']}")
            ids.add(entity['id'])
    if not data['projects'] or not data['datasets']:
        raise ValueError('LOGS export must contain a project and at least one dataset')
    samples = {s['id']: s for s in data['samples']}
    for entity in data['projects'] + data['datasets'] + data['samples']:
        refs = list(sample_references(entity))
        if refs != entity.get('sampleReferences'):
            raise ValueError(f"Sample references do not match custom values for {entity['id']}")
        for ref in refs:
            target = samples.get(ref['sampleId'])
            if target is None:
                raise ValueError(f"Unresolved LOGS sample {ref['sampleId']}")
            if ref.get('sampleUid') and ref['sampleUid'] != target['uid']:
                raise ValueError(f"UID mismatch for LOGS sample {ref['sampleId']}")

    def linked(entity, type_ids):
        return [samples[r['sampleId']] for r in entity['sampleReferences']
                if samples[r['sampleId']]['customType']['id'] in type_ids]

    for dataset in data['datasets']:
        if not linked(dataset, {31}):
            raise ValueError(f"Dataset {dataset['id']} has no Measurement Sample reference")
    for sample in data['samples']:
        type_id = sample['customType']['id']
        if type_id == 31:
            if not linked(sample, {9}) or not linked(sample, set(COCKTAIL_SIZES)):
                raise ValueError(f"Measurement sample {sample['id']} must reference "
                                 'both a Target Sample and a Cocktail Sample')
        elif type_id in COCKTAIL_SIZES:
            if len(linked(sample, {13})) != COCKTAIL_SIZES[type_id]:
                raise ValueError(f"Cocktail sample {sample['id']} must reference "
                                 f'{COCKTAIL_SIZES[type_id]} Component Sample(s)')

