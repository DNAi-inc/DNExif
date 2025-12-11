# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
LNK file parser for Windows shortcut files.

LNK files are Windows Shell Link binary format files (.lnk extension).
They contain metadata about shortcuts including target paths, working directories,
environment variables, drive serial numbers, and other Windows-specific information.
"""

import struct
from pathlib import Path
from typing import Dict, Any, Optional

from dnexif.exceptions import MetadataReadError


class LNKParser:
    """
    Parser for Windows LNK (Shell Link) files.
    
    LNK files are binary format files containing Windows shortcut metadata.
    They have a complex structure with multiple optional sections.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize LNK parser.
        
        Args:
            file_path: Path to LNK file
            file_data: LNK file data bytes
        """
        self.file_path = file_path
        self.file_data = file_data
        
        if not self.file_path and not self.file_data:
            raise ValueError("Either file_path or file_data must be provided")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse LNK file metadata.
        
        Returns:
            Dictionary of LNK metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 76:
                raise MetadataReadError("Invalid LNK file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'LNK'
            metadata['File:FileTypeExtension'] = 'lnk'
            metadata['File:MIMEType'] = 'application/x-ms-shortcut'
            metadata['LNK:Format'] = 'Windows Shell Link'
            
            # Parse LNK header (Shell Link Header Structure)
            # Header is 76 bytes
            header = file_data[:76]
            
            # Check for LNK signature (Shell Link Header)
            # LNK files start with 0x4C (L) 0x00 0x00 0x00 (or similar patterns)
            # Actually, LNK files have a ShellLinkHeader structure
            
            # Parse ShellLinkHeader structure
            # First 4 bytes: HeaderSize (should be 0x0000004C = 76)
            header_size = struct.unpack('<I', header[0:4])[0]
            if header_size != 0x4C:
                # Try big-endian
                header_size = struct.unpack('>I', header[0:4])[0]
                if header_size != 0x4C:
                    raise MetadataReadError(f"Invalid LNK file: invalid header size {header_size}")
            
            metadata['LNK:HeaderSize'] = header_size
            
            # CLSID (16 bytes at offset 4)
            clsid = header[4:20]
            metadata['LNK:CLSID'] = self._format_clsid(clsid)
            
            # LinkFlags (4 bytes at offset 20)
            link_flags = struct.unpack('<I', header[20:24])[0]
            metadata['LNK:LinkFlags'] = link_flags
            metadata['LNK:HasLinkTargetIDList'] = bool(link_flags & 0x01)
            metadata['LNK:HasLinkInfo'] = bool(link_flags & 0x02)
            metadata['LNK:HasName'] = bool(link_flags & 0x04)
            metadata['LNK:HasRelativePath'] = bool(link_flags & 0x08)
            metadata['LNK:HasWorkingDir'] = bool(link_flags & 0x10)
            metadata['LNK:HasArguments'] = bool(link_flags & 0x20)
            metadata['LNK:HasIconLocation'] = bool(link_flags & 0x40)
            metadata['LNK:IsUnicode'] = bool(link_flags & 0x80)
            metadata['LNK:ForceNoLinkInfo'] = bool(link_flags & 0x100)
            metadata['LNK:HasExpString'] = bool(link_flags & 0x200)
            metadata['LNK:RunInSeparateProcess'] = bool(link_flags & 0x400)
            metadata['LNK:HasDarwinID'] = bool(link_flags & 0x1000)
            metadata['LNK:HasIcon'] = bool(link_flags & 0x2000)
            metadata['LNK:NoPidlAlias'] = bool(link_flags & 0x8000)
            metadata['LNK:RunWithShimLayer'] = bool(link_flags & 0x20000)
            metadata['LNK:ForceNoLinkTrack'] = bool(link_flags & 0x40000)
            metadata['LNK:EnableTargetMetadata'] = bool(link_flags & 0x80000)
            metadata['LNK:DisableLinkPathTracking'] = bool(link_flags & 0x100000)
            metadata['LNK:DisableKnownFolderRelativeTracking'] = bool(link_flags & 0x200000)
            metadata['LNK:NoKFAlias'] = bool(link_flags & 0x400000)
            metadata['LNK:AllowLinkToLink'] = bool(link_flags & 0x800000)
            metadata['LNK:UnaliasOnSave'] = bool(link_flags & 0x1000000)
            metadata['LNK:PreferEnvironmentPath'] = bool(link_flags & 0x2000000)
            metadata['LNK:KeepLocalIDListForUNCPath'] = bool(link_flags & 0x4000000)
            
            # FileAttributesFlags (4 bytes at offset 24)
            file_attributes = struct.unpack('<I', header[24:28])[0]
            metadata['LNK:FileAttributes'] = file_attributes
            
            # CreationTime, AccessTime, WriteTime (each 8 bytes, FILETIME format)
            creation_time = struct.unpack('<Q', header[28:36])[0]
            access_time = struct.unpack('<Q', header[36:44])[0]
            write_time = struct.unpack('<Q', header[44:52])[0]
            
            if creation_time > 0:
                metadata['LNK:CreationTime'] = self._filetime_to_datetime(creation_time)
            if access_time > 0:
                metadata['LNK:AccessTime'] = self._filetime_to_datetime(access_time)
            if write_time > 0:
                metadata['LNK:WriteTime'] = self._filetime_to_datetime(write_time)
            
            # FileSize (4 bytes at offset 52)
            file_size = struct.unpack('<I', header[52:56])[0]
            if file_size > 0:
                metadata['LNK:FileSize'] = file_size
            
            # IconIndex (4 bytes at offset 56)
            icon_index = struct.unpack('<i', header[56:60])[0]
            metadata['LNK:IconIndex'] = icon_index
            
            # ShowCommand (4 bytes at offset 60)
            show_command = struct.unpack('<I', header[60:64])[0]
            metadata['LNK:ShowCommand'] = show_command
            
            # HotKey (2 bytes at offset 64)
            hotkey = struct.unpack('<H', header[64:66])[0]
            if hotkey > 0:
                metadata['LNK:HotKey'] = hotkey
            
            # Reserved1, Reserved2 (each 2 bytes)
            # Reserved3 (4 bytes)
            
            # Parse LinkInfo structure (if present)
            offset = 76
            if metadata['LNK:HasLinkInfo'] and offset < len(file_data):
                link_info_data = self._parse_link_info(file_data, offset)
                if link_info_data:
                    metadata.update(link_info_data)
                    # Update offset based on LinkInfo size
                    if 'LNK:LinkInfoSize' in link_info_data:
                        offset += link_info_data['LNK:LinkInfoSize']
            
            # Search for EnvironmentTarget and DriveSerialNumber in file data
            # These may be in various locations depending on LNK file structure
            
            # Search for EnvironmentTarget patterns
            env_target_patterns = [
                b'EnvironmentTarget',
                b'ENVIRONMENTTARGET',
                b'environmenttarget',
                b'%',
                b'Environment',
                b'ENVIRONMENT',
                b'environment',
            ]
            
            for pattern in env_target_patterns:
                pattern_pos = file_data.find(pattern)
                if pattern_pos != -1:
                    # Try to extract environment target value
                    env_target = self._extract_environment_target(file_data, pattern_pos)
                    if env_target:
                        metadata['LNK:EnvironmentTarget'] = env_target
                        metadata['LNK:HasEnvironmentTarget'] = True
                        break
            
            # Search for DriveSerialNumber patterns
            # Drive serial numbers are typically 4-byte values or stored as strings
            drive_serial_patterns = [
                b'DriveSerialNumber',
                b'DRIVESERIALNUMBER',
                b'driveserialnumber',
                b'SerialNumber',
                b'SERIALNUMBER',
                b'serialnumber',
                b'VolumeSerialNumber',
                b'VOLUMESERIALNUMBER',
                b'volumeserialnumber',
            ]
            
            for pattern in drive_serial_patterns:
                pattern_pos = file_data.find(pattern)
                if pattern_pos != -1:
                    # Try to extract drive serial number
                    drive_serial = self._extract_drive_serial_number(file_data, pattern_pos)
                    if drive_serial:
                        metadata['LNK:DriveSerialNumber'] = drive_serial
                        metadata['LNK:HasDriveSerialNumber'] = True
                        break
            
            # Also try to extract drive serial number from LinkInfo structure
            # LinkInfo may contain volume information with serial number
            if metadata.get('LNK:HasLinkInfo'):
                # Look for volume serial number in LinkInfo data
                volume_serial = self._extract_volume_serial_from_linkinfo(file_data, offset)
                if volume_serial:
                    metadata['LNK:DriveSerialNumber'] = volume_serial
                    metadata['LNK:HasDriveSerialNumber'] = True
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse LNK metadata: {str(e)}")
    
    def _format_clsid(self, clsid_bytes: bytes) -> str:
        """Format CLSID bytes as GUID string."""
        if len(clsid_bytes) < 16:
            return ''
        return f"{{{clsid_bytes[0:4].hex().upper()}-{clsid_bytes[4:6].hex().upper()}-{clsid_bytes[6:8].hex().upper()}-{clsid_bytes[8:10].hex().upper()}-{clsid_bytes[10:16].hex().upper()}}}"
    
    def _filetime_to_datetime(self, filetime: int) -> str:
        """Convert Windows FILETIME to datetime string."""
        try:
            # FILETIME is 100-nanosecond intervals since January 1, 1601
            # Convert to Unix timestamp
            unix_timestamp = (filetime - 116444736000000000) / 10000000.0
            if unix_timestamp > 0:
                from datetime import datetime
                dt = datetime.fromtimestamp(unix_timestamp)
                return dt.strftime('%Y:%m:%d %H:%M:%S')
        except Exception:
            pass
        return ''
    
    def _parse_link_info(self, file_data: bytes, offset: int) -> Dict[str, Any]:
        """Parse LinkInfo structure."""
        metadata = {}
        try:
            if offset + 4 > len(file_data):
                return metadata
            
            # LinkInfoSize (4 bytes)
            link_info_size = struct.unpack('<I', file_data[offset:offset+4])[0]
            metadata['LNK:LinkInfoSize'] = link_info_size
            
            if offset + link_info_size > len(file_data):
                return metadata
            
            # LinkInfoHeaderSize (4 bytes)
            if offset + 8 <= len(file_data):
                link_info_header_size = struct.unpack('<I', file_data[offset+4:offset+8])[0]
                metadata['LNK:LinkInfoHeaderSize'] = link_info_header_size
            
            # LinkInfoFlags (4 bytes)
            if offset + 12 <= len(file_data):
                link_info_flags = struct.unpack('<I', file_data[offset+8:offset+12])[0]
                metadata['LNK:LinkInfoFlags'] = link_info_flags
                metadata['LNK:VolumeIDAndLocalBasePath'] = bool(link_info_flags & 0x01)
                metadata['LNK:CommonNetworkRelativeLinkAndPathSuffix'] = bool(link_info_flags & 0x02)
            
            # VolumeID structure (if present)
            if metadata.get('LNK:VolumeIDAndLocalBasePath'):
                volume_offset = offset + link_info_header_size
                if volume_offset + 16 <= len(file_data):
                    # VolumeIDSize (4 bytes)
                    volume_id_size = struct.unpack('<I', file_data[volume_offset:volume_offset+4])[0]
                    if volume_offset + volume_id_size <= len(file_data):
                        # DriveType (4 bytes)
                        if volume_offset + 8 <= len(file_data):
                            drive_type = struct.unpack('<I', file_data[volume_offset+4:volume_offset+8])[0]
                            metadata['LNK:DriveType'] = drive_type
                        
                        # DriveSerialNumber (4 bytes)
                        if volume_offset + 12 <= len(file_data):
                            drive_serial = struct.unpack('<I', file_data[volume_offset+8:volume_offset+12])[0]
                            if drive_serial > 0:
                                metadata['LNK:DriveSerialNumber'] = f"{drive_serial:08X}"
                                metadata['LNK:HasDriveSerialNumber'] = True
        except Exception:
            pass
        
        return metadata
    
    def _extract_environment_target(self, file_data: bytes, pattern_pos: int) -> Optional[str]:
        """Extract EnvironmentTarget value from file data."""
        try:
            # Look for environment variable pattern (e.g., %VARNAME%)
            # Search around the pattern position
            search_start = max(0, pattern_pos - 100)
            search_end = min(len(file_data), pattern_pos + 200)
            search_data = file_data[search_start:search_end]
            
            # Try to decode as UTF-16 LE or UTF-8
            for encoding in ['utf-16-le', 'utf-8', 'latin-1']:
                try:
                    text = search_data.decode(encoding, errors='ignore')
                    # Look for %VARNAME% pattern
                    import re
                    env_match = re.search(r'%([A-Za-z0-9_]+)%', text)
                    if env_match:
                        return env_match.group(1)
                except Exception:
                    continue
        except Exception:
            pass
        return None
    
    def _extract_drive_serial_number(self, file_data: bytes, pattern_pos: int) -> Optional[str]:
        """Extract DriveSerialNumber value from file data."""
        try:
            # Look for serial number near the pattern
            search_start = max(0, pattern_pos - 50)
            search_end = min(len(file_data), pattern_pos + 100)
            search_data = file_data[search_start:search_end]
            
            # Try to find 4-byte or 8-byte serial number
            # Serial numbers are often stored as little-endian integers
            if pattern_pos + 12 < len(file_data):
                # Try 4-byte serial number
                serial = struct.unpack('<I', file_data[pattern_pos+8:pattern_pos+12])[0]
                if serial > 0 and serial < 0xFFFFFFFF:
                    return f"{serial:08X}"
            
            # Try to decode as text
            for encoding in ['utf-16-le', 'utf-8', 'latin-1']:
                try:
                    text = search_data.decode(encoding, errors='ignore')
                    # Look for hexadecimal serial number
                    import re
                    hex_match = re.search(r'([0-9A-Fa-f]{8})', text)
                    if hex_match:
                        return hex_match.group(1).upper()
                except Exception:
                    continue
        except Exception:
            pass
        return None
    
    def _extract_volume_serial_from_linkinfo(self, file_data: bytes, offset: int) -> Optional[str]:
        """Extract volume serial number from LinkInfo structure."""
        try:
            # Volume serial number is typically at offset + LinkInfoHeaderSize + 8
            if offset + 20 < len(file_data):
                # Try to read LinkInfoHeaderSize
                link_info_header_size = struct.unpack('<I', file_data[offset+4:offset+8])[0]
                volume_offset = offset + link_info_header_size
                
                if volume_offset + 12 < len(file_data):
                    # DriveSerialNumber is at offset + 8 from VolumeID start
                    drive_serial = struct.unpack('<I', file_data[volume_offset+8:volume_offset+12])[0]
                    if drive_serial > 0:
                        return f"{drive_serial:08X}"
        except Exception:
            pass
        return None


