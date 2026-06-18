from pathlib import Path

DB_PATH: str = str(Path(__file__).parent / "database.db")

C: dict[str, str] = {
    "bg":     "#1e1e2e",
    "panel":  "#2a2a3e",
    "panel2": "#222236",
    "accent": "#7c3aed",
    "accent2":"#06b6d4",
    "green":  "#10b981",
    "red":    "#ef4444",
    "orange": "#f59e0b",
    "yellow": "#eab308",
    "text":   "#e2e8f0",
    "sub":    "#94a3b8",
    "sel":    "#3b1f6e",
    "border": "#3f3f5a",
}
