# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
EXE file parser for Win32 Portable Executable files.

EXE files are Windows Portable Executable (PE) format files (.exe extension).
They contain metadata including PDB (Program Database) information in the
debug directory, version information, and other Windows-specific metadata.
"""

import struct
from pathlib import Path
from typing import Dict, Any, Optional

from dnexif.exceptions import MetadataReadError


class EXEParser:
    """
    Parser for Win32 EXE (Portable Executable) files.
    
    EXE files are PE format files containing Windows executable metadata.
    PDB information is stored in the PE debug directory.
    """
    
    # PE signature
    PE_SIGNATURE = b'PE\x00\x00'
    
    # IMAGE_FILE_HEADER offsets
    IMAGE_FILE_HEADER_SIZE = 20
    
    # IMAGE_OPTIONAL_HEADER offsets
    IMAGE_OPTIONAL_HEADER32_SIZE = 224
    IMAGE_OPTIONAL_HEADER64_SIZE = 240
    
    # Debug directory entry size
    IMAGE_DEBUG_DIRECTORY_SIZE = 28
    
    # Debug types
    IMAGE_DEBUG_TYPE_CODEVIEW = 2
    IMAGE_DEBUG_TYPE_POGO = 13
    IMAGE_DEBUG_TYPE_ILTCG = 14
    IMAGE_DEBUG_TYPE_MPX = 15
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize EXE parser.
        
        Args:
            file_path: Path to EXE file
            file_data: EXE file data bytes
        """
        self.file_path = file_path
        self.file_data = file_data
        
        if not self.file_path and not self.file_data:
            raise ValueError("Either file_path or file_data must be provided")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse EXE file metadata.
        
        Returns:
            Dictionary of EXE metadata including PDB information
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 64:
                raise MetadataReadError("Invalid EXE file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'EXE'
            metadata['File:FileTypeExtension'] = 'exe'
            metadata['File:MIMEType'] = 'application/x-msdownload'
            metadata['EXE:Format'] = 'Portable Executable'
            
            # Check for DOS header
            # DOS header starts with "MZ" signature (0x4D 0x5A)
            if file_data[0:2] != b'MZ':
                raise MetadataReadError("Invalid EXE file: missing DOS header")
            
            metadata['EXE:HasDOSHeader'] = True
            
            # Get PE header offset from DOS header (offset 0x3C)
            if len(file_data) < 64:
                raise MetadataReadError("Invalid EXE file: DOS header too short")
            
            pe_offset = struct.unpack('<I', file_data[60:64])[0]
            
            if pe_offset + 4 > len(file_data):
                raise MetadataReadError("Invalid EXE file: PE header offset out of range")
            
            # Check for PE signature
            if file_data[pe_offset:pe_offset+4] != self.PE_SIGNATURE:
                raise MetadataReadError("Invalid EXE file: missing PE signature")
            
            metadata['EXE:HasPEHeader'] = True
            metadata['EXE:PEHeaderOffset'] = pe_offset
            
            # Parse IMAGE_FILE_HEADER (20 bytes)
            file_header_offset = pe_offset + 4
            if file_header_offset + self.IMAGE_FILE_HEADER_SIZE > len(file_data):
                raise MetadataReadError("Invalid EXE file: file header out of range")
            
            # Machine (2 bytes)
            machine = struct.unpack('<H', file_data[file_header_offset:file_header_offset+2])[0]
            metadata['EXE:Machine'] = machine
            machine_types = {
                0x014c: 'I386',
                0x8664: 'AMD64',
                0x01c0: 'ARM',
                0xaa64: 'ARM64',
            }
            if machine in machine_types:
                metadata['EXE:MachineType'] = machine_types[machine]
            
            # NumberOfSections (2 bytes)
            num_sections = struct.unpack('<H', file_data[file_header_offset+2:file_header_offset+4])[0]
            metadata['EXE:NumberOfSections'] = num_sections
            
            # TimeDateStamp (4 bytes)
            timestamp = struct.unpack('<I', file_data[file_header_offset+4:file_header_offset+8])[0]
            if timestamp > 0:
                try:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp)
                    metadata['EXE:TimeDateStamp'] = dt.strftime('%Y:%m:%d %H:%M:%S')
                except Exception:
                    metadata['EXE:TimeDateStamp'] = timestamp
            
            # PointerToSymbolTable (4 bytes)
            symbol_table_ptr = struct.unpack('<I', file_data[file_header_offset+8:file_header_offset+12])[0]
            if symbol_table_ptr > 0:
                metadata['EXE:PointerToSymbolTable'] = symbol_table_ptr
            
            # NumberOfSymbols (4 bytes)
            num_symbols = struct.unpack('<I', file_data[file_header_offset+12:file_header_offset+16])[0]
            if num_symbols > 0:
                metadata['EXE:NumberOfSymbols'] = num_symbols
            
            # SizeOfOptionalHeader (2 bytes)
            optional_header_size = struct.unpack('<H', file_data[file_header_offset+16:file_header_offset+18])[0]
            metadata['EXE:SizeOfOptionalHeader'] = optional_header_size
            
            # Characteristics (2 bytes)
            characteristics = struct.unpack('<H', file_data[file_header_offset+18:file_header_offset+20])[0]
            metadata['EXE:Characteristics'] = characteristics
            
            # Parse IMAGE_OPTIONAL_HEADER
            optional_header_offset = file_header_offset + self.IMAGE_FILE_HEADER_SIZE
            
            # Magic (2 bytes) - determines if PE32 (0x10B) or PE32+ (0x20B)
            if optional_header_offset + 2 > len(file_data):
                raise MetadataReadError("Invalid EXE file: optional header out of range")
            
            magic = struct.unpack('<H', file_data[optional_header_offset:optional_header_offset+2])[0]
            metadata['EXE:Magic'] = magic
            
            is_pe32_plus = (magic == 0x20B)
            metadata['EXE:IsPE32Plus'] = is_pe32_plus
            
            # AddressOfEntryPoint offset depends on PE32 vs PE32+
            if is_pe32_plus:
                # PE32+ (64-bit)
                entry_point_offset = optional_header_offset + 16
                base_of_code_offset = optional_header_offset + 20
                image_base_offset = optional_header_offset + 24
                debug_dir_offset = optional_header_offset + 112
            else:
                # PE32 (32-bit)
                entry_point_offset = optional_header_offset + 16
                base_of_code_offset = optional_header_offset + 20
                image_base_offset = optional_header_offset + 28
                debug_dir_offset = optional_header_offset + 96
            
            # AddressOfEntryPoint (4 bytes)
            if entry_point_offset + 4 <= len(file_data):
                entry_point = struct.unpack('<I', file_data[entry_point_offset:entry_point_offset+4])[0]
                metadata['EXE:AddressOfEntryPoint'] = f"0x{entry_point:08X}"
            
            # BaseOfCode (4 bytes for PE32, 8 bytes for PE32+)
            if base_of_code_offset + 4 <= len(file_data):
                if is_pe32_plus:
                    base_of_code = struct.unpack('<Q', file_data[base_of_code_offset:base_of_code_offset+8])[0]
                    metadata['EXE:BaseOfCode'] = f"0x{base_of_code:016X}"
                else:
                    base_of_code = struct.unpack('<I', file_data[base_of_code_offset:base_of_code_offset+4])[0]
                    metadata['EXE:BaseOfCode'] = f"0x{base_of_code:08X}"
            
            # ImageBase (4 bytes for PE32, 8 bytes for PE32+)
            if image_base_offset + (8 if is_pe32_plus else 4) <= len(file_data):
                if is_pe32_plus:
                    image_base = struct.unpack('<Q', file_data[image_base_offset:image_base_offset+8])[0]
                    metadata['EXE:ImageBase'] = f"0x{image_base:016X}"
                else:
                    image_base = struct.unpack('<I', file_data[image_base_offset:image_base_offset+4])[0]
                    metadata['EXE:ImageBase'] = f"0x{image_base:08X}"
            
            # DataDirectory[IMAGE_DIRECTORY_ENTRY_DEBUG] (8 bytes: RVA + Size)
            if debug_dir_offset + 8 <= len(file_data):
                debug_dir_rva = struct.unpack('<I', file_data[debug_dir_offset:debug_dir_offset+4])[0]
                debug_dir_size = struct.unpack('<I', file_data[debug_dir_offset+4:debug_dir_offset+8])[0]
                
                if debug_dir_rva > 0 and debug_dir_size > 0:
                    metadata['EXE:DebugDirectoryRVA'] = f"0x{debug_dir_rva:08X}"
                    metadata['EXE:DebugDirectorySize'] = debug_dir_size
                    metadata['EXE:HasDebugDirectory'] = True
                    
                    # Parse debug directory entries
                    pdb_info = self._parse_debug_directory(file_data, debug_dir_rva, debug_dir_size)
                    if pdb_info:
                        metadata.update(pdb_info)
            
            # Search for PDB patterns in file data
            pdb_patterns = [
                b'.pdb',
                b'.PDB',
                b'PDB',
                b'pdb',
                b'Program Database',
                b'PROGRAM DATABASE',
                b'program database',
            ]
            
            pdb_found = False
            for pattern in pdb_patterns:
                if pattern in file_data:
                    pdb_found = True
                    metadata['EXE:HasPDBReference'] = True
                    break
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse EXE metadata: {str(e)}")
    
    def _parse_debug_directory(self, file_data: bytes, debug_dir_rva: int, debug_dir_size: int) -> Dict[str, Any]:
        """
        Parse debug directory entries to extract PDB information.
        
        Args:
            file_data: EXE file data
            debug_dir_rva: RVA of debug directory
            debug_dir_size: Size of debug directory
            
        Returns:
            Dictionary containing PDB information
        """
        metadata = {}
        try:
            # Convert RVA to file offset (simplified - assumes debug directory is in .rdata section)
            # For simplicity, search for debug directory signature near the RVA
            # In practice, we'd need to parse section headers to convert RVA to file offset
            
            # Search for IMAGE_DEBUG_DIRECTORY entries
            # Each entry is 28 bytes
            num_entries = debug_dir_size // self.IMAGE_DEBUG_DIRECTORY_SIZE
            
            # Try to find debug directory by searching for common patterns
            # Debug directory entries typically contain CodeView debug info
            codeview_signatures = [
                b'RSDS',  # CodeView signature (PDB 7.0+)
                b'NB10',  # CodeView signature (PDB 2.0)
                b'NB09',  # CodeView signature (old)
                b'NB05',  # CodeView signature (old)
            ]
            
            pdb_paths = []
            pdb_guids = []
            pdb_ages = []
            
            # Search for CodeView signatures in file data
            for sig in codeview_signatures:
                offset = 0
                while True:
                    sig_pos = file_data.find(sig, offset)
                    if sig_pos == -1:
                        break
                    
                    # Found CodeView signature, try to extract PDB information
                    if sig_pos + 20 < len(file_data):
                        # CodeView structure:
                        # - Signature: 4 bytes (RSDS, NB10, etc.)
                        # - GUID: 16 bytes (for RSDS)
                        # - Age: 4 bytes
                        # - PDB path: null-terminated string
                        
                        signature = file_data[sig_pos:sig_pos+4].decode('ascii', errors='ignore')
                        if signature in ('RSDS', 'NB10', 'NB09', 'NB05'):
                            metadata['EXE:CodeViewSignature'] = signature
                            metadata['EXE:HasCodeViewDebug'] = True
                            
                            if signature == 'RSDS':
                                # RSDS format (PDB 7.0+)
                                # GUID (16 bytes)
                                if sig_pos + 20 < len(file_data):
                                    guid_bytes = file_data[sig_pos+4:sig_pos+20]
                                    guid_str = self._format_guid(guid_bytes)
                                    pdb_guids.append(guid_str)
                                    metadata['EXE:PDBGUID'] = guid_str
                                
                                # Age (4 bytes)
                                if sig_pos + 24 < len(file_data):
                                    age = struct.unpack('<I', file_data[sig_pos+20:sig_pos+24])[0]
                                    pdb_ages.append(age)
                                    metadata['EXE:PDBAge'] = age
                                    
                                    # PDB path (null-terminated string)
                                    pdb_path_start = sig_pos + 24
                                    pdb_path_end = file_data.find(b'\x00', pdb_path_start)
                                    if pdb_path_end != -1:
                                        try:
                                            pdb_path = file_data[pdb_path_start:pdb_path_end].decode('utf-8', errors='ignore')
                                            if pdb_path and (pdb_path.endswith('.pdb') or '.pdb' in pdb_path.lower()):
                                                pdb_paths.append(pdb_path)
                                                metadata['EXE:PDBPath'] = pdb_path
                                                metadata['EXE:HasPDB'] = True
                                        except Exception:
                                            pass
                            
                            elif signature in ('NB10', 'NB09', 'NB05'):
                                # NB10/NB09/NB05 format (PDB 2.0)
                                # Offset: 4 bytes (usually 0)
                                # Timestamp: 4 bytes
                                # Age: 4 bytes
                                # PDB path: null-terminated string
                                
                                if sig_pos + 12 < len(file_data):
                                    timestamp = struct.unpack('<I', file_data[sig_pos+4:sig_pos+8])[0]
                                    age = struct.unpack('<I', file_data[sig_pos+8:sig_pos+12])[0]
                                    pdb_ages.append(age)
                                    metadata['EXE:PDBAge'] = age
                                    
                                    if timestamp > 0:
                                        try:
                                            from datetime import datetime
                                            dt = datetime.fromtimestamp(timestamp)
                                            metadata['EXE:PDBTimestamp'] = dt.strftime('%Y:%m:%d %H:%M:%S')
                                        except Exception:
                                            pass
                                    
                                    # PDB path (null-terminated string)
                                    pdb_path_start = sig_pos + 12
                                    pdb_path_end = file_data.find(b'\x00', pdb_path_start)
                                    if pdb_path_end != -1:
                                        try:
                                            pdb_path = file_data[pdb_path_start:pdb_path_end].decode('utf-8', errors='ignore')
                                            if pdb_path and (pdb_path.endswith('.pdb') or '.pdb' in pdb_path.lower()):
                                                pdb_paths.append(pdb_path)
                                                metadata['EXE:PDBPath'] = pdb_path
                                                metadata['EXE:HasPDB'] = True
                                        except Exception:
                                            pass
                            
                            # Break after finding first valid CodeView structure
                            break
                    
                    offset = sig_pos + 4
            
            if pdb_paths:
                metadata['EXE:PDBPathCount'] = len(pdb_paths)
                for i, pdb_path in enumerate(pdb_paths[:5], 1):  # Limit to 5 paths
                    metadata[f'EXE:PDBPath{i}'] = pdb_path
            
            if pdb_guids:
                metadata['EXE:PDBGUIDCount'] = len(pdb_guids)
                for i, guid in enumerate(pdb_guids[:5], 1):  # Limit to 5 GUIDs
                    metadata[f'EXE:PDBGUID{i}'] = guid
            
            if pdb_ages:
                metadata['EXE:PDBAgeCount'] = len(pdb_ages)
                metadata['EXE:PDBAge'] = pdb_ages[0]  # Use first age
            
        except Exception:
            pass
        
        return metadata
    
    def _format_guid(self, guid_bytes: bytes) -> str:
        """Format GUID bytes as GUID string."""
        if len(guid_bytes) < 16:
            return ''
        # GUID format: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
        return f"{{{guid_bytes[0:4].hex().upper()}-{guid_bytes[4:6].hex().upper()}-{guid_bytes[6:8].hex().upper()}-{guid_bytes[8:10].hex().upper()}-{guid_bytes[10:16].hex().upper()}}}"

