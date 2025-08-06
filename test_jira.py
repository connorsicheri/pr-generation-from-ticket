#!/usr/bin/env python3
"""
Test script to troubleshoot Jira connection and access to QUEST-39
"""
import os
from jira import JIRA

def test_jira_connection():
    print('🔍 TROUBLESHOOTING JIRA CONNECTION')
    print('=' * 40)

    # Check environment variables
    print('📋 Environment Variables:')
    jira_url = os.environ.get('JIRA_URL', 'NOT SET')
    jira_email = os.environ.get('JIRA_EMAIL', 'NOT SET')
    jira_token = os.environ.get('JIRA_TOKEN', 'NOT SET')
    
    print(f'   JIRA_URL: {jira_url}')
    print(f'   JIRA_EMAIL: {jira_email}')
    if jira_token != 'NOT SET':
        print(f'   JIRA_TOKEN: {jira_token[:10]}...{jira_token[-4:]} (masked)')
    else:
        print(f'   JIRA_TOKEN: {jira_token}')
    print()

    if 'NOT SET' in [jira_url, jira_email, jira_token]:
        print('❌ Missing environment variables! Run: source env_setup.sh')
        return

    # Test connection
    print('🔗 Testing Jira connection...')
    try:
        jira = JIRA(server=jira_url, basic_auth=(jira_email, jira_token))
        print('✅ Connection successful!')
        
        # Test server info
        print('📊 Server info:')
        info = jira.server_info()
        print(f'   Server title: {info.get("serverTitle", "Unknown")}')
        print(f'   Version: {info.get("version", "Unknown")}')
        print()
        
        # Test current user
        print('👤 Current user info:')
        user = jira.myself()
        print(f'   Name: {user.get("displayName", "Unknown")}')
        print(f'   Email: {user.get("emailAddress", "Unknown")}')
        print()
        
        # List projects user has access to
        print('📁 Projects you have access to:')
        projects = jira.projects()
        for project in projects[:10]:  # Show first 10
            print(f'   - {project.key}: {project.name}')
        if len(projects) > 10:
            print(f'   ... and {len(projects) - 10} more projects')
        print()
        
        # Test access to QUEST-39
        print('🎫 Testing access to QUEST-39...')
        issue = jira.issue('QUEST-39')
        print(f'✅ Successfully accessed QUEST-39!')
        print(f'   Summary: {issue.fields.summary}')
        print(f'   Status: {issue.fields.status.name}')
        print(f'   Project: {issue.fields.project.key}')
        print(f'   Description length: {len(issue.fields.description or "")} characters')
        print()
        print('📄 FULL TICKET DESCRIPTION:')
        print('=' * 60)
        if issue.fields.description:
            print(issue.fields.description)
        else:
            print('(No description found)')
        print('=' * 60)
        print()
        
        # Look for URLs in description
        description = issue.fields.description or ""
        print('🔍 Looking for URLs in description...')
        import re
        
        # Look for github URLs
        github_urls = re.findall(r'https://github\.com/[^\s]+', description)
        if github_urls:
            print('   GitHub URLs found:')
            for url in github_urls:
                print(f'     - {url}')
        
        # Look for any git URLs
        git_urls = re.findall(r'[^\s]*\.git[^\s]*', description)
        if git_urls:
            print('   Git URLs found:')
            for url in git_urls:
                print(f'     - {url}')
        
        # Look for any URLs
        all_urls = re.findall(r'https?://[^\s]+', description)
        if all_urls:
            print('   All URLs found:')
            for url in all_urls:
                print(f'     - {url}')
        
        if not github_urls and not git_urls and not all_urls:
            print('   No URLs found in description')
        print()
        
        # Test file extraction from description
        print('📁 TESTING FILE EXTRACTION')
        print('=' * 40)
        
        # Import the TicketContext class from main.py
        import sys
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        try:
            from main import TicketContext
            
            print('🔍 Parsing ticket description for file paths...')
            ctx = TicketContext(issue.fields.description or "")
            
            print(f'📄 Original description length: {len(ctx.description)} characters')
            print(f'📁 Found {len(ctx.file_paths)} file(s): {ctx.file_paths}')
            print(f'📝 Instructions length: {len(ctx.instructions)} characters')
            print()
            
            if ctx.file_paths:
                print('✅ Files detected in ticket:')
                for i, file_path in enumerate(ctx.file_paths, 1):
                    print(f'   {i}. {file_path}')
            else:
                print('⚠️  No file paths found in ticket description!')
                print('💡 File paths should be in backticks like: `src/components/Button.tsx`')
            print()
            
            print('📋 Processed instructions (after removing file paths):')
            print('-' * 50)
            print(ctx.instructions[:500] + ('...' if len(ctx.instructions) > 500 else ''))
            print('-' * 50)
            print()
            
            # Show the regex patterns used
            import re
            jira_regex = re.compile(r"\{\{([^{}\n]*[/\\]?[^{}\n/\\]*\.(?:py|go|js|ts|tsx|java|yaml|json|yml|md|txt|sh|jsx|vue|php|rb|cpp|c|h))\}\}")
            backtick_regex = re.compile(r"`([^`\n]*[/\\]?[^`\n/\\]*\.(?:py|go|js|ts|tsx|java|yaml|json|yml|md|txt|sh|jsx|vue|php|rb|cpp|c|h))`")
            
            print('🔧 File detection patterns:')
            print('   PRIMARY (Jira format): {{path/to/filename.ext}}')
            print('   FALLBACK (Markdown): `path/to/filename.ext`')
            print('   Supported extensions: py, go, js, ts, tsx, java, yaml, json, yml, md, txt, sh, jsx, vue, php, rb, cpp, c, h')
            print()
            
            # Test both regex patterns on the description
            jira_matches = jira_regex.findall(description)
            backtick_matches = backtick_regex.findall(description)
            print(f'🔍 Jira {{{{...}}}} matches in description: {jira_matches}')
            print(f'🔍 Backtick `...` matches in description: {backtick_matches}')
            print()
            
            # Only show if no matches found (for debugging)
            if not jira_matches and not backtick_matches:
                print('💡 Expected format: {{path/to/file.ext}} or `path/to/file.ext`')
            
        except ImportError as e:
            print(f'❌ Could not import TicketContext: {e}')
            print('💡 Make sure main.py is in the same directory')
        except Exception as e:
            print(f'❌ Error testing file extraction: {e}')
            print(f'Error type: {type(e).__name__}')
        
        print()
        
        # Check for repository URL custom field
        print()
        print('🔍 Checking for repository URL...')
        # Try common custom field IDs
        for field_id in ['customfield_12345', 'customfield_10001', 'customfield_10002', 'customfield_10003']:
            field_value = getattr(issue.fields, field_id, None)
            if field_value:
                print(f'   Found {field_id}: {field_value}')
        
        # Show all custom fields
        print('📋 All custom fields:')
        for attr in dir(issue.fields):
            if attr.startswith('customfield_'):
                value = getattr(issue.fields, attr, None)
                if value:
                    print(f'   {attr}: {str(value)[:100]}...' if len(str(value)) > 100 else f'   {attr}: {value}')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        print(f'Error type: {type(e).__name__}')
        
        # Additional troubleshooting info
        if 'Unauthorized' in str(e) or '401' in str(e):
            print('\n🔧 Troubleshooting suggestions:')
            print('   1. Check if your API token is valid')
            print('   2. Verify your email address is correct')
            print('   3. Make sure your account has access to Jira')
            
        elif 'Forbidden' in str(e) or '403' in str(e):
            print('\n🔧 Troubleshooting suggestions:')
            print('   1. Your credentials work, but you lack permissions')
            print('   2. Check if you have access to the QUEST project')
            print('   3. Verify the ticket QUEST-39 exists and you can see it')
            
        elif 'Not Found' in str(e) or '404' in str(e):
            print('\n🔧 Troubleshooting suggestions:')
            print('   1. The ticket QUEST-39 might not exist')
            print('   2. Check the correct ticket number in Jira web interface')
            print('   3. Make sure you have access to the QUEST project')

if __name__ == '__main__':
    test_jira_connection()