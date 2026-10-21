# Validate company documents privately

Real-document validation remains dependent on readable exports from an authorized source owner. The public demonstration does not grant access to private Google Sites, Docs, or Slides.

Put exports and the manifest under `loredock-local/private/company/`, outside the checkout. Export policies, the vision document, and two recent all-hands. Check text against originals, including conditions, tables, dates, and slide notes; image-only content needs extraction before import.

For PDF exports, the CLI still expects prepared Markdown/text. Preserve the original PDF, its hash, and page references; inspect rendered pages alongside extracted text. A selectable PDF can still have broken character mappings or flattened tables. Record omitted visual content and uncertain table associations rather than guessing. The PDF creation/export timestamp is a snapshot date, not necessarily a policy effective date. Keep any extraction scripts and evidence specific to private documents outside the checkout.

Use this manifest shape, replacing example values locally:

```json
{
  "id": "company-private",
  "classification": "private",
  "workspaces": {"policies": "LoreDock Private Policies", "context": "LoreDock Private Context"},
  "documents": [{
    "id": "LD-COMPANY-LEAVE",
    "file": "leave.md",
    "workspace": "policies",
    "title": "Leave policy",
    "owner": "Source owner",
    "date": "2026-01-01",
    "authority": "Published policy; verify effective date",
    "source_url": "https://example.invalid/original-private-source"
  }]
}
```

```bash
python3 -m loredock ingest --manifest ../loredock-local/private/company/manifest.json
python3 -m loredock ask policies "QUESTION" --corpus company-private
python3 -m loredock eval --manifest ../loredock-local/private/company/manifest.json --suite ../loredock-local/private/company/questions.jsonl
```

Keep private question rubrics, returned passages, reports, screenshots, and recordings outside Git. Do not rewrite bundled fictional examples with real company content. A private manifest cannot use the `public-demo` classification, and `export-public` refuses its reports.

Imported copies do not automatically inherit Google permissions. Before colleague access, establish an authentication and source-authorization design that filters retrieval before generation, synchronizes changes/deletions/revocations, and tests cross-user isolation. The initial instance is for one operator and a laptop walkthrough.
