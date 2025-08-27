# AI PR Generator Tool – Gemini Edition

A CLI utility that reads a Jira ticket, uses **Google Gemini** to generate code patches, and opens a pull request that references the issue.

## 🚀 Quick Start (CI-first)

Run entirely via GitHub Actions with per-user GitHub Environments. No local installs required.

### Configure per-user GitHub Environments

For each user (e.g., `manager`, `chris`):

1. In GitHub: Settings → Environments → New environment (name it after the user)
2. Add secrets to that environment:
   - `JIRA_URL` (e.g., https://your-domain.atlassian.net)
   - `JIRA_EMAIL` (user's Atlassian email, if needed by auth)
   - `JIRA_TOKEN` (user's Jira API token)
   - `GEMINI_API_KEY` (user's Gemini key)
   - `GH_PAT` (user's GitHub Personal Access Token with repo permissions)
3. Optional variables (Environment → Variables):
   - `DEFAULT_BASE_BRANCH` (default `main`)
   - `MAX_PROMPT_TOKENS` (default `6000`)
   - `MAX_EXTERNAL_CONTEXT_CHARS` (default `20000`) – budget for external refs (Confluence, PRs, web)
   - `PER_SOURCE_SUMMARY_CHAR_LIMIT` (default `3000`) – cap for each individual source summary
   - `SUMMARIZE_EXTERNAL_CONTEXT` (default `true`) – summarize external refs with Gemini before inclusion
   - `ENABLE_CROSS_SOURCE_SYNTHESIS` (default `true`) – adds a synthesized brief across sources
   - `SYNTHESIS_CHAR_LIMIT` (default `2000`) – cap for the synthesis brief
   - `EXTERNAL_FETCH_TIMEOUT_MS` (default `10000`) – timeout for fetching external pages
   - `GITHUB_PR_FILES_LIMIT` (default `50`) – limit PR files examined
   - `LOG_PROMPT_PREVIEW_CHARS` (default `800`) – logs the first N chars of the prompt
   - `LOG_MODEL_OUTPUT_PREVIEW_CHARS` (default `600`) – logs the first N chars of the model output
   - `LOG_SUMMARY_PREVIEW_CHARS` (default `400`) – logs the first N chars of per-source and synthesis summaries

### Run the workflow

- Manual: Actions → “AI PR from Jira” → Run workflow
  - `issue_key`: e.g., `QUEST-39`
  - `env_name`: your environment, e.g., `manager`

- From Jira Automation (label trigger): send repository_dispatch
  - URL: `https://api.github.com/repos/<owner>/<repo>/dispatches`
  - Headers: `Authorization: Bearer <GitHub PAT>`, `Accept: application/vnd.github+json`
  - Body:
    ```json
    {
      "event_type": "jira-ai-pr",
      "client_payload": {
        "issue_key": "{{issue.key}}",
        "env_name": "manager"
      }
    }
    ```

## 🔗 Jira Automation Integration

Trigger this pipeline directly from Jira with a no-code automation rule.

### Create the rule in Jira

1. Project settings → Automation → Create rule
2. Choose a trigger (examples):
   - Issue transitioned to: In Progress
   - Issue updated: Label added = `ai-pr`
3. Optional conditions:
   - Description contains a GitHub URL (e.g., `https://github.com/org/repo.git`)
   - Or a custom field contains the repository URL (e.g., `customfield_11712`)
4. Action: Send web request
   - URL: `https://api.github.com/repos/<owner>/<repo>/dispatches`
   - Method: POST
   - Headers:
     - `Authorization: Bearer <GitHub PAT>`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - Webhook body (JSON):
     ```json
     {
       "event_type": "jira-ai-pr",
       "client_payload": {
         "issue_key": "{{issue.key}}",
         "env_name": "manager"
       }
     }
     ```

Notes:
- `env_name` should map to a GitHub Environment you configured (see Quick Start).
- The script auto-detects the repository URL from the ticket description or known custom fields; include it in the ticket if possible.

### Permissions and secrets

- Use a GitHub Personal Access Token (PAT) with at least `repo` (and `workflow` if your org policy requires it) for the Jira web request.
- Store the PAT in Jira Automation as a secure credential (HTTP connection or secret); do not hardcode in the rule.

### Verify end-to-end

- Ensure your workflow listens to repository dispatch events with type `jira-ai-pr` (see `.github/workflows/ai-pr-from-jira.yml`).

### Trigger via GitHub Action using curl (with PAT)

1) Create a GitHub Personal Access Token (PAT):
- Go to `https://github.com/settings/tokens` and generate a classic token
- Scopes: `repo` (and `workflow` if your org policy requires it)

2) Run the curl command to dispatch the workflow:
```bash
GH_PAT="<your_pat_here>"
OWNER="<owner>"           # e.g., your-org
REPO="<repo>"             # e.g., your-repo
ISSUE_KEY="ENG-1234"      # Jira issue key to process
ENV_NAME="manager"        # GitHub Environment name configured with secrets

curl -X POST \
  -H "Authorization: Bearer ${GH_PAT}" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/dispatches" \
  -d "{\"event_type\":\"jira-ai-pr\",\"client_payload\":{\"issue_key\":\"${ISSUE_KEY}\",\"env_name\":\"${ENV_NAME}\"}}"
```

Notes:
- `env_name` must match a GitHub Environment that contains required secrets: `JIRA_URL`, `JIRA_TOKEN`, `GEMINI_API_KEY`, `GH_PAT` (and `JIRA_EMAIL` if applicable).
- The workflow should reference these via `${{ secrets.* }}` or environment variables.

## 📝 Jira Ticket Format

For best results, your Jira tickets should include:

- **File paths** in Jira code blocks: {{src/components/Button.tsx}} (fallback backticks also supported)
- **Clear instructions** about what needs to be implemented
- **Repository URL** in the ticket description (e.g., `https://github.com/org/repo.git`)
- **External references (optional)**: Confluence page link(s) and/or GitHub PR link(s) to use as context (either in description or in Related links)

Example ticket description:
```
Update the button component in {{src/components/Button.tsx}} to support a new 'loading' state.

Repository URL: https://github.com/org/repo.git

References:
- Confluence: https://your-domain.atlassian.net/wiki/spaces/ENG/pages/123456789/Button+Design+Spec
- Prior PR: https://github.com/org/repo/pull/1234
```

📖 See full guide: [jira-ticket-format.md](jira-ticket-format.md)

## 🛠 Running

This project is intended to run via GitHub Actions. Local execution scripts are available under `local/`.

## ✅ Tests

Run unit tests locally with pytest:

```bash
conda activate pr-generation-from-ticket
pytest -q
```

Included tests:
- Context parsing (file paths and URLs)
- Health checks (env variables)
- Prompt builder structure

## 🔍 Troubleshooting CI

- Verify the environment name passed to the workflow matches an existing GitHub Environment
- Ensure all required secrets exist in that Environment: `JIRA_URL`, `JIRA_TOKEN`, `GEMINI_API_KEY`, `GH_PAT` (and `JIRA_EMAIL` if needed)
- Check the Action logs; the job prints which environment it used
- If a repository dispatch doesn’t start the workflow, confirm your workflow has `on: repository_dispatch: types: [jira-ai-pr]` and the PAT has sufficient permissions

## 📁 Project Files

- **`app/main.py`**: The main AI PR generator script
- **`local/`**: Optional local helper scripts (runner, setup, environment)
- **`jira-ticket-format.md`**: Jira ticket formatting guide
- **`.github/workflows/ai-pr-from-jira.yml`**: CI pipeline using per-user GitHub Environments
- **`.gitignore`**, **`README.md`**, **`LICENSE`**

## 📄 License

See LICENSE file for details.

---

## 🧪 Local Example (optional)

If you want to run locally for development/debugging:

```bash
./local/setup.sh
conda activate pr-generation-from-ticket
cd local && ./configure_env.sh
source env_setup.sh
./run.sh ENG-1234
```
