"""
Multi-tenancy support for HippoRAG.

This module provides book and business management for multi-tenant deployments.
"""

from .manager import MultiTenancyManager
from .database import MultiTenancyDB

__all__ = ['MultiTenancyManager', 'MultiTenancyDB']
