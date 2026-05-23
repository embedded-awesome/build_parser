"""CMake file parser using cmakelang with targeted extraction helpers."""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from cmakelang.lex import tokenize
from cmakelang.parse import parse as cmakelang_parse
from .file_reader import FileReader


@dataclass
class CMakeCommand:
    """Represents a CMake command."""
    name: str
    args: List[str] = field(default_factory=list)
    line_no: int = 0
    
    def __repr__(self) -> str:
        return f"CMakeCommand({self.name}, args={len(self.args)}, line={self.line_no})"


@dataclass
class CMakeVariable:
    """Represents a CMake variable."""
    name: str
    value: Any
    line_no: int = 0
    
    def __repr__(self) -> str:
        return f"CMakeVariable({self.name}={self.value}, line={self.line_no})"


@dataclass
class CMakeTarget:
    """Represents a CMake target (executable, library, etc.)."""
    name: str
    type: str  # executable, library, interface, etc.
    sources: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    line_no: int = 0


@dataclass
class CMakeConditionalBranch:
    """Represents a single branch inside an if()/elseif()/else() block."""
    keyword: str
    condition: str
    line_no: int
    commands: List[CMakeCommand] = field(default_factory=list)
    variables: Dict[str, CMakeVariable] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"CMakeConditionalBranch({self.keyword} {self.condition}, line={self.line_no}, commands={len(self.commands)})"


@dataclass
class CMakeConditionalBlock:
    """Represents an if() ... endif() block with all branches."""
    start_line: int
    end_line: int = 0
    branches: List[CMakeConditionalBranch] = field(default_factory=list)


