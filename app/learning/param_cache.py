"""
Learning parameter cache to avoid disk I/O on hot path.
Zone C Optimization: Cache learning_params.json in memory with file watching.
"""
import json
import time
from pathlib import Path
from typing import Dict, Any


class LearningParameterCache:
    """
    In-memory cache for learning parameters with file change detection.
    
    Zone C Optimization:
    - Loads learning_params.json once at startup
    - Watches for file changes instead of reading on every cycle
    - Eliminates pure disk I/O on the hot path
    """
    
    def __init__(self, params_path: str = "./data/learning_params.json"):
        """
        Initialize learning parameter cache.
        
        Args:
            params_path: Path to learning parameters JSON file
        """
        self._params_path = Path(params_path)
        self._params_cache: Dict[str, Any] = {}
        self._params_mtime: float = 0.0
        self._initialized = False
    
    def load_parameters(self) -> Dict[str, Any]:
        """
        Load parameters from cache or file if changed.
        
        Returns:
            Learning parameters dictionary
        """
        # Check if file exists
        if not self._params_path.exists():
            if not self._initialized:
                # First load - create default params
                self._params_cache = self._get_default_params()
                self._save_params()
                self._initialized = True
            return self._params_cache
        
        # Check if file has been modified
        try:
            mtime = self._params_path.stat().st_mtime
        except FileNotFoundError:
            return self._params_cache
        
        # Reload if file changed
        if mtime != self._params_mtime:
            try:
                self._params_cache = json.loads(self._params_path.read_text())
                self._params_mtime = mtime
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠ Error loading learning params: {e}, using cached version")
        
        return self._params_cache
    
    def update_parameter(self, key: str, value: Any):
        """
        Update a single parameter and save to disk.
        
        Args:
            key: Parameter key
            value: Parameter value
        """
        self._params_cache[key] = value
        self._save_params()
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """
        Get a single parameter value.
        
        Args:
            key: Parameter key
            default: Default value if key not found
            
        Returns:
            Parameter value or default
        """
        params = self.load_parameters()
        return params.get(key, default)
    
    def _save_params(self):
        """Save current parameters to disk."""
        try:
            self._params_path.parent.mkdir(parents=True, exist_ok=True)
            self._params_path.write_text(json.dumps(self._params_cache, indent=2))
            self._params_mtime = self._params_path.stat().st_mtime
        except IOError as e:
            print(f"⚠ Error saving learning params: {e}")
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Get default learning parameters."""
        return {
            "risk_per_trade": 0.01,
            "max_position_size": 1000,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.04,
            "max_open_positions": 3,
            "learning_rate": 0.001,
            "min_trades_for_evaluation": 30,
            "profit_factor_threshold": 1.2,
            "last_updated": time.time()
        }
    
    @property
    def cache_info(self) -> Dict[str, Any]:
        """Get cache information."""
        return {
            "cached": self._initialized,
            "params_count": len(self._params_cache),
            "last_modified": self._params_mtime,
            "file_exists": self._params_path.exists()
        }
