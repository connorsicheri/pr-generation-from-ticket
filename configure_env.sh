#!/bin/bash

# Environment Configuration Script
# Generates a template file for manual configuration

set -e

echo "🔧 AI PR Generator - Environment Configuration"
echo "=============================================="
echo ""

# Check if env_setup.sh already exists
if [[ -f "env_setup.sh" ]]; then
    echo "⚠️  env_setup.sh already exists!"
    echo "📝 Remove it first if you want to regenerate: rm env_setup.sh"
    exit 1
fi

echo "📄 Creating environment template file: env_setup.sh"

# Create the environment template file
cat > env_setup.sh << 'EOF'
#!/bin/bash
# AI PR Generator Environment Variables
# 
# INSTRUCTIONS:
# 1. Fill in your actual API tokens below (replace the placeholder values)
# 2. Save this file
# 3. Load the environment: source env_setup.sh
# 4. Run the tool: ./run.sh ISSUE-KEY
#
# SECURITY NOTE: This file contains sensitive API tokens!
# It is automatically git-ignored to prevent accidental commits.

# === REQUIRED ENVIRONMENT VARIABLES ===
# Replace these placeholder values with your actual tokens:

export JIRA_URL="https://your-company.atlassian.net"
export JIRA_TOKEN="your-jira-api-token-here"
export GITHUB_TOKEN="your-github-personal-access-token-here"
export GEMINI_API_KEY="your-google-gemini-api-key-here"

# === OPTIONAL ENVIRONMENT VARIABLES ===
# These have sensible defaults, but you can customize them:

export GEMINI_MODEL="gemini-1.5-pro"
export MAX_PROMPT_TOKENS="6000"
export DEFAULT_BASE_BRANCH="main"

# === TOKEN SETUP INSTRUCTIONS ===
#
# 1. JIRA_TOKEN:
#    - Go to: https://id.atlassian.com/manage-profile/security/api-tokens
#    - Click "Create API token"
#    - Copy the token and replace "your-jira-api-token-here" above
#
# 2. GITHUB_TOKEN:
#    - Go to: https://github.com/settings/tokens
#    - Click "Generate new token (classic)"
#    - Select scopes: repo, read:org
#    - Copy the token and replace "your-github-personal-access-token-here" above
#
# 3. GEMINI_API_KEY:
#    - Go to: https://makersuite.google.com/app/apikey
#    - Click "Create API key"
#    - Copy the key and replace "your-google-gemini-api-key-here" above

echo "✅ Environment variables loaded for AI PR Generator"
echo "🎯 You can now run: ./run.sh ISSUE-KEY"
EOF

# Make the file executable
chmod +x env_setup.sh

echo "✅ Template created successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Edit env_setup.sh and fill in your actual API tokens"
echo "2. Load the environment: source env_setup.sh"
echo "3. Run the tool: ./run.sh ENG-1234"
echo ""
echo "📖 The file contains detailed instructions for getting each API token."