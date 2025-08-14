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

## 📝 Jira Ticket Format

For best results, your Jira tickets should include:

- **File paths** in Jira code blocks: {{src/components/Button.tsx}} (fallback backticks also supported)
- **Clear instructions** about what needs to be implemented
- **Repository URL** in the ticket description (e.g., `https://github.com/org/repo.git`)

Example ticket description:
```
Update the button component in {{src/components/Button.tsx}} to support a new 'loading' state.

Repository URL: https://github.com/org/repo.git
```

📖 See full guide: [jira-ticket-format.md](jira-ticket-format.md)

## 🛠 Local Example (optional)

If you want to run locally for development/debugging:

```bash
./setup.sh
conda activate pr-generation-from-ticket
./configure_env.sh
./run.sh ENG-1234
```

## 🔍 Troubleshooting CI

- Verify the environment name passed to the workflow matches an existing GitHub Environment
- Ensure all required secrets exist in that Environment: `JIRA_URL`, `JIRA_TOKEN`, `GEMINI_API_KEY`, `GH_PAT` (and `JIRA_EMAIL` if needed)
- Check the Action logs; the job prints which environment it used

## 📁 Project Files

- **`app/main.py`**: The main AI PR generator script
- **`environment.yml`**: Conda environment
- **`environment-simple.yml`**: Simplified conda environment
- **`setup.sh`**: Automated environment setup script (local dev)
- **`configure_env.sh`**: Generates local `env_setup.sh` (local dev)
- **`run.sh`**: Local runner with validation
- **`jira-ticket-format.md`**: Jira ticket formatting guide
- **`.github/workflows/ai-pr-from-jira.yml`**: CI pipeline using per-user GitHub Environments
- **`.gitignore`**, **`README.md`**, **`LICENSE`**

## 📄 License

See LICENSE file for details.