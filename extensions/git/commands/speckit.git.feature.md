---
description: "Create a GitFlow branch (feature/, hotfix/, or release/) with sequential or timestamp numbering"
---

# Create GitFlow Branch

Create and switch to a new GitFlow branch (`feature/`, `hotfix/`, or `release/`) for the given specification. This command handles **branch creation only** — the spec directory and files are created by the core `__SPECKIT_COMMAND_SPECIFY__` workflow.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Environment Variable Override

If the user explicitly provided `GIT_BRANCH_NAME` (e.g., via environment variable, argument, or in their request), pass it through to the script by setting the `GIT_BRANCH_NAME` environment variable before invoking the script. When `GIT_BRANCH_NAME` is set:
- The script uses the exact value as the branch name, bypassing all prefix/suffix generation
- `--short-name`, `--number`, and `--timestamp` flags are ignored
- `FEATURE_NUM` is extracted when the final path segment starts with a numeric or timestamp feature marker (for example `042-name`, `feat/042-name`, or `jdoe/app/042-name`), otherwise set to the full branch name

## Prerequisites

- Verify Git is available by running `git rev-parse --is-inside-work-tree 2>/dev/null`
- If Git is not available, warn the user and skip branch creation

## GitFlow Branch Type

Determine the GitFlow branch type (`GITFLOW_TYPE`) from the user input **before** any validation:

- If the input starts with or contains the keyword `hotfix` (e.g., `hotfix: fix login crash`, `hotfix fix critical bug`) → `GITFLOW_TYPE=hotfix`
- If the input starts with or contains the keyword `release` (e.g., `release: 1.2.0`, `release 2.0`) → `GITFLOW_TYPE=release`
- Otherwise → `GITFLOW_TYPE=feature` (default)

Strip the type keyword and any trailing colon/space from the input to get the clean feature description used for branch name generation.

## GitFlow Branch Validation

Before creating the branch, validate the current base branch against the GitFlow conventions for `GITFLOW_TYPE`:

1. Run `git rev-parse --abbrev-ref HEAD` to get the current branch name (`CURRENT_BRANCH`).
2. Apply the validation rule for the detected type:

| `GITFLOW_TYPE` | Valid base branch | Action if invalid |
|---|---|---|
| `feature` | `develop` | ⚠️ Warn + confirm |
| `release` | `develop` | ⚠️ Warn + confirm |
| `hotfix` | `main` or `master` | ⚠️ Warn + confirm |

3. If the current branch matches the valid base, proceed directly without any prompt.
4. If the current branch does **not** match, display the appropriate warning:

**For `feature` or `release` branches (base should be `develop`):**
```
⚠️  GitFlow Warning: Current branch '{CURRENT_BRANCH}' is not 'develop'.
GitFlow convention requires '{GITFLOW_TYPE}/*' branches to be created from 'develop'.
  Expected:  git checkout develop
  Then:      /speckit.git.feature {GITFLOW_TYPE}: <description>

Type 'yes' to create the branch from '{CURRENT_BRANCH}' anyway, or switch to 'develop' first.
```

**For `hotfix` branches (base should be `main` or `master`):**
```
⚠️  GitFlow Warning: Current branch '{CURRENT_BRANCH}' is not 'main' or 'master'.
GitFlow convention requires 'hotfix/*' branches to be created from 'main' or 'master'.
  Expected:  git checkout main
  Then:      /speckit.git.feature hotfix: <description>

Type 'yes' to create the branch from '{CURRENT_BRANCH}' anyway, or switch to 'main'/'master' first.
```

5. If the user confirms (`yes`), proceed with branch creation from the current branch.

## Branch Numbering Mode

Determine the branch numbering strategy by checking configuration in this order:

1. Check `.specify/extensions/git/git-config.yml` for `branch_numbering` value
2. Check `.specify/init-options.json` for `feature_numbering` value (inherit from core)
3. Check `.specify/init-options.json` for `branch_numbering` value (deprecated, backward compatibility — will be removed in a future release)
4. Default to `sequential` if none of the above exist