class CMakeParser:
    """Parser for CMake files using cmakelang library."""

    def __init__(self, file_path: str):
        """Initialize parser.
        
        Args:
            file_path: Path to CMakeLists.txt file
        """
        self.file_path = file_path
        self.content = ""
        self.parse_tree = None
        self.commands: List[CMakeCommand] = []
        self.variables: Dict[str, CMakeVariable] = {}
        self.targets: Dict[str, CMakeTarget] = {}
        self.includes: List[str] = []
        self.conditionals: List[CMakeConditionalBlock] = []
        self.set_commands: List[CMakeVariable] = []
        self.add_library_commands: List[CMakeCommand] = []
        self.zephyr_commands: List[CMakeCommand] = []

    def parse(self) -> Dict[str, Any]:
        """Parse the CMake file using cmakelang.
        
        Returns:
            Dictionary containing parsed CMake structure
        """
        self.commands = []
        self.variables = {}
        self.targets = {}
        self.includes = []
        self.conditionals = []
        self.set_commands = []
        self.add_library_commands = []
        self.zephyr_commands = []

        self.content = FileReader.read_file(self.file_path)
        
        try:
            # Use cmakelang for robust parsing
            tokens = tokenize(self.content)
            self.parse_tree = cmakelang_parse(tokens)
            
            # Build command list from source text so we can preserve practical
            # command boundaries and line numbers for block tracking.
            self._extract_commands_from_source()
            
            # Extract variables set via set()
            self._extract_variables()
            
            # Extract targets
            self._extract_targets()
            
            # Extract includes
            self._extract_includes()

            # Extract conditionals and command groupings
            self._extract_conditionals()
            self._extract_add_library_commands()
            self._extract_zephyr_commands()
            
        except Exception as e:
            raise ValueError(f"Failed to parse CMake file {self.file_path}: {e}")
        
        return {
            'commands': self.commands,
            'variables': self.variables,
            'targets': self.targets,
            'includes': self.includes,
            'conditionals': self.conditionals,
            'set_values': self.set_commands,
            'add_libraries': self.add_library_commands,
            'zephyr_commands': self.zephyr_commands,
        }

    def _extract_commands_from_source(self) -> None:
        """Extract commands from source with line numbers and multiline handling."""
        self.commands = []

        lines = self.content.splitlines()
        current_name = ""
        current_start = 0
        current_body: List[str] = []
        paren_balance = 0
        in_quote = False

        for idx, raw_line in enumerate(lines, start=1):
            line = self._strip_comment(raw_line)
            if not line.strip() and not current_name:
                continue

            if not current_name:
                match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
                if not match:
                    continue

                current_name = match.group(1).lower()
                current_start = idx
                current_body = [line]
                paren_delta, in_quote = self._paren_delta_with_state(line, False)
                paren_balance = paren_delta
            else:
                current_body.append(line)
                paren_delta, in_quote = self._paren_delta_with_state(line, in_quote)
                paren_balance += paren_delta

            if current_name and paren_balance <= 0:
                cmd_text = "\n".join(current_body)
                args = self._split_args(cmd_text)
                self.commands.append(
                    CMakeCommand(name=current_name, args=args, line_no=current_start)
                )
                current_name = ""
                current_start = 0
                current_body = []
                paren_balance = 0
                in_quote = False

    def _extract_variables(self) -> None:
        """Extract variable assignments from commands."""
        self.set_commands = []
        for cmd in self.commands:
            if cmd.name == 'set' and len(cmd.args) >= 2:
                var_name = cmd.args[0]
                var_value = ' '.join(cmd.args[1:])
                variable = CMakeVariable(
                    name=var_name,
                    value=var_value,
                    line_no=cmd.line_no
                )
                self.variables[var_name] = variable
                self.set_commands.append(variable)

    def _extract_targets(self) -> None:
        """Extract target definitions from commands."""
        for cmd in self.commands:
            if cmd.name in ('add_executable', 'add_library'):
                if len(cmd.args) >= 1:
                    target_name = cmd.args[0]
                    target_type = cmd.args[1] if cmd.name == 'add_library' and len(cmd.args) > 1 else cmd.name
                    sources = cmd.args[2:] if len(cmd.args) > 2 else []
                    
                    target = CMakeTarget(
                        name=target_name,
                        type=target_type,
                        sources=sources,
                        line_no=cmd.line_no
                    )
                    self.targets[target_name] = target

    def _extract_includes(self) -> None:
        """Extract include directives."""
        for cmd in self.commands:
            if cmd.name in ('include', 'include_directories'):
                self.includes.extend(cmd.args)

    def _extract_conditionals(self) -> None:
        """Track if()/elseif()/else()/endif() blocks and contained commands."""
        self.conditionals = []
        block_stack: List[CMakeConditionalBlock] = []

        for cmd in self.commands:
            name = cmd.name

            if name == 'if':
                block = CMakeConditionalBlock(start_line=cmd.line_no)
                block.branches.append(
                    CMakeConditionalBranch(
                        keyword='if',
                        condition=' '.join(cmd.args).strip(),
                        line_no=cmd.line_no,
                    )
                )
                self.conditionals.append(block)
                block_stack.append(block)
                continue

            if name == 'elseif' and block_stack:
                block_stack[-1].branches.append(
                    CMakeConditionalBranch(
                        keyword='elseif',
                        condition=' '.join(cmd.args).strip(),
                        line_no=cmd.line_no,
                    )
                )
                continue

            if name == 'else' and block_stack:
                block_stack[-1].branches.append(
                    CMakeConditionalBranch(
                        keyword='else',
                        condition='else',
                        line_no=cmd.line_no,
                    )
                )
                continue

            if name == 'endif' and block_stack:
                block = block_stack.pop()
                block.end_line = cmd.line_no
                continue

            if block_stack and block_stack[-1].branches:
                branch = block_stack[-1].branches[-1]
                branch.commands.append(cmd)

                if cmd.name == 'set' and len(cmd.args) >= 2:
                    set_var = CMakeVariable(
                        name=cmd.args[0],
                        value=' '.join(cmd.args[1:]),
                        line_no=cmd.line_no,
                    )
                    branch.variables[set_var.name] = set_var

    def _extract_add_library_commands(self) -> None:
        """Collect add_library() commands for direct access."""
        self.add_library_commands = [cmd for cmd in self.commands if cmd.name == 'add_library']

    def _extract_zephyr_commands(self) -> None:
        """Collect all zephyr_* commands and their arguments."""
        self.zephyr_commands = [cmd for cmd in self.commands if cmd.name.startswith('zephyr_')]

    def _strip_comment(self, line: str) -> str:
        """Strip inline # comments while respecting double-quoted strings."""
        result = []
        in_quote = False
        escaped = False

        for ch in line:
            if escaped:
                result.append(ch)
                escaped = False
                continue

            if ch == '\\':
                result.append(ch)
                escaped = True
                continue

            if ch == '"':
                in_quote = not in_quote
                result.append(ch)
                continue

            if ch == '#' and not in_quote:
                break

            result.append(ch)

        return ''.join(result)

    def _paren_delta_with_state(self, text: str, in_quote: bool) -> Tuple[int, bool]:
        """Count net parentheses and return updated quote state.

        Args:
            text: Source text chunk to inspect
            in_quote: Whether scanner starts inside a quote

        Returns:
            Tuple of (paren_delta, in_quote)
        """
        balance = 0
        escaped = False

        for ch in text:
            if escaped:
                escaped = False
                continue

            if ch == '\\':
                escaped = True
                continue

            if ch == '"':
                in_quote = not in_quote
                continue

            if in_quote:
                continue

            if ch == '(':
                balance += 1
            elif ch == ')':
                balance -= 1

        return balance, in_quote

    def _split_args(self, cmd_text: str) -> List[str]:
        """Split command arguments from full command text."""
        open_idx = cmd_text.find('(')
        close_idx = cmd_text.rfind(')')
        if open_idx < 0 or close_idx <= open_idx:
            return []

        arg_text = cmd_text[open_idx + 1:close_idx]
        normalized = arg_text.replace('\n', ' ').strip()
        if not normalized:
            return []

        # Keep quoted args intact, collapse whitespace elsewhere.
        raw_tokens = re.findall(r'"[^"\\]*(?:\\.[^"\\]*)*"|\S+', normalized)
        return [tok.strip().strip('"') for tok in raw_tokens if tok.strip()]

    def get_command_by_name(self, name: str) -> List[CMakeCommand]:
        """Get all commands with given name.
        
        Args:
            name: Command name
            
        Returns:
            List of matching commands
        """
        return [cmd for cmd in self.commands if cmd.name == name.lower()]

    def get_variable(self, name: str) -> Optional[CMakeVariable]:
        """Get variable by name.
        
        Args:
            name: Variable name
            
        Returns:
            CMakeVariable or None
        """
        return self.variables.get(name)

    def get_target(self, name: str) -> Optional[CMakeTarget]:
        """Get target by name.
        
        Args:
            name: Target name
            
        Returns:
            CMakeTarget or None
        """
        return self.targets.get(name)
