# Public gate source provenance

This directory incorporates the existing public `tempesty-ai/qa-release-gate` implementation as a TMS module.

- Source: [qa-release-gate](https://github.com/tempesty-ai/qa-release-gate)
- Source commit: [`cde5b8c31205ca08fb54f94da1939a8820442444`](https://github.com/tempesty-ai/qa-release-gate/tree/cde5b8c31205ca08fb54f94da1939a8820442444)
- File inventory: [UPSTREAM.json](UPSTREAM.json), SHA-256 of UTF-8 text with LF newlines
- Original code, fixtures, documentation and tests are retained without logic changes.
- Original Git history remains in the source repository; it is not rewritten, deleted or archived.
- Generated reports, caches, Git metadata and environment files are excluded.

The source was already public and uses synthetic data. No company source was used.
No additional license is asserted here; this records provenance within the repository owner's public projects.

TMS imports the workflow evaluator locally. S1/S2/S3 classification lives in `tms/severity.py` and maps
explicitly to the existing P1/P2/P3 input contract; legacy thresholds, CSV engine and exit codes are preserved.
The nested `.github/` files are source records, not active workflows in this repository.
The root TMS workflow tests expected NO_GO outcomes as successful regression checks rather than failed releases.
