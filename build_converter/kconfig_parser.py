"""KConfig file parser using kconfiglib library."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import re
from .kconfiglib import Kconfig, KconfigError


@dataclass
class KConfigOption:
    """Represents a KConfig option."""
    name: str
    option_type: str  # config, choice, menu, etc.
    properties: Dict[str, Any] = field(default_factory=dict)
    line_no: int = 0
    children: List['KConfigOption'] = field(default_factory=list)
    
    def __repr__(self) -> str:
        return f"KConfigOption({self.name}, type={self.option_type}, line={self.line_no})"


class KConfigParser:
    """Parser for KConfig files using kconfiglib library."""

    # Type mapping from kconfiglib numeric types to string names
    TYPE_MAP = {
        0: 'UNKNOWN',
        1: 'BOOL',
        2: 'TRISTATE',
        3: 'INT',
        4: 'HEX',
        5: 'STRING',
    }

    def __init__(self, file_path: str):
        """Initialize parser.
        
        Args:
            file_path: Path to Kconfig file
        """
        self.file_path = file_path
        self.kconf: Optional[Any] = None
        self.options: List[KConfigOption] = []
        self.option_dict: Dict[str, KConfigOption] = {}

    def parse(self) -> Dict[str, Any]:
        """Parse the KConfig file using kconfiglib.
        
        Returns:
            Dictionary containing parsed KConfig structure
        """
        try:
            # Use kconfiglib for parsing
            self.kconf = Kconfig(self.file_path, warn_to_stderr=False)
            
            # Extract options from symbols
            self._extract_options()
            
        except Exception as e:
            raise ValueError(f"Failed to parse KConfig file {self.file_path}: {e}")
        
        return {
            'options': self.options,
            'option_dict': self.option_dict,
        }

    def _extract_options(self) -> None:
        """Extract options from kconfiglib symbols."""
        if not self.kconf:
            return
        
        processed = set()
        
        for name, sym in self.kconf.syms.items():
            # Skip numeric symbols and already processed ones
            if name in processed or not name or name.isdigit():
                continue
            
            processed.add(name)
            
            # Determine option type
            sym_type = self.TYPE_MAP.get(sym.type, 'UNKNOWN')
            
            # Map kconfiglib type numbers to config/choice/menu
            option_type = self._get_option_type(sym)
            
            # Extract properties
            properties = self._extract_properties(sym)
            
            option = KConfigOption(
                name=name,
                option_type=option_type,
                properties=properties,
                line_no=sym.linenr if hasattr(sym, 'linenr') else 0
            )
            
            self.options.append(option)
            self.option_dict[name] = option

    def _get_option_type(self, sym: Any) -> str:
        """Determine the option type from kconfiglib symbol.
        
        Args:
            sym: kconfiglib Symbol object
            
        Returns:
            Option type string
        """
        # Extract type from symbol repr string using regex
        # This is more reliable than trying to decode numeric types
        if sym.nodes:
            node = sym.nodes[0]
            repr_str = repr(node.item)
            
            # Match bool, tristate, int, hex, or string
            match = re.search(r'\b(bool|tristate|int|hex|string)\b', repr_str)
            if match:
                return match.group(1)
        
        return 'config'

    def _extract_properties(self, sym: Any) -> Dict[str, Any]:
        """Extract properties from kconfiglib symbol.
        
        Args:
            sym: kconfiglib Symbol object
            
        Returns:
            Dictionary of properties
        """
        properties = {}
        
        # Add type - use _get_option_type for consistent extraction
        option_type = self._get_option_type(sym)
        if option_type != 'config':
            properties['type'] = option_type
        
        # Get prompt and help from first node if available
        if sym.nodes:
            node = sym.nodes[0]
            
            # Add prompt if available
            if node.prompt:
                prompt_text = node.prompt[0] if isinstance(node.prompt, (list, tuple)) else str(node.prompt)
                properties['prompt'] = prompt_text
            
            # Add help if available
            if node.help:
                properties['help'] = node.help
        
        # Add defaults
        if sym.defaults:
            properties['default'] = []
            for default_val, cond in sym.defaults:
                default_entry = {'value': str(default_val)}
                if cond:
                    default_entry['condition'] = str(cond)
                properties['default'].append(default_entry)
        
        # Add dependencies
        if sym.direct_dep:
            properties['depends_on'] = str(sym.direct_dep)
        
        # Add selects
        if sym.selects:
            properties['select'] = []
            for select_sym, cond in sym.selects:
                select_entry = {'option': str(select_sym)}
                if cond:
                    select_entry['condition'] = str(cond)
                properties['select'].append(select_entry)
        
        # Add implies
        if sym.implies:
            properties['imply'] = []
            for imply_sym, cond in sym.implies:
                imply_entry = {'option': str(imply_sym)}
                if cond:
                    imply_entry['condition'] = str(cond)
                properties['imply'].append(imply_entry)
        
        # Add range for numeric types
        if sym.ranges:
            properties['range'] = []
            for range_min, range_max, cond in sym.ranges:
                range_entry = {'min': str(range_min), 'max': str(range_max)}
                if cond:
                    range_entry['condition'] = str(cond)
                properties['range'].append(range_entry)
        
        return properties

    def get_option(self, name: str) -> Optional[KConfigOption]:
        """Get option by name.
        
        Args:
            name: Option name
            
        Returns:
            KConfigOption or None
        """
        return self.option_dict.get(name)

    def get_options_by_type(self, option_type: str) -> List[KConfigOption]:
        """Get all options of a specific type.
        
        Args:
            option_type: Type to filter by (bool, int, hex, string, etc.)
            
        Returns:
            List of matching options
        """
        return [opt for opt in self.options if opt.option_type == option_type]

    def find_options_with_property(self, property_name: str) -> List[KConfigOption]:
        """Find all options that have a specific property.
        
        Args:
            property_name: Property name to search for
            
        Returns:
            List of options with that property
        """
        return [opt for opt in self.options if property_name in opt.properties]
