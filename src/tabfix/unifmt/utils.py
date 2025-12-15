class ReportGenerator:
    def __init__(self):
        self.stats = {
            "total_files": 0,
            "formatted": 0,
            "failed": 0,
            "skipped": 0,
        }

    def generate_report(self) -> str:
        return f"Processed: {self.stats['total_files']}, Formatted: {self.stats['formatted']}"
