# AI PR Generator Tool – Gemini Edition

A CLI utility that reads a Jira ticket, uses **Google Gemini** to generate code patches, and opens a pull request that references the issue.

## 🚀 Quick Start (For Managers)

### Prerequisites
- [Conda](https://docs.conda.io/en/latest/miniconda.html) installed on your system
- Access to the required API tokens (see Environment Variables section)

### Setup (30 seconds!)

```bash
git clone <your-repo-url>
cd pr-generation-from-ticket
./setup.sh
```

That's it! The setup script automatically handles everything - conda environment, dependencies, and API token configuration. 🎉

## 🚀 Usage

```bash
./run.sh TICKET-KEY
```

The setup script automatically configures all required API tokens and environment variables.

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

## 🛠 Example

```bash
./run.sh ENG-1234
```

The tool automatically:
1. Reads ticket ENG-1234 from Jira
2. Generates code changes using AI
3. Creates branch: ai/eng-1234
4. Commits and pushes changes
5. Opens a pull request on GitHub

## 🔍 Troubleshooting

If you encounter any issues, simply re-run the setup:

```bash
./setup.sh
```

The setup script handles all common issues automatically.

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