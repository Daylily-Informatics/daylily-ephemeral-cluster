# Daylily README Style Guide

This guide captures the style, structure, and operator-documentation patterns used by Daylily READMEs. The goal is not to make every repo identical; the goal is to make every Daylily README feel like it belongs to the same operator-first family.

## Core Principles

1. **Operator first, marketing second.**
   - Explain how to get the thing running.
   - Keep architecture in service of operations.
   - Assume the reader may be under time pressure and debugging AWS at 2 a.m.

2. **Show the exact command.**
   - Prefer real commands over abstract descriptions.
   - Include representative environment variables.
   - When possible, include the path, profile, region, and artifact location.

3. **Preserve Daylily personality.**
   - It is okay to have style.
   - Parenthetical asides, pointed warnings, and a slightly opinionated voice are part of the original docs.
   - Keep the tone direct, practical, and a little human.

4. **Document the lifecycle, not just the creation step.**
   - Daylily docs should cover: create, validate, run, monitor, export, delete.
   - If the README stops at “cluster created,” it is incomplete.

5. **Make failure modes visible.**
   - Known issues, warning notes, quota caveats, and cost traps belong in the README.
   - Do not optimize them away in the name of brevity.

## Voice And Formatting

### Voice

- Use direct, imperative language.
  - Good: “Run preflight before create.”
  - Bad: “Users may wish to consider running preflight.”
- Talk to the operator.
- It is acceptable to be lightly opinionated if the recommendation is grounded in real operating experience.

### Formatting patterns to keep

- Strong section headers with memorable names.
- Short explanatory paragraphs followed by concrete commands.
- Blockquotes for warnings, caveats, and operator advice.
- Italics for context notes and parenthetical guidance.
- A required badge row near the top of every top-level `README.md`.
- Decorative HTML image-divider section breaks for major sections.
- Horizontal rules (`---`) only for minor section divisions.
- Screenshots or diagrams where they reduce ambiguity.

### Daylily-style callouts

Use these frequently:

- `> If this is missing, cluster creation will fail in annoying ways.`
- `> The cluster is ephemeral. The bucket is durable. That is the point.`
- `_only useful if you already have AWS configured_`
- `VERY IMPORTANT` in headings when something is genuinely failure-prone

## Common Daylily README Sections

These sections appear often and should be considered the default structure for Daylily repos.

### 1. Title + one-paragraph summary

State what the repo does in operational terms.

### 1a. Required badge row

Every top-level `README.md` must include a badge row near the top of the document.

- This is mandatory, not optional.
- Each repo should use repo-specific badge URLs, labels, and colors that match that repo.
- For `daylily-ephemeral-cluster`, the canonical badge pattern is:

```markdown
[![Latest release](https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2FDaylily-Informatics%2Fdaylily-ephemeral-cluster%2Fmain%2Fconfig%2Fdaylily_cli_global.yaml&query=%24.daylily.git_ephemeral_cluster_repo_release_tag&label=latest%20release&cacheSeconds=300&color=teal)](https://github.com/Daylily-Informatics/daylily-ephemeral-cluster/releases) [![Latest tag](https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2FDaylily-Informatics%2Fdaylily-ephemeral-cluster%2Fmain%2Fconfig%2Fdaylily_cli_global.yaml&query=%24.daylily.git_ephemeral_cluster_repo_tag&label=latest%20tag&color=pink&cacheSeconds=300)](https://github.com/Daylily-Informatics/daylily-ephemeral-cluster/tags)
```

### 2. Highlights

Usually includes:

- single-command or minimal-command path
- architecture/features bullet list
- why the tool exists

### 3. Architecture at a Glance

Explain the major layers/components in a numbered list. Keep it concrete.

Typical components:

- control plane / CLI
- cloud resources
- data plane / storage
- workflow registry
- monitoring / budget hooks

### 4. Reference Data / Shared State

For Daylily systems, this is usually crucial.

Document:

- where durable data lives
- what is region-scoped
- what is mounted/shared
- what survives cluster deletion

### 5. Installation -- Quickest Start

This section should contain the shortest supported path, not just a link.

It should include:

- environment setup
- the main CLI entrypoint
- any required env vars
- a reference to the deeper runbook if one exists

### 6. Installation -- Detailed

This is where Daylily READMEs become truly useful.

Include:

- AWS identity assumptions
- IAM/policy notes
- quotas
- local prerequisites
- credential/profile setup
- config file preparation
- success expectations

### 7. Create / Validate / Operate

