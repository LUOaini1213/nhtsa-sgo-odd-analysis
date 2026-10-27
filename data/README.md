# data/raw

The two CSV files are unmodified copies of NHTSA's Standing General Order 2021-01 incident report data (third amendment form; release of 2026-10-15, covering reports received 2025-06-16 to 2026-09-15). They were downloaded from static.nhtsa.gov on 2026-10-27; NHTSA's landing page is <https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting>.

| File | SHA-256 |
|---|---|
| `SGO-2021-01_Incident_Reports_ADS.csv` | `1dbc685559c54b63806305bbdf367bb6804697c3029b4b2c2a1d4282b301db6b` |
| `SGO-2021-01_Incident_Reports_ADAS.csv` | `07aab76367c8dd0e2ab8fcc895e370d1716c46126d90e08a6506f23bb64f6251` |

These data were published by NHTSA, an agency of the U.S. federal government. Works of the U.S. federal government are not subject to copyright in the United States. NHTSA's own caveats apply: the reports are not normalised by exposure, reporting thresholds differ between ADS and Level 2 ADAS, reports may be incomplete or unverified, and some fields are redacted (see `report.md`, section 3). Nothing in this repository is endorsed by NHTSA.

The pipeline treats these files as read-only and never executes anything from this folder (`python -I`).
