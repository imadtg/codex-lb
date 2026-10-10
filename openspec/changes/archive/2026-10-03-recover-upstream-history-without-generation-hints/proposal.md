# Recover history without fork-specific generation hints

## Why

The first repair preserved the old canonical lookup when a logical-generation hint was absent. State written by the unmodified base can therefore retain the compacted model fork but select the older branch after a restart. The fork must accept that state without resetting the conversation or requiring new metadata.

## What Changes

- Regress service replacement with a shared persistent database: unmodified producer, patched continuation, unmodified follow-up.
- Find existing completed history proofs within the caller's API-key scope when an unanchored full resend cannot prove the selected branch.
- Use a unique fully validated match only to authorize projected fresh execution, never to infer an upstream account owner or overwrite existing exact aliases.
- Retain existing operation/recovery fences, file ownership, tool settlement, and explicit-anchor semantics.

## Impact

Responses HTTP bridge compatibility. Existing schema and wire contracts; no required fork-only state, manual conversion, production deployment, or client change.
