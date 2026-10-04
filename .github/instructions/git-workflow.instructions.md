---
description: "Use when finalizing a large feature, preparing a Git commit, writing a commit message, pushing changes, or wrapping up repository changes in the Media Player project."
name: "Git Workflow"
---
# Git Workflow Guidelines

- For a large new feature, finish the implementation and validation work before offering Git actions.
- Ask the user whether they want you to create a Git commit before committing anything.
- When the user wants a commit, use a semantic Conventional Commits message such as `feat: ...`, `fix: ...`, `refactor: ...`, or `docs: ...` that reflects the actual change.
- Write commit messages, PR titles and descriptions in English: `type(scope): summary` in the imperative, lowercase, no trailing period, 50 characters as a goal and 72 as the limit. Use the body for the why. Full rules and examples in `writing.instructions.md`.
- Write the manual and changelog in Portuguese, plain and specific, following `writing.instructions.md`.
- After creating the commit for a large new feature, perform the push as part of the same workflow unless the user explicitly asks you not to.
- Before the commit, summarize the relevant files changed and the validation you ran so the user can confirm with context.
- Do not create checkpoint or speculative commits for incomplete work unless the user explicitly asks for that.
- Keep long feature inventories and shortcut lists in `README.md` instead of duplicating them in commit-oriented summaries or instructions.
