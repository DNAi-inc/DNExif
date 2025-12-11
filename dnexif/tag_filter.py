# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Tag filtering utilities

Provides advanced tag filtering capabilities including regex-based filtering,
conditional operations, and tag creation.

Copyright 2025 DNAi inc.
"""

import re
from typing import Dict, Any, List, Optional, Callable, Union
from pathlib import Path

from dnexif.core import DNExif
from dnexif.exceptions import MetadataWriteError


class TagFilter:
    """
    Advanced tag filtering and manipulation utilities.
    
    Provides regex-based filtering, conditional operations,
    and dynamic tag creation.
    """
    
    @staticmethod
    def filter_tags(
        metadata: Dict[str, Any],
        pattern: str,
        include: bool = True
    ) -> Dict[str, Any]:
        """
        Filter tags by regex pattern.
        
        Args:
            metadata: Metadata dictionary
            pattern: Regex pattern to match
            include: If True, include matching tags; if False, exclude them
            
        Returns:
            Filtered metadata dictionary
        """
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            raise ValueError(f"Invalid regex pattern: {pattern}")
        
        if include:
            return {k: v for k, v in metadata.items() if regex.search(k)}
        else:
            return {k: v for k, v in metadata.items() if not regex.search(k)}
    
    @staticmethod
    def filter_by_group(
        metadata: Dict[str, Any],
        groups: List[str],
        include: bool = True
    ) -> Dict[str, Any]:
        """
        Filter tags by group names.
        
        Args:
            metadata: Metadata dictionary
            groups: List of group names (e.g., ['EXIF', 'IPTC'])
            include: If True, include tags from groups; if False, exclude them
            
        Returns:
            Filtered metadata dictionary
        """
        if include:
            return {
                k: v for k, v in metadata.items()
                if any(k.startswith(f"{group}:") for group in groups)
            }
        else:
            return {
                k: v for k, v in metadata.items()
                if not any(k.startswith(f"{group}:") for group in groups)
            }
    
    @staticmethod
    def filter_by_value(
        metadata: Dict[str, Any],
        condition: Callable[[Any], bool]
    ) -> Dict[str, Any]:
        """
        Filter tags by value condition.
        
        Args:
            metadata: Metadata dictionary
            condition: Function that takes a value and returns True/False
            
        Returns:
            Filtered metadata dictionary
        """
        return {k: v for k, v in metadata.items() if condition(v)}
    
    @staticmethod
    def create_tag(
        file_path: str,
        tag_name: str,
        value: Any,
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new tag dynamically.
        
        Args:
            file_path: Path to file
            tag_name: Tag name (with or without namespace)
            value: Tag value
            namespace: Optional namespace (if not in tag_name)
            
        Returns:
            Dictionary with operation results
        """
        try:
            # Ensure tag has namespace
            if ':' not in tag_name and namespace:
                tag_name = f"{namespace}:{tag_name}"
            elif ':' not in tag_name:
                # Default to EXIF namespace
                tag_name = f"EXIF:{tag_name}"
            
            manager = DNExif(file_path, read_only=False)
            manager.set_tag(tag_name, value)
            manager.save()
            
            return {
                'success': True,
                'tag': tag_name,
                'value': value,
                'created': True
            }
        
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to create tag: {str(e)}")
    
    @staticmethod
    def create_custom_namespace(
        file_path: str,
        namespace: str,
        tags: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create tags in a custom namespace.
        
        Args:
            file_path: Path to file
            namespace: Custom namespace name
            tags: Dictionary of tag names to values
            
        Returns:
            Dictionary with operation results
        """
        try:
            manager = DNExif(file_path, read_only=False)
            
            created = 0
            for tag_name, value in tags.items():
                full_tag = f"{namespace}:{tag_name}"
                manager.set_tag(full_tag, value)
                created += 1
            
            manager.save()
            
            return {
                'success': True,
                'namespace': namespace,
                'created': created,
                'tags': list(tags.keys())
            }
        
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to create custom namespace: {str(e)}")
    
    @staticmethod
    def conditional_filter(
        metadata: Dict[str, Any],
        condition: str,
        undef_tags: bool = False
    ) -> Dict[str, Any]:
        """
        Filter tags based on a conditional expression.
        
        Supports expressions like:
        - "EXIF:Make == 'Canon'"
        - "EXIF:ISO > 400"
        - "IPTC:Keywords contains 'nature'"
        
        Args:
            metadata: Metadata dictionary
            condition: Conditional expression string
            undef_tags: If True, undefined tags are treated as having a value (None/empty) 
                       without modifying them. If False (default), undefined tags cause 
                       condition to fail.
            
        Returns:
            Filtered metadata dictionary
        """
        # Simple conditional parser
        # This is a basic implementation - can be enhanced
        
        def get_tag_value(tag_name: str) -> Optional[Any]:
            """
            Get tag value, handling undefined tags based on undef_tags option.
            
            Returns:
                Tag value if exists, None if undefined and undef_tags is True,
                raises KeyError if undefined and undef_tags is False
            """
            if tag_name in metadata:
                return metadata[tag_name]
            elif undef_tags:
                # Undefined tag - treat as None/empty without modifying
                return None
            else:
                # Undefined tag - raise KeyError to indicate tag doesn't exist
                raise KeyError(f"Tag {tag_name} is undefined")
        
        try:
            # Parse condition
            if '==' in condition:
                parts = condition.split('==', 1)
                tag_name = parts[0].strip()
                expected_value = parts[1].strip().strip("'\"")
                
                try:
                    actual_value = get_tag_value(tag_name)
                    # Convert None to empty string for comparison
                    if actual_value is None:
                        actual_value = ''
                    actual_value = str(actual_value)
                    if actual_value == expected_value:
                        return metadata
                    else:
                        return {}
                except KeyError:
                    # Tag is undefined and undef_tags is False
                    return {}
            
            elif '!=' in condition:
                parts = condition.split('!=', 1)
                tag_name = parts[0].strip()
                expected_value = parts[1].strip().strip("'\"")
                
                try:
                    actual_value = get_tag_value(tag_name)
                    # Convert None to empty string for comparison
                    if actual_value is None:
                        actual_value = ''
                    actual_value = str(actual_value)
                    if actual_value != expected_value:
                        return metadata
                    else:
                        return {}
                except KeyError:
                    # Tag is undefined and undef_tags is False
                    return {}
            
            elif '>' in condition:
                parts = condition.split('>', 1)
                tag_name = parts[0].strip()
                threshold = float(parts[1].strip())
                
                try:
                    actual_value = get_tag_value(tag_name)
                    if actual_value is None:
                        # Undefined tag treated as 0 for comparison
                        actual_value = 0.0
                    try:
                        actual_value = float(actual_value)
                        if actual_value > threshold:
                            return metadata
                    except (ValueError, TypeError):
                        pass
                    return {}
                except KeyError:
                    # Tag is undefined and undef_tags is False
                    return {}
            
            elif '<' in condition:
                parts = condition.split('<', 1)
                tag_name = parts[0].strip()
                threshold = float(parts[1].strip())
                
                try:
                    actual_value = get_tag_value(tag_name)
                    if actual_value is None:
                        # Undefined tag treated as 0 for comparison
                        actual_value = 0.0
                    try:
                        actual_value = float(actual_value)
                        if actual_value < threshold:
                            return metadata
                    except (ValueError, TypeError):
                        pass
                    return {}
                except KeyError:
                    # Tag is undefined and undef_tags is False
                    return {}
            
            elif 'contains' in condition.lower():
                parts = condition.split('contains', 1)
                tag_name = parts[0].strip()
                search_value = parts[1].strip().strip("'\"")
                
                try:
                    actual_value = get_tag_value(tag_name)
                    # Convert None to empty string for comparison
                    if actual_value is None:
                        actual_value = ''
                    actual_value = str(actual_value)
                    if search_value.lower() in actual_value.lower():
                        return metadata
                    else:
                        return {}
                except KeyError:
                    # Tag is undefined and undef_tags is False
                    return {}
            
            # If condition doesn't match, return empty
            return {}
        
        except Exception:
            return {}
    
    @staticmethod
    def evaluate_condition(
        metadata: Dict[str, Any],
        condition: str,
        undef_tags: bool = False
    ) -> bool:
        """
        Evaluate a conditional expression on metadata.
        
        Args:
            metadata: Metadata dictionary
            condition: Conditional expression string
            undef_tags: If True, undefined tags are treated as having a value (None/empty) 
                       without modifying them. If False (default), undefined tags cause 
                       condition to fail.
            
        Returns:
            True if condition is met, False otherwise
        """
        filtered = TagFilter.conditional_filter(metadata, condition, undef_tags=undef_tags)
        return len(filtered) > 0

