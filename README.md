# FandanGO - NMR@GUF plugin

[![OSV Scanner](https://github.com/FragmentScreen/fandanGO-nmr-guf/actions/workflows/osv-scanner.yml/badge.svg)](https://github.com/FragmentScreen/fandanGO-nmr-guf/actions/workflows/osv-scanner.yml)

FandanGO plugin for the NMR facility at Goethe University Frankfurt (GUF).

## Installation

Install FandanGO as explained in the [FandanGO Core documentation](https://github.com/FragmentScreen/fandanGO-core)

Install the `fandanGO-nmr-guf` plugin into your FandanGO environment once:
```
git clone https://github.com/FragmentScreen/fandanGO-nmr-guf.git

fandango install-plugin --plugin fandanGO-nmr-guf
```

Set up your `plugin.cfg` and `.env` files based on the provided templates.

The plugin requires `fandanGO-aria==2.2.6`. Update an existing environment with
`python -m pip install --upgrade fandanGO-aria==2.2.6`. Field uploads use the
library's `push_safe_cli()` retries, restoring the JSON object before each attempt
and checking for an already accepted field before retrying.

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

By default, the sender reads the saved export and only writes to ARIA. It does
not connect to LOGS or change dataset Notes. Read access is sufficient to
generate an export.

To explicitly append an ARIA record link to each source dataset's Notes after a
confirmed upload, configure `ARIA_RECORD_URL_TEMPLATE` from `.env.template` for
your output service and enable write-back:

```sh
fandanGO execute --name guf --action send-metadata --visit-id VISIT_ID --write-back-logs yes
```

This requires a LOGS API key with dataset edit access and an unambiguous writable
Notes field. Existing notes are preserved. The plugin uses the documented SDK
custom-field setter and `LOGS.update(dataset)`; it does not invent a write endpoint.
Do not enable it for production datasets without authorization. Without this
option, traceability is ARIA → LOGS only; bidirectional links are not claimed.

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
