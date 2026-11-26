"""Lossless, read-only LOGS metadata graph export.

This script builds the complete project → dataset → measurement → target/cocktail → component hierarchy,
retrieves referenced samples, preserves scientific values and units, and checks for missing or incorrect information.
It does not modify LOGS.

Sample references use the API's dataType, not a section index or field label.
Shared samples are stored once; IDs/UIDs connect the graph, including cycles.

The main flow is:
build_metadata()
  → serialize projects and datasets
  → retrieve referenced samples
  → verify custom types
  → audit scientific completeness
  → validate the resulting graph

"""

from collections import deque
from copy import deepcopy
import re

from LOGS.Entities import CustomTypeRequestParameter, SampleRequestParameter

# Roles are identified from API type names; IDs and UIDs are retained and verified
# against the server's definitions rather than substituted from local constants.
def type_role(entity):
    """Identify the entity's role from its type name, or return None if unknown."""
    name = ((entity.get('customType') or {}).get('name') or '').strip().casefold()
    name = re.sub(r'[-_\s]+', ' ', name)
    roles = {'instruct eric project': 'project',
             'instruct eric screening dataset': 'dataset',
             'instruct eric measurement sample': 'measurement',
             'instruct eric target sample': 'target',
             'instruct eric component sample': 'component'}
    if name in roles:
        return roles[name]
    match = re.fullmatch(r'instruct eric (1|4|12) cocktail sample', name)
    return 'cocktail' + match[1] if match else None


def custom_fields(entity):
    """Yield fields from every custom-value section, retaining API ordering."""
    def walk(items):
        """Descend into nested sections and yield their custom fields in order."""
        for item in items or []:
            if item.get('type') == 'CustomField':
                yield item
            elif 'content' in item:
                yield from walk(item['content'])

    yield from walk(entity.get('customValues'))


def custom_value(entity, name):
    """Return one populated field by exact name, or None; reject ambiguous matches."""
    values = [f.get('value') for f in custom_fields(entity) if f.get('name') == name]
    populated = [v for v in values if v is not None and v != '']
    if len(populated) > 1:
        raise ValueError(f"Ambiguous {name} fields in LOGS entity {entity.get('id')}")
    return populated[0] if populated else None


def sample_references(entity):
    """Yield IDs, UIDs and source field details for valid Sample/SampleArray references."""
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
    """Fetch metadata and add its LOGS URL, type identity and sample references.

    Datasets fetch additional information. Original custom values and units are
    preserved; the full custom-type field schema is omitted from each entity.
    """
    entity.fetch()
    if dataset:
        entity.fetchFull()
    data = deepcopy(entity.toDict())
    # Keep the data and type identity, without repeating the type's field schema.
    custom_type = data.get('customType') or {}
    data['customType'] = {k: custom_type.get(k) for k in ('id', 'name', 'uid')}
    data['url'] = entity.getUIUrl()
    data['sampleReferences'] = list(sample_references(data))
    _validate_identity(data, allow_untyped=True)
    return data


def _validate_identity(entity, allow_untyped=False):
    """Raise if required identity fields are missing.

    Relaxed mode still requires ID, UID and URL, but leaves missing names and
    custom-type details for the scientific quality report to describe.
    """
    for key in (('id', 'uid', 'url') if allow_untyped else ('id', 'name', 'uid', 'url')):
        if not entity.get(key):
            raise ValueError(f"LOGS entity {entity.get('id')} is missing {key}")
    for key in (() if allow_untyped else ('id', 'name', 'uid')):
        if not (entity.get('customType') or {}).get(key):
            raise ValueError(f"LOGS entity {entity.get('id')} is missing customType.{key}")


def build_metadata(logs, projects, datasets):
    """Build the graph, resolve sample references and verify its custom types.

    Cache shared and unavailable samples, including references outside the
    project. Return available metadata with a quality report; raise on retrieval
    failures or inconsistent identities rather than inventing missing data.
    """
    result = {
        'projects': [serialize_entity(p) for p in projects],
        'datasets': [serialize_entity(d, dataset=True) for d in datasets],
        'samples': [],
    }
    resolved = {}
    missing = set()
    pending = deque(r for e in result['projects'] + result['datasets']
                    for r in e['sampleReferences'])
    while pending:
        ref = pending.popleft()
        sample_id = ref['sampleId']
        if sample_id in missing:
            continue
        if sample_id not in resolved:
            try:
                found = logs.samples(SampleRequestParameter(ids=[sample_id])).toList()
            except Exception as error:
                raise ValueError(f'LOGS retrieval failed for sample {sample_id}: {error}') from error
            if not found:
                missing.add(sample_id)
                continue
            if len(found) != 1 or found[0].id != sample_id:
                raise ValueError(f'Unexpected LOGS response for sample {sample_id}')
            data = serialize_entity(found[0])
            resolved[sample_id] = data
            pending.extend(data['sampleReferences'])
        if ref.get('sampleUid') and ref['sampleUid'] != resolved[sample_id]['uid']:
            raise ValueError(f'UID mismatch for LOGS sample {sample_id}')
    result['samples'] = list(resolved.values())
    result['customTypes'] = verify_custom_types(logs, result)
    result['dataQuality'] = audit_metadata(result)
    validate_metadata(result, allow_incomplete=True)
    return result


