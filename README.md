[![PyPI version](https://img.shields.io/pypi/v/tabfix-tool.svg)](https://pypi.org/project/tabfix-tool/)
[![PyPI downloads](https://img.shields.io/pypi/dm/tabfix-tool.svg)](https://pypi.org/project/tabfix-tool/)
[![Python versions](https://img.shields.io/pypi/pyversions/tabfix-tool.svg)](https://pypi.org/project/tabfix-tool/)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/7fceb52b899d44b3bb151b568dc99d38)](https://app.codacy.com/gh/hairpin01/tabfix/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![GitHub repo size](https://img.shields.io/github/repo-size/hairpin01/tabfix)](https://github.com/hairpin01/tabfix)
[![GitHub last commit](https://img.shields.io/github/last-commit/hairpin01/tabfix)](https://github.com/hairpin01/tabfix/commits/main)
[![GitHub issues](https://img.shields.io/github/issues-raw/hairpin01/tabfix)](https://github.com/hairpin01/tabfix/issues)
[![GitHub forks](https://img.shields.io/github/forks/hairpin01/tabfix?style=flat)](https://github.com/hairpin01/tabfix/network/members)
[![GitHub stars](https://img.shields.io/github/stars/hairpin01/tabfix)](https://github.com/hairpin01/tabfix/stargazers)
[![GitHub license](https://img.shields.io/github/license/hairpin01/tabfix)](https://github.com/hairpin01/tabfix/blob/main/LICENSE) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# TabFix Tool
Advanced tool for fixing `tab/space` indentation issues in `code` files.

## Features
> - Fix mixed tabs and spaces indentation
> - Remove trailing whitespace
> - Normalize line endings
> - Handle `UTF-8` BOM markers
> - Format `JSON` files
> - `Git` integration
> - Progress bars with tqdm
> - Colorful output

## Installation
```bash
# Install from PyPI
pip install tabfix-tool
```
```bash
# Or directly from GitHub
pip install git+https://github.com/hairpin01/tabfix.git
```
or via installer
```bash
curl https://raw.githubusercontent.com/hairpin01/tabfix/refs/heads/main/src/tabfix/installer.py | python3
```
> [!TIP]
> to install the unifmt package, see [optional](https://github.com/hairpin01/tabfix#install-optional-unifmt-or-devencodingfull)


## From source
```bash
git clone https://github.com/hairpin01/tabfix.git && cd tabfix && pip install -e .
```
## Usage
```bash
# Basic usage
tabfix file.py
```
```bash
# Recursive processing
tabfix --recursive src/
```
```bash
# Fix multiple issues
tabfix --all --progress .
```
```bash
# Check without modifying
tabfix --check-mixed --recursive .
```
## Complete Help Reference

<details>
<summary><b>Show full command reference (tabfix -h)</b></summary>

```bash
$ tabfix -h
usage: tabfix [-h] [-s SPACES] [-r] [--git-staged] [--git-unstaged]
              [--git-all-changed] [--no-gitignore] [--autoformat]
              [--check-format] [--list-formatters] [--formatters FORMATTERS]
              [--init-autoformat] [--skip-binary] [--no-skip-binary]
              [--force-encoding FORCE_ENCODING]
              [--fallback-encoding FALLBACK_ENCODING] [--warn-encoding]
              [--max-file-size MAX_FILE_SIZE] [--smart-processing]
              [--no-smart-processing] [--preserve-quotes] [-m] [-t] [-f]
              [--remove-bom] [--keep-bom] [--format-json] [-i] [--progress]
              [--dry-run] [--backup] [--diff FILE1 FILE2] [-v] [-q]
              [--no-color] [--init] [--config CONFIG] [--no-config]
              [paths ...]

Advanced tab/space indentation fixer with autoformatting

positional arguments:
  paths                 Files or directories to process

options:
  -h, --help            show this help message and exit
  -s, --spaces SPACES   Number of spaces per tab (default: 4)
  -r, --recursive       Process directories recursively
  --init                Initialize configuration file (.tabfixrc)
  --config CONFIG       Path to configuration file
  --no-config           Ignore configuration files

Git integration:
  --git-staged          Process only staged files in git
  --git-unstaged        Process only unstaged files in git
  --git-all-changed     Process all changed files in git
  --no-gitignore        Do not use .gitignore patterns

Autoformatting:
  --autoformat, -a      Autoformat files using external formatters
  --check-format        Check formatting without making changes
  --list-formatters     List available formatters and exit
  --formatters FORMATTERS
                        Comma-separated list of formatters to use (e.g.
                        black,isort)
  --init-autoformat     Initialize autoformat configuration file

Encoding and binary file handling:
  --skip-binary         Skip files that appear to be binary (default: True)
  --no-skip-binary      Process files even if they appear to be binary
  --force-encoding FORCE_ENCODING
                        Force specific encoding (skip auto-detection)
  --fallback-encoding FALLBACK_ENCODING
                        Fallback encoding when detection fails (default:
                        latin-1)
  --warn-encoding       Warn when encoding detection is uncertain
  --max-file-size MAX_FILE_SIZE
                        Maximum file size to process in bytes (default:
                        10MB)

File type specific processing:
  --smart-processing    Enable smart processing for different file types
                        (default: True)
  --no-smart-processing
                        Disable smart processing for different file types
  --preserve-quotes     Preserve original string quotes in code files

Formatting options:
  -m, --fix-mixed       Fix mixed tabs/spaces indentation
  -t, --fix-trailing    Remove trailing whitespace
  -f, --final-newline   Ensure file ends with newline
  --remove-bom          Remove UTF-8 BOM marker
  --keep-bom            Preserve existing BOM marker
  --format-json         Format JSON files with proper indentation

Operation mode:
  -i, --interactive     Interactive mode (confirm each change)
  --progress            Show progress bar during processing
  --dry-run             Show changes without modifying files
  --backup              Create backup files (.bak)
  --diff FILE1 FILE2    Compare indentation between two files

Output control:
  -v, --verbose         Verbose output
  -q, --quiet           Quiet mode (minimal output)
  --no-color            Disable colored output

Examples:
  tabfix --init                    # Create .tabfixrc config file
  tabfix --init-autoformat         # Create autoformat config
  tabfix --autoformat              # Autoformat files using external tools
  tabfix --check-format            # Check formatting without changes
  tabfix --list-formatters         # List available formatters
  tabfix --recursive --remove-bom  # Process recursively, remove BOM
  tabfix --git-staged --interactive # Interactive mode on staged files
  tabfix --diff file1.py file2.py  # Compare indentation
```
</details>


## install optional dev/encoding/full 
```
pip install tabfix-tool[all] # or {optional}
```

## API Documentation
<details>
<summary><b> Python API examples</b></summary>
  
```python
# developer_script.py
from tabfix import TabFixAPI, TabFixConfig, fix_string, fix_file

# Method 1: Using API class
config = TabFixConfig(spaces=2, fix_mixed=True, fix_trailing=True)
api = TabFixAPI(config)

# Fix a string
fixed_content, changes = api.fix_string("def foo():\n\tprint('hello')", Path("test.py"))
print(f"Fixed content: {fixed_content}")
print(f"Changes: {changes}")

# Fix a file
changed, file_changes = api.fix_file(Path("my_script.py"))
print(f"File changed: {changed}")
print(f"File changes: {file_changes}")

# Method 2: Using convenience functions
# Fix string directly
content = "if True:\n\tprint('tab')"
fixed, changes = fix_string(content, spaces=4)
print(f"Fixed: {fixed}")

# Check if file needs fixing
needs_fix, issues = check_file(Path("config.json"))
print(f"Needs fix: {needs_fix}, Issues: {issues}")

# Detect indentation style
result = detect_indentation(content)
print(f"Indentation: {result}")

# Create config file
create_config_file(Path(".tabfixrc.json"))
```
More:
```python
# developer_script.py
from tabfix import TabFixAPI, TabFixConfig, fix_string, fix_file

# Method 1: Using API class
config = TabFixConfig(spaces=2, fix_mixed=True, fix_trailing=True)
api = TabFixAPI(config)

# Fix a string
fixed_content, changes = api.fix_string("def foo():\n\tprint('hello')", Path("test.py"))
print(f"Fixed content: {fixed_content}")
print(f"Changes: {changes}")

# Fix a file
changed, file_changes = api.fix_file(Path("my_script.py"))
print(f"File changed: {changed}")
print(f"File changes: {file_changes}")

# Method 2: Using convenience functions
# Fix string directly
content = "if True:\n\tprint('tab')"
fixed, changes = fix_string(content, spaces=4)
print(f"Fixed: {fixed}")

# Check if file needs fixing
needs_fix, issues = check_file(Path("config.json"))
print(f"Needs fix: {needs_fix}, Issues: {issues}")

# Detect indentation style
result = detect_indentation(content)
print(f"Indentation: {result}")

# Create config file
create_config_file(Path(".tabfixrc.json"))
```

**telegram bot**

```python
#!/usr/bin/env python3
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional
import json
import shutil

from telegram import Update, BotCommand, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

from tabfix import TabFixAPI, TabFixConfig, fix_string, detect_indentation


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml',
    '.md', '.txt', '.html', '.htm', '.css', '.scss', '.sass',
    '.xml', '.ini', '.cfg', '.toml', '.sh', '.bash', '.zsh',
    '.cpp', '.c', '.h', '.hpp', '.java', '.go', '.rs'
}

class TabFixBot:
    def __init__(self, token: str, admin_ids: list = None):
        self.token = token
        self.admin_ids = admin_ids or []
        self.config = TabFixConfig(spaces=4, fix_mixed=True, fix_trailing=True, final_newline=True)
        self.api = TabFixAPI(self.config)
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = """👋 *TabFix Bot*

I can fix indentation and formatting issues in your code files!

*Supported formats:*
• Python (.py)
• JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
• JSON (.json)
• YAML (.yaml, .yml)
• Markdown (.md)
• HTML/CSS (.html, .css)
• Shell scripts (.sh, .bash)
• C/C++/Java/Go/Rust

*How to use:*
1. Send me a code file
2. I'll fix indentation, trailing spaces, and formatting
3. I'll send back the fixed file

*Commands:*
/start - Show this message
/help - Show help
/fixconfig - Show current config
/setspaces <N> - Set spaces per tab (default: 4)
/fixmixed <on/off> - Toggle mixed indentation fixing
/fixtrailing <on/off> - Toggle trailing space fixing
/newline <on/off> - Toggle final newline

*Example:* Send me a Python file with mixed tabs and spaces."""
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """📚 *Help*

Send me any code file and I'll fix:
• Mixed tabs/spaces indentation
• Trailing whitespace
• Missing final newline
• JSON formatting

*Quick commands:*
/setspaces 2 - Use 2 spaces per tab
/fixmixed off - Don't fix mixed indentation
/fixtrailing on - Fix trailing spaces
/newline on - Ensure final newline

*Admin commands* (if you're admin):
/config <json> - Set custom configuration
/stats - Show bot statistics
"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def show_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = self.api.config.to_dict()
        config_str = json.dumps(config, indent=2, default=str)
        await update.message.reply_text(f"```json\n{config_str}\n```", parse_mode='Markdown')
    
    async def set_spaces(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("Usage: /setspaces <number>")
                return
            
            spaces = int(context.args[0])
            if spaces < 1 or spaces > 8:
                await update.message.reply_text("Please use a number between 1 and 8")
                return
            
            self.config.spaces = spaces
            self.api = TabFixAPI(self.config)
            await update.message.reply_text(f"✅ Spaces per tab set to {spaces}")
        except ValueError:
            await update.message.reply_text("Please provide a valid number")
    
    async def toggle_fix_mixed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("Usage: /fixmixed <on/off>")
                return
            
            state = context.args[0].lower()
            if state == 'on':
                self.config.fix_mixed = True
                await update.message.reply_text("✅ Mixed indentation fixing enabled")
            elif state == 'off':
                self.config.fix_mixed = False
                await update.message.reply_text("✅ Mixed indentation fixing disabled")
            else:
                await update.message.reply_text("Please use 'on' or 'off'")
            
            self.api = TabFixAPI(self.config)
        except Exception as e:
            logger.error(f"Error in toggle_fix_mixed: {e}")
            await update.message.reply_text("❌ Error updating setting")
    
    async def toggle_fix_trailing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("Usage: /fixtrailing <on/off>")
                return
            
            state = context.args[0].lower()
            if state == 'on':
                self.config.fix_trailing = True
                await update.message.reply_text("✅ Trailing space fixing enabled")
            elif state == 'off':
                self.config.fix_trailing = False
                await update.message.reply_text("✅ Trailing space fixing disabled")
            else:
                await update.message.reply_text("Please use 'on' or 'off'")
            
            self.api = TabFixAPI(self.config)
        except Exception as e:
            logger.error(f"Error in toggle_fix_trailing: {e}")
            await update.message.reply_text("❌ Error updating setting")
    
    async def toggle_newline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("Usage: /newline <on/off>")
                return
            
            state = context.args[0].lower()
            if state == 'on':
                self.config.final_newline = True
                await update.message.reply_text("✅ Final newline enforcement enabled")
            elif state == 'off':
                self.config.final_newline = False
                await update.message.reply_text("✅ Final newline enforcement disabled")
            else:
                await update.message.reply_text("Please use 'on' or 'off'")
            
            self.api = TabFixAPI(self.config)
        except Exception as e:
            logger.error(f"Error in toggle_newline: {e}")
            await update.message.reply_text("❌ Error updating setting")
    
    async def process_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.chat.send_action(ChatAction.TYPING)
        
        document = update.message.document
        if not document:
            await update.message.reply_text("❌ Please send a file")
            return
        
        file_size = document.file_size
        if file_size > self.max_file_size:
            await update.message.reply_text(f"❌ File too large ({file_size / 1024:.0f}KB). Max size is 10MB")
            return
        
        file_ext = Path(document.file_name).suffix.lower()
        if file_ext not in SUPPORTED_EXTENSIONS:
            await update.message.reply_text(f"❌ Unsupported file type: {file_ext}")
            await update.message.reply_text(f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
            return
        
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="tabfix_"))
            original_path = temp_dir / document.file_name
            
            file = await context.bot.get_file(document.file_id)
            await file.download_to_drive(original_path)
            
            logger.info(f"Processing file: {original_path}, size: {file_size} bytes")
            
            changed, changes = self.api.fix_file(original_path)
            
            if not changed:
                await update.message.reply_text("✅ File is already properly formatted!")
                shutil.rmtree(temp_dir)
                return
            
            fixed_path = temp_dir / f"fixed_{document.file_name}"
            shutil.copy(original_path, fixed_path)
            
            with open(fixed_path, 'rb') as f:
                await update.message.reply_document(
                    document=InputFile(f, filename=f"fixed_{document.file_name}"),
                    caption=f"✅ Fixed {len(changes)} issue(s)\nChanges: {', '.join(changes[:3])}"
                )
            
            shutil.rmtree(temp_dir)
            
        except Exception as e:
            logger.error(f"Error processing file: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Error processing file: {str(e)}")
    
    async def process_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.chat.send_action(ChatAction.TYPING)
        
        text = update.message.text
        if not text or len(text) < 10:
            await update.message.reply_text("❌ Please send code text to fix")
            return
        
        if len(text) > 4000:
            await update.message.reply_text("❌ Text too long. Please send as a file for large code")
            return
        
        try:
            fixed_text, changes = fix_string(text, spaces=self.config.spaces)
            
            if not changes:
                await update.message.reply_text("✅ Text is already properly formatted!")
                return
            
            await update.message.reply_text(
                f"```\n{fixed_text}\n```\n\n"
                f"✅ Fixed {len(changes)} issue(s)\n"
                f"Changes: {', '.join(changes)}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            await update.message.reply_text(f"❌ Error processing text: {str(e)}")
    
    async def detect_indent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.chat.send_action(ChatAction.TYPING)
        
        text = update.message.text
        if not text or len(text) < 10:
            await update.message.reply_text("❌ Please send code text to analyze")
            return
        
        try:
            result = detect_indentation(text)
            
            message = f"*Indentation Analysis*\n\n"
            message += f"Uses tabs: {'✅ Yes' if result['uses_tabs'] else '❌ No'}\n"
            message += f"Uses spaces: {'✅ Yes' if result['uses_spaces'] else '❌ No'}\n"
            message += f"Mixed indentation: {'⚠️ Yes' if result['mixed'] else '✅ No'}\n"
            
            if result['common_indent']:
                message += f"Common indent size: {result['common_indent']}\n"
            
            message += f"Total lines: {result['total_lines']}\n"
            message += f"Indented lines: {result['indented_lines']}\n\n"
            
            if result['mixed']:
                message += "*Recommendation:* Run /fixmixed on to fix mixed indentation"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error detecting indent: {e}")
            await update.message.reply_text(f"❌ Error analyzing text: {str(e)}")
    
    async def set_custom_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in self.admin_ids:
            await update.message.reply_text("❌ Admin only command")
            return
        
        try:
            if not context.args:
                await update.message.reply_text("Usage: /config <json_config>")
                return
            
            config_json = ' '.join(context.args)
            config_dict = json.loads(config_json)
            
            self.config.update_from_dict(config_dict)
            self.api = TabFixAPI(self.config)
            
            await update.message.reply_text("✅ Configuration updated successfully")
            
        except json.JSONDecodeError:
            await update.message.reply_text("❌ Invalid JSON format")
        except Exception as e:
            logger.error(f"Error setting config: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in self.admin_ids:
            await update.message.reply_text("❌ Admin only command")
            return
        
        stats = {
            "spaces_per_tab": self.config.spaces,
            "fix_mixed": self.config.fix_mixed,
            "fix_trailing": self.config.fix_trailing,
            "final_newline": self.config.final_newline,
            "max_file_size": self.max_file_size,
        }
        
        stats_str = json.dumps(stats, indent=2)
        await update.message.reply_text(f"```json\n{stats_str}\n```", parse_mode='Markdown')
    
    def setup_handlers(self, application: Application):
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("fixconfig", self.show_config))
        application.add_handler(CommandHandler("setspaces", self.set_spaces))
        application.add_handler(CommandHandler("fixmixed", self.toggle_fix_mixed))
        application.add_handler(CommandHandler("fixtrailing", self.toggle_fix_trailing))
        application.add_handler(CommandHandler("newline", self.toggle_newline))
        application.add_handler(CommandHandler("config", self.set_custom_config))
        application.add_handler(CommandHandler("stats", self.show_stats))
        application.add_handler(CommandHandler("detect", self.detect_indent))
        
        application.add_handler(MessageHandler(filters.Document.ALL, self.process_file))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_text))
    
    async def setup_bot_commands(self, application: Application):
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help"),
            BotCommand("fixconfig", "Show current configuration"),
            BotCommand("setspaces", "Set spaces per tab"),
            BotCommand("fixmixed", "Toggle mixed indentation fixing"),
            BotCommand("fixtrailing", "Toggle trailing space fixing"),
            BotCommand("newline", "Toggle final newline"),
            BotCommand("detect", "Analyze indentation"),
        ]
        
        if self.admin_ids:
            commands.extend([
                BotCommand("config", "Set custom config (admin)"),
                BotCommand("stats", "Show bot stats (admin)"),
            ])
        
        await application.bot.set_my_commands(commands)
    
    async def run(self):
        application = Application.builder().token(self.token).build()
        
        self.setup_handlers(application)
        await self.setup_bot_commands(application)
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("Bot started successfully")
        
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("Shutting down bot...")
            await application.stop()
            logger.info("Bot stopped")


def main():
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_IDS = [int(id.strip()) for id in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if id.strip()]
    
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is required")
        print("Create a .env file with:")
        print("TELEGRAM_BOT_TOKEN=your_bot_token_here")
        print("TELEGRAM_ADMIN_IDS=123456789,987654321 (optional)")
        return
    
    bot = TabFixBot(token=TOKEN, admin_ids=ADMIN_IDS)
    
    print(f"Starting TabFix Telegram Bot...")
    print(f"Admin IDs: {ADMIN_IDS}")
    print("Press Ctrl+C to stop")
    
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
```

</details>
