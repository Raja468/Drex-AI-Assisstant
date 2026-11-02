# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/markdown_renderer.py  —  Markdown Renderer
#
#  Renders markdown-formatted text in Tkinter text widgets.
#
#  Features:
#  - Headers (H1-H6)
#  - Bold and italic
#  - Code blocks with syntax highlighting
#  - Inline code
#  - Lists (ordered and unordered)
#  - Links
#  - Blockquotes
#  - Horizontal rules
#
#  Uses regex-based parsing for lightweight rendering
#  without external dependencies.
# ============================================================

import re
import tkinter as tk
from typing import Optional
from loguru import logger


class MarkdownRenderer:
    """
    Markdown renderer for Tkinter text widgets.
    
    Parses markdown and applies appropriate tags for styling.
    
    Usage:
        renderer = MarkdownRenderer(text_widget)
        renderer.render("# Hello **World**")
    """
    
    # Markdown patterns
    PATTERNS = {
        "h1": re.compile(r'^# (.+)$', re.MULTILINE),
        "h2": re.compile(r'^## (.+)$', re.MULTILINE),
        "h3": re.compile(r'^### (.+)$', re.MULTILINE),
        "h4": re.compile(r'^#### (.+)$', re.MULTILINE),
        "h5": re.compile(r'^##### (.+)$', re.MULTILINE),
        "h6": re.compile(r'^###### (.+)$', re.MULTILINE),
        "bold": re.compile(r'\*\*(.+?)\*\*'),
        "italic": re.compile(r'\*(.+?)\*'),
        "code_block": re.compile(r'```(\w*)\n(.*?)```', re.DOTALL),
        "inline_code": re.compile(r'`([^`]+)`'),
        "link": re.compile(r'\[([^\]]+)\]\(([^)]+)\)'),
        "blockquote": re.compile(r'^> (.+)$', re.MULTILINE),
        "ul": re.compile(r'^[\-\*] (.+)$', re.MULTILINE),
        "ol": re.compile(r'^\d+\. (.+)$', re.MULTILINE),
        "hr": re.compile(r'^---+$', re.MULTILINE),
        "table_row": re.compile(r'^\|(.+)\|$', re.MULTILINE),
    }
    
    # Default styles (can be overridden via apply_theme())
    STYLES = {
        "h1": {"font": ("Segoe UI", 20, "bold"), "foreground": "#e4e4e7", "spacing1": 14, "spacing3": 10},
        "h2": {"font": ("Segoe UI", 17, "bold"), "foreground": "#e4e4e7", "spacing1": 12, "spacing3": 8},
        "h3": {"font": ("Segoe UI", 15, "bold"), "foreground": "#e4e4e7", "spacing1": 10, "spacing3": 6},
        "h4": {"font": ("Segoe UI", 13, "bold"), "foreground": "#d4d4d8", "spacing1": 8, "spacing3": 4},
        "h5": {"font": ("Segoe UI", 12, "bold"), "foreground": "#d4d4d8", "spacing1": 6, "spacing3": 2},
        "h6": {"font": ("Segoe UI", 11, "bold"), "foreground": "#a1a1aa", "spacing1": 6, "spacing3": 2},
        "bold": {"font": ("Segoe UI", 11, "bold")},
        "italic": {"font": ("Segoe UI", 11, "italic")},
        "code": {"font": ("Consolas", 10), "foreground": "#f472b6", "background": "#1e1e3f",
                 "borderwidth": 1, "relief": "solid"},
        "code_block": {"font": ("Consolas", 10), "foreground": "#a5f3fc", "background": "#0f172a",
                        "lmargin1": 16, "lmargin2": 16, "spacing1": 10, "spacing3": 10,
                        "borderwidth": 1, "relief": "solid"},
        "link": {"foreground": "#60a5fa", "underline": True},
        "blockquote": {"foreground": "#a1a1aa", "lmargin1": 20, "lmargin2": 16,
                       "font": ("Segoe UI", 11, "italic"),
                       "borderwidth": 0, "background": "#16161a"},
        "ul": {"lmargin1": 32, "lmargin2": 24, "spacing1": 2, "spacing3": 2},
        "ol": {"lmargin1": 32, "lmargin2": 24, "spacing1": 2, "spacing3": 2},
        "hr": {"foreground": "#3f3f46", "spacing1": 12, "spacing3": 12},
        "table": {"font": ("Segoe UI", 11), "lmargin1": 0, "lmargin2": 0,
                  "spacing1": 2, "spacing3": 2},
        "table_header": {"font": ("Segoe UI", 11, "bold"), "foreground": "#e4e4e7",
                         "background": "#1e293b", "spacing1": 4, "spacing3": 4},
        "table_sep": {"font": ("Segoe UI", 11), "foreground": "#4a4a50"},
    }
    
    def __init__(self, text_widget: tk.Text, theme: dict | None = None):
        self.text_widget = text_widget
        if theme:
            for tag, style in theme.items():
                if tag in self.STYLES:
                    self.STYLES[tag] = style
        self._configure_tags()
        logger.debug("MarkdownRenderer initialized")
    
    def _configure_tags(self):
        """Configure text tags for markdown elements."""
        for tag_name, style in self.STYLES.items():
            try:
                self.text_widget.tag_configure(tag_name, **style)
            except Exception as e:
                logger.warning("Failed to configure tag {}: {}", tag_name, e)
    
    def render(self, markdown_text: str):
        """
        Render markdown text to the text widget.
        
        Args:
            markdown_text: Markdown-formatted text to render
        """
        # Clear existing content
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        
        # Process markdown
        processed = self._process_markdown(markdown_text)
        
        # Insert processed text
        self.text_widget.insert("1.0", processed["text"])
        
        # Apply tags
        for tag_name, ranges in processed["tags"].items():
            for start, end in ranges:
                try:
                    self.text_widget.tag_add(tag_name, start, end)
                except Exception as e:
                    logger.warning("Failed to apply tag {}: {}", tag_name, e)
        
        self.text_widget.config(state="disabled")
    
    def append(self, markdown_text: str):
        """
        Append markdown text to the text widget.
        
        Args:
            markdown_text: Markdown-formatted text to append
        """
        self.text_widget.config(state="normal")
        
        # Get current end position
        start_pos = self.text_widget.index("end-1c")
        
        # Process markdown
        processed = self._process_markdown(markdown_text)
        
        # Insert processed text
        self.text_widget.insert("end", processed["text"])
        
        # Apply tags (adjusting positions)
        start_line = int(start_pos.split(".")[0])
        for tag_name, ranges in processed["tags"].items():
            for rel_start, rel_end in ranges:
                # Convert relative positions to absolute
                rel_start_line, rel_start_col = rel_start.split(".")
                rel_end_line, rel_end_col = rel_end.split(".")
                
                abs_start = f"{start_line + int(rel_start_line) - 1}.{rel_start_col}"
                abs_end = f"{start_line + int(rel_end_line) - 1}.{rel_end_col}"
                
                try:
                    self.text_widget.tag_add(tag_name, abs_start, abs_end)
                except Exception:
                    pass
        
        self.text_widget.config(state="disabled")
        self.text_widget.see("end")
    
    def _process_markdown(self, text: str) -> dict:
        """
        Process markdown text and extract tags.
        
        Returns dict with 'text' and 'tags' keys.
        """
        result = {"text": text, "tags": {tag: [] for tag in self.STYLES}}
        
        # Process code blocks first (to avoid processing markdown inside)
        text, code_tags = self._process_code_blocks(text)
        result["tags"]["code_block"] = code_tags
        
        # Process headers
        text, h_tags = self._process_headers(text)
        for level, ranges in h_tags.items():
            result["tags"][level] = ranges
        
        # Process inline elements
        text, inline_tags = self._process_inline(text)
        for tag, ranges in inline_tags.items():
            result["tags"][tag] = ranges
        
        # Process lists
        text, list_tags = self._process_lists(text)
        for tag, ranges in list_tags.items():
            result["tags"][tag] = ranges
        
        # Process blockquotes
        text, bq_tags = self._process_blockquotes(text)
        result["tags"]["blockquote"] = bq_tags

        # Process tables
        text, table_tags = self._process_tables(text)
        for tag, ranges in table_tags.items():
            result["tags"][tag] = ranges

        # Process horizontal rules
        text, hr_tags = self._process_hr(text)
        result["tags"]["hr"] = hr_tags
        
        result["text"] = text
        return result
    
    def _process_code_blocks(self, text: str) -> tuple[str, list]:
        """Process code blocks."""
        tags = []
        
        def replace_code_block(match):
            lang = match.group(1)
            code = match.group(2)
            start = len(text[:match.start()].split("\n"))
            end = start + len(code.split("\n"))
            tags.append((f"{start}.0", f"{end}.0"))
            return f"\n{code}\n"
        
        text = self.PATTERNS["code_block"].sub(replace_code_block, text)
        return text, tags
    
    def _process_headers(self, text: str) -> tuple[str, dict]:
        """Process headers."""
        tags = {f"h{i}": [] for i in range(1, 7)}
        
        for level in range(1, 7):
            pattern = self.PATTERNS[f"h{level}"]
            
            def replace_header(match, lvl=level):
                content = match.group(1)
                line_num = len(text[:match.start()].split("\n"))
                tags[f"h{lvl}"].append((f"{line_num}.0", f"{line_num}.{len(content)}"))
                return content
            
            text = pattern.sub(replace_header, text)
        
        return text, tags
    
    def _process_inline(self, text: str) -> tuple[str, dict]:
        """Process inline elements (bold, italic, code, links)."""
        tags = {"bold": [], "italic": [], "code": [], "link": []}
        
        # Process bold
        for match in self.PATTERNS["bold"].finditer(text):
            start = match.start()
            end = match.start() + len(match.group(1))
            line = len(text[:start].split("\n"))
            col_start = start - text.rfind("\n", 0, start) - 1
            col_end = col_start + len(match.group(1))
            tags["bold"].append((f"{line}.{col_start}", f"{line}.{col_end}"))
        
        text = self.PATTERNS["bold"].sub(r'\1', text)
        
        # Process italic
        for match in self.PATTERNS["italic"].finditer(text):
            start = match.start()
            line = len(text[:start].split("\n"))
            col_start = start - text.rfind("\n", 0, start) - 1
            col_end = col_start + len(match.group(1))
            tags["italic"].append((f"{line}.{col_start}", f"{line}.{col_end}"))
        
        text = self.PATTERNS["italic"].sub(r'\1', text)
        
        # Process inline code
        for match in self.PATTERNS["inline_code"].finditer(text):
            start = match.start()
            line = len(text[:start].split("\n"))
            col_start = start - text.rfind("\n", 0, start) - 1
            col_end = col_start + len(match.group(1))
            tags["code"].append((f"{line}.{col_start}", f"{line}.{col_end}"))
        
        text = self.PATTERNS["inline_code"].sub(r'\1', text)
        
        # Process links
        for match in self.PATTERNS["link"].finditer(text):
            start = match.start()
            line = len(text[:start].split("\n"))
            col_start = start - text.rfind("\n", 0, start) - 1
            col_end = col_start + len(match.group(1))
            tags["link"].append((f"{line}.{col_start}", f"{line}.{col_end}"))
        
        text = self.PATTERNS["link"].sub(r'\1', text)
        
        return text, tags
    
    def _process_lists(self, text: str) -> tuple[str, dict]:
        """Process lists."""
        tags = {"ul": [], "ol": []}
        
        # Unordered lists
        for match in self.PATTERNS["ul"].finditer(text):
            line = len(text[:match.start()].split("\n"))
            tags["ul"].append((f"{line}.0", f"{line}.{len(match.group(0))}"))
        
        # Ordered lists
        for match in self.PATTERNS["ol"].finditer(text):
            line = len(text[:match.start()].split("\n"))
            tags["ol"].append((f"{line}.0", f"{line}.{len(match.group(0))}"))
        
        return text, tags
    
    def _process_blockquotes(self, text: str) -> tuple[str, dict]:
        """Process blockquotes."""
        tags = []
        
        for match in self.PATTERNS["blockquote"].finditer(text):
            line = len(text[:match.start()].split("\n"))
            tags.append((f"{line}.0", f"{line}.{len(match.group(1))}"))
        
        text = self.PATTERNS["blockquote"].sub(r'\1', text)
        return text, tags

    def _process_tables(self, text: str) -> tuple[str, dict]:
        """Process markdown tables into aligned monospace text."""
        lines = text.split("\n")
        result_lines = []
        i = 0
        while i < len(lines):
            trimmed = lines[i].strip()
            if not (trimmed.startswith("|") and trimmed.endswith("|")):
                result_lines.append(lines[i])
                i += 1
                continue

            # Collect consecutive table rows
            tbl_rows = []
            sep_idx = -1
            j = i
            while j < len(lines) and lines[j].strip().startswith("|") and lines[j].strip().endswith("|"):
                tbl_rows.append(lines[j].strip())
                j += 1

            # Find separator row
            for k, row in enumerate(tbl_rows):
                cells = row[1:-1].split("|")
                if all(re.match(r'^[\-:]+$', c.strip()) for c in cells if c.strip()):
                    sep_idx = k
                    break

            # Extract rows (skip separator)
            if sep_idx >= 0:
                data_rows = [r for idx, r in enumerate(tbl_rows) if idx != sep_idx]
                header = [c.strip() for c in tbl_rows[0][1:-1].split("|")]
                header_row = data_rows[0] if data_rows else ""
                data_rows = data_rows[1:] if data_rows else []
            else:
                header = None
                data_rows = tbl_rows

            # Calculate column widths
            all_rows = []
            for row in tbl_rows:
                cells = row[1:-1].split("|")
                if not all(re.match(r'^[\-:]+$', c.strip()) for c in cells if c.strip()):
                    all_rows.append([c.strip() for c in cells])

            if not all_rows:
                i = j
                continue

            widths = [max(len(row[k]) if k < len(row) else 0 for row in all_rows)
                      for k in range(max(len(r) for r in all_rows))]

            # Render aligned table
            sep_line = "-" * (sum(widths) + 3 * (len(widths) - 1) + 2)
            separator = "  " + sep_line + "  "

            # Header row (bolded) + separator
            header = all_rows[0]
            hdr_text = "  " + " | ".join(
                h.ljust(widths[i]) for i, h in enumerate(header)) + "  "
            result_lines.append(hdr_text)
            result_lines.append(separator)

            # Data rows
            for row in all_rows[1:]:
                row_text = "  " + " | ".join(
                    (row[i] if i < len(row) else "").ljust(widths[i])
                    for i in range(len(widths))
                ) + "  "
                result_lines.append(row_text)

            result_lines.append("")
            i = j

        return "\n".join(result_lines), {"table": [], "table_header": [], "table_sep": []}

    def _process_hr(self, text: str) -> tuple[str, dict]:
        """Process horizontal rules."""
        tags = []
        
        for match in self.PATTERNS["hr"].finditer(text):
            line = len(text[:match.start()].split("\n"))
            tags.append((f"{line}.0", f"{line}.{len(match.group(0))}"))
        
        text = self.PATTERNS["hr"].sub("─" * 40, text)
        return text, tags
    
    def clear(self):
        """Clear the text widget."""
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.config(state="disabled")
    
    def __repr__(self) -> str:
        return "MarkdownRenderer()"