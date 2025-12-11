# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Command-line interface for DNExif

Provides a CLI for reading and writing metadata from image files.
This is a 100% pure Python implementation with no external dependencies.

This module imports the enhanced CLI for comprehensive metadata operations.

Copyright 2025 DNAi inc.
"""

# Import enhanced CLI for comprehensive metadata operations
from dnexif.cli_enhanced import main

# Re-export main for backward compatibility
__all__ = ['main']

# Import required modules for helper functions
import json
import sys
from pathlib import Path
from typing import List, Optional

from dnexif.core import DNExif
from dnexif.exceptions import DNExifError


def format_output(metadata: dict, format_type: str = "text") -> str:
    """
    Format metadata output based on format type.
    
    Args:
        metadata: Dictionary of metadata
        format_type: Output format ('text', 'json', 'csv')
        
    Returns:
        Formatted output string
    """
    if format_type == "json":
        return json.dumps(metadata, indent=2, ensure_ascii=False)
    elif format_type == "csv":
        lines = ["Tag,Value"]
        for tag, value in sorted(metadata.items()):
            # Escape commas and quotes in CSV
            value_str = str(value).replace('"', '""')
            lines.append(f'"{tag}","{value_str}"')
        return "\n".join(lines)
    else:  # text format (default)
        lines = []
        for tag, value in sorted(metadata.items()):
            lines.append(f"{tag}: {value}")
        return "\n".join(lines)


def read_metadata(
    file_path: Path,
    tags: Optional[List[str]] = None,
    format_type: str = "text"
) -> str:
    """
    Read metadata from a file.
    
    Args:
        file_path: Path to the image file
        tags: Optional list of specific tags to read
        format_type: Output format
        
    Returns:
        Formatted metadata string
    """
    try:
        with DNExif(file_path, read_only=True) as exif:
            if tags:
                metadata = exif.get_tags(tags)
            else:
                metadata = exif.get_all_metadata()
            
            return format_output(metadata, format_type)
    except DNExifError as e:
        return f"Error: {str(e)}"


def write_metadata(
    file_path: Path,
    tags: dict,
    output_path: Optional[Path] = None
) -> str:
    """
    Write metadata to a file.
    
    Args:
        file_path: Path to the image file
        tags: Dictionary of tags to write
        output_path: Optional output path
        
    Returns:
        Status message
    """
    try:
        with DNExif(file_path, read_only=False) as exif:
            exif.set_tags(tags)
            exif.save(output_path)
            return f"Metadata written successfully to {output_path or file_path}"
    except DNExifError as e:
        return f"Error: {str(e)}"
    except NotImplementedError as e:
        return f"Error: {str(e)}"
    except DNExifError as e:
        return f"Error: {str(e)}"


def parse_tag_assignments(args: List[str]) -> dict:
    """
    Parse tag assignments from command-line arguments.
    
    Format: -TAGNAME=value or TAGNAME=value
    
    Args:
        args: List of tag assignment strings
        
    Returns:
        Dictionary of tag names to values
    """
    tags = {}
    for arg in args:
        if '=' not in arg:
            continue
        
        # Remove leading dash if present
        tag_name = arg.lstrip('-')
        
        if '=' in tag_name:
            key, value = tag_name.split('=', 1)
            tags[key] = value
    
    return tags


# The main function is imported from cli_enhanced
# This file provides backward compatibility and helper functions

if __name__ == "__main__":
    main()

