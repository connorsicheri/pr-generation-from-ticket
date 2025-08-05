# Jira Ticket Format for AI PR Generator

This document describes the required format for Jira tickets that work with the AI PR Generator tool.

## 📋 **Required Fields**

### **1. Summary/Title**
- Brief description of what needs to be implemented
- This becomes the PR title

**Example:**
```
Add loading state to button component
```

### **2. Description** 
The description should contain:
- **File paths** in backticks (`` `file/path.ext` ``)
- **Clear instructions** about what to implement
- **Context** about the feature/fix

### **3. Repository URL (Custom Field)**
- Must be configured in your Jira instance
- Currently expects `customfield_12345` (see main.py line 206)
- Should contain the full Git repository URL

## 🎯 **Supported File Types**

The tool automatically detects file paths for these extensions:
- **Python**: `.py`
- **Go**: `.go` 
- **JavaScript**: `.js`
- **TypeScript**: `.ts`, `.tsx`
- **Java**: `.java`
- **Configuration**: `.yaml`, `.json`

## ✅ **Good Ticket Examples**

### **Example 1: Feature Implementation**
```
Summary: Add dark mode toggle to settings page

Description:
Implement a dark mode toggle in the settings component `src/components/Settings.tsx`.

The toggle should:
- Save the preference to localStorage
- Update the global theme context
- Show a moon/sun icon depending on current mode
- Apply dark styles defined in `src/styles/dark-theme.css`

When dark mode is enabled, update the main layout in `src/components/Layout.tsx` to apply the dark theme class.

Repository URL: https://github.com/company/frontend-app.git
```

### **Example 2: Bug Fix**
```
Summary: Fix validation error in user registration form

Description:
The email validation in `src/forms/RegisterForm.tsx` is not working correctly for emails with plus signs (e.g., user+test@example.com).

Update the email regex pattern in the validation function and add unit tests in `src/forms/__tests__/RegisterForm.test.tsx` to cover edge cases including:
- Emails with plus signs
- Emails with dots in the local part
- International domain names

Repository URL: https://github.com/company/frontend-app.git
```

### **Example 3: API Integration**
```
Summary: Integrate payment processing API

Description:
Add payment processing functionality to the checkout flow.

Create a new service `src/services/PaymentService.ts` that:
- Handles credit card processing via Stripe API
- Validates payment data before submission
- Returns proper error messages for failed transactions

Update the checkout component `src/components/Checkout.tsx` to:
- Use the new payment service
- Show loading states during processing
- Handle success and error scenarios

Add payment-related types to `src/types/payment.ts`.

Repository URL: https://github.com/company/ecommerce-api.git
```

## ❌ **Bad Ticket Examples**

### **Too Vague**
```
Summary: Fix the website

Description:
The website is broken, please fix it.
```
*Issues: No file paths, no specific instructions*

### **Missing File Paths**
```
Summary: Add user authentication

Description:
We need to add user login and registration functionality.
```
*Issues: No specific files mentioned in backticks*

### **Wrong File Path Format**
```
Summary: Update header component

Description:
Change the header in src/components/Header.tsx to include a search bar.
```
*Issues: File path not in backticks*

## 🏷️ **Future Enhancement: Jira Templates**

### **Jira Issue Template (Future)**
You could create a Jira issue template with this format:

```
## Summary
[Brief description of the feature/fix]

## Files to Modify
- `path/to/file1.ext` - [What to change]
- `path/to/file2.ext` - [What to change]

## Implementation Details
[Detailed instructions for the AI]

## Acceptance Criteria
- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Repository
[Auto-populated from project settings]
```

### **Jira Automation Ideas**
1. **Auto-tag Detection**: Use Jira automation to detect tickets with specific labels (e.g., "ai-ready") and format them automatically
2. **Template Enforcement**: Require the template for tickets in certain projects
3. **File Path Validation**: Jira automation could validate that file paths exist in the repository
4. **Status Updates**: Automatically update ticket status when PR is created

## 🔧 **Configuration Notes**

### **Custom Field Setup**
Currently the tool expects repository URL in `customfield_12345`. To change this:

1. Find your custom field ID in Jira admin
2. Update line 206 in `main.py`:
   ```python
   repo_url = issue.fields.customfield_YOUR_ID
   ```

### **File Type Extensions**
To add support for more file types, update the regex in `main.py` line 94:
```python
file_regex = re.compile(r"`([^`\n]+\.(?:py|go|js|ts|tsx|java|yaml|json|YOUR_EXT))`")
```

## 🎯 **Best Practices**

1. **Be Specific**: Include exact file paths and clear instructions
2. **Use Examples**: Show expected input/output when relevant  
3. **Break Down Complex Tasks**: Split large features into multiple tickets
4. **Include Context**: Explain why the change is needed
5. **Test Cases**: Mention what should be tested
6. **Dependencies**: Note any files that might be affected

## 📖 **Template Checklist**

Before running the AI PR Generator, ensure your ticket has:

- [ ] Clear, specific summary
- [ ] File paths in backticks (`` `path/file.ext` ``)
- [ ] Detailed implementation instructions
- [ ] Repository URL in custom field
- [ ] Supported file extensions (.py, .js, .ts, etc.)
- [ ] Context about why the change is needed
- [ ] Expected behavior described