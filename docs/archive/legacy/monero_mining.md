> Archived on 2026-03-08. This topic is not part of the current supported operator workflow. Use [../../README.md](../../README.md) and [../README.md](../README.md) for current docs.

# Monero Mining

During cluster creation, you are prompted if you would like to enable the experimental monero mining capability. This is experimental, and you should not enable this feature unless you understand the implications of doing so. The intention was to set this up so that when a headnode or compute node has idle cpu, monero mining could fill in the gap (folks may specify the wallet of their choosing, donate to daylily development or to [the Rare Cancer Research Foundation](https://www.rarecancer.org/)).  This works in that mining will begin, but it does not yet play nicely with running processes and tends to jam up the compute nodes. I advise against using this feature at this time.
