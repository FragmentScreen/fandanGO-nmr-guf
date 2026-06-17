# FandanGO - nmr-guf plugin

[![OSV Scanner](https://github.com/FragmentScreen/fandanGO-nmr-guf/actions/workflows/osv-scanner.yml/badge.svg)](https://github.com/FragmentScreen/fandanGO-nmr-guf/actions/workflows/osv-scanner.yml)

FandanGO plugin designed for NMR facility at GUF university (Frankfurt, Germany).

## Installation

Install FandanGO as explained at [https://github.com/FragmentScreen/fandanGO-core](https://github.com/FragmentScreen/fandanGO-core)

Download and install the `fandanGO-nmr-guf` plugin in FandanGO once:
```
git clone https://github.com/FragmentScreen/fandanGO-nmr-guf.git

fandango install-plugin --plugin fandanGO-nmr-guf
```

Set up your plugin.cfg and .env files based on their templates.

## Usage

Create FandanGO project:
```
fandango create-project --name guf
```

You can check it was created:
```
fandango list-projects
```
	
Link this project to the `fandango-nmr-guf`:
```
fandango link-project --name guf --plugin fandanGO-nmr-guf
```

You can check which "actions" can be executed for this project:
```
fandango execute --name guf --help
```

Generate project metadata from LOGS system (will create `guf_experiment_metadata.json` file):
```
fandango execute --name guf --action generate-experiment-metadata --logs-project-id 227
```

Generate library metadata for compound 'cocktails' from excel file (will create `guf_analyzed_metadata.json` file):
```
fandango execute --name guf --action generate-library-from-excel --input <cocktails>.xlsx
```

Generate filtered library metadata (will create `guf_filtered_analyzed_metadata.json` file):
```
fandango execute --name guf --action generate-library-metadata
```

Check what we have for the FandanGO project:
```
fandango execute --name guf --action print-project
```

Send the previous files (`guf_experiment_metadata.json` and `guf_filtered_analyzed_metadata.json`) to ARIA (for visit ID 2):
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
