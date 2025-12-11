# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Metadata Normalization Module

This module provides functions for normalizing and resolving conflicts in metadata
from multiple sources (EXIF, IPTC, XMP, etc.). It helps choose the best values
when multiple sources contain conflicting or duplicate information.

Copyright 2025 DNAi inc.
"""

from typing import Dict, Any, Optional, List, Tuple, Set
from datetime import datetime
import re
from enum import Enum


class MetadataSource(Enum):
    """Enumeration of metadata sources with priority order (higher number = higher priority)."""
    FILE_SYSTEM = 1
    IPTC = 2
    XMP = 3
    EXIF = 4
    MAKERNOTE = 5
    COMPOSITE = 6  # Highest priority - computed values


class PriorityConfig:
    """
    Configuration for metadata priority resolution.
    
    This class defines priority rules for resolving conflicts between
    different metadata sources. Higher priority sources are preferred
    when multiple sources contain the same tag.
    """
    
    def __init__(self):
        """Initialize with default priority rules."""
        # Default source priority (higher number = higher priority)
        self.source_priority = {
            'Composite': MetadataSource.COMPOSITE.value,
            'MakerNotes': MetadataSource.MAKERNOTE.value,
            'EXIF': MetadataSource.EXIF.value,
            'XMP': MetadataSource.XMP.value,
            'IPTC': MetadataSource.IPTC.value,
            'File': MetadataSource.FILE_SYSTEM.value,
        }
        
        # Tag-specific priority overrides
        # Format: {tag_name: [(source_pattern, priority), ...]}
        # Example: {'DateTimeOriginal': [('EXIF', 10), ('XMP', 8), ('IPTC', 5)]}
        self.tag_priorities: Dict[str, List[Tuple[str, int]]] = {}
        
        # Tags that should prefer more recent values
        self.prefer_recent_tags: Set[str] = {
            'ModifyDate', 'DateTime', 'MetadataDate', 'FileModifyDate'
        }
        
        # Tags that should prefer older values (original creation)
        self.prefer_original_tags: Set[str] = {
            'DateTimeOriginal', 'CreateDate', 'DateCreated', 'CreationDate'
        }
    
    def get_source_priority(self, tag_name: str, source: str) -> int:
        """
        Get priority for a tag from a specific source.
        
        Args:
            tag_name: Name of the tag (without group prefix)
            source: Source group name (e.g., 'EXIF', 'XMP', 'IPTC')
            
        Returns:
            Priority value (higher = more preferred)
        """
        # Check for tag-specific priority override
        if tag_name in self.tag_priorities:
            for source_pattern, priority in self.tag_priorities[tag_name]:
                if source_pattern in source:
                    return priority
        
        # Use default source priority
        for source_key, priority in self.source_priority.items():
            if source_key in source:
                return priority
        
        # Default priority for unknown sources
        return 0


def parse_date_string(date_str: str) -> Optional[datetime]:
    """
    Parse a date string into a datetime object.
    
    Supports multiple date formats commonly found in metadata:
    - EXIF format: "YYYY:MM:DD HH:MM:SS"
    - ISO format: "YYYY-MM-DDTHH:MM:SS"
    - ISO with timezone: "YYYY-MM-DDTHH:MM:SS+HH:MM"
    - XMP format: "YYYY-MM-DDTHH:MM:SS"
    - With subseconds: "YYYY:MM:DD HH:MM:SS.sss"
    
    Args:
        date_str: Date string to parse
        
    Returns:
        datetime object or None if parsing fails
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    if not date_str:
        return None
    
    # Common date patterns
    patterns = [
        # EXIF format: "YYYY:MM:DD HH:MM:SS" or "YYYY:MM:DD HH:MM:SS.sss"
        (r'(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?', '%Y:%m:%d %H:%M:%S'),
        # ISO format: "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DDTHH:MM:SS.sss"
        (r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?', '%Y-%m-%dT%H:%M:%S'),
        # Simple date: "YYYY-MM-DD"
        (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
        # EXIF date only: "YYYY:MM:DD"
        (r'(\d{4}):(\d{2}):(\d{2})', '%Y:%m:%d'),
    ]
    
    for pattern, fmt in patterns:
        match = re.match(pattern, date_str)
        if match:
            try:
                # Extract date components
                groups = match.groups()
                date_part = f"{groups[0]}-{groups[1]}-{groups[2]}"
                
                if len(groups) >= 6:
                    # Has time component
                    time_part = f"{groups[3]}:{groups[4]}:{groups[5]}"
                    dt_str = f"{date_part} {time_part}"
                    
                    # Try parsing with microseconds if available
                    if len(groups) >= 7 and groups[6]:
                        microseconds = int(groups[6][:6].ljust(6, '0'))  # Pad to 6 digits
                        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').replace(microsecond=microseconds)
                    else:
                        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                else:
                    # Date only
                    return datetime.strptime(date_part, '%Y-%m-%d')
            except (ValueError, IndexError):
                continue
    
    # Try standard datetime parsing as fallback
    try:
        return datetime.fromisoformat(date_str.replace(':', '-', 2).replace(' ', 'T', 1))
    except (ValueError, AttributeError):
        pass
    
    return None


def choose_best_timestamps(
    metadata: Dict[str, Any],
    tag_name: str,
    config: Optional[PriorityConfig] = None
) -> Optional[str]:
    """
    Choose the best timestamp value from multiple metadata sources.
    
    This function looks for a tag across different metadata sources (EXIF, XMP, IPTC, etc.)
    and selects the best value based on priority rules and data quality.
    
    Args:
        metadata: Dictionary of metadata tags (keys like 'EXIF:DateTimeOriginal', 'XMP:CreateDate', etc.)
        tag_name: Base tag name to search for (e.g., 'DateTimeOriginal', 'CreateDate')
        config: Optional PriorityConfig object. If None, uses default configuration.
        
    Returns:
        Best timestamp value as string, or None if not found
        
    Example:
        >>> metadata = {
        ...     'EXIF:DateTimeOriginal': '2023:01:15 10:30:00',
        ...     'XMP:DateTimeOriginal': '2023-01-15T10:30:00',
        ...     'IPTC:DateCreated': '2023-01-15'
        ... }
        >>> best = choose_best_timestamps(metadata, 'DateTimeOriginal')
        >>> # Returns '2023:01:15 10:30:00' (EXIF has higher priority)
    """
    if config is None:
        config = PriorityConfig()
    
    # Find all occurrences of this tag across different sources
    candidates: List[Tuple[str, str, int]] = []  # (full_tag_name, value, priority)
    
    # Search for tag in all metadata sources
    for full_tag, value in metadata.items():
        if not value:
            continue
        
        # Extract source and tag name
        if ':' in full_tag:
            source, tag = full_tag.split(':', 1)
        else:
            source = ''
            tag = full_tag
        
        # Check if this tag matches what we're looking for
        if tag == tag_name or tag.endswith(tag_name):
            priority = config.get_source_priority(tag_name, source)
            candidates.append((full_tag, str(value), priority))
    
    if not candidates:
        return None
    
    # Sort by priority (higher priority first)
    candidates.sort(key=lambda x: x[2], reverse=True)
    
    # If multiple candidates have the same priority, prefer:
    # 1. More complete timestamps (with time component)
    # 2. More recent values (for ModifyDate tags)
    # 3. Older values (for CreateDate/DateTimeOriginal tags)
    
    best_candidate = None
    best_score = -1
    
    for full_tag, value, priority in candidates:
        # Parse the date to assess quality
        parsed_date = parse_date_string(value)
        
        score = priority * 1000  # Base score from priority
        
        if parsed_date:
            # Prefer timestamps with time component
            if ':' in value and len(value) > 10:
                score += 100
            
            # Prefer more recent for ModifyDate tags
            if tag_name in config.prefer_recent_tags:
                score += parsed_date.timestamp()
            
            # Prefer older for CreateDate tags
            elif tag_name in config.prefer_original_tags:
                score += (datetime.max.timestamp() - parsed_date.timestamp())
        
        if score > best_score:
            best_score = score
            best_candidate = value
    
    return best_candidate


def unify_date_fields(
    metadata: Dict[str, Any],
    config: Optional[PriorityConfig] = None
) -> Dict[str, Any]:
    """
    Unify date fields across different metadata sources.
    
    This function normalizes date fields by:
    1. Choosing the best value for each date tag from multiple sources
    2. Normalizing date formats to a consistent format
    3. Creating unified tags without source prefixes
    
    Args:
        metadata: Dictionary of metadata tags
        config: Optional PriorityConfig object. If None, uses default configuration.
        
    Returns:
        New metadata dictionary with unified date fields added
        
    Example:
        >>> metadata = {
        ...     'EXIF:DateTimeOriginal': '2023:01:15 10:30:00',
        ...     'XMP:CreateDate': '2023-01-15T10:30:00'
        ... }
        >>> unified = unify_date_fields(metadata)
        >>> # Adds 'DateTimeOriginal': '2023:01:15 10:30:00' and 'CreateDate': '2023-01-15T10:30:00'
    """
    if config is None:
        config = PriorityConfig()
    
    unified_metadata = metadata.copy()
    
    # Common date/time tags to unify
    date_tags = [
        'DateTimeOriginal',
        'CreateDate',
        'ModifyDate',
        'DateTime',
        'DateTimeDigitized',
        'DateCreated',
        'DateModified',
        'MetadataDate',
    ]
    
    for tag_name in date_tags:
        # Find best value for this tag
        best_value = choose_best_timestamps(metadata, tag_name, config)
        
        if best_value:
            # Add unified tag (without source prefix)
            if tag_name not in unified_metadata:
                unified_metadata[tag_name] = best_value
            
            # Normalize format to EXIF format if possible
            parsed_date = parse_date_string(best_value)
            if parsed_date:
                normalized = parsed_date.strftime('%Y:%m:%d %H:%M:%S')
                unified_metadata[f'Unified:{tag_name}'] = normalized
    
    return unified_metadata


def resolve_priority(
    metadata: Dict[str, Any],
    tag_name: str,
    config: Optional[PriorityConfig] = None
) -> Optional[Any]:
    """
    Resolve priority conflicts for a specific tag across multiple metadata sources.
    
    This function finds all occurrences of a tag across different sources and
    returns the value from the highest priority source according to the
    priority configuration.
    
    Args:
        metadata: Dictionary of metadata tags
        tag_name: Base tag name to resolve (e.g., 'Artist', 'Copyright')
        config: Optional PriorityConfig object. If None, uses default configuration.
        
    Returns:
        Value from highest priority source, or None if not found
        
    Example:
        >>> metadata = {
        ...     'EXIF:Artist': 'John Doe',
        ...     'XMP:Creator': 'Jane Smith',
        ...     'IPTC:By-line': 'Bob Johnson'
        ... }
        >>> artist = resolve_priority(metadata, 'Artist')
        >>> # Returns 'John Doe' (EXIF has higher priority than XMP/IPTC)
    """
    if config is None:
        config = PriorityConfig()
    
    # Find all occurrences of this tag
    candidates: List[Tuple[str, Any, int]] = []  # (full_tag_name, value, priority)
    
    for full_tag, value in metadata.items():
        if not value:
            continue
        
        # Extract source and tag name
        if ':' in full_tag:
            source, tag = full_tag.split(':', 1)
        else:
            source = ''
            tag = full_tag
        
        # Check if this tag matches (exact match or common aliases)
        if tag == tag_name:
            priority = config.get_source_priority(tag_name, source)
            candidates.append((full_tag, value, priority))
    
    if not candidates:
        return None
    
    # Sort by priority and return highest priority value
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[0][1]


def normalize_metadata(
    metadata: Dict[str, Any],
    config: Optional[PriorityConfig] = None,
    unify_dates: bool = True,
    resolve_conflicts: bool = True
) -> Dict[str, Any]:
    """
    Comprehensive metadata normalization function.
    
    This function performs all normalization operations:
    1. Unifies date fields across sources
    2. Resolves priority conflicts for common tags
    3. Adds normalized tags for easier access
    
    Args:
        metadata: Dictionary of metadata tags
        config: Optional PriorityConfig object. If None, uses default configuration.
        unify_dates: If True, unify date fields across sources
        resolve_conflicts: If True, resolve priority conflicts for common tags
        
    Returns:
        New metadata dictionary with normalized fields added
        
    Example:
        >>> metadata = {
        ...     'EXIF:DateTimeOriginal': '2023:01:15 10:30:00',
        ...     'XMP:CreateDate': '2023-01-15T10:30:00',
        ...     'EXIF:Artist': 'John Doe',
        ...     'XMP:Creator': 'Jane Smith'
        ... }
        >>> normalized = normalize_metadata(metadata)
        >>> # Adds unified date fields and resolves Artist/Creator conflict
    """
    if config is None:
        config = PriorityConfig()
    
    normalized_metadata = metadata.copy()
    
    # Unify date fields
    if unify_dates:
        normalized_metadata = unify_date_fields(normalized_metadata, config)
    
    # Resolve conflicts for common tags
    if resolve_conflicts:
        common_tags = [
            'Artist', 'Creator', 'Copyright', 'Title', 'Description',
            'Keywords', 'Subject', 'Rating', 'Orientation'
        ]
        
        for tag_name in common_tags:
            resolved_value = resolve_priority(normalized_metadata, tag_name, config)
            if resolved_value and tag_name not in normalized_metadata:
                normalized_metadata[tag_name] = resolved_value
    
    return normalized_metadata


