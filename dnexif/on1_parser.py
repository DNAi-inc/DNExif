# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
ON1 preset file (.ONP) metadata parser

This module handles reading metadata from ON1 preset files.
ON1 preset files are ZIP archives containing preset configuration data.

Copyright 2025 DNAi inc.
"""

import zipfile
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class ON1Parser:
    """
    Parser for ON1 preset file metadata.
    
    ON1 preset files are ZIP archives containing:
    - Preset configuration files (XML/JSON)
    - Thumbnail images
    - Metadata files
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize ON1 preset parser.
        
        Args:
            file_path: Path to ON1 preset file
            file_data: ON1 preset file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse ON1 preset metadata.
        
        Returns:
            Dictionary of ON1 preset metadata
        """
        try:
            metadata = {}
            metadata['File:FileType'] = 'ON1'
            metadata['File:FileTypeExtension'] = 'onp'
            metadata['File:MIMEType'] = 'application/x-on1-preset'
            
            # Read file data if needed
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 4:
                raise MetadataReadError("Invalid ON1 preset file: too short")
            
            # Check ZIP signature (ON1 presets are ZIP archives)
            if not file_data.startswith(b'PK\x03\x04') and not file_data.startswith(b'PK\x05\x06'):
                raise MetadataReadError("Invalid ON1 preset file: not a valid ZIP archive")
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            else:
                metadata['File:FileSize'] = len(file_data)
                metadata['File:FileSizeBytes'] = len(file_data)
            
            # Parse ZIP archive
            try:
                if self.file_path:
                    zip_file = zipfile.ZipFile(self.file_path, 'r')
                else:
                    import io
                    zip_file = zipfile.ZipFile(io.BytesIO(file_data), 'r')
                
                file_list = zip_file.namelist()
                metadata['ON1:FileCount'] = len(file_list)
                
                # Look for common ON1 preset files
                preset_files = [f for f in file_list if f.endswith('.preset') or f.endswith('.xml') or f.endswith('.json')]
                if preset_files:
                    metadata['ON1:PresetFileCount'] = len(preset_files)
                    for i, preset_file in enumerate(preset_files[:10], 1):  # Limit to 10 preset files
                        metadata[f'ON1:PresetFile{i}'] = preset_file
                
                # Look for thumbnail images
                thumbnail_files = [f for f in file_list if 'thumb' in f.lower() or f.endswith(('.jpg', '.jpeg', '.png'))]
                if thumbnail_files:
                    metadata['ON1:ThumbnailCount'] = len(thumbnail_files)
                    for i, thumb_file in enumerate(thumbnail_files[:5], 1):  # Limit to 5 thumbnails
                        metadata[f'ON1:Thumbnail{i}'] = thumb_file
                
                # Try to parse preset configuration files
                for preset_file in preset_files[:3]:  # Try first 3 preset files
                    try:
                        preset_data = zip_file.read(preset_file)
                        
                        # Try to parse as JSON
                        if preset_file.endswith('.json'):
                            try:
                                preset_json = json.loads(preset_data.decode('utf-8'))
                                if isinstance(preset_json, dict):
                                    # Extract common fields
                                    if 'name' in preset_json:
                                        metadata['ON1:PresetName'] = preset_json['name']
                                    if 'version' in preset_json:
                                        metadata['ON1:PresetVersion'] = preset_json['version']
                                    if 'description' in preset_json:
                                        metadata['ON1:PresetDescription'] = preset_json['description']
                                    if 'category' in preset_json:
                                        metadata['ON1:PresetCategory'] = preset_json['category']
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                pass
                        
                        # Try to parse as XML
                        elif preset_file.endswith('.xml') or preset_file.endswith('.preset'):
                            try:
                                root = ET.fromstring(preset_data)
                                # Look for common XML elements
                                for elem in root.iter():
                                    tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                                    if tag_name.lower() in ('name', 'title'):
                                        if elem.text:
                                            metadata['ON1:PresetName'] = elem.text
                                    elif tag_name.lower() in ('version', 'ver'):
                                        if elem.text:
                                            metadata['ON1:PresetVersion'] = elem.text
                                    elif tag_name.lower() in ('description', 'desc'):
                                        if elem.text:
                                            metadata['ON1:PresetDescription'] = elem.text
                                    elif tag_name.lower() in ('category', 'cat'):
                                        if elem.text:
                                            metadata['ON1:PresetCategory'] = elem.text
                            except ET.ParseError:
                                pass
                    except Exception:
                        pass
                
                zip_file.close()
                
            except zipfile.BadZipFile:
                raise MetadataReadError("Invalid ON1 preset file: not a valid ZIP archive")
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse ON1 preset metadata: {str(e)}")

