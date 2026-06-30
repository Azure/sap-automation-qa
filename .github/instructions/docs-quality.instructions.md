---
applyTo: "articles/sap/automation/**/*.md"
---

# Microsoft Learn Documentation Standards for SAP on Azure

These rules apply automatically when editing documentation articles under
`articles/sap/automation/`. Follow them for all new content and edits.

## YAML Front Matter (required)

Every article must begin with front matter containing at minimum:

```yaml
---
title: "<concise title, max 60 characters>"
description: "<one-line summary for SEO, max 160 characters>"
ms.date: MM/DD/YYYY
ms.topic: article | how-to-guide | concept | reference
ms.service: sap-on-azure
ms.subservice: sap-automation
author: <GitHub username>
ms.author: <Microsoft alias>
---
```

- `ms.date` must reflect the date of the last substantive content edit.
- `ms.topic` values: use `how-to-guide` for procedural content, `concept` for
  explanations, `reference` for parameter/API docs, `article` for overviews.

## Formatting

- **Callouts**: use `[!NOTE]`, `[!TIP]`, `[!WARNING]`, `[!IMPORTANT]` — never HTML.
- **Internal links**: relative paths (`../overview.md`), not absolute URLs.
- **Code blocks**: always specify language (`bash`, `yaml`, `powershell`, `json`).
- **Tables**: markdown tables only, max 5 columns. Use lists for complex content.
- **Headings**: Title Case for H2, sentence case for H3 and below. Never skip levels.
- **Lists**: use `-` for unordered, `1.` for ordered. No blank lines between items.

## Content Rules

- **Audience**: SAP Basis administrators who know SAP but are learning Azure.
- **Structure**: lead with "what" and "why" before "how".
- **Prerequisites**: include a prerequisites section for any procedural article.
- **SAP Notes**: reference by number with link: `[SAP Note 1928533](https://...)`.
- **Azure resources**: use backtick formatting for resource names and SKUs
  (`Standard_D4ds_v5`, `Premium_LRS`).
- **No duplication**: never duplicate content from another article. Use relative links
  or Learn includes (`[!INCLUDE [description](path)]`) instead.
- **Parameters**: document with a table (Parameter | Required | Description | Example).

## Prohibited

- No screenshots without descriptive alt text.
- No hardcoded subscription IDs, resource group names, or IP addresses in examples.
- No version-specific statements without date context ("As of June 2026, ...").
- No first person ("I", "we") — use second person ("you") or imperative mood.
- No marketing language or superlatives ("best-in-class", "seamless", "powerful").
