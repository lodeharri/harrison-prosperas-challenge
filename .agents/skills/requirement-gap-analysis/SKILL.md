---
name: requirement-gap-analysis
description: Systematic workflow for cross-referencing PRD features with actual code symbols.
---

# Instructions
1. **Extraction**: Create a temporary list of mandatory functional requirements from `PRD.md`.
2. **Validation Loop**: 
   - For each requirement, use `grep -r` to find relevant function signatures or decorators.
   - For DevOps requirements, verify file existence (e.g., `Dockerfile`, `docker-compose.yml`).
3. **Status Coding**: Assign one of these states to each requirement:
   - `IMPLEMENTED`: Symbol found and matches PRD.
   - `PARTIAL`: Symbol found but missing logic (e.g., placeholder comments).
   - `MISSING`: No trace found in filesystem.
4. **Completion**: Summarize findings in a table to be consumed by the Orchestrator.