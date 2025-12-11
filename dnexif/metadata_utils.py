# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Metadata utility functions for common operations.

This module provides utility functions for common metadata operations,
including batch processing, file operations, and metadata manipulation.

Copyright 2025 DNAi inc.
"""

from typing import Dict, List, Optional, Union, Any, Callable
from pathlib import Path
from dnexif.core import DNExif
from dnexif.exceptions import DNExifError, MetadataReadError, MetadataWriteError


def has_metadata(file_path: Union[str, Path], quick_check: bool = True) -> bool:
    """
    Quickly check if a file has metadata without fully parsing it.
    
    This function performs a quick check by reading only the file header
    and looking for metadata markers (EXIF, IPTC, XMP signatures).
    This is much faster than full metadata parsing for batch operations.
    
    Args:
        file_path: Path to the file to check
        quick_check: If True, only checks file header for metadata markers.
                    If False, performs full metadata parsing (slower but more accurate)
        
    Returns:
        True if file appears to have metadata, False otherwise
        
    Example:
        >>> if has_metadata('image.jpg'):
        ...     # Process file
        ...     pass
    """
    path = Path(file_path)
    
    if not path.exists():
        return False
    
    if quick_check:
        # Quick check: look for metadata markers in file header
        try:
            with open(path, 'rb') as f:
                # Read first 64KB (enough for most metadata headers)
                header = f.read(65536)
                
                # Check for EXIF signature (0xFF 0xE1 followed by "Exif")
                if b'\xFF\xE1' in header[:65536]:
                    exif_pos = header.find(b'\xFF\xE1')
                    if exif_pos + 6 < len(header):
                        if b'Exif' in header[exif_pos:exif_pos+20]:
                            return True
                
                # Check for XMP signature
                if b'http://ns.adobe.com/xap/1.0/' in header or b'xmp' in header.lower():
                    return True
                
                # Check for IPTC signature (APP13 segment)
                if b'\xFF\xED' in header[:65536]:
                    return True
                
                # Check for TIFF signature (II or MM)
                if header[:4] in [b'II*\x00', b'MM\x00*']:
                    return True
                
                # Check for JPEG signature
                if header[:2] == b'\xFF\xD8':
                    # JPEG files often have metadata in APP segments
                    # Check for any APP segment markers (0xFF 0xE0-0xEF)
                    for i in range(len(header) - 1):
                        if header[i] == 0xFF and 0xE0 <= header[i+1] <= 0xEF:
                            return True
                
                return False
        except Exception:
            return False
    else:
        # Full check: parse metadata
        try:
            with DNExif(path, read_only=True) as exif:
                metadata = exif.get_all_metadata()
                return len(metadata) > 0
        except Exception:
            return False


def batch_read_metadata(
    file_paths: List[Union[str, Path]],
    tags: Optional[List[str]] = None,
    error_handler: Optional[Callable[[Path, Exception], None]] = None,
    skip_no_metadata: bool = False
) -> Dict[Path, Dict[str, Any]]:
    """
    Read metadata from multiple files in batch.
    
    Args:
        file_paths: List of file paths to read
        tags: Optional list of specific tags to read (if None, reads all)
        error_handler: Optional callback function for handling errors (path, exception)
        skip_no_metadata: If True, skip files that don't have metadata (faster for large batches)
        
    Returns:
        Dictionary mapping file paths to metadata dictionaries
        
    Example:
        >>> files = ['image1.jpg', 'image2.jpg']
        >>> metadata = batch_read_metadata(files)
        >>> print(metadata['image1.jpg']['EXIF:Make'])
    """
    results = {}
    
    for file_path in file_paths:
        path = Path(file_path)
        
        # Skip files without metadata if requested (performance optimization)
        if skip_no_metadata and not has_metadata(path, quick_check=True):
            continue
        
        try:
            with DNExif(path, read_only=True) as exif:
                if tags:
                    metadata = {tag: exif.get_tag(tag) for tag in tags}
                else:
                    metadata = exif.get_all_metadata()
                results[path] = metadata
        except Exception as e:
            if error_handler:
                error_handler(path, e)
            else:
                # Default: store error in results
                results[path] = {'_error': str(e)}
    
    return results


def batch_write_metadata(
    file_paths: List[Union[str, Path]],
    metadata_updates: Dict[str, Any],
    create_backup: bool = False,
    error_handler: Optional[Callable[[Path, Exception], None]] = None
) -> Dict[Path, bool]:
    """
    Write metadata to multiple files in batch.
    
    Args:
        file_paths: List of file paths to write
        metadata_updates: Dictionary of tag names to values to set
        create_backup: Whether to create backup files before writing
        error_handler: Optional callback function for handling errors (path, exception)
        
    Returns:
        Dictionary mapping file paths to success status (True/False)
        
    Example:
        >>> files = ['image1.jpg', 'image2.jpg']
        >>> updates = {'EXIF:Artist': 'John Doe', 'EXIF:Copyright': '2025'}
        >>> results = batch_write_metadata(files, updates)
        >>> print(results['image1.jpg'])  # True if successful
    """
    results = {}
    
    for file_path in file_paths:
        path = Path(file_path)
        success = False
        
        try:
            # Create backup if requested
            if create_backup:
                backup_path = path.with_suffix(path.suffix + '.bak')
                import shutil
                shutil.copy2(path, backup_path)
            
            with DNExif(path, read_only=False) as exif:
                for tag_name, value in metadata_updates.items():
                    exif.set_tag(tag_name, value)
                exif.save()
                success = True
        except Exception as e:
            if error_handler:
                error_handler(path, e)
            success = False
        
        results[path] = success
    
    return results


def copy_metadata(
    source_file: Union[str, Path],
    target_file: Union[str, Path],
    tags: Optional[List[str]] = None,
    overwrite: bool = True
) -> bool:
    """
    Copy metadata from source file to target file.
    
    Args:
        source_file: Source file path
        target_file: Target file path
        tags: Optional list of specific tags to copy (if None, copies all)
        overwrite: Whether to overwrite existing tags in target file
        
    Returns:
        True if successful, False otherwise
        
    Example:
        >>> copy_metadata('source.jpg', 'target.jpg')
        True
        >>> copy_metadata('source.jpg', 'target.jpg', tags=['EXIF:Make', 'EXIF:Model'])
        True
    """
    try:
        # Read metadata from source
        source_path = Path(source_file)
        target_path = Path(target_file)
        
        with DNExif(source_path, read_only=True) as source_exif:
            if tags:
                source_metadata = {tag: source_exif.get_tag(tag) for tag in tags}
            else:
                source_metadata = source_exif.get_all_metadata()
        
        # Write metadata to target
        with DNExif(target_path, read_only=False) as target_exif:
            for tag_name, value in source_metadata.items():
                if value is not None:
                    # Skip if tag exists and overwrite is False
                    if not overwrite and target_exif.get_tag(tag_name) is not None:
                        continue
                    target_exif.set_tag(tag_name, value)
            target_exif.save()
        
        return True
    except Exception:
        return False


def filter_metadata_by_groups(
    metadata: Dict[str, Any],
    groups: List[str],
    include: bool = True
) -> Dict[str, Any]:
    """
    Filter metadata by group names.
    
    Args:
        metadata: Metadata dictionary
        groups: List of group names (e.g., ['EXIF', 'IPTC'])
        include: If True, include only specified groups; if False, exclude specified groups
        
    Returns:
        Filtered metadata dictionary
        
    Example:
        >>> metadata = {'EXIF:Make': 'Canon', 'IPTC:Keywords': 'test', 'XMP:Title': 'Image'}
        >>> filtered = filter_metadata_by_groups(metadata, ['EXIF'], include=True)
        >>> # Returns: {'EXIF:Make': 'Canon'}
    """
    filtered = {}
    
    for tag_name, value in metadata.items():
        tag_group = tag_name.split(':', 1)[0] if ':' in tag_name else ''
        
        if include:
            if tag_group in groups:
                filtered[tag_name] = value
        else:
            if tag_group not in groups:
                filtered[tag_name] = value
    
    return filtered


def merge_metadata(
    *metadata_dicts: Dict[str, Any],
    priority: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Merge multiple metadata dictionaries.
    
    Args:
        *metadata_dicts: Variable number of metadata dictionaries to merge
        priority: Optional list of group names in priority order (first occurrence wins)
        
    Returns:
        Merged metadata dictionary
        
    Example:
        >>> meta1 = {'EXIF:Make': 'Canon'}
        >>> meta2 = {'EXIF:Model': 'EOS'}
        >>> merged = merge_metadata(meta1, meta2)
        >>> # Returns: {'EXIF:Make': 'Canon', 'EXIF:Model': 'EOS'}
    """
    merged = {}
    
    if priority:
        # Merge in priority order
        for group in priority:
            for metadata in metadata_dicts:
                for tag_name, value in metadata.items():
                    tag_group = tag_name.split(':', 1)[0] if ':' in tag_name else ''
                    if tag_group == group and tag_name not in merged:
                        merged[tag_name] = value
        
        # Add remaining tags
        for metadata in metadata_dicts:
            for tag_name, value in metadata.items():
                if tag_name not in merged:
                    merged[tag_name] = value
    else:
        # Simple merge (later dictionaries overwrite earlier ones)
        for metadata in metadata_dicts:
            merged.update(metadata)
    
    return merged


def get_metadata_summary(
    metadata: Dict[str, Any],
    include_counts: bool = True
) -> Dict[str, Any]:
    """
    Get summary statistics about metadata.
    
    Args:
        metadata: Metadata dictionary
        include_counts: Whether to include tag counts by group
        
    Returns:
        Dictionary with summary information
        
    Example:
        >>> metadata = {'EXIF:Make': 'Canon', 'EXIF:Model': 'EOS', 'IPTC:Keywords': 'test'}
        >>> summary = get_metadata_summary(metadata)
        >>> # Returns: {'total_tags': 3, 'groups': {'EXIF': 2, 'IPTC': 1}}
    """
    summary = {
        'total_tags': len(metadata)
    }
    
    if include_counts:
        group_counts = {}
        for tag_name in metadata.keys():
            group = tag_name.split(':', 1)[0] if ':' in tag_name else 'Unknown'
            group_counts[group] = group_counts.get(group, 0) + 1
        summary['groups'] = group_counts
    
    return summary

