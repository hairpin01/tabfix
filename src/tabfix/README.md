# Project structure
```
tabfix/
├── src/
│   └── tabfix/
│       ├── __init__.py         # Public API
│       ├── __main__.py         # CLI entry point
│       ├── api.py              # Developer API
│       ├── core.py             # Main functionality
│       ├── config.py           # Configuration handling
│       └── unifmt/             # Universal formatter
│           ├── __init__.py
│           ├── __main__.py
│           ├── cli.py
│           ├── config.py
│           ├── formatters.py
│           └── collector.py
├── tests/                      # Test suite
├── pyproject.toml             # Build configuration
└── README.md                  # This file
```