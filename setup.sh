#!/bin/bash

# AI PR Generator Setup Script
# Makes it super easy to get the environment ready

set -e  # Exit on any error

echo "🚀 Setting up AI PR Generator environment..."

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Conda is not installed. Please install Miniconda or Anaconda first:"
    echo "   https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Create conda environment
echo "📦 Creating conda environment..."
echo "Trying simplified environment first..."

if conda env create -f environment-simple.yml; then
    echo "✅ Environment created successfully with simplified setup!"
else
    echo "⚠️  Simplified setup failed, trying full environment with Rust compiler..."
    conda env create -f environment.yml
fi

echo "✅ Environment created successfully!"
echo ""
echo "🎯 Next steps:"
echo "1. Activate the environment:"
echo "   conda activate pr-generation-from-ticket"
echo ""
echo "2. Configure your API tokens:"
echo "   ./configure_env.sh"
echo ""
echo "3. Run the tool:"
echo "   ./run.sh ENG-1234"
echo ""
echo "📖 See README.md for detailed instructions on getting API tokens."
echo ""

# Ask if user wants to generate environment template now
read -p "🔧 Would you like to generate the environment template now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Generating environment template..."
    ./configure_env.sh
    echo ""
    echo "📝 Next: Edit env_setup.sh with your API tokens, then run: source env_setup.sh"
else
    echo "💭 You can generate the environment template later by running: ./configure_env.sh"
fi