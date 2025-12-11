# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
TNEF (Transport Neutral Encapsulation Format) file metadata parser

This module handles reading metadata from TNEF files.
TNEF files are used by Microsoft Outlook for email attachments (often "winmail.dat").

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class TNEFParser:
    """
    Parser for TNEF (Transport Neutral Encapsulation Format) metadata.
    
    TNEF files contain embedded attachments and metadata from Microsoft Outlook emails.
    Structure:
    - TNEF signature (0x223E9F78)
    - LVL (Level) messages
    - Attachments (ATTACHMENT objects)
    - MAPI properties
    """
    
    # TNEF signature
    TNEF_SIGNATURE = 0x223E9F78
    
    # TNEF message types
    MESSAGE_TYPES = {
        0x00000001: 'LVL',
        0x00000002: 'Attachment',
        0x00000003: 'Recipient',
        0x00000004: 'MAPI',
    }
    
    # TNEF attribute types
    ATTRIBUTE_TYPES = {
        0x00000001: 'Owner',
        0x00000002: 'SentFor',
        0x00000003: 'Delegate',
        0x00000004: 'DateStart',
        0x00000005: 'DateEnd',
        0x00000006: 'AidOwner',
        0x00000007: 'RequestRes',
        0x00000008: 'From',
        0x00000009: 'Subject',
        0x0000000A: 'DateSent',
        0x0000000B: 'DateReceived',
        0x0000000C: 'MessageStatus',
        0x0000000D: 'MessageClass',
        0x0000000E: 'MessageID',
        0x0000000F: 'ParentID',
        0x00000010: 'ConversationID',
        0x00000011: 'Body',
        0x00000012: 'Priority',
        0x00000013: 'AttachData',
        0x00000014: 'AttachTitle',
        0x00000015: 'AttachMetaFile',
        0x00000016: 'AttachCreateDate',
        0x00000017: 'AttachModifyDate',
        0x00000018: 'DateModified',
        0x00000019: 'AttachTransportFilename',
        0x0000001A: 'AttachRenddata',
        0x0000001B: 'MAPIProps',
        0x0000001C: 'RecipTable',
        0x0000001D: 'Attachment',
        0x0000001E: 'TnefVersion',
        0x0000001F: 'OemCodepage',
        0x00000020: 'OriginalMessageClass',
    }
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize TNEF parser.
        
        Args:
            file_path: Path to TNEF file
            file_data: TNEF file data bytes
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
        Parse TNEF metadata.
        
        Returns:
            Dictionary of TNEF metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid TNEF file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'TNEF'
            metadata['File:FileTypeExtension'] = 'tnef'
            metadata['File:MIMEType'] = 'application/vnd.ms-tnef'
            
            # Check TNEF signature
            if len(file_data) < 4:
                raise MetadataReadError("Invalid TNEF file: missing signature")
            
            signature = struct.unpack('<I', file_data[0:4])[0]
            if signature != self.TNEF_SIGNATURE:
                raise MetadataReadError("Invalid TNEF file: missing TNEF signature")
            
            metadata['TNEF:Signature'] = hex(signature)
            metadata['TNEF:HasTNEFSignature'] = True
            
            # Parse TNEF messages
            tnef_metadata = self._parse_tnef_messages(file_data)
            if tnef_metadata:
                metadata.update(tnef_metadata)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse TNEF metadata: {str(e)}")
    
    def _parse_tnef_messages(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse TNEF messages and attributes.
        
        Args:
            file_data: TNEF file data bytes
            
        Returns:
            Dictionary of parsed TNEF metadata
        """
        metadata = {}
        
        try:
            offset = 4  # Skip signature
            
            attachment_count = 0
            attributes = []
            
            while offset < len(file_data) - 8:
                # Read message header (8 bytes):
                # - Type (4 bytes, little-endian)
                # - Length (4 bytes, little-endian)
                
                if offset + 8 > len(file_data):
                    break
                
                msg_type = struct.unpack('<I', file_data[offset:offset+4])[0]
                msg_length = struct.unpack('<I', file_data[offset+4:offset+8])[0]
                
                offset += 8
                
                # Validate message length
                if msg_length < 0 or offset + msg_length > len(file_data):
                    break
                
                # Parse message based on type
                if msg_type == 0x00000001:  # LVL
                    # Level message - contains attributes
                    attr_metadata = self._parse_attributes(file_data[offset:offset+msg_length])
                    if attr_metadata:
                        attributes.extend(attr_metadata)
                
                elif msg_type == 0x00000002:  # Attachment
                    attachment_count += 1
                    metadata[f'TNEF:Attachment{attachment_count}:Present'] = True
                    # Parse attachment attributes
                    attr_metadata = self._parse_attributes(file_data[offset:offset+msg_length])
                    if attr_metadata:
                        for attr in attr_metadata:
                            # Rename attributes with attachment prefix
                            for key, value in attr.items():
                                metadata[f'TNEF:Attachment{attachment_count}:{key}'] = value
                
                offset += msg_length
            
            # Store attributes
            if attributes:
                metadata['TNEF:AttributeCount'] = len(attributes)
                for i, attr in enumerate(attributes[:50], 1):  # Limit to 50 attributes
                    for key, value in attr.items():
                        metadata[f'TNEF:Attribute{i}:{key}'] = value
            
            if attachment_count > 0:
                metadata['TNEF:AttachmentCount'] = attachment_count
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_attributes(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Parse TNEF attributes from data.
        
        Args:
            data: Attribute data bytes
            
        Returns:
            List of attribute dictionaries
        """
        attributes = []
        
        try:
            offset = 0
            
            while offset < len(data) - 8:
                # Read attribute header (8 bytes):
                # - Type (4 bytes, little-endian)
                # - Length (4 bytes, little-endian)
                
                if offset + 8 > len(data):
                    break
                
                attr_type = struct.unpack('<I', data[offset:offset+4])[0]
                attr_length = struct.unpack('<I', data[offset+4:offset+8])[0]
                
                offset += 8
                
                # Validate attribute length
                if attr_length < 0 or offset + attr_length > len(data):
                    break
                
                attr_data = data[offset:offset+attr_length]
                
                # Get attribute name
                attr_name = self.ATTRIBUTE_TYPES.get(attr_type, f'Attribute{attr_type}')
                
                # Parse attribute value based on type
                attr_value = self._parse_attribute_value(attr_type, attr_data)
                
                attributes.append({
                    'Type': attr_name,
                    'TypeCode': attr_type,
                    'Value': attr_value,
                    'Length': attr_length,
                })
                
                offset += attr_length
        
        except Exception:
            pass
        
        return attributes
    
    def _parse_attribute_value(self, attr_type: int, attr_data: bytes) -> Any:
        """
        Parse attribute value based on attribute type.
        
        Args:
            attr_type: Attribute type code
            attr_data: Attribute data bytes
            
        Returns:
            Parsed attribute value
        """
        try:
            # String attributes (Subject, Body, From, etc.)
            if attr_type in (0x00000008, 0x00000009, 0x0000000D, 0x0000000E, 0x0000000F, 
                            0x00000010, 0x00000011, 0x00000014, 0x00000019, 0x00000020):
                # Try to decode as UTF-16-LE (common for TNEF strings)
                try:
                    return attr_data.decode('utf-16-le', errors='ignore').strip('\x00')
                except Exception:
                    # Fallback to UTF-8 or Latin-1
                    try:
                        return attr_data.decode('utf-8', errors='ignore').strip('\x00')
                    except Exception:
                        return attr_data.decode('latin-1', errors='ignore').strip('\x00')
            
            # Date attributes (DateStart, DateEnd, DateSent, DateReceived, etc.)
            elif attr_type in (0x00000004, 0x00000005, 0x0000000A, 0x0000000B, 0x00000016, 
                              0x00000017, 0x00000018):
                # TNEF dates are typically FILETIME (64-bit Windows timestamp)
                if len(attr_data) >= 8:
                    filetime = struct.unpack('<Q', attr_data[:8])[0]
                    # Convert FILETIME to readable date (FILETIME is 100-nanosecond intervals since 1601-01-01)
                    # This is a simplified conversion
                    return f'FILETIME:{filetime}'
                return attr_data.hex()
            
            # Integer attributes (Priority, MessageStatus, etc.)
            elif attr_type in (0x00000012, 0x0000000C):
                if len(attr_data) >= 4:
                    return struct.unpack('<I', attr_data[:4])[0]
                elif len(attr_data) >= 2:
                    return struct.unpack('<H', attr_data[:2])[0]
                elif len(attr_data) >= 1:
                    return attr_data[0]
            
            # Version attributes (TnefVersion)
            elif attr_type == 0x0000001E:
                if len(attr_data) >= 4:
                    version = struct.unpack('<I', attr_data[:4])[0]
                    return f'{version >> 16}.{version & 0xFFFF}'
            
            # Binary data attributes (AttachData, AttachMetaFile, etc.)
            else:
                # Return as hex string for binary data
                if len(attr_data) <= 100:
                    return attr_data.hex()
                else:
                    return attr_data[:100].hex() + '...'
        
        except Exception:
            return attr_data.hex() if len(attr_data) <= 100 else attr_data[:100].hex() + '...'

