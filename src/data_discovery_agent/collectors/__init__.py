"""
Background Discovery Collectors

These modules scan data sources and collect metadata for indexing.
"""

from .bigquery_collector import BigQueryCollector

__all__ = ["BigQueryCollector"]

