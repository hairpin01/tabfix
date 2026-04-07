# Changelog

## Unreleased
- honor `preserve_quotes` flag during JSON fixes (stops auto-converting single → double quotes while still trimming trailing commas)
- add tests covering brace/colon placeholders and quote preservation
- add `--detect-spaces` auto-detection of indent width from project files
- add `--respect-strings` to skip indent fixes inside Python triple-quoted strings
- add `--install-pre-commit` helper to drop a Git hook that runs tabfix in check-only mode

## 1.1.0 

### New Features
- Improved file encoding detection
- Smart processing for different file types
- Better binary file detection
- Enhanced error handling

### Bug Fixes
- Fixed Unicode decoding errors
- Improved .gitignore handling
- Better progress reporting

## 1.0.0 
- Initial release
