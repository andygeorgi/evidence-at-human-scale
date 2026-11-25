# Sources

Every external source the paper relies on is listed here with the passage it was used for and its stated limits. Public records are cited directly. Internal engagement material is **described, not published**: see [engagement records](engagement-records.md).

## Index

| ID | Source | Used for | Page |
| --- | --- | --- | --- |
| EN01 | National Audit Office of Iceland, follow-up audit of fisheries monitoring, May 2023 | The attention problem | [public records](public-records.md#en01) |
| EN02 | Ministry of Industries (Iceland), appeal ruling of 14 April 2026 on a special fee for over-catch in coastal fishing | C02 lifecycle, invalidation of derivatives and pending approvals, EV12 | [public records](public-records.md#en02) |
| EN03 | Ministry of Industries (Iceland), appeal ruling of 7 November 2025 on the cancellation of catch shares | Deterministic findings that declare rule version, inputs, reference period and scope | [public records](public-records.md#en03) |
| EN04 | Data Protection Authority of Iceland, ruling of 28 March 2023, case 2021030579 | Purpose and permission as enforceable inputs | [public records](public-records.md#en04) |
| EN05 | Data Protection Authority of Iceland, guidance on developing and introducing AI | Non-AI and zero-specialist baselines | [public records](public-records.md#en05) |
| RG01 | NIST AI RMF 1.0 (NIST AI 100-1), January 2023, sections 3.4 and 3.5 | Positioning only | [guidance and standards](guidance-and-standards.md#rg01) |
| RG02 | Regulation (EU) 2024/1689, Article 14 | Positioning only | [guidance and standards](guidance-and-standards.md#rg02) |
| REF-JSON01 | JSON Schema, Draft 2020-12 | Structural contracts | [guidance and standards](guidance-and-standards.md#ref-json01) |
| AZ01–AZ05 | Official Azure documentation, verified 17 November 2026 UTC | Optional product mapping | [Azure sources](azure-sources.md) |
| IN01–IN04 | The author's internal engagement records (not published) | Observations 2, 6 and 7 and the coverage lesson | [engagement records](engagement-records.md) |

## Evidence classes

- **Real public records** are dated single cases; they are never presented as systemic failure.
- **Real internal engagement records** are the author's own working records of case research and prototype tests. They are AI-assisted, prototypes ran on synthetic data, and they are not independent evaluations.
- **Synthetic illustration** is any scenario, fixture or example in this repository. It is invented and belongs to no customer.
- **Not available, not claimed:** any interview, data, approval or outcome from the authority; any customer endorsement; any runtime, human, safety, cost, latency or ROI result for this architecture.

The [claims and limits](../docs/claims-and-limits.md) page states the consequences.

## How this edition was produced

The author is accountable for the content.

## Checking the URLs

`python scripts/check_urls.py --list` prints the complete inventory of external URLs that the repository cites, and where each is cited, without using the network. Without `--list` the script requests each URL and reports the ones that are broken. See [`scripts/README.md`](../scripts/README.md#check_urlspy).

## Third-party material

The [MIT License](../LICENSE) covers what this repository's author wrote. The sources listed here are cited, not copied or relicensed, and each stays under its owner's terms.

## Dates and retrieval

Public records were fetched and the cited passages checked in the original language on 23 November 2026; EN05 is an undated page first retrieved on 16 October 2026 and re-checked on 23 November 2026. Product statements carry their own verification date (17 November 2026 UTC). Links can move or change; the dated description of each source is what the paper relies on.
