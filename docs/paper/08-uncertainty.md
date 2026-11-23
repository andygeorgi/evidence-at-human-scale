# 8. Uncertainty is part of the result

[← 7. One interaction](07-one-interaction.md) · [Paper contents](README.md) · [Next: authority →](09-authority.md)

Absence has several meanings, and collapsing them changes decisions. An expected input may not arrive; a completed retrieval may return no relevant record; a principal may lack access; a dependency may fail; an explicit observation may report absence. These are different states with different remedies and different implications for action.

## Seven labels that must not collapse

| State | Meaning the reader must retain |
| --- | --- |
| `missing` | Expected input was not obtained; the reason may be unknown. |
| `not_retrieved` | A completed scoped retrieval found no relevant record. This is not evidence of absence. |
| `inaccessible` | The current principal lacks permission. Existence and reason are disclosed only when permitted. |
| `unavailable` | A source or dependency could not provide data, distinct from permission denial. |
| `negative` | An explicit, adequately scoped absence observation, with method, time, and coverage. |
| `not_assessed` | A check or assessment was not performed. |
| `stale` | An available record fails its applicable freshness requirement. |

Partial coverage, exclusions, and omissions remain visible with each applicable state. Evaluation or publication NOT ASSESSED denotes insufficient assessment coverage, not a negative source finding or a completed test. A gap can limit a conclusion or block an action that depends on its missing basis; a low-confidence severe signal can still require attention. The system must not manufacture a negative, or disclose protected existence to explain an omission.

<!-- figure:F09:start -->
<!-- figure:F09:end -->

An explicit uncertainty model also makes recovery accountable. It directs the source owner, access owner, assessor, or operator toward the actual reason for the limitation. That does not guarantee recovery. It prevents a smooth summary from disguising why a consequential choice remains unsupported.

**See it working:** one synthetic decision packet in the [worked example](../../examples/README.md) carries all seven labels, each with the reference the contract requires. The schema rejects, for instance, a `not_retrieved` entry that does not point to a completed retrieval.

[← 7. One interaction](07-one-interaction.md) · [Paper contents](README.md) · [Next: authority →](09-authority.md)
