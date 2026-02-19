# AgentSync Coordination

This project uses **AgentSync MCP** for multi-agent coordination. You have access to file locking tools that prevent conflicts when multiple AI agents work on the same codebase.

## Required Workflow

**Before editing any file**, you MUST:
1. Call `request_file_lock` with the files you plan to edit and a brief description of your work
2. If any file is **blocked**, tell the user which agent has it locked and what they're doing. Work on something else or wait.
3. Only edit files you have successfully locked.

**After finishing your edits**, you MUST:
1. Call `release_file_lock` with all files you locked
2. If you made a git commit, include the `commit_hash`

## Quick Reference

- `request_file_lock(files, description)` — Lock files before editing
- `release_file_lock(files)` — Unlock files when done
- `check_file_status(files)` — Check if files are available
- `get_active_work()` — See what all agents are working on