## Branch Name Template

Check `.specify/extensions/git/git-config.yml` for an optional `branch_template` value. If it is empty or missing, use the default branch shape `{number}-{slug}`. If it is set, `{slug}` must not appear before `{number}`, its final path segment must start with `{number}-`, and the script expands these tokens:

- `{author}`: sanitized Git config author (`user.name`, falling back to the email local part)
- `{app}`: sanitized Spec Kit init directory name
- `{number}`: sequential number or timestamp
- `{slug}`: generated short branch slug

For monorepos, a template such as `{author}/{app}/{number}-{slug}` creates names like `jdoe/web/008-guided-tour` while preserving per-project feature numbering.

The script also accepts `branch_prefix` as a shorthand for simple namespaces; it expands to `<branch_prefix>/{number}-{slug}`.

## Execution

Generate a concise short name (2-4 words) for the branch:
- Analyze the feature description and extract the most meaningful keywords
- Use action-noun format when possible (e.g., "add-user-auth", "fix-payment-bug")
- Preserve technical terms and acronyms (OAuth2, API, JWT, etc.)

Run the appropriate script based on your platform:

- **Bash**: `.specify/extensions/git/scripts/bash/create-new-feature-branch.sh --json --short-name "<short-name>" "<feature description>"`
- **Bash (timestamp)**: `.specify/extensions/git/scripts/bash/create-new-feature-branch.sh --json --timestamp --short-name "<short-name>" "<feature description>"`
- **PowerShell**: `.specify/extensions/git/scripts/powershell/create-new-feature-branch.ps1 -Json -ShortName "<short-name>" "<feature description>"`
- **PowerShell (timestamp)**: `.specify/extensions/git/scripts/powershell/create-new-feature-branch.ps1 -Json -Timestamp -ShortName "<short-name>" "<feature description>"`

**IMPORTANT**:
- Do NOT pass `--number` — the script determines the correct next number automatically
- Always include the JSON flag (`--json` for Bash, `-Json` for PowerShell) so the output can be parsed reliably
- You must only ever run this script once per feature
- The JSON output will contain `BRANCH_NAME` and `FEATURE_NUM`
- Do not manually expand `branch_template`; the script reads the git extension config and applies it consistently

## GitFlow Prefix Application

After the script runs and outputs `BRANCH_NAME` (e.g., `003-add-user-auth`), apply the GitFlow prefix:

1. Rename the branch to include the correct prefix:
   ```
   git branch -m {BRANCH_NAME} {GITFLOW_TYPE}/{BRANCH_NAME}
   ```
2. Store the full name as `FULL_BRANCH_NAME={GITFLOW_TYPE}/{BRANCH_NAME}` (e.g., `feature/003-add-user-auth`, `hotfix/003-fix-login-crash`, `release/003-v1-2-0`).
3. Use `FULL_BRANCH_NAME` in all subsequent references and output messages.

## Graceful Degradation

If Git is not installed or the current directory is not a Git repository:
- Branch creation is skipped with a warning: `[specify] Warning: Git repository not detected; skipped branch creation`
- The script still outputs `BRANCH_NAME` and `FEATURE_NUM` so the caller can reference them

## Output

The script outputs JSON with:
- `BRANCH_NAME`: The raw branch name without GitFlow prefix (e.g., `003-user-auth`, `20260319-143022-user-auth`, or `jdoe/web/003-user-auth`)
- `FEATURE_NUM`: The numeric or timestamp prefix used

After the GitFlow prefix is applied, the final branch name (`FULL_BRANCH_NAME`) will be:
- `feature/003-user-auth` — for new features
- `hotfix/003-fix-login-crash` — for urgent bug fixes from `main`/`master`
- `release/003-v1-2-0` — for release preparation from `develop`
