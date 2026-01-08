"""
Costco Shopping Automation Agent v1
Automates the shopping flow on Costco.com
"""

__version__ = "1.0.0"
__author__ = "AIBOT"

from .agent import CostcoShoppingAgent
from .config import CostcoConfig

__all__ = ["CostcoShoppingAgent", "CostcoConfig"]
