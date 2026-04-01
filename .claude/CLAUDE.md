# Claude Code Rules - MMORPG Bot Project

## DEBUGGING RULES (Repo-grounded debugging)

### Mandatory First Step: Search
Before explaining any bug, **always search the repo first**:
- Search for route name, error string, class/function name, or unique keyword from the bug report
- Use ripgrep/grep for strings and symbols
- Read files only that the search hits
- Prefer following imports and call sites over reading whole directories

### No "Probably" Without Citation
Every claim about behavior must point to exact code:
- **Format:** `file_path:line_number` or `ClassName.method_name`
- Example ❌: "likely the session is per-user"
- Example ✅: `services/activity_http.py:42 — ACTIVE_ACTIVITY[discord_id]` stores per-user state

### One Trace Per Bug
Required output block for every bug investigation:
```
Entry → handler → service → where state is stored → key used

Example:
/market buy [Discord handler]
  → market_buy() [economy_cog.py:80]
  → add_item() [inventory_service.py:155]
  → INSERT inventory table with character_id key
```

### Hypothesis Checklist for Sync/Multiplayer Bugs
For issues involving multiple clients or async state:
- ✓ Explicitly check: same key vs different key for two clients
- ✓ Verify state is stored with correct key (user_id, run_id, session_id, etc.)
- ✓ Check if state isolation is per-user or per-instance
- ✓ Trace the authoritative source of truth (database vs in-memory cache)

### Smallest Diff Only
After identifying root cause:
- Fix must be minimal and touch only files the trace touched
- No refactoring or cleanup beyond the bug fix
- List exact changed files and lines

---

## IMPLEMENTATION RULES

### 1. PLAN BEFORE ACTION
- Always provide a clear step-by-step PLAN before making changes
- Do not execute anything until approval is given
- Format:
  ```
  PLAN:
  1. ...
  2. ...
  
  FILES AFFECTED:
  - ...
  
  RISKS:
  - ...
  ```

### 2. NO BLIND CHANGES
- Never modify files without showing exactly what will change
- Always show diffs or explain changes clearly before applying

### 3. READ BEFORE WRITE
- Always read relevant files before making changes
- Never assume file structure or behavior

### 4. MINIMAL CHANGES ONLY
- Make the smallest possible change to solve the problem
- Do not refactor or restructure unless explicitly asked

### 5. CITATIONS REQUIRED
- Every claim must have file + line reference
- No speculation without code evidence

### 6. FILE SAFETY
- Never delete files
- Never overwrite large sections without approval

### 7. TERMINAL SAFETY
- Never run destructive commands (rm -rf, git reset --hard, git clean -fd)
- Ask for approval before risky commands

### 8. ERROR HANDLING
- If something fails: STOP immediately
- Explain the error clearly
- Suggest next steps (don't retry blindly)

---

## GIT WORKFLOW

- Commit with co-author: `Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>`
- Create NEW commits instead of amending (unless explicitly asked)
- Never skip hooks or bypass signing
- Push only after confirmation

---

## GENERAL BEHAVIOR

- Optimize for safety over speed
- Prefer asking questions over guessing
- Be precise and conservative
- If unclear: STOP and ask
- Cite sources for every mechanism claim
