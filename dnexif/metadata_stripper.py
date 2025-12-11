# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Metadata Stripping Module for Privacy

This module provides functions for stripping metadata from files to protect privacy.
It supports multiple privacy presets and selective stripping by tag groups.

Copyright 2025 DNAi inc.
"""

from typing import Dict, Any, Optional, List, Set, Union
from enum import Enum
import re


class PrivacyPreset(Enum):
    """Privacy presets for metadata stripping."""
    MINIMAL = "minimal"  # Remove only obvious PII (GPS, serial numbers)
    STANDARD = "standard"  # Remove PII + device identifiers + location data
    STRICT = "strict"  # Remove all metadata except basic image properties
    CUSTOM = "custom"  # Custom tag group selection


class PrivacyConfig:
    """
    Configuration for metadata stripping operations.
    
    This class defines which tags should be stripped based on privacy presets
    and custom tag group selections.
    """
    
    def __init__(self, preset: PrivacyPreset = PrivacyPreset.STANDARD):
        """
        Initialize privacy configuration.
        
        Args:
            preset: Privacy preset level (MINIMAL, STANDARD, STRICT, or CUSTOM)
        """
        self.preset = preset
        self.strip_groups: Set[str] = set()
        self.strip_tags: Set[str] = set()
        self.keep_groups: Set[str] = set()
        self.keep_tags: Set[str] = set()
        
        # Initialize based on preset
        if preset == PrivacyPreset.MINIMAL:
            self._init_minimal()
        elif preset == PrivacyPreset.STANDARD:
            self._init_standard()
        elif preset == PrivacyPreset.STRICT:
            self._init_strict()
    
    def _init_minimal(self):
        """Initialize minimal privacy preset - removes only obvious PII."""
        # GPS and location data
        self.strip_groups.update(['GPS', 'Location'])
        self.strip_tags.update([
            'GPSLatitude', 'GPSLongitude', 'GPSAltitude', 'GPSPosition',
            'GPSDateStamp', 'GPSTimeStamp', 'GPSDateTime',
            'Location', 'City', 'State', 'Country', 'CountryCode',
            'Sublocation', 'WorldRegion'
        ])
        
        # Serial numbers and device identifiers
        self.strip_tags.update([
            'SerialNumber', 'BodySerialNumber', 'LensSerialNumber',
            'CameraSerialNumber', 'InternalSerialNumber',
            'ImageUniqueID', 'OriginalImageUniqueID',
            'InstanceID', 'DocumentID'
        ])
    
    def _init_standard(self):
        """Initialize standard privacy preset - removes PII + device identifiers + location."""
        # Include minimal preset
        self._init_minimal()
        
        # Additional location and identification data
        self.strip_groups.update(['IPTC', 'XMP'])
        self.strip_tags.update([
            # IPTC location tags
            'IPTC:City', 'IPTC:Province-State', 'IPTC:Country-PrimaryLocationName',
            'IPTC:Country-PrimaryLocationCode', 'IPTC:Sublocation',
            'IPTC:WorldRegion',
            # XMP location tags
            'XMP:City', 'XMP:State', 'XMP:Country', 'XMP:Location',
            # Creator/author information
            'Artist', 'Creator', 'By-line', 'By-lineTitle', 'Credit',
            'Copyright', 'CopyrightNotice', 'Rights',
            # Contact information
            'Contact', 'CreatorContactInfo', 'ContactEmail', 'ContactPhone',
            'ContactAddress', 'ContactCity', 'ContactState', 'ContactCountry',
            # Software and camera info (can identify device)
            'Software', 'CameraModelName', 'LensModel',
            # Timestamps (can reveal when/where photo was taken)
            'DateTimeOriginal', 'CreateDate', 'DateCreated',
            'GPSDateTime', 'GPSTimeStamp',
            # MakerNote data (often contains device-specific info)
            'MakerNotes', 'MakerNote',
        ])
        
        # Strip entire MakerNote groups
        self.strip_groups.update([
            'Canon', 'Nikon', 'Sony', 'Fujifilm', 'Olympus',
            'Panasonic', 'Pentax', 'Samsung', 'Apple', 'MakerNotes'
        ])
    
    def _init_strict(self):
        """Initialize strict privacy preset - removes all metadata except basic image properties."""
        # Include standard preset
        self._init_standard()
        
        # Remove all metadata groups except basic image properties
        self.strip_groups.update([
            'EXIF', 'IPTC', 'XMP', 'GPS', 'MakerNotes',
            'Canon', 'Nikon', 'Sony', 'Fujifilm', 'Olympus',
            'Panasonic', 'Pentax', 'Samsung', 'Apple',
            'QuickTime', 'Composite', 'File'
        ])
        
        # Keep only essential image properties
        self.keep_tags.update([
            'ImageWidth', 'ImageHeight', 'BitsPerSample',
            'ColorSpace', 'Compression', 'Orientation'
        ])
    
    def should_strip(self, tag_name: str) -> bool:
        """
        Determine if a tag should be stripped based on configuration.
        
        Args:
            tag_name: Full tag name (e.g., 'EXIF:DateTimeOriginal' or 'GPS:GPSLatitude')
            
        Returns:
            True if tag should be stripped, False otherwise
        """
        # Check if tag is explicitly kept
        if tag_name in self.keep_tags:
            return False
        
        # Check if tag name (without group) is explicitly kept
        if ':' in tag_name:
            _, base_tag = tag_name.split(':', 1)
            if base_tag in self.keep_tags:
                return False
        
        # Check if tag is explicitly marked for stripping
        if tag_name in self.strip_tags:
            return True
        
        # Check if tag name (without group) is explicitly marked for stripping
        if ':' in tag_name:
            _, base_tag = tag_name.split(':', 1)
            if base_tag in self.strip_tags:
                return True
        
        # Check if tag's group should be stripped
        if ':' in tag_name:
            group, _ = tag_name.split(':', 1)
            if group in self.strip_groups:
                return True
        
        # For strict preset, strip everything not explicitly kept
        if self.preset == PrivacyPreset.STRICT:
            return True
        
        return False


class PIIDetector:
    """
    PII (Personally Identifiable Information) detector.
    
    Detects common PII patterns in metadata values.
    """
    
    # Email pattern
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    
    # Phone number patterns (various formats)
    PHONE_PATTERNS = [
        re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),  # US format
        re.compile(r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b'),  # International
    ]
    
    # Credit card pattern (basic detection)
    CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
    
    # Social Security Number pattern (US)
    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    
    # IP address pattern
    IP_PATTERN = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
    
    # MAC address pattern
    MAC_PATTERN = re.compile(r'\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b')
    
    @classmethod
    def contains_pii(cls, value: str) -> bool:
        """
        Check if a value contains PII patterns.
        
        Args:
            value: String value to check
            
        Returns:
            True if PII patterns detected, False otherwise
        """
        if not isinstance(value, str):
            value = str(value)
        
        # Check for email
        if cls.EMAIL_PATTERN.search(value):
            return True
        
        # Check for phone numbers
        for pattern in cls.PHONE_PATTERNS:
            if pattern.search(value):
                return True
        
        # Check for credit card (basic)
        if cls.CREDIT_CARD_PATTERN.search(value):
            return True
        
        # Check for SSN
        if cls.SSN_PATTERN.search(value):
            return True
        
        # Check for IP address
        if cls.IP_PATTERN.search(value):
            return True
        
        # Check for MAC address
        if cls.MAC_PATTERN.search(value):
            return True
        
        return False
    
    @classmethod
    def detect_pii_tags(cls, metadata: Dict[str, Any]) -> List[str]:
        """
        Detect tags containing PII in metadata.
        
        Args:
            metadata: Dictionary of metadata tags
            
        Returns:
            List of tag names containing PII
        """
        pii_tags = []
        
        for tag_name, value in metadata.items():
            if cls.contains_pii(str(value)):
                pii_tags.append(tag_name)
        
        return pii_tags


def strip_metadata(
    metadata: Dict[str, Any],
    config: Optional[PrivacyConfig] = None,
    remove_pii: bool = True
) -> Dict[str, Any]:
    """
    Strip metadata based on privacy configuration.
    
    Args:
        metadata: Dictionary of metadata tags to strip
        config: PrivacyConfig object. If None, uses STANDARD preset.
        remove_pii: If True, also removes tags containing detected PII
        
    Returns:
        New metadata dictionary with stripped tags removed
        
    Example:
        >>> metadata = {
        ...     'EXIF:DateTimeOriginal': '2023:01:15 10:30:00',
        ...     'GPS:GPSLatitude': '40.7128',
        ...     'EXIF:Artist': 'John Doe',
        ...     'EXIF:ImageWidth': 1920
        ... }
        >>> config = PrivacyConfig(PrivacyPreset.STANDARD)
        >>> stripped = strip_metadata(metadata, config)
        >>> # Returns metadata with GPS and Artist removed, ImageWidth kept
    """
    if config is None:
        config = PrivacyConfig(PrivacyPreset.STANDARD)
    
    stripped_metadata = {}
    pii_tags = set()
    
    # Detect PII if requested
    if remove_pii:
        pii_tags = set(PIIDetector.detect_pii_tags(metadata))
    
    # Filter metadata based on configuration
    for tag_name, value in metadata.items():
        # Skip if tag should be stripped
        if config.should_strip(tag_name):
            continue
        
        # Skip if tag contains PII
        if remove_pii and tag_name in pii_tags:
            continue
        
        # Keep the tag
        stripped_metadata[tag_name] = value
    
    return stripped_metadata


def strip_by_groups(
    metadata: Dict[str, Any],
    groups_to_strip: List[str],
    keep_tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Strip metadata by tag groups.
    
    Args:
        metadata: Dictionary of metadata tags
        groups_to_strip: List of group names to strip (e.g., ['GPS', 'EXIF'])
        keep_tags: Optional list of specific tags to keep even if their group is stripped
        
    Returns:
        New metadata dictionary with specified groups removed
        
    Example:
        >>> metadata = {
        ...     'GPS:GPSLatitude': '40.7128',
        ...     'EXIF:DateTimeOriginal': '2023:01:15',
        ...     'EXIF:ImageWidth': 1920
        ... }
        >>> stripped = strip_by_groups(metadata, ['GPS'], keep_tags=['EXIF:ImageWidth'])
        >>> # Returns metadata with GPS removed, EXIF tags kept
    """
    if keep_tags is None:
        keep_tags = []
    
    keep_tags_set = set(keep_tags)
    groups_to_strip_set = set(groups_to_strip)
    
    stripped_metadata = {}
    
    for tag_name, value in metadata.items():
        # Always keep explicitly listed tags
        if tag_name in keep_tags_set:
            stripped_metadata[tag_name] = value
            continue
        
        # Check if tag belongs to a group to strip
        if ':' in tag_name:
            group, _ = tag_name.split(':', 1)
            if group in groups_to_strip_set:
                continue
        
        # Keep the tag
        stripped_metadata[tag_name] = value
    
    return stripped_metadata


