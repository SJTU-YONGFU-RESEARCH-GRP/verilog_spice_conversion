"""Parser module for extracting design information from Yosys JSON output."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ModuleInfo:
    """Information about a Verilog module.
    
    Attributes:
        name: Module name
        ports: Dictionary mapping port names to port information
        parameters: Dictionary mapping parameter names to default values
        cells: List of cell instances in this module
        nets: Dictionary of nets/wires in this module
    """
    
    def __init__(
        self,
        name: str,
        ports: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        cells: Optional[List[Dict[str, Any]]] = None,
        nets: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize ModuleInfo.
        
        Args:
            name: Module name
            ports: Dictionary mapping port names to port information
            parameters: Dictionary mapping parameter names to default values
            cells: List of cell instances
            nets: Dictionary of nets/wires
        """
        self.name = name
        self.ports = ports or {}
        self.parameters = parameters or {}
        self.cells = cells or []
        self.nets = nets or {}


def parse_yosys_json(json_data: Dict[str, Any]) -> Dict[str, ModuleInfo]:
    """Parse Yosys JSON output and extract module information.
    
    Args:
        json_data: Yosys JSON data structure
        
    Returns:
        Dictionary mapping module names to ModuleInfo objects
    """
    modules: Dict[str, ModuleInfo] = {}
    
    yosys_modules = json_data.get("modules", {})
    
    for module_name, module_data in yosys_modules.items():
        logger.debug(f"Parsing module: {module_name}")
        
        # Extract ports
        ports = {}
        port_data = module_data.get("ports", {})
        for port_name, port_info in port_data.items():
            ports[port_name] = {
                "direction": port_info.get("direction", "unknown"),
                "bits": port_info.get("bits", []),
            }
        
        # Extract cells (gate instances)
        cells = []
        cell_data = module_data.get("cells", {})
        for cell_name, cell_info in cell_data.items():
            cell_type = cell_info.get("type", "unknown")
            cell_ports = cell_info.get("port_directions", {})
            cell_connections = cell_info.get("connections", {})
            
            cells.append({
                "name": cell_name,
                "type": cell_type,
                "ports": cell_ports,
                "connections": cell_connections,
            })
        
        # Extract nets
        nets = {}
        net_data = module_data.get("netnames", {})
        for net_name, net_info in net_data.items():
            nets[net_name] = {
                "bits": net_info.get("bits", []),
                "attributes": net_info.get("attributes", {}),
            }
        
        # Extract parameters (if available)
        parameters = {}
        attrs = module_data.get("attributes", {})
        for key, value in attrs.items():
            if key.startswith("\\") and key.endswith("_param"):
                param_name = key[1:-6]  # Remove leading \ and trailing _param
                parameters[param_name] = value
        
        modules[module_name] = ModuleInfo(
            name=module_name,
            ports=ports,
            parameters=parameters,
            cells=cells,
            nets=nets,
        )
    
    logger.info(f"Parsed {len(modules)} module(s)")
    return modules


def get_top_module(
    modules: Dict[str, ModuleInfo],
    top_name: Optional[str] = None,
) -> ModuleInfo:
    """Get the top-level module.
    
    Args:
        modules: Dictionary of all modules
        top_name: Optional top module name
        
    Returns:
        ModuleInfo for the top module
        
    Raises:
        ValueError: If top module cannot be determined or doesn't exist
    """
    if top_name:
        # Try exact match first
        if top_name in modules:
            logger.info(f"Using specified top module: {top_name}")
            return modules[top_name]
        
        # Try with escaped backslash (Yosys format)
        escaped_name = f"\\{top_name}"
        if escaped_name in modules:
            logger.info(f"Using specified top module (escaped): {escaped_name}")
            return modules[escaped_name]
        
        # Try without backslash if module has it
        for mod_name in modules:
            if mod_name.lstrip("\\") == top_name:
                logger.info(f"Using specified top module: {mod_name}")
                return modules[mod_name]
        
        # Extract module names without backslashes for error message
        module_names = [m.lstrip("\\") for m in modules.keys()]
        raise ValueError(
            f"Specified top module '{top_name}' not found. "
            f"Available modules: {module_names}"
        )
    
    # If no top name specified, find the module with no parent
    # Strategy: find module that is not instantiated by others
    if len(modules) == 1:
        top_module = list(modules.values())[0]
        module_name_clean = top_module.name.lstrip("\\")
        logger.info(f"Auto-detected top module: {module_name_clean}")
        return top_module
    
    # For multiple modules, try to find the one that's not instantiated
    # Check which modules are used as cell types
    used_modules = set()
    for module_info in modules.values():
        for cell in module_info.cells:
            used_modules.add(cell["type"])
    
    # Find modules that are not used as cell types (likely top-level)
    top_candidates = [
        mod for mod_name, mod in modules.items()
        if mod_name not in used_modules and mod_name.lstrip("\\") not in used_modules
    ]
    
    if top_candidates:
        top_module = top_candidates[0]
        module_name_clean = top_module.name.lstrip("\\")
        logger.info(f"Auto-detected top module: {module_name_clean}")
        return top_module
    
    # Fallback: use first module
    if modules:
        top_module = list(modules.values())[0]
        module_name_clean = top_module.name.lstrip("\\")
        logger.warning(
            f"Multiple modules found. Using first module as top: {module_name_clean}"
        )
        return top_module
    
    raise ValueError("No modules found in design")