def validate_metadata(data, allow_incomplete=False):
    """Check graph structure and identity consistency, then return its quality report.

    Reject old flattened exports, duplicate IDs and inconsistent references.
    Scientific incompleteness also raises unless allow_incomplete is enabled;
    that option does not bypass structural or identity checks.
    """
    if not isinstance(data, dict) or not all(key in data for key in ('projects', 'datasets', 'samples')):
        raise ValueError('Regenerate experiment metadata with generate-experiment-metadata; '
                         'a LOGS hierarchy with projects, datasets and samples is required')
    for key in ('projects', 'datasets', 'samples'):
        if not isinstance(data.get(key), list):
            raise ValueError(f'Metadata is missing the {key} list')
        ids = set()
        for entity in data[key]:
            _validate_identity(entity, allow_untyped=True)
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
            if target is not None and ref.get('sampleUid') and ref['sampleUid'] != target['uid']:
                raise ValueError(f"UID mismatch for LOGS sample {ref['sampleId']}")
    if 'customTypes' in data:
        registry = {t['id']: t for t in data['customTypes']}
        for entity in data['projects'] + data['datasets'] + data['samples']:
            identity = entity['customType']
            if identity.get('id') is not None:
                definition = registry.get(identity['id']) or {}
                if any(identity.get(k) != definition.get(k) for k in ('name', 'uid')):
                    raise ValueError(f"Custom type identity mismatch for LOGS entity {entity['id']}")
    quality = audit_metadata(data)
    if not allow_incomplete and not quality['complete']:
        first = next(i for i in quality['issues'] if i['severity'] == 'error')
        raise ValueError(f"Incomplete LOGS metadata: {first['message']}. "
                         'Review dataQuality; use --incomplete-policy preserve only to '
                         'explicitly deposit the available historical/incomplete metadata')
    return quality


def verify_custom_types(logs, data):
    """Fetch type definitions in one batch and verify entity type names and UIDs.

    Fill abbreviated type identities from LOGS definitions, update the graph's
    entities, and return the definitions. Conflicting identities raise an error.
    """
    entities = data['projects'] + data['datasets'] + data['samples']
    ids = sorted({e['customType']['id'] for e in entities if e['customType'].get('id') is not None})
    definitions = logs.customTypes(CustomTypeRequestParameter(ids=ids)).toList()
    types = {}
    for definition in definitions:
        raw = definition.toDict()
        types[raw['id']] = {k: raw.get(k) for k in ('id', 'name', 'uid', 'entityType')}
    for entity in entities:
        identity = entity['customType']
        if identity.get('id') is None:
            continue
        expected = types.get(identity['id'])
        if expected is None or any(identity.get(k) is not None and identity[k] != expected[k]
                                   for k in ('uid', 'name')):
            raise ValueError(f"Custom type identity mismatch for LOGS entity {entity['id']}")
        entity['customType'] = {k: expected[k] for k in ('id', 'name', 'uid')}
    return list(types.values())


def _field_name(name):
    """Normalize a label for comparison without changing exported labels or units."""
    # Normalization is for validation only; never rewrite labels, units or values.
    return re.sub(r'\s+', ' ', re.sub(r'\[[^]]*\]', '', name or '').strip().casefold())


