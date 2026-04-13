# Archive

This directory is the home for historical Daylily documentation and unsupported legacy material. The main docs tree in `README.md` and `docs/` is the supported operator surface. Everything here is reference-only.

## What Lives Here

### 1. Dated pre-rewrite snapshot

`2026-04-pre-rewrite/` is a point-in-time copy of the published docs surface that existed immediately before the canonical rewrite. It preserves the exact relative layout of:

- `README.md`
- `README.md.bland`
- every previously published non-archive Markdown file under `docs/`

Use this when you need to answer "what did the docs say before the rewrite?"

### 2. Older historical material

Other dated or topical archive directories under `docs/archive/` are older reference material that may still be useful for archaeology, screenshots, benchmark notes, or historical context.

### 3. Unsupported legacy assets

Legacy flows, retired environment installers, and historical operator surfaces belong here or in explicit quarantine locations such as:

- `bin/legacy/`
- `daylily_ec/resources/payload/quarantine/`

They are not the supported operator path.

## Reference-Only Source Material

Some workspaces also carry a local `docs_orig/` tree used as a shape and style reference for older Daylily documentation. Treat it as reference-only material when present. It is not the source of truth for current behavior. The current codebase and tests are the source of truth.

## Legacy Appendix

For historical notes on retired flows:

- [legacy/README.md](legacy/README.md)
- [legacy-dayoa-env/](legacy-dayoa-env/)

If you are looking for current instructions, go back to:

- [../overview.md](../overview.md)
- [../operations.md](../operations.md)
- [../aws_setup.md](../aws_setup.md)
- [../testing_and_debugging.md](../testing_and_debugging.md)
