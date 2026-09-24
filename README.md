# Kairon Insights local page-router prototype

Standalone PDF page-selection benchmark. All inference runs on `gx10-fbb7`; it never calls the existing 27B extractor. See [application README](page-router/README.md) and [verified SemIf API](page-router/RESEARCH.md).

Routing objectives are compiled compactly and every prompt is token-checked before inference. See the [40-page regression report](page-router/REGRESSION_REPORT.md) for validation of the 80-field benchmark fix.

From this directory on NicoPC WSL:

```bash
./run.sh
```

Open **http://localhost:8507** and upload the PDF, instructions JSON, and reference XLSX. Keep the terminal open for the private SSH tunnel. The app retains its loaded model across analyses.

```bash
./fetch-results.sh    # copy remote JSON, CSV, and logs here
```

Initial installation/reinstallation: `./setup-remote.sh` (internet required for dependencies/weights). Normal startup is offline. `./sync-remote.sh` transfers source changes without touching remote models, results, or the existing extraction service.