def audit_metadata(data):
    """Return completeness and issues for scientific values and sample relationships.

    Check required concentrations, volumes, named references and cocktail sizes.
    Report historical/unsupported types and missing information without fetching
    data, calculating concentrations or modifying the supplied graph.
    """
    issues = []
    samples = {s['id']: s for s in data['samples']}

    def issue(entity, code, message, severity='error'):
        """Record an issue with the affected entity's identity, code and severity."""
        issues.append({'entityId': entity['id'], 'entityUid': entity['uid'],
                       'code': code, 'severity': severity, 'message': message})

    def check_reference(entity, refs, label, expected_roles, code):
        """Require one named reference and verify the resolved sample's role.

        Unavailable destinations are reported separately as unresolved samples.
        """
        # Validate the named preparation slot, not an unrelated edge elsewhere
        # in the graph. This keeps Component N paired with Component N Volume.
        matches = [r for r in refs if _field_name(r.get('fieldName')) == _field_name(label)]
        if len(matches) != 1:
            issue(entity, code, f"Entity {entity['id']} needs exactly one {label} reference")
        elif matches[0]['sampleId'] in samples:
            target = samples[matches[0]['sampleId']]
            if type_role(target) not in expected_roles:
                issue(entity, code, f"Entity {entity['id']} {label} points to the wrong sample type")

    required = {
        'project': [('PID',), ('VID',)],
        'measurement': [('Barcode Number',), ('Lock Solvent',), ('Buffer',), ('pH', 'pH too'),
                        ('Total Volume',), ('Target Sample Volume',), ('Cocktail Sample Volume',)],
        'target': [('Target Name',), ('Target Concentration',), ('Target Type',),
                   ('Target Sequence',), ('Lock Solvent',), ('Buffer',), ('pH', 'pH too')],
        'component': [('Component Name', 'Component 1 Name'), ('InChI', 'Component 1 InChI'),
                      ('Component Concentration', 'Component 1 Concentration')],
    }
    for entity in data['projects'] + data['datasets'] + data['samples']:
        role = type_role(entity)
        if not entity.get('name'):
            issue(entity, 'missing_entity_name', f"Entity {entity['id']} has no name in LOGS")
        fields = list(custom_fields(entity))
        values = [(_field_name(f.get('name')), f.get('value')) for f in fields]
        if any(not entity['customType'].get(k) for k in ('id', 'name', 'uid')):
            issue(entity, 'missing_type_identity', f"Entity {entity['id']} has incomplete custom type identity")
        needs = list(required.get(role, []))
        if role and role.startswith('cocktail'):
            needs += [('Cocktail Name',), ('Total Volume',)]
            needs += [(f'Component {n} Volume',) for n in range(1, int(role[8:]) + 1)]
        for aliases in needs:
            if not any(label in {_field_name(name) for name in aliases}
                       and value is not None and value != '' for label, value in values):
                issue(entity, 'missing_scientific_value', f"Entity {entity['id']} is missing {aliases[0]}")
        refs = list(sample_references(entity))
        linked = []
        for ref in refs:
            target = samples.get(ref['sampleId'])
            if target is None:
                issue(entity, 'unresolved_sample', f"Entity {entity['id']} references unavailable sample {ref['sampleId']}")
            else:
                linked.append(type_role(target))
        if entity in data['datasets']:
            if role != 'dataset':
                issue(entity, 'historical_dataset_type',
                      f"Dataset {entity['id']} uses source type {entity['customType']['name']}", 'warning')
            if 'measurement' not in linked:
                issue(entity, 'missing_measurement', f"Dataset {entity['id']} has no Measurement Sample reference")
            if role == 'dataset':
                check_reference(entity, refs, 'Measurement Sample', {'measurement'},
                                'wrong_measurement_type')
        elif role == 'measurement':
            if 'target' not in linked or not any(r and r.startswith('cocktail') for r in linked):
                issue(entity, 'incomplete_measurement',
                      f"Measurement sample {entity['id']} must reference a Target Sample and Cocktail Sample")
            check_reference(entity, refs, 'Target Sample', {'target'}, 'wrong_target_reference')
            # The live LOGS type has used "Measurement Sample" as the label for
            # its cocktail slot. Preserve that source label; verify its target.
            cocktail_label = 'Cocktail Sample'
            if not any(label == 'cocktail sample' for label, value in values):
                cocktail_label = 'Measurement Sample'
            check_reference(entity, refs, cocktail_label,
                            {'cocktail1', 'cocktail4', 'cocktail12'}, 'wrong_cocktail_reference')
        elif role and role.startswith('cocktail'):
            count = int(role[8:])
            if linked.count('component') != count:
                issue(entity, 'component_count', f"Cocktail {entity['id']} needs {count} component references")
            for number in range(1, count + 1):
                check_reference(entity, refs, f'Component {number}', {'component'},
                                'wrong_component_reference')
        elif role is None and entity not in data['datasets']:
            issue(entity, 'unsupported_custom_type', f"Entity {entity['id']} has unsupported custom type {entity['customType']['name']}")
    return {'complete': not any(i['severity'] == 'error' for i in issues), 'issues': issues}
