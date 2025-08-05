# AI PR Generator Tool – Gemini Edition

A CLI utility that reads a Jira ticket, uses **Google Gemini** to generate code patches, and opens a pull request that references the issue.

## 🚀 Quick Start (For Managers)

### Prerequisites
- [Conda](https://docs.conda.io/en/latest/miniconda.html) installed on your system
- Access to the required API tokens (see Environment Variables section)

### Setup (2 minutes!)

#### Option 1: Automated Setup (Recommended)
```bash
# 1. Clone and navigate to the project
git clone <your-repo-url>
cd pr-generation-from-ticket

# 2. Run the setup script
./setup.sh

# 3. Activate the environment
conda activate pr-generation-from-ticket

# 4. Generate and configure API tokens
./configure_env.sh          # Creates env_setup.sh template
# Edit env_setup.sh with your actual API tokens
source env_setup.sh         # Load the environment variables

# 5. Run the tool
./run.sh ENG-1234
```

#### Option 2: Manual Setup
```bash
# 1. Clone and navigate to the project
git clone <your-repo-url>
cd pr-generation-from-ticket

# 2. Create the conda environment (try simple version first)
conda env create -f environment-simple.yml
# If that fails, try: conda env create -f environment.yml

# 3. Activate the environment
conda activate pr-generation-from-ticket

# 4. Configure your API tokens
./configure_env.sh
source env_setup.sh

# 5. Run the tool
python main.py ENG-1234
```

That's it! 🎉

## 🔧 Environment Variables

The easiest way to set up environment variables is using our template generation script:

```bash
./configure_env.sh    # Generates env_setup.sh template
# Edit env_setup.sh with your actual API tokens
source env_setup.sh   # Load the environment variables
```

This script creates a template file with clear instructions and placeholder values that you can manually fill in.

### Manual Setup (Alternative)

If you prefer to set environment variables manually:

```bash
# Required
export JIRA_URL="https://your-company.atlassian.net"
export JIRA_TOKEN="your-jira-api-token"
export GITHUB_TOKEN="your-github-personal-access-token"
export GEMINI_API_KEY="your-google-gemini-api-key"

# Optional
export GEMINI_MODEL="gemini-1.5-pro"  # Default model
export MAX_PROMPT_TOKENS="6000"       # Character budget for file content
export DEFAULT_BASE_BRANCH="main"     # Default branch to target for PRs
```

### Getting API Tokens

1. **Jira Token**: Go to Atlassian Account Settings → Security → Create API Token
2. **GitHub Token**: Go to GitHub Settings → Developer Settings → Personal Access Tokens → Generate new token (classic)
3. **Gemini API Key**: Go to [Google AI Studio](https://makersuite.google.com/app/apikey) → Create API Key

## 📋 How It Works

1. **Fetches Jira Ticket**: Reads the ticket description and extracts file paths and instructions
2. **Clones Repository**: Creates a new branch for the changes
3. **AI Code Generation**: Uses Gemini AI to generate code patches based on the ticket
4. **Creates Pull Request**: Commits changes and opens a PR on GitHub

## 📝 Jira Ticket Format

For best results, your Jira tickets should include:

- **File paths** in backticks: `src/components/Button.tsx`
- **Clear instructions** about what needs to be implemented
- **Repository URL** in a custom field (adjust `customfield_12345` in main.py)

Example ticket description:
```
Update the button component in `src/components/Button.tsx` to support a new 'loading' state.

The button should show a spinner when loading=true and be disabled during this state.
```

📖 **For detailed formatting guidelines and examples, see: [jira-ticket-format.md](jira-ticket-format.md)**

## 🛠 Usage Examples

```bash
# Recommended usage (with validation and helpful error messages)
./run.sh ENG-1234

# Direct usage (advanced users only)
python main.py ENG-1234

# The tool will:
# 1. Read ticket ENG-1234 from Jira
# 2. Generate code changes using Gemini AI
# 3. Create a new branch: ai/eng-1234
# 4. Commit and push changes
# 5. Open a pull request on GitHub
```

## 🔍 Troubleshooting

**Environment not activated?**
```bash
conda activate pr-generation-from-ticket
```

**Missing environment variables?**
```bash
echo $JIRA_URL $JIRA_TOKEN $GITHUB_TOKEN $GEMINI_API_KEY
```

**Python not finding modules?**
```bash
conda list  # Verify packages are installed
```

**tiktoken build errors (missing Rust compiler)?**
Try the simplified environment:
```bash
conda env remove -n pr-generation-from-ticket
conda env create -f environment-simple.yml
```

**Need to update dependencies?**
```bash
conda env update -f environment-simple.yml
# Or if using full environment: conda env update -f environment.yml
```

## 📁 Project Files

- **`main.py`**: The main AI PR generator script
- **`environment.yml`**: Conda environment with all dependencies (includes Rust compiler)
- **`environment-simple.yml`**: Simplified conda environment (recommended)
- **`setup.sh`**: Automated environment setup script
- **`configure_env.sh`**: Script to generate environment template for manual configuration
- **`env_template.sh`**: Template for environment variables (manual setup)
- **`run.sh`**: Main script to run the AI PR Generator with validation and easy execution
- **`jira-ticket-format.md`**: Detailed guide on how to format Jira tickets for optimal AI results
- **`.gitignore`**: Prevents sensitive files from being committed to git
- **`README.md`**: This documentation file

## 📄 License

See LICENSE file for details.