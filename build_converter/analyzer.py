"""Analysis module for extracting meaningful structures from parsed files."""

from typing import Dict, List, Any, Set
from .cmake_parser import CMakeParser
from .kconfig_parser import KConfigParser


class Analyzer:
    """Analyzer for CMake and KConfig files."""

    def __init__(self, cmake_file: str = None, kconfig_file: str = None):
        """Initialize analyzer.
        
        Args:
            cmake_file: Path to CMakeLists.txt file
            kconfig_file: Path to Kconfig file
        """
        self.cmake_parser = None
        self.kconfig_parser = None
        self.cmake_data = {}
        self.kconfig_data = {}
        
        if cmake_file:
            self.cmake_parser = CMakeParser(cmake_file)
        
        if kconfig_file:
            self.kconfig_parser = KConfigParser(kconfig_file)

    def analyze(self) -> Dict[str, Any]:
        """Run analysis on both CMake and KConfig files.
        
        Returns:
            Dictionary with analysis results
        """
        results = {
            'cmake': self._analyze_cmake(),
            'kconfig': self._analyze_kconfig(),
            'correlations': self._find_correlations(),
        }
        return results

    def _analyze_cmake(self) -> Dict[str, Any]:
        """Analyze CMake file.
        
        Returns:
            Analysis results
        """
        if not self.cmake_parser:
            return {}
        
        self.cmake_data = self.cmake_parser.parse()
        
        return {
            'total_commands': len(self.cmake_data.get('commands', [])),
            'total_variables': len(self.cmake_data.get('variables', {})),
            'total_targets': len(self.cmake_data.get('targets', {})),
            'includes': self.cmake_data.get('includes', []),
            'commands_by_type': self._group_commands_by_type(),
            'target_details': self._get_target_details(),
        }

    def _analyze_kconfig(self) -> Dict[str, Any]:
        """Analyze KConfig file.
        
        Returns:
            Analysis results
        """
        if not self.kconfig_parser:
            return {}
        
        self.kconfig_data = self.kconfig_parser.parse()
        
        options = self.kconfig_data.get('options', [])
        
        return {
            'total_options': len(options),
            'options_by_type': self._group_options_by_type(),
            'options_with_depends': self._get_options_with_property('depends_on'),
            'options_with_selects': self._get_options_with_property('select'),
            'boolean_options': len(self.kconfig_parser.get_options_by_type('config')),
        }

    def _group_commands_by_type(self) -> Dict[str, int]:
        """Group CMake commands by type.
        
        Returns:
            Dictionary with command type counts
        """
        grouped = {}
        for cmd in self.cmake_data.get('commands', []):
            cmd_name = cmd.name
            grouped[cmd_name] = grouped.get(cmd_name, 0) + 1
        return grouped

    def _group_options_by_type(self) -> Dict[str, int]:
        """Group KConfig options by type.
        
        Returns:
            Dictionary with option type counts
        """
        grouped = {}
        for opt in self.kconfig_data.get('options', []):
            opt_type = opt.option_type
            grouped[opt_type] = grouped.get(opt_type, 0) + 1
        return grouped

    def _get_target_details(self) -> List[Dict[str, Any]]:
        """Get details about targets.
        
        Returns:
            List of target details
        """
        targets = self.cmake_data.get('targets', {})
        return [
            {
                'name': name,
                'type': target.type,
                'num_sources': len(target.sources),
            }
            for name, target in targets.items()
        ]

    def _get_options_with_property(self, property_name: str) -> List[str]:
        """Get option names with specific property.
        
        Args:
            property_name: Property to search for
            
        Returns:
            List of option names
        """
        if not self.kconfig_parser:
            return []
        
        options = self.kconfig_parser.find_options_with_property(property_name)
        return [opt.name for opt in options]

    def _find_correlations(self) -> Dict[str, Any]:
        """Find correlations between CMake and KConfig structures.
        
        Returns:
            Correlation analysis
        """
        correlations = {}
        
        # Look for shared variable/option names
        if self.cmake_data and self.kconfig_data:
            cmake_names = set(self.cmake_data.get('variables', {}).keys())
            kconfig_names = set(opt.name for opt in self.kconfig_data.get('options', []))
            
            common_names = cmake_names & kconfig_names
            correlations['shared_names'] = list(common_names)
        
        return correlations

    def get_cmake_summary(self) -> str:
        """Get human-readable CMake summary.
        
        Returns:
            Summary string
        """
        if not self.cmake_data:
            return "No CMake data available"
        
        lines = [
            "CMake Analysis Summary:",
            f"  Total commands: {len(self.cmake_data.get('commands', []))}",
            f"  Total variables: {len(self.cmake_data.get('variables', {}))}",
            f"  Total targets: {len(self.cmake_data.get('targets', {}))}",
        ]
        
        cmd_types = self._group_commands_by_type()
        if cmd_types:
            lines.append("  Command types:")
            for cmd_type, count in sorted(cmd_types.items()):
                lines.append(f"    {cmd_type}: {count}")
        
        return "\n".join(lines)

    def get_kconfig_summary(self) -> str:
        """Get human-readable KConfig summary.
        
        Returns:
            Summary string
        """
        if not self.kconfig_data:
            return "No KConfig data available"
        
        lines = [
            "KConfig Analysis Summary:",
            f"  Total options: {len(self.kconfig_data.get('options', []))}",
        ]
        
        opt_types = self._group_options_by_type()
        if opt_types:
            lines.append("  Option types:")
            for opt_type, count in sorted(opt_types.items()):
                lines.append(f"    {opt_type}: {count}")
        
        return "\n".join(lines)
