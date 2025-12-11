# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Tag operations and redirection

Provides tag redirection, copying, and transformation capabilities
compatible with standard tag redirection syntax.

Copyright 2025 DNAi inc.
"""

from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from dnexif.core import DNExif
from dnexif.exceptions import MetadataWriteError


class TagOperations:
    """
    Advanced tag operations including redirection and copying.
    
    Supports standard syntax:
    - -TAG1<-TAG2 (copy value from TAG2 to TAG1)
    - -TAG1<+TAG2 (copy value if TAG1 doesn't exist)
    - -TAG1<-TAG2@ (copy value and delete TAG2)
    """
    
    @staticmethod
    def redirect_tag(
        file_path: str,
        target_tag: str,
        source_tag: str,
        delete_source: bool = False,
        only_if_missing: bool = False
    ) -> Dict[str, Any]:
        """
        Redirect (copy) a tag value from source to target.
        
        Args:
            file_path: Path to file
            target_tag: Target tag name (where to copy to)
            source_tag: Source tag name (where to copy from)
            delete_source: Whether to delete source tag after copying
            only_if_missing: Only copy if target tag doesn't exist
            
        Returns:
            Dictionary with operation results
        """
        try:
            manager = DNExif(file_path, read_only=False)
            metadata = manager.get_all_metadata()
            
            # Check if source tag exists
            if source_tag not in metadata:
                return {
                    'success': False,
                    'error': f'Source tag {source_tag} not found',
                    'copied': False
                }
            
            # Check if target already exists
            if only_if_missing and target_tag in metadata:
                return {
                    'success': True,
                    'copied': False,
                    'reason': 'Target tag already exists'
                }
            
            # Get source value
            source_value = metadata[source_tag]
            
            # Copy to target
            manager.set_tag(target_tag, source_value)
            
            # Delete source if requested
            if delete_source:
                manager.delete_tag(source_tag)
            
            # Save changes
            manager.save()
            
            return {
                'success': True,
                'copied': True,
                'target_tag': target_tag,
                'source_tag': source_tag,
                'value': source_value,
                'source_deleted': delete_source
            }
        
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to redirect tag: {str(e)}")
    
    @staticmethod
    def redirect_tags(
        file_path: str,
        redirections: List[tuple],
        delete_source: bool = False,
        only_if_missing: bool = False
    ) -> Dict[str, Any]:
        """
        Redirect multiple tags at once.
        
        Args:
            file_path: Path to file
            redirections: List of (target_tag, source_tag) tuples
            delete_source: Whether to delete source tags after copying
            only_if_missing: Only copy if target tag doesn't exist
            
        Returns:
            Dictionary with operation results
        """
        results = {
            'total': len(redirections),
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for target_tag, source_tag in redirections:
            try:
                result = TagOperations.redirect_tag(
                    file_path,
                    target_tag,
                    source_tag,
                    delete_source=delete_source,
                    only_if_missing=only_if_missing
                )
                
                if result['success']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                
                results['details'].append({
                    'target': target_tag,
                    'source': source_tag,
                    'result': result
                })
            
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'target': target_tag,
                    'source': source_tag,
                    'error': str(e)
                })
        
        return results
    
    @staticmethod
    def parse_redirection_syntax(redirection_str: str) -> tuple:
        """
        Parse standard format redirection syntax.
        
        Supports:
        - -TAG1<-TAG2 (copy TAG2 to TAG1)
        - -TAG1<+TAG2 (copy TAG2 to TAG1 only if TAG1 doesn't exist)
        - -TAG1<-TAG2@ (copy TAG2 to TAG1 and delete TAG2)
        
        Args:
            redirection_str: Redirection string (e.g., "-EXIF:Artist<-IPTC:By-line")
            
        Returns:
            Tuple of (target_tag, source_tag, delete_source, only_if_missing)
        """
        # Remove leading dash if present
        redirection_str = redirection_str.lstrip('-')
        
        # Check for @ (delete source)
        delete_source = '@' in redirection_str
        if delete_source:
            redirection_str = redirection_str.replace('@', '')
        
        # Check for <+ (only if missing)
        only_if_missing = '<+' in redirection_str
        if only_if_missing:
            parts = redirection_str.split('<+', 1)
        elif '<-' in redirection_str:
            parts = redirection_str.split('<-', 1)
        else:
            raise ValueError(f"Invalid redirection syntax: {redirection_str}")
        
        if len(parts) != 2:
            raise ValueError(f"Invalid redirection syntax: {redirection_str}")
        
        target_tag = parts[0].strip()
        source_tag = parts[1].strip()
        
        return (target_tag, source_tag, delete_source, only_if_missing)
    
    @staticmethod
    def transform_tag(
        file_path: str,
        tag_name: str,
        transform_func: Callable[[Any], Any]
    ) -> Dict[str, Any]:
        """
        Transform a tag value using a transformation function.
        
        Args:
            file_path: Path to file
            tag_name: Tag name to transform
            transform_func: Function to transform the value
            
        Returns:
            Dictionary with operation results
        """
        try:
            manager = DNExif(file_path, read_only=False)
            metadata = manager.get_all_metadata()
            
            if tag_name not in metadata:
                return {
                    'success': False,
                    'error': f'Tag {tag_name} not found'
                }
            
            # Get current value
            current_value = metadata[tag_name]
            
            # Transform value
            new_value = transform_func(current_value)
            
            # Set new value
            manager.set_tag(tag_name, new_value)
            manager.save()
            
            return {
                'success': True,
                'tag': tag_name,
                'old_value': current_value,
                'new_value': new_value
            }
        
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to transform tag: {str(e)}")
    
    @staticmethod
    def copy_tag_between_namespaces(
        file_path: str,
        target_tag: str,
        source_tag: str,
        namespace_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Copy a tag value between different namespaces.
        
        Args:
            file_path: Path to file
            target_tag: Target tag name (with namespace)
            source_tag: Source tag name (with namespace)
            namespace_mapping: Optional mapping for namespace conversion
            
        Returns:
            Dictionary with operation results
        """
        return TagOperations.redirect_tag(file_path, target_tag, source_tag)
    
    @staticmethod
    def delete_tags_by_group(
        file_path: str,
        group: str
    ) -> Dict[str, Any]:
        """
        Delete all tags from a specific group.
        
        Args:
            file_path: Path to file
            group: Group name (e.g., 'EXIF', 'IPTC', 'XMP')
            
        Returns:
            Dictionary with operation results
        """
        try:
            manager = DNExif(file_path, read_only=False)
            metadata = manager.get_all_metadata()
            
            # Find all tags in the group
            group_tags = [
                tag for tag in metadata.keys()
                if tag.startswith(f'{group}:')
            ]
            
            if not group_tags:
                return {
                    'success': True,
                    'deleted': 0,
                    'message': f'No tags found in group {group}'
                }
            
            # Delete all tags in the group
            deleted_count = 0
            for tag in group_tags:
                try:
                    manager.delete_tag(tag)
                    deleted_count += 1
                except Exception:
                    pass
            
            # Save changes
            manager.save()
            
            return {
                'success': True,
                'deleted': deleted_count,
                'group': group,
                'tags': group_tags
            }
        
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to delete tags by group: {str(e)}")

