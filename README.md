# FandanGO - NMR@GUF plugin

[![OSV Scanner](https://github.com/FragmentScreen/fandanGO-nmr-guf/actions/workflows/osv-scanner.yml/badge.svg)](https://github.com/FragmentScreen/fandanGO-nmr-guf/actions/workflows/osv-scanner.yml)

FandanGO plugin for the NMR facility at Goethe University Frankfurt (GUF), automating metadata collection from LOGS and Excel, generating structured JSON files, and transferring metadata to ARIA.

For an overview of the workflow and a brief explanation of each Python function,
see the [function guide](#function-guide).

## Installation

Install FandanGO as explained in the [FandanGO Core documentation](https://github.com/FragmentScreen/fandanGO-core)

Install the `fandanGO-nmr-guf` plugin into your FandanGO environment once:
```
git clone https://github.com/FragmentScreen/fandanGO-nmr-guf.git

fandango install-plugin --plugin fandanGO-nmr-guf
```

Set up your `plugin.cfg` and `.env` files based on the provided templates.

The plugin requires `fandanGO-aria==2.2.6`. Update an existing environment with
`python -m pip install --upgrade fandanGO-aria==2.2.6`

Experiment exports contain: `projects`, `datasets`,
`samples`, verified `customTypes` and a `dataQuality` report. Sample references
resolve to complete sample entries, including shared target, cocktail and
component samples. All custom-value sections and unit-bearing field labels are
preserved. Concentrations are not calculated or guessed.

## Usage

> [!NOTE]
> On Windows, you can automate this process using the `utils/windows/run.bat` script. For more information, see [the Windows readme](utils/windows/README).


1. Create a new FandanGO project:
   ```
   fandango create-project --name guf
   ```

2. Check it was created:
   ```
   fandango list-projects
   ```

3. Link this project to the `fandanGO-nmr-guf` plugin:
   ```
   fandango link-project --name guf --plugin fandanGO-nmr-guf
   ```

4. Check which "actions" can be executed for this project:
   ```
   fandango execute --name guf --help
   ```

5. Generate project metadata from LOGS system (will create `guf_experiment_metadata.json` file):
   ```
   fandango execute --name guf --action generate-experiment-metadata --logs-project-id 227
   ```

6. Generate library metadata for compound 'cocktails' from excel file (will create `guf_analyzed_metadata.json` file):
   ```
   fandango execute --name guf --action generate-library-from-excel --input <cocktails>.xlsx
   ```

7. Generate filtered library metadata (will create `guf_filtered_analyzed_metadata.json` file):
   ```
   fandango execute --name guf --action generate-library-metadata
   ```

8. Inspect our project outputs:
   ```
   fandango execute --name guf --action print-project
   ```

9. Send the previous files (`guf_experiment_metadata.json` and `guf_filtered_analyzed_metadata.json`) to ARIA in one `JSON_LOGS` field (e.g. for visit ID 2):
   ```
   fandango execute --name guf --action send-metadata --visit-id 2
   ```

   The visit must match the VID in the exported LOGS project. The sender includes
   the full experiment graph and both analysis products when registered:
   `analyzedMetadata` from `generate-library-from-excel`, and `libraryAnalysis`
   from `generate-library-metadata`.

## Incomplete and historical metadata

Generation preserves the available metadata and reports missing references,
missing scientific values, unsupported types and historical dataset labels in
`dataQuality.issues`. Historical labels are not rewritten to modern types.
Unknown concentrations or volumes are never replaced with zero. A transient
LOGS retrieval failure leaves the previous export file intact.

Uploads reject scientifically incomplete graphs by default. After reviewing the
quality report, explicitly preserve the available metadata with:

```sh
fandanGO execute --name guf --action send-metadata --visit-id VISIT_ID --incomplete-policy preserve
```

This retains the quality report in ARIA; it does not repair missing information.

## LOGS–ARIA links and retries

There are two separate steps. First, `generate-experiment-metadata` reads the
experiment information from LOGS and saves a JSON file on your computer. This
requires a LOGS API key with read access. Later, `send-metadata` reads that saved
file and uploads its contents to ARIA.

A normal upload changes ARIA only:

```sh
fandanGO execute --name guf --action send-metadata --visit-id VISIT_ID
```

The uploaded metadata includes links to the original LOGS datasets. Someone
viewing the metadata in ARIA can therefore follow those links back to LOGS.
The source datasets in LOGS, including their Notes, stay unchanged. This upload
does not need LOGS edit permission or a connection to LOGS.

**Write-back means adding a link in the other direction: from LOGS to ARIA.**
With `--write-back-logs yes`, the plugin also connects to LOGS. After ARIA confirms
the metadata upload, it appends a line to each exported dataset's Notes:

```text
ARIA record: <URL of the uploaded ARIA record>
```

For example, Notes containing `Measured at 298 K` would keep that text and gain
the ARIA link underneath it. The plugin does not replace the existing Notes or
change the scientific data. A person opening the dataset in LOGS can then follow
the new link to its ARIA record. Adding this line is still a change to LOGS, so it
requires a LOGS API key with edit permission for the affected datasets.

`ARIA_RECORD_URL_TEMPLATE` tells the plugin how to build that ARIA record link.
Copy the setting from `.env.template` into your `.env` file and set its host to
your ARIA output website—the website where people view records, rather than the
GraphQL API endpoint. The plugin fills in placeholders such as `{record_id}`
using the identifiers returned by ARIA. Then explicitly enable write-back:

```sh
fandanGO execute --name guf --action send-metadata --visit-id VISIT_ID --write-back-logs yes
```

Replace `VISIT_ID` with the VID in the exported LOGS project. Each dataset also
needs an unambiguous writable Notes field. If you only want to upload to ARIA and
leave LOGS unchanged, omit `--write-back-logs yes`. Enable it only when you intend
and are authorized to add the Notes links. Both upload modes require ARIA edit
access to the selected visit.

| Command option | Changes in ARIA | Changes in LOGS |
| --- | --- | --- |
| No write-back option | Uploads metadata containing LOGS dataset links. | None. |
| `--write-back-logs yes` | Uploads the same metadata. | Appends the ARIA record link to each source dataset's Notes after upload confirmation. |

The incomplete-data policy is a separate setting. If you have reviewed an
incomplete export and intend to upload the available metadata, add
`--incomplete-policy preserve` to either command. It does not grant LOGS edit
permission or enable write-back.

A local receipt records known bucket, record and field IDs and completed
backlinks. Retry with unchanged export and analysis files after a partial failure.
The sender checks an existing record for an identical `JSON_LOGS` field before
uploading again, covering a lost field response. An unknown bucket or record
creation outcome requires manual inspection rather than automatically creating a
duplicate. Concurrent uploads for the same project are not supported. Avoid
concurrent Notes edits while writing backlinks; there is no cross-system transaction.

ARIA must advertise the `LOGS` schema and `JSON_LOGS` field type. The installed
`ddapi-record-logs` library contains the base handler but some versions register
only its specialized variants. Register `LOGSJSONHandler` in the service if it is
missing. The sender checks capabilities before creating objects and passes a
Python object to the ARIA SDK, which serializes it exactly once. Configure the
GraphQL/proxy body limits for the size of a complete metadata graph.

## Function guide

This section describes the Python functions in `nmrguf/`, including internal
helpers. Names beginning with `_` are implementation helpers rather than CLI
commands. The same function name can appear in different action modules.

### How the pieces fit together

1. `Plugin` registers CLI arguments and connects each action to its `perform_action()` entry point.
2. `generate-experiment-metadata` reads LOGS and builds a graph containing projects, datasets and their referenced samples. It saves the export and its data-quality report.
3. `generate-library-from-excel` creates the full analysis file. `generate-library-metadata` filters that analysis to the mixes present in the experiment.
4. `send-metadata` reads these saved files, validates them, and uploads one `JSON_LOGS` field to ARIA. It saves progress in the local project database so retries can reuse known remote objects.
5. If explicitly enabled, LOGS write-back appends the confirmed ARIA record URL to dataset Notes. Default uploads leave LOGS unchanged.

Most action functions return `(success, info)`. Their `perform_action()` wrappers
turn this into `{'success': success, 'info': info}` for FandanGO to display.
Metadata helpers return dictionaries, lists or generators and raise exceptions
when they cannot safely interpret the input; the calling action handles errors.

### CLI registration — [`nmrguf/__init__.py`](nmrguf/__init__.py)

| Function | What it does |
| --- | --- |
| `Plugin.define_args()` | Defines each action's CLI options, help text and allowed values, including the visit ID, incomplete-data policy and optional LOGS write-back. |
| `Plugin.define_methods()` | Maps action names such as `send-metadata` to the corresponding module's `perform_action()` function. |

### Experiment export — [`generate_experiment_metadata.py`](nmrguf/actions/generate_experiment_metadata.py)

| Function | What it does |
| --- | --- |
| `generate_experiment_metadata(project_name, logs_project_id)` | Connects to LOGS, retrieves the requested project and its datasets, calls `build_metadata()`, and saves the resulting JSON. Writes a temporary file before replacing the previous export, registers the output path in the local database, and reports completeness and issue count. |
| `perform_action(args)` | Reads the project name and LOGS project ID from CLI arguments, runs generation, and returns its result to FandanGO. |

### Graph construction and validation — [`logs_metadata.py`](nmrguf/logs_metadata.py)

The graph stores entities once in `projects`, `datasets` and `samples`.
`sampleReferences` connect them by ID/UID. Original custom values, field labels
and units remain in each entity's `customValues`; `customTypes` holds verified
type definitions. `dataQuality` records missing information without inventing it.

| Function | What it does |
| --- | --- |
| `type_role(entity)` | Recognizes a project's, dataset's or sample's role from its custom-type name. Distinguishes 1-, 4- and 12-component cocktails and returns `None` for an unrecognized type. |
| `custom_fields(entity)` | Yields custom fields from every custom-value section, preserving their source order. |
| `custom_fields.walk(items)` | Internal recursive helper that descends into sections to find fields; it does not follow remote sample references. |
| `custom_value(entity, name)` | Finds one populated custom value by its exact field name, such as `PID` or `VID`. Returns `None` if absent and rejects multiple populated matches as ambiguous. |
| `sample_references(entity)` | Reads fields typed `Sample` or `SampleArray` and yields their field name/ID and referenced sample ID/UID. Rejects malformed references. |
| `serialize_entity(entity, dataset=False)` | Fetches the entity, retrieves additional dataset information when requested, copies its metadata into a dictionary, and adds its LOGS UI URL and sample references. Retains custom-type identity without repeating the type's entire field schema. |
| `_validate_identity(entity, allow_untyped=False)` | Checks the identity fields needed to identify an entity safely. The relaxed mode allows missing names/type identity to be reported later as data-quality issues while still requiring entity ID, UID and URL. |
| `build_metadata(logs, projects, datasets)` | Builds the graph, follows sample references recursively, and caches resolved and unavailable samples so shared references and cycles do not cause repeated lookups. Verifies type definitions and attaches the quality report. A retrieval failure raises an error; unavailable samples remain explicitly unresolved. |
| `validate_metadata(data, allow_incomplete=False)` | Checks the hierarchy structure, entity lists, duplicate IDs, reference consistency, UID consistency and saved type definitions. Recomputes the quality report and rejects incomplete scientific metadata unless explicitly allowed. |
| `verify_custom_types(logs, data)` | Retrieves authoritative custom-type definitions from LOGS in one batch, checks entity type names/UIDs against them, and fills abbreviated type identities from the returned definitions. |
| `_field_name(name)` | Normalizes case, spacing and bracketed units for validation comparisons only. It never rewrites the original labels or values in the export. |
| `audit_metadata(data)` | Produces `{'complete': ..., 'issues': [...]}` by checking required scientific values, measurement/target/cocktail/component relationships, cocktail sizes, missing references and historical or unsupported types. It does not calculate concentrations. |
| `audit_metadata.issue(...)` | Internal helper that records an issue with its entity ID/UID, code, severity and explanation. |
| `audit_metadata.check_reference(...)` | Internal helper that verifies a named reference points to exactly one sample of the expected role. This prevents an unrelated valid sample from hiding a wrong reference and keeps each Component N associated with its own preparation volume. |

### Excel analysis — [`generate_library_metadata_from_excel.py`](nmrguf/actions/generate_library_metadata_from_excel.py)

These functions build analysis metadata from Excel. They do not replace the
scientific metadata of LOGS Component Samples.

| Function | What it does |
| --- | --- |
| `generate_library_metadata(project_name, input_file)` | Reads the `Fragment Library`, `Summary`, `Protein Sequence` and `cocktails` sheets, groups compounds by mix, adds SMILES and binding-analysis information, saves `<project>_analyzed_metadata.json`, and registers its path. The protein-sequence sheet is read but is not currently included in the output. |
| `find_compounds_by_mix(mix_name)` | Nested helper that returns the compound names assigned to a mix. |
| `find_SMILES_Formula_by_compound(compound_name)` | Nested helper that looks up a compound's SMILES in the fragment library, returning `None` when not found. |
| `find_summary_info_from_compound(compound_name)` | Nested helper that looks up Bindingstate, Waterlogsy, T2, CSP and STD results for a compound. Returns `None` when no matching summary row exists. |
| `package_info(mix_name)` | Nested helper that combines a mix's compound names, SMILES and summary results into a dictionary. |
| `convert_mix_to_json(mix)` | Nested helper that formats the current mix's compound dictionary as JSON-like text for the existing assembly/parsing step. It uses the surrounding loop's `mix_name`. |
| `perform_action(args)` | Passes the CLI project name and input workbook path to the Excel generation function and returns the action result. |

### Analysis filtering — [`generate_library_metadata.py`](nmrguf/actions/generate_library_metadata.py)

| Function | What it does |
| --- | --- |
| `generate_library_metadata(project_name)` | Reads the registered experiment and full analysis files, keeps mixes represented by the experiment, saves `<project>_filtered_analyzed_metadata.json`, and registers its path. |
| `filter_json(mix_list, file_path)` | Loads the analysis JSON and keeps entries whose mix keys occur in `mix_list`. It selects mixes; it does not recalculate binding results. |
| `generate_mix_list(file_path)` | Extracts unique mix names from dataset names by taking the text before `/`. Accepts both the current experiment format and the old flattened format. |
| `perform_action(args)` | Runs analysis filtering for the CLI project name and returns the result. |

### ARIA upload — [`send_metadata.py`](nmrguf/actions/send_metadata.py)

| Function | What it does |
| --- | --- |
| `_is_permission_error(error)` | Recognizes HTTP 403 responses and permission-denial text, including errors wrapped by the ARIA client. |
| `_record_url(template, **values)` | Builds the public ARIA record link from the configured template, URL-escapes substituted identifiers, and checks the URL and placeholders. A template must contain `{record_id}`. |
| `_verify_aria_types(visit)` | Queries the destination to confirm it advertises the `LOGS` record schema and `JSON_LOGS` field type before creating objects. |
| `_recover_field(visit, record_id, payload)` | Reads an existing record's fields and looks for one identical `JSON_LOGS` payload. Returns its field ID to avoid another upload after a lost response; rejects multiple matches as ambiguous. |
| `_RetryingFieldUpload.__init__(manager, payload)` | Creates an upload adapter around the ARIA manager and keeps an untouched copy of the intended payload. The original manager handles API requests and object storage. |
| `_RetryingFieldUpload.push(field)` | Before another attempt, checks whether the preceding attempt already created the field. Otherwise restores the original JSON object and delegates to the manager's `push()`, preventing repeated JSON encoding by ARIA 2.2.6. |
| `_RetryingFieldUpload.push_safe_cli(field)` | **Inherited from `fandanGO-aria`, not defined in this repository.** Applies the library's retry/backoff policy and prints attempts. Each attempt calls the adapter's `push()` described above. |
| `send_metadata(project_name, visit_id, incomplete_policy='reject', write_back_logs=False)` | Validates the saved experiment and matching VID, adds available full/filtered analysis, and creates or reuses the ARIA bucket, `LOGS` record and single `JSON_LOGS` field. Saves progress, handles errors and optionally writes LOGS backlinks after field confirmation. Rejects incomplete scientific metadata by default. |
| `send_metadata.save_receipt()` | Nested helper that saves the current upload progress under `aria_deposition_receipt` in the local project database. Stores known IDs, payload fingerprint, destination and completed backlinks. |
| `perform_action(args)` | Reads the CLI arguments, selects the incomplete-data policy and explicit write-back setting, calls the sender and returns its result. |

The sender includes `analyzedMetadata` when the full Excel analysis is registered,
`libraryAnalysis` when the filtered analysis is registered, and an `aria` object
containing visit, bucket and record IDs. The ARIA SDK serializes the field content
for its GraphQL request. The public `record_url`, when configured, is returned in
the local receipt; it is also written to LOGS only when write-back is enabled.

Receipts are matched by payload fingerprint, visit ID and ARIA endpoint. A changed
payload starts a new deposition. Unknown bucket/record creation outcomes require
manual inspection rather than automatically creating a duplicate. Uploads and
LOGS updates are separate operations, so `metadata_uploaded: True` can accompany
a backlink error. Concurrent uploads for the same project are not supported.

### Optional backlinks — [`logs_backlinks.py`](nmrguf/logs_backlinks.py)

| Function | What it does |
| --- | --- |
| `backlink_dataset(logs, exported, record_url=None)` | Retrieves the current source dataset, checks its UID against the export, finds an unambiguous Notes field, detects an existing identical link, and checks edit/read-only permissions when an update is needed. Returns the dataset, Notes metadata and whether the link already exists. |
| `write_backlink(logs, exported, record_url)` | Preserves the current Notes text, appends the ARIA record link once using the SDK custom-field setter, and calls `LOGS.update(dataset)`. Returns without updating when the same link already exists. |

These helpers run only with `--write-back-logs yes`. They require dataset edit
access. Reading the current Notes reduces the risk of overwriting stale text,
but concurrent Notes changes are not protected by a cross-system transaction.

### LOGS discovery

| Module/function | What it does |
| --- | --- |
| [`get_logs_types.py`](nmrguf/actions/get_logs_types.py): `get_custom_types(project_name, search_term=None)` | Searches LOGS custom types and saves the returned type IDs in the local project database. |
| `get_logs_types.fetch_custom_types(logs_session, search_term)` | Performs the LOGS custom-type query using a lowercase search term. |
| `get_logs_types.perform_action(args)` | Runs the custom-type search using the CLI project name and optional search term. |
| [`get_logs_projects.py`](nmrguf/actions/get_logs_projects.py): `get_project_ids(project_name, type_id=None)` | Finds LOGS projects using the supplied type ID, or the previously saved type IDs, and stores their project IDs locally. |
| `get_logs_projects.fetch_projects(logs_session, type_ids)` | Performs the LOGS project query filtered by custom-type IDs. |
| `get_logs_projects.perform_action(args)` | Runs project discovery using the CLI project name and optional LOGS type ID. |

### Local project storage — [`sqlite_db.py`](nmrguf/db/sqlite_db.py)

These helpers use the local plugin database configured by `plugin.cfg`. Updating
this database does **not** modify LOGS datasets or ARIA records.

| Function | What it does |
| --- | --- |
| `_db_conn()` | Builds the `fGOdb.ProjectInfo` interface using `plugin.cfg` and the plugin's database name. |
| `update_project(project_name, key, value)` | Saves a local project metadata value, such as a generated file path or upload receipt. |
| `get_project_info(project_name)` | Returns column labels and all locally stored metadata rows for a project. |
| `get_project_metadata(project_name)` | Retrieves the locally stored filtered-library and experiment metadata entries using the database library's multi-key lookup. |
| `get_project_value(project_name, key, default)` | Reads a local project value and returns `default` if the stored value is missing or otherwise falsey. |

### Project display — [`print_project.py`](nmrguf/actions/print_project.py)

| Function | What it does |
| --- | --- |
| `print_project(project_name)` | Reads the local project metadata and prints it as a table, returning the rows and success status. |
| `perform_action(args)` | Runs project display for the CLI project name and returns the result. |

## Security Scanning

This repo uses [OSV Scanner](https://github.com/google/osv-scanner) for vulnerability detection.

**When it runs:**
- Daily at 03:00 UTC (full scan)
- On PRs targeting main (changed deps only)
- On push to main (full scan)

**If vulnerabilities are found:**
1. Check the [Security tab](../../security) for alerts
2. To ignore false positives, add entries to `osv-scanner.toml`:
   ```toml
   [[IgnoredVulns]]
   id = "GHSA-xxxx-xxxx-xxxx"
   reason = "Justification"
   ```

**References:**
- [OSV Scanner docs](https://google.github.io/osv-scanner/)
- [GitHub Action](https://github.com/google/osv-scanner-action)
- [OSV Database](https://osv.dev/)
