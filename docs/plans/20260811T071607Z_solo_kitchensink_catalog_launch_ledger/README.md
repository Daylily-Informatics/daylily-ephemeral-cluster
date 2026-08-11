# Solo kitchen-sink six-manifest inputs

The active launch inputs for DYEC 16.1.81 / DayOA 13.4.30 are the six TSVs in
each of these directories:

- `manifests/ilmn`
- `manifests/ont`
- `manifests/ultima`

Pass the selected directory explicitly as `dyec catalog render/launch
--manifest-dir`. These are provider-neutral DayOA 13 six-manifest contracts;
the legacy source and migration files in this local working directory are not
workflow inputs and are not part of the release.

All `Z-` identities are reserved non-customer validation fixtures. They must
not be registered, persisted as owner-issued identities, or accepted for a
customer release.