A Daylily README should show the whole operator loop:

- create the thing
- validate it worked
- connect to it
- run the workflow
- monitor it
- export the results
- delete it safely

### 8. Costs

If the repo creates cloud resources, include a cost section.

Document:

- major cost drivers
- stale-resource traps
- budget/tag/heartbeat guidance
- how to inspect pricing or spend

### 9. Monitoring / Troubleshooting / Known Issues

This is not optional in operator-facing repos.

At minimum include:

- where to look when provisioning fails
- most common quota/IAM/storage failure modes
- the main monitoring commands or dashboards

### 10. Documentation / Historical Material / Contributing / Versioning

Close by linking the deeper docs, archives, contributing guide, and versioning story.

## Command And Example Rules

1. **Use current canonical commands.**
   - Do not preserve stale commands just because they appeared in an older README.
   - If a repo moved from shell scripts to a Python CLI, the README should reflect that.

2. **Keep representative examples inline.**
   - Do not reduce the README to a link directory.
   - Even if a deeper doc exists, keep at least one real example in the README.

3. **Prefer copy-pasteable snippets.**
   - Include exports, file paths, and argument names.
   - Avoid pseudo-commands unless absolutely necessary.

4. **Show what success looks like.**
   - Include at least one expected artifact, output, screenshot, or sanity-check command.

## Visual Style Rules

- Use screenshots where they clarify operations, costs, or topology.
- Use diagrams where they reduce explanation burden.
- Keep distinctive Daylily flourishes if they still render cleanly.
- Do not remove visuals just to make the README look shorter.

### Required major section breaks

Major section breaks must use the decorative HTML image-divider pattern rather than plain Markdown alone.

- This is a style requirement for Daylily top-level READMEs.
- The divider color palette should be unique per repository.
- In this repo, `ORIG_README.md` is the canonical example for `daylily-ephemeral-cluster`.
- For `daylily-ephemeral-cluster`, preserve this divider pattern exactly as the canonical example:

```html
<p valign="middle"><a href=http://www.workwithcolor.com/color-converter-01.htm?cp=ff8c00><img src="docs/images/0000002.png" valign="bottom" ></a></p>

<p valign="middle"><img src="docs/images/000000.png" valign="bottom" ></p>
```

### Minor section breaks

Minor section divisions may use `---` instead of the decorative image-divider pattern.

## What To Preserve From Older Daylily READMEs

When modernizing an old Daylily README, preserve these qualities even if commands change:

- operator-first sequencing
- warnings and caveats
- example-heavy workflow guidance
- costs and deletion safety notes
- practical AWS troubleshooting advice
- a distinct voice instead of generic SaaS-speak

## What To Avoid

- turning the README into only a repo landing page
- replacing procedures with vague bullets
- hiding all detail in linked docs
- removing warnings because they are “messy”
- deleting screenshots or outputs that help operators confirm state
- flattening a runbook into an abstract architecture summary

## Recommended Skeleton

```markdown
# <Repo Name>

<One-paragraph operator summary>

<required badge row>

## Highlights
### Single Command <Action>
### Architecture & Features

## Architecture at a Glance

## <Reference Data / Shared State / Inputs>

## Cost Monitoring & Budget Enforcement

## Installation -- Quickest Start

## Installation -- Detailed

### <Create / Validate / Operate>

## Working With <The System>

## Costs

## Other Monitoring Tools

## Known Issues

## Documentation

## Historical Material

## Contributing

## Versioning
```

## README Review Checklist

Before calling a Daylily README “done,” check:

- Does it include a required badge row near the top of the top-level `README.md`?
- Does it contain a real quickstart?
- Does it include at least one current canonical command?
- Does it explain the operator lifecycle after provisioning?
- Does it mention cost traps and deletion safety?
- Does it surface the most common failure modes?
- Do major section breaks use the required decorative HTML image-divider pattern?
- Are plain `---` separators used only for minor section divisions?
- Does it still sound like Daylily, not a generic AI summary?

If the answer to any of those is “no,” the README probably got flattened too far.

## Doc Ownership And Review

Every Daylily repo should have an obvious documentation owner, even if that owner is just “the team maintaining the CLI.”

- assign one primary owner for the README and operator docs
- review the README whenever CLI commands, config defaults, or workflow entrypoints change
- re-check commands, links, screenshots, and image paths before release
- do a lightweight README review on a regular cadence if the repo changes often
- treat stale operator docs as an operational bug, not a cosmetic issue