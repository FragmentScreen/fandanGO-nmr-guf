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

## Usage

> [!NOTE]
> On Windows, you can automate this process using the `utils/windows/run.bat` script. For more information, see [windows.md](utils/windows/windows.md).


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

9. Send the previous files (`guf_experiment_metadata.json` and `guf_filtered_analyzed_metadata.json`) to ARIA (e.g. for visit ID 2):
   ```
   fandango execute --name guf --action send-metadata --visit-id 2
   ```

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