def strip_by_tags(
    metadata: Dict[str, Any],
    tags_to_strip: List[str]
) -> Dict[str, Any]:
    """
    Strip specific tags from metadata.
    
    Args:
        metadata: Dictionary of metadata tags
        tags_to_strip: List of tag names to strip (supports wildcards)
        
    Returns:
        New metadata dictionary with specified tags removed
        
    Example:
        >>> metadata = {
        ...     'EXIF:DateTimeOriginal': '2023:01:15',
        ...     'EXIF:Artist': 'John Doe',
        ...     'EXIF:ImageWidth': 1920
        ... }
        >>> stripped = strip_by_tags(metadata, ['EXIF:Artist', 'EXIF:DateTime*'])
        >>> # Returns metadata with Artist and DateTimeOriginal removed
    """
    tags_to_strip_set = set(tags_to_strip)
    stripped_metadata = {}
    
    for tag_name, value in metadata.items():
        # Check exact match
        if tag_name in tags_to_strip_set:
            continue
        
        # Check wildcard patterns
        should_strip = False
        for pattern in tags_to_strip_set:
            if '*' in pattern:
                # Simple wildcard matching
                pattern_re = pattern.replace('*', '.*')
                if re.match(pattern_re, tag_name):
                    should_strip = True
                    break
        
        if should_strip:
            continue
        
        # Keep the tag
        stripped_metadata[tag_name] = value
    
    return stripped_metadata


def get_stripped_count(
    original_metadata: Dict[str, Any],
    stripped_metadata: Dict[str, Any]
) -> Dict[str, int]:
    """
    Get statistics about stripped metadata.
    
    Args:
        original_metadata: Original metadata dictionary
        stripped_metadata: Stripped metadata dictionary
        
    Returns:
        Dictionary with statistics (total_original, total_stripped, removed_count)
    """
    original_count = len(original_metadata)
    stripped_count = len(stripped_metadata)
    removed_count = original_count - stripped_count
    
    return {
        'total_original': original_count,
        'total_stripped': stripped_count,
        'removed_count': removed_count,
        'removed_percentage': (removed_count / original_count * 100) if original_count > 0 else 0.0
    }


