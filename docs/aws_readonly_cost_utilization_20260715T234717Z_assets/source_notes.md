# Source Notes And Chart Map

- Delivery mode: MCP app report; audience: technical.
- Chart: `July month-to-date cost by service`; question: where July cost is concentrated; family: comparison/ranking; type: horizontal bar; fields: service and July UnblendedCost; source: `service_monthly.csv`; supported claim: EC2 and storage dominate spend.
- The chart dataset retains June cost, July share, July daily cost, and rank for auditability beyond the plotted fields.
- Tables are used for exact resource IDs, utilization measurements, tag state, and missing-data labels.
- Resource-level cost coverage is partial and is disclosed adjacent to the affected findings.
- Required technical-report sections are present. Implications are integrated into recommendations. No additional visible methods appendix is needed beyond the durable evidence list in the Markdown companion.
- Lifecycle tables distinguish live provider state, stack state, and owner state. `DELETE_COMPLETE` history is never treated as a live cluster, and stale Resource Groups Tagging API rows are verified against service-specific reads before orphan classification.
