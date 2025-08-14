#!/bin/bash

# AI PR Generator Runner
# This is the recommended way to run the AI PR Generator tool

echo "🎯 AI PR Generator"
echo "================================"

# Check if environment is activated
if [[ "$CONDA_DEFAULT_ENV" != "pr-generation-from-ticket" ]]; then
    echo "❌ Conda environment not activated!"
    echo ""
    echo "Please run these commands first:"
    echo "1. conda activate pr-generation-from-ticket"
    echo "2. source env_setup.sh  (after you've configured it)"
    echo ""
    echo "Need help? See README.md for complete setup instructions."
    exit 1
fi

# Check if environment variables are set
if [[ -z "$JIRA_URL" || -z "$JIRA_TOKEN" || -z "$GITHUB_TOKEN" || -z "$GEMINI_API_KEY" ]]; then
    echo "❌ Environment variables not set!"
    echo ""
    
    # Check if env_setup.sh exists
    if [[ -f "env_setup.sh" ]]; then
        echo "Found env_setup.sh file. Loading environment variables..."
        source env_setup.sh
        
        # Check again after sourcing
        if [[ -z "$JIRA_URL" || -z "$JIRA_TOKEN" || -z "$GITHUB_TOKEN" || -z "$GEMINI_API_KEY" ]]; then
            echo "❌ env_setup.sh exists but doesn't contain all required variables!"
            echo "Please run: ./configure_env.sh"
            exit 1
        else
            echo "✅ Environment variables loaded from env_setup.sh"
        fi
    else
        echo "Please configure your environment first:"
        echo "1. Run: ./configure_env.sh"
        echo "2. Then run this script again"
        echo ""
        echo "See README.md for help getting API tokens."
        exit 1
    fi
fi

# Check if issue key was provided
if [[ $# -eq 0 ]]; then
    echo "❌ Please provide a Jira issue key!"
    echo ""
    echo "Usage: $0 ENG-1234"
    echo ""
    echo "Example: $0 ENG-1234"
    exit 1
fi

ISSUE_KEY=$1

echo "✅ Environment looks good!"
echo "🎫 Processing Jira issue: $ISSUE_KEY"
echo ""

# Run the main script
python app/main.py "$ISSUE_KEY"

echo ""
echo "🎉 Done! Check your GitHub repository for the new pull request."