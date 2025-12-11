# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Advanced features for DNExif

This module provides advanced features like tag copying, batch operations,
and advanced metadata manipulation.

Copyright 2025 DNAi inc.
"""

from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime, timezone, timedelta
import re
from dnexif import DNExif
from dnexif.exceptions import MetadataReadError, MetadataWriteError


class AdvancedFeatures:
    """
    Advanced features for metadata manipulation.
    
    Provides features like tag copying, batch operations,
    and advanced filtering.
    """
    
    @staticmethod
    def copy_tags(
        source_file: Union[str, Path],
        target_file: Union[str, Path],
        tag_filter: Optional[List[str]] = None,
        metadata_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Copy metadata tags from one file to another.
        
        Args:
            source_file: Source file path
            target_file: Target file path
            tag_filter: Optional list of tag names to copy (None = all)
            metadata_types: Optional list of metadata types ('EXIF', 'IPTC', 'XMP')
            
        Returns:
            Dictionary with copy statistics
        """
        try:
            source = DNExif(source_file)
            source_metadata = source.get_all_metadata()
            
            target = DNExif(target_file)
            
            copied = 0
            skipped = 0
            
            for tag_name, value in source_metadata.items():
                # Apply filters
                if tag_filter and tag_name not in tag_filter:
                    skipped += 1
                    continue
                
                if metadata_types:
                    tag_type = tag_name.split(':')[0] if ':' in tag_name else ''
                    if tag_type not in metadata_types:
                        skipped += 1
                        continue
                
                # Copy tag
                try:
                    target.set_tag(tag_name, value)
                    copied += 1
                except Exception:
                    skipped += 1
            
            # Save target file
            target.save()
            
            return {
                'copied': copied,
                'skipped': skipped,
                'total': len(source_metadata)
            }
        except Exception as e:
            raise MetadataWriteError(f"Failed to copy tags: {str(e)}")
    
    @staticmethod
    def batch_process(
        file_paths: List[Union[str, Path]],
        operation: callable,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process multiple files in batch.
        
        Args:
            file_paths: List of file paths to process
            operation: Function to apply to each file
            **kwargs: Additional arguments for operation
            
        Returns:
            Dictionary with batch processing statistics
        """
        results = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for file_path in file_paths:
            try:
                operation(file_path, **kwargs)
                results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'file': str(file_path),
                    'error': str(e)
                })
            finally:
                results['processed'] += 1
        
        return results
    
    @staticmethod
    def filter_tags(
        metadata: Dict[str, Any],
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Filter metadata tags based on patterns.
        
        Args:
            metadata: Metadata dictionary
            include_patterns: List of patterns to include (e.g., ['EXIF:*', 'IPTC:*'])
            exclude_patterns: List of patterns to exclude
            
        Returns:
            Filtered metadata dictionary
        """
        filtered = {}
        
        for tag_name, value in metadata.items():
            # Check include patterns
            if include_patterns:
                included = False
                for pattern in include_patterns:
                    if pattern.endswith('*'):
                        prefix = pattern[:-1]
                        if tag_name.startswith(prefix):
                            included = True
                            break
                    elif pattern == tag_name:
                        included = True
                        break
                if not included:
                    continue
            
            # Check exclude patterns
            if exclude_patterns:
                excluded = False
                for pattern in exclude_patterns:
                    if pattern.endswith('*'):
                        prefix = pattern[:-1]
                        if tag_name.startswith(prefix):
                            excluded = True
                            break
                    elif pattern == tag_name:
                        excluded = True
                        break
                if excluded:
                    continue
            
            filtered[tag_name] = value
        
        return filtered
    
    @staticmethod
    def get_tag_statistics(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics about metadata tags.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_tags': len(metadata),
            'by_type': {
                'EXIF': 0,
                'IPTC': 0,
                'XMP': 0,
                'GPS': 0,
                'MakerNote': 0,
                'Other': 0,
            },
            'tag_names': list(metadata.keys()),
        }
        
        for tag_name in metadata.keys():
            if tag_name.startswith('EXIF:'):
                stats['by_type']['EXIF'] += 1
            elif tag_name.startswith('IPTC:'):
                stats['by_type']['IPTC'] += 1
            elif tag_name.startswith('XMP:'):
                stats['by_type']['XMP'] += 1
            elif tag_name.startswith('GPS:'):
                stats['by_type']['GPS'] += 1
            elif 'MakerNote' in tag_name:
                stats['by_type']['MakerNote'] += 1
            else:
                stats['by_type']['Other'] += 1
        
        return stats
    
    @staticmethod
    def manipulate_datetime(
        file_path: Union[str, Path],
        operation: str,
        value: Union[int, timedelta],
        tag_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Manipulate date/time tags in a file.
        
        Args:
            file_path: Path to file
            operation: Operation to perform ('add', 'subtract', 'set')
            value: Value to add/subtract (timedelta) or set (datetime)
            tag_names: Optional list of tag names to modify (None = all datetime tags)
            
        Returns:
            Dictionary with operation results
        """
        if tag_names is None:
            # Default datetime tags
            tag_names = [
                'EXIF:DateTimeOriginal',
                'EXIF:DateTimeDigitized',
                'EXIF:DateTime',
                'IFD0:DateTime',
            ]
        
        try:
            manager = DNExif(file_path)
            metadata = manager.get_all_metadata()
            
            modified = 0
            errors = []
            
            for tag_name in tag_names:
                if tag_name not in metadata:
                    continue
                
                try:
                    current_value = metadata[tag_name]
                    if not isinstance(current_value, str):
                        continue
                    
                    # Parse datetime
                    dt = datetime.strptime(current_value, '%Y:%m:%d %H:%M:%S')
                    
                    if operation == 'add':
                        if isinstance(value, timedelta):
                            new_dt = dt + value
                        else:
                            new_dt = dt + timedelta(seconds=value)
                    elif operation == 'subtract':
                        if isinstance(value, timedelta):
                            new_dt = dt - value
                        else:
                            new_dt = dt - timedelta(seconds=value)
                    elif operation == 'set':
                        if isinstance(value, datetime):
                            new_dt = value
                        else:
                            raise ValueError("Set operation requires datetime object")
                    else:
                        raise ValueError(f"Unknown operation: {operation}")
                    
                    # Format back to EXIF format
                    new_value = new_dt.strftime('%Y:%m:%d %H:%M:%S')
                    manager.set_tag(tag_name, new_value)
                    modified += 1
                except Exception as e:
                    errors.append({'tag': tag_name, 'error': str(e)})
            
            if modified > 0:
                manager.save()
            
            return {
                'modified': modified,
                'errors': errors
            }
        except Exception as e:
            raise MetadataWriteError(f"Failed to manipulate datetime: {str(e)}")
    
    @staticmethod
    def apply_timezone(
        file_path: Union[str, Path],
        timezone_offset: Union[int, timedelta],
        tag_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Apply timezone offset to datetime tags.
        
        Args:
            file_path: Path to file
            timezone_offset: Timezone offset in hours (int) or timedelta
            tag_names: Optional list of tag names to modify
            
        Returns:
            Dictionary with operation results
        """
        if isinstance(timezone_offset, int):
            offset = timedelta(hours=timezone_offset)
        else:
            offset = timezone_offset
        
        return AdvancedFeatures.manipulate_datetime(
            file_path,
            'add',
            offset,
            tag_names
        )
    
    @staticmethod
    def geotag(
        file_path: Union[str, Path],
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Add GPS coordinates to a file.
        
        Args:
            file_path: Path to file
            latitude: Latitude in degrees (-90 to 90)
            longitude: Longitude in degrees (-180 to 180)
            altitude: Optional altitude in meters
            
        Returns:
            Dictionary with operation results
        """
        if not (-90 <= latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        
        try:
            manager = DNExif(file_path)
            
            # Convert to EXIF GPS format (degrees, minutes, seconds)
            lat_ref = 'N' if latitude >= 0 else 'S'
            lon_ref = 'E' if longitude >= 0 else 'W'
            
            lat_abs = abs(latitude)
            lat_deg = int(lat_abs)
            lat_min = int((lat_abs - lat_deg) * 60)
            lat_sec = ((lat_abs - lat_deg) * 60 - lat_min) * 60
            
            lon_abs = abs(longitude)
            lon_deg = int(lon_abs)
            lon_min = int((lon_abs - lon_deg) * 60)
            lon_sec = ((lon_abs - lon_deg) * 60 - lon_min) * 60
            
            # Set GPS tags
            manager.set_tag('GPS:GPSLatitudeRef', lat_ref)
            manager.set_tag('GPS:GPSLatitude', f"{lat_deg}/1 {lat_min}/1 {lat_sec}/100")
            manager.set_tag('GPS:GPSLongitudeRef', lon_ref)
            manager.set_tag('GPS:GPSLongitude', f"{lon_deg}/1 {lon_min}/1 {lon_sec}/100")
            
            if altitude is not None:
                manager.set_tag('GPS:GPSAltitudeRef', '0' if altitude >= 0 else '1')
                manager.set_tag('GPS:GPSAltitude', f"{abs(altitude)}/1")
            
            manager.save()
            
            return {
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'success': True
            }
        except Exception as e:
            raise MetadataWriteError(f"Failed to geotag: {str(e)}")
    
    @staticmethod
    def format_output(
        metadata: Dict[str, Any],
        format_type: str = 'dict',
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> Union[Dict[str, Any], str, List[str]]:
        """
        Format metadata output in different formats.
        
        Args:
            metadata: Metadata dictionary
            format_type: Output format ('dict', 'json', 'list', 'table')
            include_types: Optional list of metadata types to include
            exclude_types: Optional list of metadata types to exclude
            
        Returns:
            Formatted output
        """
        # Filter by type if needed
        filtered = metadata.copy()
        if include_types:
            filtered = {k: v for k, v in filtered.items() 
                       if any(k.startswith(t + ':') for t in include_types)}
        if exclude_types:
            filtered = {k: v for k, v in filtered.items() 
                       if not any(k.startswith(t + ':') for t in exclude_types)}
        
        if format_type == 'dict':
            return filtered
        elif format_type == 'json':
            import json
            return json.dumps(filtered, indent=2, default=str)
        elif format_type == 'list':
            return [f"{k}: {v}" for k, v in filtered.items()]
        elif format_type == 'table':
            lines = []
            lines.append(f"{'Tag':<40} {'Value':<40}")
            lines.append("-" * 80)
            for k, v in sorted(filtered.items()):
                value_str = str(v)[:38] if len(str(v)) > 38 else str(v)
                lines.append(f"{k:<40} {value_str:<40}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Unknown format type: {format_type}")
    
    @staticmethod
    def convert_format(
        source_file: Union[str, Path],
        target_format: str,
        output_path: Optional[Union[str, Path]] = None
    ) -> Path:
        """
        Convert file format with metadata preservation.
        
        This method extracts metadata from the source file and can preserve it
        during format conversion. Full image conversion requires external libraries
        like PIL/Pillow, but metadata extraction and preservation is implemented.
        
        Args:
            source_file: Source file path
            target_format: Target format ('JPEG', 'TIFF', 'PNG')
            output_path: Optional output path
            
        Returns:
            Path to converted file
            
        Raises:
            NotImplementedError: If image conversion libraries are not available
        """
        source_path = Path(source_file)
        
        # Extract metadata from source
        try:
            manager = DNExif(source_file)
            metadata = manager.get_all_metadata()
        except Exception as e:
            raise MetadataWriteError(f"Failed to extract metadata: {str(e)}")
        
        # Determine output path
        if output_path is None:
            output_path = source_path.parent / f"{source_path.stem}.{target_format.lower()}"
        else:
            output_path = Path(output_path)
        
        # Check if PIL/Pillow is available for image conversion
        try:
            from PIL import Image
            PIL_AVAILABLE = True
        except ImportError:
            PIL_AVAILABLE = False
        
        if not PIL_AVAILABLE:
            raise NotImplementedError(
                "Format conversion requires PIL/Pillow library. "
                "Install it with: pip install Pillow\n"
                "Metadata extraction is complete and ready to be preserved."
            )
        
        # Perform image conversion with PIL
        try:
            img = Image.open(source_path)
            
            # Convert based on target format
            if target_format.upper() == 'JPEG':
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Convert to RGB for JPEG
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = rgb_img
                img.save(output_path, 'JPEG', quality=95)
            elif target_format.upper() == 'TIFF':
                img.save(output_path, 'TIFF')
            elif target_format.upper() == 'PNG':
                img.save(output_path, 'PNG')
            else:
                raise ValueError(f"Unsupported target format: {target_format}")
            
            # Write metadata to converted file
            try:
                converted_manager = DNExif(output_path)
                for tag_name, value in metadata.items():
                    try:
                        converted_manager.set_tag(tag_name, value)
                    except Exception:
                        pass  # Skip tags that can't be written
                converted_manager.save()
            except Exception:
                # Metadata writing may fail for some formats
                pass
            
            return output_path
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to convert format: {str(e)}")

