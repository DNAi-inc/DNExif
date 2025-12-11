# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Metadata Diff Module

This module provides functions for comparing metadata between two files
and reporting differences. Similar to standard -diff option.

Copyright 2025 DNAi inc.
"""

from typing import Dict, Any, Optional, List, Tuple, Set
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import re


class DiffType(Enum):
    """Type of difference between two metadata values."""
    MISSING_IN_FILE1 = "missing_in_file1"  # Tag exists in file2 but not in file1
    MISSING_IN_FILE2 = "missing_in_file2"  # Tag exists in file1 but not in file2
    VALUE_DIFFERENT = "value_different"  # Tag exists in both but values differ
    BINARY_DIFFERENT = "binary_different"  # Binary data differs
    MATCHED = "matched"  # Tags match


@dataclass
class MetadataDiff:
    """Represents a difference between two metadata values."""
    tag_name: str
    diff_type: DiffType
    file1_value: Optional[Any] = None
    file2_value: Optional[Any] = None
    normalized_file1_value: Optional[str] = None
    normalized_file2_value: Optional[str] = None


@dataclass
class DiffResult:
    """Result of comparing metadata between two files."""
    file1_path: Path
    file2_path: Path
    total_tags_file1: int
    total_tags_file2: int
    matched_tags: int
    differences: List[MetadataDiff]
    missing_in_file1: List[str]
    missing_in_file2: List[str]
    value_differences: List[MetadataDiff]
    binary_differences: List[MetadataDiff]


def normalize_value(value: Any) -> str:
    """
    Normalize a metadata value for comparison.
    
    Args:
        value: Metadata value to normalize
        
    Returns:
        Normalized string representation
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        # For binary data, return hex representation
        try:
            return value.hex()
        except Exception:
            return str(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(str(normalize_value(v)) for v in value)
    return str(value).strip()


def normalize_tag_name(tag_name: str) -> str:
    """
    Normalize tag name for comparison (case-insensitive).
    
    Args:
        tag_name: Tag name to normalize
        
    Returns:
        Normalized tag name
    """
    # Remove standard format-specific tags
    if tag_name.startswith('standard format:'):
        return ""
    
    # Case-insensitive comparison
    return tag_name.lower()


def is_binary_data(value: Any) -> bool:
    """
    Check if a value is binary data.
    
    Args:
        value: Value to check
        
    Returns:
        True if value is binary data
    """
    return isinstance(value, bytes)


def compare_values(
    value1: Any,
    value2: Any,
    tag_name: str = ""
) -> Tuple[bool, Optional[str]]:
    """
    Compare two metadata values with tolerance for numeric differences.
    
    Args:
        value1: First value to compare
        value2: Second value to compare
        tag_name: Tag name (for context)
        
    Returns:
        Tuple of (is_match, reason_if_different)
    """
    # Normalize values
    norm1 = normalize_value(value1)
    norm2 = normalize_value(value2)
    
    # Exact match
    if norm1 == norm2:
        return True, None
    
    # Case-insensitive comparison
    if norm1.lower() == norm2.lower():
        return True, None
    
    # Check if both are binary data
    if is_binary_data(value1) and is_binary_data(value2):
        # Compare binary data
        if value1 == value2:
            return True, None
        return False, "Binary data differs"
    
    # Numeric sequence comparison (for arrays like ColorMatrix)
    def _is_numeric_sequence(s: str) -> Tuple[bool, List[float]]:
        """Check if string is a numeric sequence."""
        s = s.strip()
        if not s:
            return False, []
        
        parts = s.split()
        floats: List[float] = []
        for part in parts:
            if not re.fullmatch(r'[+-]?(?:\d+\.?\d*|\d*\.?\d+)(?:[eE][+-]?\d+)?', part):
                return False, []
            try:
                floats.append(float(part))
            except ValueError:
                return False, []
        return True, floats
    
    is_num1, nums1 = _is_numeric_sequence(norm1)
    is_num2, nums2 = _is_numeric_sequence(norm2)
    
    if is_num1 and is_num2 and len(nums1) == len(nums2):
        # Element-wise comparison with tolerance
        all_close = True
        for a, b in zip(nums1, nums2):
            # Absolute tolerance of 1e-6 and relative tolerance of 1e-6
            if abs(a - b) > 1e-6 and abs(a - b) > 1e-6 * max(abs(a), abs(b), 1.0):
                all_close = False
                break
        if all_close:
            return True, None
    
    # Values differ
    return False, f"'{norm1}' != '{norm2}'"


def diff_metadata(
    metadata1: Dict[str, Any],
    metadata2: Dict[str, Any],
    file1_path: Optional[Path] = None,
    file2_path: Optional[Path] = None,
    ignore_tags: Optional[List[str]] = None,
    ignore_groups: Optional[List[str]] = None
) -> DiffResult:
    """
    Compare metadata between two files and report differences.
    
    Args:
        metadata1: Metadata dictionary from first file
        metadata2: Metadata dictionary from second file
        file1_path: Optional path to first file (for reporting)
        file2_path: Optional path to second file (for reporting)
        ignore_tags: Optional list of tag names to ignore in comparison
        ignore_groups: Optional list of group names to ignore (e.g., ['standard format'])
        
    Returns:
        DiffResult object with comparison results
        
    Example:
        >>> metadata1 = {'EXIF:DateTimeOriginal': '2023:01:15', 'EXIF:Artist': 'John'}
        >>> metadata2 = {'EXIF:DateTimeOriginal': '2023:01:15', 'EXIF:Artist': 'Jane'}
        >>> result = diff_metadata(metadata1, metadata2)
        >>> print(f"Differences: {len(result.differences)}")
    """
    if ignore_tags is None:
        ignore_tags = []
    if ignore_groups is None:
        ignore_groups = ['standard format']  # Ignore standard format-specific tags by default
    
    ignore_tags_set = {normalize_tag_name(tag) for tag in ignore_tags}
    ignore_groups_set = {group.lower() for group in ignore_groups}
    
    # Normalize tag names for comparison
    normalized_metadata1 = {}
    normalized_metadata2 = {}
    
    for tag, value in metadata1.items():
        norm_tag = normalize_tag_name(tag)
        if norm_tag and norm_tag not in ignore_tags_set:
            # Check if tag's group should be ignored
            if ':' in tag:
                group = tag.split(':', 1)[0].lower()
                if group in ignore_groups_set:
                    continue
            normalized_metadata1[norm_tag] = (tag, value)
    
    for tag, value in metadata2.items():
        norm_tag = normalize_tag_name(tag)
        if norm_tag and norm_tag not in ignore_tags_set:
            # Check if tag's group should be ignored
            if ':' in tag:
                group = tag.split(':', 1)[0].lower()
                if group in ignore_groups_set:
                    continue
            normalized_metadata2[norm_tag] = (tag, value)
    
    # Find differences
    differences: List[MetadataDiff] = []
    missing_in_file1: List[str] = []
    missing_in_file2: List[str] = []
    value_differences: List[MetadataDiff] = []
    binary_differences: List[MetadataDiff] = []
    matched_count = 0
    
    # Check tags in file1
    for norm_tag, (orig_tag, value1) in normalized_metadata1.items():
        if norm_tag in normalized_metadata2:
            # Tag exists in both files
            _, value2 = normalized_metadata2[norm_tag]
            is_match, reason = compare_values(value1, value2, orig_tag)
            
            if is_match:
                matched_count += 1
            else:
                diff = MetadataDiff(
                    tag_name=orig_tag,
                    diff_type=DiffType.VALUE_DIFFERENT if not is_binary_data(value1) else DiffType.BINARY_DIFFERENT,
                    file1_value=value1,
                    file2_value=value2,
                    normalized_file1_value=normalize_value(value1),
                    normalized_file2_value=normalize_value(value2)
                )
                differences.append(diff)
                if is_binary_data(value1) or is_binary_data(value2):
                    binary_differences.append(diff)
                else:
                    value_differences.append(diff)
        else:
            # Tag exists only in file1
            diff = MetadataDiff(
                tag_name=orig_tag,
                diff_type=DiffType.MISSING_IN_FILE2,
                file1_value=value1,
                normalized_file1_value=normalize_value(value1)
            )
            differences.append(diff)
            missing_in_file2.append(orig_tag)
    
    # Check tags in file2
    for norm_tag, (orig_tag, value2) in normalized_metadata2.items():
        if norm_tag not in normalized_metadata1:
            # Tag exists only in file2
            diff = MetadataDiff(
                tag_name=orig_tag,
                diff_type=DiffType.MISSING_IN_FILE1,
                file2_value=value2,
                normalized_file2_value=normalize_value(value2)
            )
            differences.append(diff)
            missing_in_file1.append(orig_tag)
    
    return DiffResult(
        file1_path=file1_path or Path("file1"),
        file2_path=file2_path or Path("file2"),
        total_tags_file1=len(normalized_metadata1),
        total_tags_file2=len(normalized_metadata2),
        matched_tags=matched_count,
        differences=differences,
        missing_in_file1=missing_in_file1,
        missing_in_file2=missing_in_file2,
        value_differences=value_differences,
        binary_differences=binary_differences
    )


def format_diff_result(result: DiffResult, verbose: bool = False) -> str:
    """
    Format diff result as a human-readable string.
    
    Args:
        result: DiffResult object to format
        verbose: If True, include more details
        
    Returns:
        Formatted string
    """
    lines = []
    lines.append("=" * 70)
    lines.append("Metadata Comparison Results")
    lines.append("=" * 70)
    lines.append(f"File 1: {result.file1_path}")
    lines.append(f"File 2: {result.file2_path}")
    lines.append("")
    lines.append(f"File 1 tags: {result.total_tags_file1}")
    lines.append(f"File 2 tags: {result.total_tags_file2}")
    lines.append(f"Matched tags: {result.matched_tags}")
    lines.append(f"Total differences: {len(result.differences)}")
    lines.append("")
    
    if result.missing_in_file1:
        lines.append(f"Tags only in File 2 ({len(result.missing_in_file1)}):")
        for tag in result.missing_in_file1[:20]:  # Limit to first 20
            lines.append(f"  + {tag}")
        if len(result.missing_in_file1) > 20:
            lines.append(f"  ... and {len(result.missing_in_file1) - 20} more")
        lines.append("")
    
    if result.missing_in_file2:
        lines.append(f"Tags only in File 1 ({len(result.missing_in_file2)}):")
        for tag in result.missing_in_file2[:20]:  # Limit to first 20
            lines.append(f"  - {tag}")
        if len(result.missing_in_file2) > 20:
            lines.append(f"  ... and {len(result.missing_in_file2) - 20} more")
        lines.append("")
    
    if result.value_differences:
        lines.append(f"Value differences ({len(result.value_differences)}):")
        for diff in result.value_differences[:20]:  # Limit to first 20
            lines.append(f"  {diff.tag_name}:")
            lines.append(f"    File 1: {diff.normalized_file1_value}")
            lines.append(f"    File 2: {diff.normalized_file2_value}")
        if len(result.value_differences) > 20:
            lines.append(f"  ... and {len(result.value_differences) - 20} more")
        lines.append("")
    
    if result.binary_differences:
        lines.append(f"Binary data differences ({len(result.binary_differences)}):")
        for diff in result.binary_differences[:10]:  # Limit to first 10
            lines.append(f"  {diff.tag_name}: Binary data differs")
        if len(result.binary_differences) > 10:
            lines.append(f"  ... and {len(result.binary_differences) - 10} more")
        lines.append("")
    
    return "\n".join(lines)


def diff_files(
    file1_path: Path,
    file2_path: Path,
    ignore_tags: Optional[List[str]] = None,
    ignore_groups: Optional[List[str]] = None
) -> DiffResult:
    """
    Compare metadata between two files.
    
    Args:
        file1_path: Path to first file
        file2_path: Path to second file
        ignore_tags: Optional list of tag names to ignore
        ignore_groups: Optional list of group names to ignore
        
    Returns:
        DiffResult object with comparison results
    """
    from dnexif.core import DNExif
    
    # Read metadata from both files
    metadata1 = {}
    metadata2 = {}
    
    try:
        with DNExif(file1_path, read_only=True) as exif1:
            metadata1 = exif1.get_all_metadata()
    except Exception as e:
        raise ValueError(f"Error reading metadata from {file1_path}: {e}")
    
    try:
        with DNExif(file2_path, read_only=True) as exif2:
            metadata2 = exif2.get_all_metadata()
    except Exception as e:
        raise ValueError(f"Error reading metadata from {file2_path}: {e}")
    
    # Compare metadata
    return diff_metadata(
        metadata1,
        metadata2,
        file1_path=file1_path,
        file2_path=file2_path,
        ignore_tags=ignore_tags,
        ignore_groups=ignore_groups
    )


