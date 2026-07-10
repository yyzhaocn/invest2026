"""
Data Caching System for Stock Analysis
Caches data for 3 hours to avoid repeated API calls
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DataCache:
    """Cache manager for stock data"""
    
    def __init__(self, cache_dir: str = "generated/cache/stockd"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_duration = timedelta(hours=3)
    
    def _get_cache_file(self, stock_code: str, module: str) -> Path:
        """Get cache file path for a stock and module"""
        stock_dir = self.cache_dir / stock_code
        stock_dir.mkdir(exist_ok=True)
        return stock_dir / f"module_{module}.json"
    
    def get(self, stock_code: str, module: str) -> Optional[Dict]:
        """
        Get cached data if it exists and is not expired
        
        Args:
            stock_code: Stock code (e.g., "002916")
            module: Module number (e.g., "1", "2", etc.)
        
        Returns:
            Cached data dict if valid, None otherwise
        """
        cache_file = self._get_cache_file(stock_code, module)
        
        if not cache_file.exists():
            logger.info(f"Cache miss: {stock_code} module_{module}")
            return None
        
        try:
            # Check file modification time
            file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - file_mtime > self.cache_duration:
                logger.info(f"Cache expired: {stock_code} module_{module}")
                return None
            
            # Load and return cached data
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Cache hit: {stock_code} module_{module}")
            return data
            
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None
    
    def set(self, stock_code: str, module: str, data: Dict) -> bool:
        """
        Save data to cache
        
        Args:
            stock_code: Stock code
            module: Module number
            data: Data to cache
        
        Returns:
            True if successful, False otherwise
        """
        cache_file = self._get_cache_file(stock_code, module)
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Cached: {stock_code} module_{module}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            return False
    
    def clear(self, stock_code: Optional[str] = None):
        """
        Clear cache for a specific stock or all stocks
        
        Args:
            stock_code: Stock code to clear, or None to clear all
        """
        if stock_code:
            stock_dir = self.cache_dir / stock_code
            if stock_dir.exists():
                for file in stock_dir.glob("*.json"):
                    file.unlink()
                logger.info(f"Cleared cache for {stock_code}")
        else:
            for stock_dir in self.cache_dir.iterdir():
                if stock_dir.is_dir():
                    for file in stock_dir.glob("*.json"):
                        file.unlink()
            logger.info("Cleared all cache")
    
    def get_cache_info(self, stock_code: str) -> Dict:
        """Get cache information for a stock"""
        stock_dir = self.cache_dir / stock_code
        
        if not stock_dir.exists():
            return {"cached_modules": 0, "total_modules": 7, "modules": {}}
        
        info = {
            "cached_modules": 0,
            "total_modules": 7,
            "modules": {}
        }
        
        for i in range(1, 8):
            cache_file = stock_dir / f"module_{i}.json"
            if cache_file.exists():
                file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                is_valid = datetime.now() - file_mtime <= self.cache_duration
                
                info["modules"][f"module_{i}"] = {
                    "cached": True,
                    "valid": is_valid,
                    "cached_at": file_mtime.isoformat(),
                    "expires_at": (file_mtime + self.cache_duration).isoformat()
                }
                
                if is_valid:
                    info["cached_modules"] += 1
            else:
                info["modules"][f"module_{i}"] = {
                    "cached": False,
                    "valid": False
                }
        
        return info

