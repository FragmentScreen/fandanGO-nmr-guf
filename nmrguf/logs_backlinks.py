"""Explicitly enabled LOGS write-back using the LOGS-Py entity update API."""
from LOGS.Entities import DatasetRequestParameter

from nmrguf.logs_metadata import custom_fields


def backlink_dataset(logs, exported, record_url=None):
    """Read current Notes and verify the dataset identity before any update."""
    found = logs.datasets(DatasetRequestParameter(ids=[exported['id']])).toList()
    if len(found) != 1 or found[0].id != exported['id']:
        raise ValueError(f"Cannot find LOGS dataset {exported['id']} for write-back")
    dataset = found[0]
    dataset.fetch()
    data = dataset.toDict()
    if data.get('uid') != exported['uid']:
        raise ValueError(f"UID mismatch for LOGS dataset {exported['id']}")
    notes = [f for f in custom_fields(data)
             if f.get('name') == 'Notes' and f.get('dataType') == 'String']
    if len(notes) != 1:
        raise ValueError(f"LOGS dataset {exported['id']} needs an unambiguous Notes field")
    notes = notes[0]
    if record_url and f'ARIA record: {record_url}' in (notes.get('value') or '').splitlines():
        return dataset, notes, True
    for section in (data.get('customType') or {}).get('sections') or []:
        for definition in section.get('customFields') or []:
            if definition.get('id') == notes['id'] and definition.get('readOnly'):
                raise PermissionError(f"LOGS dataset {exported['id']} Notes field is read-only")
    if (data.get('permissions') or {}).get('canEdit') is False:
        raise PermissionError(f"LOGS API key cannot edit dataset {exported['id']}; "
                              'write-back needs dataset edit permission')
    return dataset, notes, False


def write_backlink(logs, exported, record_url):
    """Preserve current Notes, append one record link, then use LOGS.update()."""
    dataset, notes, exists = backlink_dataset(logs, exported, record_url)
    if exists:
        return
    custom_field = dataset.customValues.customField(notes['id'])
    if custom_field is None:
        raise ValueError(f"Cannot access Notes for LOGS dataset {exported['id']}")
    previous = notes.get('value') or ''
    custom_field.value = previous + ('\n\n' if previous else '') + 'ARIA record: ' + record_url
    logs.update(dataset)
