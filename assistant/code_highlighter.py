"""
DREX - AI Assistant Runtime
assistant/code_highlighter.py - Syntax Highlighting

Provides syntax highlighting for code blocks in chat messages.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class Token:
    """A syntax-highlighted token."""
    text: str
    token_type: str
    color: str = ""


@dataclass
class CodeBlock:
    """A code block with language and content."""
    language: str
    code: str
    highlighted: bool = False


# Color scheme for syntax highlighting
COLORS = {
    "keyword": "#C678DD",      # Purple
    "string": "#98C379",       # Green
    "number": "#D19A66",       # Orange
    "comment": "#5C6370",      # Gray
    "function": "#61AFEF",     # Blue
    "class": "#E5C07B",        # Yellow
    "operator": "#56B6C2",     # Cyan
    "punctuation": "#ABB2BF",  # Light gray
    "builtin": "#E06C75",      # Red
    "decorator": "#C678DD",    # Purple
    "default": "#ABB2BF",      # Light gray
}

# Python keywords
PYTHON_KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield"
}

# Python builtins
PYTHON_BUILTINS = {
    "abs", "all", "any", "bin", "bool", "bytes", "callable", "chr",
    "classmethod", "compile", "complex", "delattr", "dict", "dir",
    "divmod", "enumerate", "eval", "exec", "filter", "float", "format",
    "frozenset", "getattr", "globals", "hasattr", "hash", "help", "hex",
    "id", "input", "int", "isinstance", "issubclass", "iter", "len",
    "list", "locals", "map", "max", "memoryview", "min", "next", "object",
    "oct", "open", "ord", "pow", "print", "property", "range", "repr",
    "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
    "str", "sum", "super", "tuple", "type", "vars", "zip"
}

# JavaScript keywords
JS_KEYWORDS = {
    "async", "await", "break", "case", "catch", "class", "const", "continue",
    "debugger", "default", "delete", "do", "else", "export", "extends",
    "false", "finally", "for", "function", "if", "import", "in", "instanceof",
    "let", "new", "null", "of", "return", "static", "super", "switch",
    "this", "throw", "true", "try", "typeof", "undefined", "var", "void",
    "while", "with", "yield"
}


class CodeHighlighter:
    """
    Syntax highlighter for code blocks.
    
    Supports:
    - Python
    - JavaScript/TypeScript
    - JSON
    - Bash/Shell
    - Plain text fallback
    """
    
    def __init__(self):
        """Initialize the code highlighter."""
        self._languages = {
            "python": self._highlight_python,
            "py": self._highlight_python,
            "javascript": self._highlight_javascript,
            "js": self._highlight_javascript,
            "typescript": self._highlight_javascript,
            "ts": self._highlight_javascript,
            "json": self._highlight_json,
            "bash": self._highlight_bash,
            "sh": self._highlight_bash,
            "shell": self._highlight_bash,
        }
        logger.debug("CodeHighlighter initialized")
    
    def highlight(self, code: str, language: str = "") -> List[Token]:
        """
        Highlight code with syntax coloring.
        
        Args:
            code: Source code to highlight
            language: Programming language (auto-detected if empty)
            
        Returns:
            List of Token objects with text and color
        """
        # Auto-detect language if not specified
        if not language:
            language = self._detect_language(code)
        
        language = language.lower().strip()
        
        # Get highlighter function
        highlighter = self._languages.get(language, self._highlight_plain)
        
        try:
            return highlighter(code)
        except Exception as e:
            logger.error(f"Highlighting error: {e}")
            return self._highlight_plain(code)
    
    def highlight_to_html(self, code: str, language: str = "") -> str:
        """
        Highlight code and return HTML with inline styles.
        
        Args:
            code: Source code to highlight
            language: Programming language
            
        Returns:
            HTML string with syntax highlighting
        """
        tokens = self.highlight(code, language)
        
        html_parts = ['<pre class="code-block"><code>']
        
        for token in tokens:
            if token.color:
                html_parts.append(
                    f'<span style="color: {token.color}">{self._escape_html(token.text)}</span>'
                )
            else:
                html_parts.append(self._escape_html(token.text))
        
        html_parts.append('</code></pre>')
        
        return ''.join(html_parts)
    
    def _detect_language(self, code: str) -> str:
        """Auto-detect the programming language from code content."""
        # Check for common patterns
        if "def " in code and ":" in code:
            return "python"
        if "function " in code or "=>" in code or "const " in code:
            return "javascript"
        if code.strip().startswith("{") and code.strip().endswith("}"):
            return "json"
        if code.strip().startswith("#!") or "$ " in code:
            return "bash"
        
        return "plain"
    
    def _highlight_python(self, code: str) -> List[Token]:
        """Highlight Python code."""
        tokens = []
        i = 0
        
        while i < len(code):
            # Comments
            if code[i] == '#':
                end = code.find('\n', i)
                if end == -1:
                    end = len(code)
                tokens.append(Token(code[i:end], "comment", COLORS["comment"]))
                i = end
                continue
            
            # Strings
            if code[i] in ('"', "'"):
                quote = code[i]
                # Check for triple quotes
                if code[i:i+3] in ('"""', "'''"):
                    quote = code[i:i+3]
                    end = code.find(quote, i + 3)
                    if end == -1:
                        end = len(code) - 3
                    end += 3
                else:
                    end = i + 1
                    while end < len(code):
                        if code[end] == '\\':
                            end += 2
                            continue
                        if code[end] == quote:
                            end += 1
                            break
                        end += 1
                
                tokens.append(Token(code[i:end], "string", COLORS["string"]))
                i = end
                continue
            
            # Numbers
            if code[i].isdigit() or (code[i] == '.' and i + 1 < len(code) and code[i+1].isdigit()):
                end = i + 1
                while end < len(code) and (code[end].isalnum() or code[end] in '._'):
                    end += 1
                tokens.append(Token(code[i:end], "number", COLORS["number"]))
                i = end
                continue
            
            # Decorators
            if code[i] == '@':
                end = i + 1
                while end < len(code) and (code[end].isalnum() or code[end] == '_'):
                    end += 1
                tokens.append(Token(code[i:end], "decorator", COLORS["decorator"]))
                i = end
                continue
            
            # Words (keywords, builtins, identifiers)
            if code[i].isalpha() or code[i] == '_':
                end = i + 1
                while end < len(code) and (code[end].isalnum() or code[end] == '_'):
                    end += 1
                word = code[i:end]
                
                if word in PYTHON_KEYWORDS:
                    tokens.append(Token(word, "keyword", COLORS["keyword"]))
                elif word in PYTHON_BUILTINS:
                    tokens.append(Token(word, "builtin", COLORS["builtin"]))
                elif end < len(code) and code[end] == '(':
                    tokens.append(Token(word, "function", COLORS["function"]))
                else:
                    tokens.append(Token(word, "identifier", COLORS["default"]))
                
                i = end
                continue
            
            # Operators
            if code[i] in '+-*/%=<>!&|^~':
                tokens.append(Token(code[i], "operator", COLORS["operator"]))
                i += 1
                continue
            
            # Punctuation
            if code[i] in '()[]{}:;,.':
                tokens.append(Token(code[i], "punctuation", COLORS["punctuation"]))
                i += 1
                continue
            
            # Default (whitespace, etc.)
            tokens.append(Token(code[i], "default", COLORS["default"]))
            i += 1
        
        return tokens
    
    def _highlight_javascript(self, code: str) -> List[Token]:
        """Highlight JavaScript/TypeScript code."""
        tokens = []
        i = 0
        
        while i < len(code):
            # Single-line comments
            if code[i:i+2] == '//':
                end = code.find('\n', i)
                if end == -1:
                    end = len(code)
                tokens.append(Token(code[i:end], "comment", COLORS["comment"]))
                i = end
                continue
            
            # Multi-line comments
            if code[i:i+2] == '/*':
                end = code.find('*/', i + 2)
                if end == -1:
                    end = len(code) - 2
                end += 2
                tokens.append(Token(code[i:end], "comment", COLORS["comment"]))
                i = end
                continue
            
            # Strings
            if code[i] in ('"', "'", '`'):
                quote = code[i]
                end = i + 1
                while end < len(code):
                    if code[end] == '\\':
                        end += 2
                        continue
                    if code[end] == quote:
                        end += 1
                        break
                    end += 1
                
                tokens.append(Token(code[i:end], "string", COLORS["string"]))
                i = end
                continue
            
            # Numbers
            if code[i].isdigit():
                end = i + 1
                while end < len(code) and (code[end].isalnum() or code[end] in '._'):
                    end += 1
                tokens.append(Token(code[i:end], "number", COLORS["number"]))
                i = end
                continue
            
            # Words
            if code[i].isalpha() or code[i] in '_$':
                end = i + 1
                while end < len(code) and (code[end].isalnum() or code[end] in '_$'):
                    end += 1
                word = code[i:end]
                
                if word in JS_KEYWORDS:
                    tokens.append(Token(word, "keyword", COLORS["keyword"]))
                elif end < len(code) and code[end] == '(':
                    tokens.append(Token(word, "function", COLORS["function"]))
                else:
                    tokens.append(Token(word, "identifier", COLORS["default"]))
                
                i = end
                continue
            
            # Operators and punctuation
            if code[i] in '+-*/%=<>!&|^~?:':
                tokens.append(Token(code[i], "operator", COLORS["operator"]))
                i += 1
                continue
            
            if code[i] in '()[]{}:;,.':
                tokens.append(Token(code[i], "punctuation", COLORS["punctuation"]))
                i += 1
                continue
            
            tokens.append(Token(code[i], "default", COLORS["default"]))
            i += 1
        
        return tokens
    
    def _highlight_json(self, code: str) -> List[Token]:
        """Highlight JSON code."""
        tokens = []
        i = 0
        
        while i < len(code):
            # Strings (keys and values)
            if code[i] == '"':
                end = i + 1
                while end < len(code):
                    if code[end] == '\\':
                        end += 2
                        continue
                    if code[end] == '"':
                        end += 1
                        break
                    end += 1
                
                text = code[i:end]
                # Check if it's a key (followed by :)
                j = end
                while j < len(code) and code[j] in ' \t':
                    j += 1
                
                if j < len(code) and code[j] == ':':
                    tokens.append(Token(text, "key", COLORS["function"]))
                else:
                    tokens.append(Token(text, "string", COLORS["string"]))
                
                i = end
                continue
            
            # Numbers
            if code[i].isdigit() or code[i] == '-':
                end = i + 1
                while end < len(code) and (code[end].isdigit() or code[end] in '.eE+-'):
                    end += 1
                tokens.append(Token(code[i:end], "number", COLORS["number"]))
                i = end
                continue
            
            # Keywords
            if code[i:i+4] == 'true':
                tokens.append(Token('true', "keyword", COLORS["keyword"]))
                i += 4
                continue
            if code[i:i+5] == 'false':
                tokens.append(Token('false', "keyword", COLORS["keyword"]))
                i += 5
                continue
            if code[i:i+4] == 'null':
                tokens.append(Token('null', "keyword", COLORS["keyword"]))
                i += 4
                continue
            
            # Punctuation
            if code[i] in '{}[]:,':
                tokens.append(Token(code[i], "punctuation", COLORS["punctuation"]))
                i += 1
                continue
            
            tokens.append(Token(code[i], "default", COLORS["default"]))
            i += 1
        
        return tokens
    
    def _highlight_bash(self, code: str) -> List[Token]:
        """Highlight Bash/Shell code."""
        tokens = []
        i = 0
        
        while i < len(code):
            # Comments
            if code[i] == '#':
                end = code.find('\n', i)
                if end == -1:
                    end = len(code)
                tokens.append(Token(code[i:end], "comment", COLORS["comment"]))
                i = end
                continue
            
            # Strings
            if code[i] in ('"', "'"):
                quote = code[i]
                end = i + 1
                while end < len(code):
                    if code[end] == '\\' and quote == '"':
                        end += 2
                        continue
                    if code[end] == quote:
                        end += 1
                        break
                    end += 1
                
                tokens.append(Token(code[i:end], "string", COLORS["string"]))
                i = end
                continue
            
            # Variables
            if code[i] == '$':
                end = i + 1
                if end < len(code) and code[end] == '{':
                    end = code.find('}', end)
                    if end == -1:
                        end = len(code)
                    else:
                        end += 1
                else:
                    while end < len(code) and (code[end].isalnum() or code[end] == '_'):
                        end += 1
                
                tokens.append(Token(code[i:end], "variable", COLORS["builtin"]))
                i = end
                continue
            
            # Words
            if code[i].isalpha() or code[i] == '_':
                end = i + 1
                while end < len(code) and (code[end].isalnum() or code[end] in '_-'):
                    end += 1
                word = code[i:end]
                
                # Common bash commands
                if word in ('cd', 'ls', 'pwd', 'echo', 'cat', 'grep', 'sed', 'awk',
                           'find', 'mkdir', 'rm', 'cp', 'mv', 'chmod', 'chown',
                           'sudo', 'apt', 'yum', 'pip', 'npm', 'git'):
                    tokens.append(Token(word, "command", COLORS["function"]))
                else:
                    tokens.append(Token(word, "identifier", COLORS["default"]))
                
                i = end
                continue
            
            tokens.append(Token(code[i], "default", COLORS["default"]))
            i += 1
        
        return tokens
    
    def _highlight_plain(self, code: str) -> List[Token]:
        """Return plain text without highlighting."""
        return [Token(code, "default", COLORS["default"])]
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))


# Singleton instance
_highlighter: Optional[CodeHighlighter] = None


def get_highlighter() -> CodeHighlighter:
    """Get the singleton CodeHighlighter instance."""
    global _highlighter
    if _highlighter is None:
        _highlighter = CodeHighlighter()
    return _highlighter