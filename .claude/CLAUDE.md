# Claude Code Rules - MMORPG Bot Project

## STRICT RULES FOR THIS PROJECT

### 1. PLAN BEFORE ACTION
- Always provide a clear step-by-step PLAN before making any changes
- Do not execute anything until approval is given
- Format:
  ```
  PLAN:
  1. ...
  2. ...
  3. ...
  
  FILES AFFECTED:
  - ...
  
  RISKS:
  - ...
  
  WAITING FOR APPROVAL
  ```

### 2. NO BLIND CHANGES
- Never modify, delete, or overwrite files without showing exactly what will change
- Always show diffs or explain changes clearly before applying them

### 3. READ BEFORE WRITE
- Always read and analyze relevant files before making changes
- Never assume file structure or behavior

### 4. MINIMAL CHANGES ONLY
- Make the smallest possible change to solve the problem
- Do not refactor or restructure unless explicitly asked

### 5. FILE SAFETY
- Never delete files
- Never overwrite large sections of code without explicit approval

### 6. TERMINAL SAFETY
- Never run destructive commands such as:
  - `rm -rf`
  - `git reset --hard`
  - `git clean -fd`
- Ask for approval before any risky command

### 7. NO HALLUCINATIONS
- If unsure about anything, say: "I don't know" and ask for clarification
- Do NOT guess

### 8. EXPLANATION REQUIRED
For every change, explain:
- Why this change is needed
- What could break
- Alternative approaches

### 9. CONFIDENCE SCORE
After every PLAN and RESULT, include:
```
CONFIDENCE: XX%
REASON: Brief explanation of uncertainty
```

### 10. DEPENDENCY SAFETY
- Before installing or updating anything:
  - Explain why it is needed
  - Mention possible conflicts
  - Check compatibility

### 11. ERROR HANDLING
- If something fails:
  - STOP immediately
  - Explain the error clearly
  - Suggest next steps
- Do not retry blindly

### 12. DRY RUN WHEN POSSIBLE
- Simulate changes before applying them when possible

### 13. BACKUP AWARENESS
- Suggest creating a git commit or backup before major changes

### 14. IMPACT ANALYSIS
Before major changes, explain:
- What parts of the system are affected
- Possible side effects

### 15. ROLLBACK PLAN
- Always explain how to undo the change if something breaks

---

## GENERAL BEHAVIOR

- **Optimize for safety over speed**
- **Prefer asking questions over guessing**
- **Do not take shortcuts**
- **Be precise and conservative**
- **If anything is unclear: STOP and ask**

---

## EXISTING CONVENTIONS

### Bug Investigation
- When asked to "find a bug": locate it and explain the cause
- Do NOT make changes without explicit permission
- Provide clear explanation of the issue

### Commits
- Always use meaningful commit messages
- Include co-author: `Claude Haiku 4.5 <noreply@anthropic.com>`
- Never skip hooks or bypass signing
