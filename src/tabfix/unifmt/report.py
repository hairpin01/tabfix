from typing import Dict
from dataclasses import dataclass, field


@dataclass
class ReportStats:
    total_files: int = 0
    formatted: int = 0
    failed: int = 0
    skipped: int = 0
    unchanged: int = 0
    by_formatter: Dict[str, int] = field(default_factory=dict)


class ReportGenerator:
    def __init__(self):
        self.stats = ReportStats()

    def add_result(self, formatted: bool = False, failed: bool = False,
                   skipped: bool = False, formatter: str = None):
        self.stats.total_files += 1
        if formatted:
            self.stats.formatted += 1
        elif failed:
            self.stats.failed += 1
        elif skipped:
            self.stats.skipped += 1
        else:
            self.stats.unchanged += 1

        if formatter:
            self.stats.by_formatter[formatter] = self.stats.by_formatter.get(formatter, 0) + 1

    def generate_report(self, verbose: bool = False) -> str:
        lines = [
            "=" * 50,
            "UNIFMT REPORT",
            "=" * 50,
            f"Total files:     {self.stats.total_files}",
            f"Formatted:       {self.stats.formatted}",
            f"Failed:          {self.stats.failed}",
            f"Skipped:         {self.stats.skipped}",
            f"Unchanged:       {self.stats.unchanged}",
        ]

        if verbose and self.stats.by_formatter:
            lines.append("\nBy formatter:")
            for formatter, count in sorted(self.stats.by_formatter.items()):
                lines.append(f"  {formatter}: {count}")

        if self.stats.failed > 0:
            lines.append("\n✗ Some files failed to format")

        return "\n".join(lines)

    def has_failures(self) -> bool:
        return self.stats.failed > 0

    def needs_formatting(self) -> bool:
        return self.stats.formatted > 0
