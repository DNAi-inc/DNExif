# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
C2PA (Coalition for Content Provenance and Authenticity) JUMBF Parser.

C2PA uses JUMBF (JPEG Universal Metadata Box Format) to embed provenance
metadata in various file formats including PNG, JPEG, TIFF, MP4, etc.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class C2PAParser:
    """
    Parser for C2PA (Coalition for Content Provenance and Authenticity) JUMBF metadata.
    
    C2PA uses JUMBF (JPEG Universal Metadata Box Format) to embed provenance
    metadata in various file formats including PNG, JPEG, TIFF, MP4, etc.
    
    JUMBF boxes can contain:
    - C2PA manifests (c2pa claim manifests)
    - CAI (Content Authenticity Initiative) metadata
    - CBOR-format metadata
    - Salt values for verification
    """
    
    # JUMBF box type identifiers
    JUMBF_BOX_TYPE = b'jumd'  # JUMBF Description box
    C2PA_BOX_TYPE = b'c2pa'    # C2PA manifest box
    CAI_BOX_TYPE = b'cai '     # CAI metadata box
    
    # C2PA signature patterns
    C2PA_SIGNATURE = b'c2pa'
    CAI_SIGNATURE = b'cai '
    
    # CBOR format indicators
    # CBOR (Concise Binary Object Representation) is used in CAI JUMBF
    # CBOR data starts with specific byte patterns (major type indicators)
    CBOR_MAJOR_TYPES = {
        0: 'unsigned integer',
        1: 'negative integer',
        2: 'byte string',
        3: 'text string',
        4: 'array',
        5: 'map',
        6: 'tag',
        7: 'float/simple'
    }
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize C2PA parser.
        
        Args:
            file_path: Path to file containing C2PA metadata
            file_data: File data as bytes (alternative to file_path)
        """
        self.file_path = Path(file_path) if file_path else None
        self.file_data = file_data
        
        if not file_path and not file_data:
            raise ValueError("Either file_path or file_data must be provided")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse C2PA JUMBF metadata from file.
        
        Returns:
            Dictionary of C2PA metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) == 0:
                return {}
            
            metadata = {}
            metadata['C2PA:HasC2PAMetadata'] = False
            
            # Extract Salt values if C2PA metadata is present
            # Salt values are used for cryptographic verification in C2PA
            salt_values = self._extract_salt_values(file_data)
            if salt_values:
                metadata.update(salt_values)
            
            # Extract JUMBF metadata blocks if C2PA metadata is present
            # JUMBF blocks contain the actual C2PA manifest data
            jumbf_blocks = self._extract_jumbf_blocks(file_data)
            if jumbf_blocks:
                metadata.update(jumbf_blocks)
            
            # Detect CBOR-format metadata in CAI JUMBF blocks
            # CBOR is used for structured metadata in CAI JUMBF
            cbor_data = self._detect_cbor_metadata(file_data)
            if cbor_data:
                metadata.update(cbor_data)
            
            # Detect file format and parse accordingly
            if self.file_path:
                ext = self.file_path.suffix.lower()
                
                # PNG files - C2PA can be in PNG chunks
                if ext == '.png':
                    c2pa_data = self._parse_png_c2pa(file_data)
                    if c2pa_data:
                        metadata.update(c2pa_data)
                        metadata['C2PA:HasC2PAMetadata'] = True
                
                # JPEG files - C2PA can be in JPEG APP segments
                elif ext in ('.jpg', '.jpeg', '.jph'):
                    c2pa_data = self._parse_jpeg_c2pa(file_data)
                    if c2pa_data:
                        metadata.update(c2pa_data)
                        metadata['C2PA:HasC2PAMetadata'] = True
                
                # TIFF files - C2PA can be in TIFF IFD entries or UUID boxes
                elif ext in ('.tif', '.tiff', '.dng'):
                    c2pa_data = self._parse_tiff_c2pa(file_data)
                    if c2pa_data:
                        metadata.update(c2pa_data)
                        metadata['C2PA:HasC2PAMetadata'] = True
                
                # MP4/MOV files - C2PA can be in QuickTime UUID boxes
                elif ext in ('.mp4', '.mov', '.m4v', '.m4a'):
                    c2pa_data = self._parse_quicktime_c2pa(file_data)
                    if c2pa_data:
                        metadata.update(c2pa_data)
                        metadata['C2PA:HasC2PAMetadata'] = True
                
                # WebP files - C2PA can be in WebP chunks
                elif ext == '.webp':
                    c2pa_data = self._parse_webp_c2pa(file_data)
                    if c2pa_data:
                        metadata.update(c2pa_data)
                        metadata['C2PA:HasC2PAMetadata'] = True
                
                # TTF/OTF font files - C2PA can be in font tables
                elif ext in ('.ttf', '.otf'):
                    c2pa_data = self._parse_font_c2pa(file_data)
                    if c2pa_data:
                        metadata.update(c2pa_data)
                        metadata['C2PA:HasC2PAMetadata'] = True
                
                # PDF files - C2PA can be in PDF objects or XMP metadata
                elif ext == '.pdf':
                    c2pa_data = self._parse_pdf_c2pa(file_data)
                    if c2pa_data:
                        metadata.update(c2pa_data)
                        metadata['C2PA:HasC2PAMetadata'] = True
                
                # SVG files - C2PA can be in SVG metadata elements or embedded data
                elif ext == '.svg':
                    c2pa_data = self._parse_svg_c2pa(file_data)
                    if c2pa_data:
                        metadata.update(c2pa_data)
                        metadata['C2PA:HasC2PAMetadata'] = True
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse C2PA metadata: {str(e)}")
    
    def _parse_png_c2pa(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse C2PA metadata from PNG chunks.
        
        C2PA JUMBF metadata in PNG files can be stored in:
        - iTXt chunks with keyword "C2PA" or "c2pa"
        - Custom PNG chunks (if supported)
        """
        metadata = {}
        
        try:
            if len(file_data) < 8 or file_data[:8] != b'\x89PNG\r\n\x1a\n':
                return metadata
            
            offset = 8
            c2pa_chunks = []
            
            while offset < len(file_data) - 8:
                # Read chunk length (4 bytes, big-endian)
                if offset + 4 > len(file_data):
                    break
                chunk_length = struct.unpack('>I', file_data[offset:offset + 4])[0]
                offset += 4
                
                # Read chunk type (4 bytes)
                if offset + 4 > len(file_data):
                    break
                chunk_type = file_data[offset:offset + 4]
                offset += 4
                
                # Check for iTXt chunk (international text chunk)
                if chunk_type == b'iTXt':
                    chunk_data = file_data[offset:offset + chunk_length]
                    
                    # iTXt format: keyword (null-terminated), compression flag, compression method, language tag, translated keyword, text
                    # Find keyword (null-terminated)
                    keyword_end = chunk_data.find(b'\x00')
                    if keyword_end > 0:
                        keyword = chunk_data[:keyword_end].decode('ascii', errors='ignore').lower()
                        
                        # Check if this is a C2PA chunk
                        if keyword in ('c2pa', 'cai', 'jumbf'):
                            c2pa_chunks.append({
                                'keyword': keyword,
                                'offset': offset - 8,
                                'length': chunk_length,
                                'data': chunk_data
                            })
                            
                            # Extract C2PA signature if present
                            if self.C2PA_SIGNATURE in chunk_data:
                                metadata['C2PA:Signature'] = 'C2PA'
                                metadata['C2PA:Location'] = 'PNG iTXt'
                                metadata['C2PA:Offset'] = offset - 8
                                metadata['C2PA:DataLength'] = chunk_length
                            
                            if self.CAI_SIGNATURE in chunk_data:
                                metadata['C2PA:CAISignature'] = 'CAI'
                                metadata['C2PA:CAILocation'] = 'PNG iTXt'
                                metadata['C2PA:CAIOffset'] = offset - 8
                                metadata['C2PA:CAIDataLength'] = chunk_length
                
                offset += chunk_length + 4  # Skip data and CRC
                
                if chunk_type == b'IEND':
                    break
            
            if c2pa_chunks:
                metadata['C2PA:ChunkCount'] = len(c2pa_chunks)
                metadata['C2PA:Chunks'] = [chunk['keyword'] for chunk in c2pa_chunks]
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_jpeg_c2pa(self, file_data: bytes) -> Dict[str, Any]:
        """Parse C2PA metadata from JPEG APP segments."""
        metadata = {}
        
        try:
            if not file_data.startswith(b'\xff\xd8'):
                return metadata
            
            offset = 2  # Skip JPEG signature
            
            while offset < len(file_data) - 4:
                # Look for APP marker (0xFFE0-0xFFEF)
                if file_data[offset] == 0xFF and 0xE0 <= file_data[offset + 1] <= 0xEF:
                    # Read segment length
                    length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                    
                    # Check for C2PA signature in segment
                    segment_data = file_data[offset + 4:offset + 2 + length]
                    
                    if self.C2PA_SIGNATURE in segment_data:
                        metadata['C2PA:Signature'] = 'C2PA'
                        metadata['C2PA:Location'] = 'JPEG APP'
                        metadata['C2PA:Offset'] = offset
                        metadata['C2PA:DataLength'] = length
                    
                    if self.CAI_SIGNATURE in segment_data:
                        metadata['C2PA:CAISignature'] = 'CAI'
                        metadata['C2PA:CAILocation'] = 'JPEG APP'
                        metadata['C2PA:CAIOffset'] = offset
                        metadata['C2PA:CAIDataLength'] = length
                    
                    offset += length
                else:
                    offset += 1
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_tiff_c2pa(self, file_data: bytes) -> Dict[str, Any]:
        """Parse C2PA metadata from TIFF files."""
        metadata = {}
        
        try:
            # Search for C2PA signatures in TIFF data
            if self.C2PA_SIGNATURE in file_data:
                offset = file_data.find(self.C2PA_SIGNATURE)
                metadata['C2PA:Signature'] = 'C2PA'
                metadata['C2PA:Location'] = 'TIFF'
                metadata['C2PA:Offset'] = offset
            
            if self.CAI_SIGNATURE in file_data:
                offset = file_data.find(self.CAI_SIGNATURE)
                metadata['C2PA:CAISignature'] = 'CAI'
                metadata['C2PA:CAILocation'] = 'TIFF'
                metadata['C2PA:CAIOffset'] = offset
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_quicktime_c2pa(self, file_data: bytes) -> Dict[str, Any]:
        """Parse C2PA metadata from QuickTime/MP4 files."""
        metadata = {}
        
        try:
            # Search for C2PA signatures in QuickTime data
            if self.C2PA_SIGNATURE in file_data:
                offset = file_data.find(self.C2PA_SIGNATURE)
                metadata['C2PA:Signature'] = 'C2PA'
                metadata['C2PA:Location'] = 'QuickTime'
                metadata['C2PA:Offset'] = offset
            
            if self.CAI_SIGNATURE in file_data:
                offset = file_data.find(self.CAI_SIGNATURE)
                metadata['C2PA:CAISignature'] = 'CAI'
                metadata['C2PA:CAILocation'] = 'QuickTime'
                metadata['C2PA:CAIOffset'] = offset
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_webp_c2pa(self, file_data: bytes) -> Dict[str, Any]:
        """Parse C2PA metadata from WebP files."""
        metadata = {}
        
        try:
            # Search for C2PA signatures in WebP data
            if self.C2PA_SIGNATURE in file_data:
                offset = file_data.find(self.C2PA_SIGNATURE)
                metadata['C2PA:Signature'] = 'C2PA'
                metadata['C2PA:Location'] = 'WebP'
                metadata['C2PA:Offset'] = offset
            
            if self.CAI_SIGNATURE in file_data:
                offset = file_data.find(self.CAI_SIGNATURE)
                metadata['C2PA:CAISignature'] = 'CAI'
                metadata['C2PA:CAILocation'] = 'WebP'
                metadata['C2PA:CAIOffset'] = offset
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_font_c2pa(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse C2PA metadata from TTF/OTF font files.
        
        C2PA JUMBF metadata in font files can be stored in:
        - Custom font tables
        - Metadata tables
        """
        metadata = {}
        
        try:
            # TTF/OTF files start with specific signatures
            # TTF: 0x00010000 or 'OTTO'
            # OTF: 'OTTO' or 0x00010000
            if len(file_data) < 4:
                return metadata
            
            # Check for TTF/OTF signature
            signature = file_data[:4]
            is_ttf = signature == b'\x00\x01\x00\x00' or signature == b'OTTO'
            is_otf = signature == b'OTTO' or signature == b'\x00\x01\x00\x00'
            
            if not (is_ttf or is_otf):
                return metadata
            
            # Search for C2PA signatures in font data
            # C2PA metadata in fonts is typically in custom tables
            if self.C2PA_SIGNATURE in file_data:
                offset = file_data.find(self.C2PA_SIGNATURE)
                metadata['C2PA:Signature'] = 'C2PA'
                metadata['C2PA:Location'] = 'Font Table'
                metadata['C2PA:Offset'] = offset
                
                # Try to find table name if possible (fonts have table directory)
                # Font table directory starts at offset 12 (after version and table count)
                if len(file_data) > 12:
                    try:
                        num_tables = struct.unpack('>H', file_data[4:6])[0]
                        # Each table entry is 16 bytes: tag (4), checksum (4), offset (4), length (4)
                        table_dir_offset = 12
                        for i in range(min(num_tables, 100)):  # Limit search
                            table_entry_offset = table_dir_offset + (i * 16)
                            if table_entry_offset + 16 <= len(file_data):
                                table_tag = file_data[table_entry_offset:table_entry_offset + 4]
                                table_offset = struct.unpack('>I', file_data[table_entry_offset + 8:table_entry_offset + 12])[0]
                                table_length = struct.unpack('>I', file_data[table_entry_offset + 12:table_entry_offset + 16])[0]
                                
                                # Check if C2PA signature is within this table
                                if table_offset <= offset < table_offset + table_length:
                                    metadata['C2PA:TableTag'] = table_tag.decode('ascii', errors='ignore')
                                    break
                    except Exception:
                        pass
            
            if self.CAI_SIGNATURE in file_data:
                offset = file_data.find(self.CAI_SIGNATURE)
                metadata['C2PA:CAISignature'] = 'CAI'
                metadata['C2PA:CAILocation'] = 'Font Table'
                metadata['C2PA:CAIOffset'] = offset
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_pdf_c2pa(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse C2PA metadata from PDF files.
        
        C2PA JUMBF metadata in PDF files can be stored in:
        - PDF objects (streams)
        - XMP metadata packets
        - Embedded file attachments
        """
        metadata = {}
        
        try:
            if not file_data.startswith(b'%PDF'):
                return metadata
            
            # Search for C2PA signatures in PDF data
            # PDF files are structured with objects, so we search for C2PA in the raw data
            if self.C2PA_SIGNATURE in file_data:
                offset = file_data.find(self.C2PA_SIGNATURE)
                metadata['C2PA:Signature'] = 'C2PA'
                metadata['C2PA:Location'] = 'PDF'
                metadata['C2PA:Offset'] = offset
                
                # Try to find PDF object number if possible
                # Look backwards for object reference pattern: "N M obj" where N is object number
                try:
                    search_start = max(0, offset - 200)
                    search_data = file_data[search_start:offset]
                    # Look for object pattern
                    import re
                    obj_pattern = rb'(\d+)\s+(\d+)\s+obj'
                    matches = list(re.finditer(obj_pattern, search_data))
                    if matches:
                        last_match = matches[-1]
                        obj_num = last_match.group(1).decode('ascii', errors='ignore')
                        metadata['C2PA:PDFObject'] = obj_num
                except Exception:
                    pass
            
            if self.CAI_SIGNATURE in file_data:
                offset = file_data.find(self.CAI_SIGNATURE)
                metadata['C2PA:CAISignature'] = 'CAI'
                metadata['C2PA:CAILocation'] = 'PDF'
                metadata['C2PA:CAIOffset'] = offset
                
                # Try to find PDF object number
                try:
                    search_start = max(0, offset - 200)
                    search_data = file_data[search_start:offset]
                    import re
                    obj_pattern = rb'(\d+)\s+(\d+)\s+obj'
                    matches = list(re.finditer(obj_pattern, search_data))
                    if matches:
                        last_match = matches[-1]
                        obj_num = last_match.group(1).decode('ascii', errors='ignore')
                        metadata['C2PA:CAIPDFObject'] = obj_num
                except Exception:
                    pass
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_svg_c2pa(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse C2PA metadata from SVG files.
        
        C2PA JUMBF metadata in SVG files can be stored in:
        - SVG metadata elements
        - Embedded data URIs
        - XMP metadata within SVG
        """
        metadata = {}
        
        try:
            # SVG files are XML-based, so we can search for C2PA in the text
            # Decode to string for text search
            try:
                svg_str = file_data.decode('utf-8')
            except UnicodeDecodeError:
                svg_str = file_data.decode('latin-1', errors='ignore')
            
            # Search for C2PA signatures in SVG text
            if 'c2pa' in svg_str.lower():
                # Find offset in original bytes
                c2pa_lower = file_data.lower()
                offset = c2pa_lower.find(b'c2pa')
                if offset != -1:
                    metadata['C2PA:Signature'] = 'C2PA'
                    metadata['C2PA:Location'] = 'SVG'
                    metadata['C2PA:Offset'] = offset
                    
                    # Try to find if it's in a metadata element
                    if 'metadata' in svg_str.lower():
                        metadata['C2PA:InMetadataElement'] = True
            
            if 'cai' in svg_str.lower():
                c2pa_lower = file_data.lower()
                offset = c2pa_lower.find(b'cai')
                if offset != -1:
                    metadata['C2PA:CAISignature'] = 'CAI'
                    metadata['C2PA:CAILocation'] = 'SVG'
                    metadata['C2PA:CAIOffset'] = offset
                    
                    # Try to find if it's in a metadata element
                    if 'metadata' in svg_str.lower():
                        metadata['C2PA:CAIInMetadataElement'] = True
        
        except Exception:
            pass
        
        return metadata
    
    def _extract_salt_values(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract C2PA Salt values from file data.
        
        C2PA Salt values are used for cryptographic verification and are typically
        found in JUMBF boxes or C2PA manifest structures.
        
        Salt values are usually:
        - Binary data (16-32 bytes typically)
        - Found near C2PA signatures
        - Used for hash verification
        """
        metadata = {}
        
        try:
            # Search for C2PA signature first
            if self.C2PA_SIGNATURE not in file_data:
                return metadata
            
            c2pa_offset = file_data.find(self.C2PA_SIGNATURE)
            
            # Look for salt patterns near C2PA signature
            # Salt values are typically found within 1KB of C2PA signature
            search_start = max(0, c2pa_offset - 512)
            search_end = min(len(file_data), c2pa_offset + 1024)
            search_region = file_data[search_start:search_end]
            
            # Common salt patterns in C2PA:
            # 1. "salt" keyword followed by binary data
            # 2. Binary data blocks (16-32 bytes) near C2PA signature
            # 3. Base64-encoded salt values
            
            # Look for "salt" keyword (case-insensitive)
            salt_keyword_patterns = [b'salt', b'Salt', b'SALT']
            for pattern in salt_keyword_patterns:
                salt_keyword_pos = search_region.find(pattern)
                if salt_keyword_pos != -1:
                    # Try to extract salt value after keyword
                    # Salt values are typically 16-32 bytes of binary data
                    salt_start = salt_keyword_pos + len(pattern)
                    # Skip whitespace/null bytes
                    while salt_start < len(search_region) and search_region[salt_start] in (0x00, 0x20, 0x09, 0x0A, 0x0D):
                        salt_start += 1
                    
                    # Extract potential salt value (16-32 bytes)
                    if salt_start + 16 <= len(search_region):
                        salt_length = min(32, len(search_region) - salt_start)
                        salt_value = search_region[salt_start:salt_start + salt_length]
                        
                        # Check if it looks like binary salt data (not all zeros, not all same byte)
                        if len(set(salt_value)) > 1 and not all(b == 0 for b in salt_value[:16]):
                            # Convert to hex string for storage
                            salt_hex = salt_value.hex()
                            metadata['C2PA:Salt'] = salt_hex
                            metadata['C2PA:SaltLength'] = len(salt_value)
                            metadata['C2PA:SaltOffset'] = search_start + salt_start + (c2pa_offset - 512)
                            break
            
            # Also look for binary salt patterns (16-32 byte blocks near C2PA signature)
            # These might be salt values without explicit "salt" keyword
            if 'C2PA:Salt' not in metadata:
                # Look for binary blocks that might be salt values
                # Salt values are typically random-looking binary data
                for offset in range(max(0, c2pa_offset - 256), min(len(file_data) - 32, c2pa_offset + 512)):
                    potential_salt = file_data[offset:offset + 16]
                    # Check if it looks like random binary data (not all zeros, not all same byte, not ASCII text)
                    if (len(set(potential_salt)) > 4 and 
                        not all(b == 0 for b in potential_salt) and
                        not all(32 <= b <= 126 for b in potential_salt)):  # Not all printable ASCII
                        # This might be a salt value
                        salt_hex = potential_salt.hex()
                        metadata['C2PA:Salt'] = salt_hex
                        metadata['C2PA:SaltLength'] = 16
                        metadata['C2PA:SaltOffset'] = offset
                        break
        
        except Exception:
            pass
        
        return metadata
    
    def _extract_jumbf_blocks(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract JUMBF metadata blocks from file data.
        
        JUMBF (JPEG Universal Metadata Box Format) blocks contain the actual
        C2PA manifest data. This method extracts the raw JUMBF block data
        for further processing or verification.
        
        Returns:
            Dictionary containing JUMBF block information
        """
        metadata = {}
        
        try:
            # Search for JUMBF box signatures
            # JUMBF boxes start with box size (4 bytes) and box type (4 bytes)
            # Common JUMBF box types: 'jumd' (description), 'c2pa' (C2PA manifest), 'cai ' (CAI metadata)
            
            jumbf_blocks = []
            offset = 0
            
            while offset < len(file_data) - 8:
                # Look for JUMBF box type signatures
                # Check for 'jumd' (JUMBF Description box)
                if offset + 4 <= len(file_data):
                    potential_type = file_data[offset:offset + 4]
                    
                    if potential_type == self.JUMBF_BOX_TYPE:
                        # Found JUMBF Description box
                        # Read box size (4 bytes before type, big-endian)
                        if offset >= 4:
                            box_size = struct.unpack('>I', file_data[offset - 4:offset])[0]
                            box_data = file_data[offset - 4:offset - 4 + box_size] if offset - 4 + box_size <= len(file_data) else file_data[offset - 4:]
                            jumbf_blocks.append({
                                'type': 'jumd',
                                'offset': offset - 4,
                                'size': box_size,
                                'data_length': len(box_data)
                            })
                    
                    elif potential_type == self.C2PA_BOX_TYPE:
                        # Found C2PA box
                        if offset >= 4:
                            box_size = struct.unpack('>I', file_data[offset - 4:offset])[0]
                            box_data = file_data[offset - 4:offset - 4 + box_size] if offset - 4 + box_size <= len(file_data) else file_data[offset - 4:]
                            jumbf_blocks.append({
                                'type': 'c2pa',
                                'offset': offset - 4,
                                'size': box_size,
                                'data_length': len(box_data)
                            })
                    
                    elif potential_type == self.CAI_BOX_TYPE:
                        # Found CAI box
                        if offset >= 4:
                            box_size = struct.unpack('>I', file_data[offset - 4:offset])[0]
                            box_data = file_data[offset - 4:offset - 4 + box_size] if offset - 4 + box_size <= len(file_data) else file_data[offset - 4:]
                            jumbf_blocks.append({
                                'type': 'cai',
                                'offset': offset - 4,
                                'size': box_size,
                                'data_length': len(box_data)
                            })
                
                offset += 1
                
                # Limit search to prevent excessive processing
                if offset > 100000:  # Search first 100KB
                    break
            
            if jumbf_blocks:
                metadata['C2PA:JUMBFBlockCount'] = len(jumbf_blocks)
                metadata['C2PA:JUMBFBlocks'] = jumbf_blocks
                
                # Extract block information
                for i, block in enumerate(jumbf_blocks):
                    metadata[f'C2PA:JUMBFBlock{i+1}:Type'] = block['type']
                    metadata[f'C2PA:JUMBFBlock{i+1}:Offset'] = block['offset']
                    metadata[f'C2PA:JUMBFBlock{i+1}:Size'] = block['size']
                    metadata[f'C2PA:JUMBFBlock{i+1}:DataLength'] = block['data_length']
        
        except Exception:
            pass
        
        return metadata
    
    def _detect_cbor_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Detect CBOR-format metadata in CAI JUMBF blocks.
        
        CBOR (Concise Binary Object Representation) is used for structured
        metadata in CAI JUMBF blocks. This method detects CBOR data patterns
        near CAI signatures.
        
        Returns:
            Dictionary containing CBOR detection information
        """
        metadata = {}
        
        try:
            # Search for CAI signature first (CBOR is typically in CAI JUMBF blocks)
            if self.CAI_SIGNATURE not in file_data:
                return metadata
            
            cai_offset = file_data.find(self.CAI_SIGNATURE)
            
            # Look for CBOR data patterns near CAI signature
            # CBOR data starts with specific byte patterns indicating major types
            # Common CBOR patterns: 0x00-0x17 (unsigned integers), 0x40-0x57 (byte strings), etc.
            search_start = max(0, cai_offset - 256)
            search_end = min(len(file_data), cai_offset + 2048)  # Search 2KB after CAI signature
            search_region = file_data[search_start:search_end]
            
            cbor_detections = []
            
            # Look for CBOR major type patterns
            # CBOR major types are encoded in the first 3 bits of the first byte
            for offset in range(len(search_region) - 1):
                byte_val = search_region[offset]
                major_type = (byte_val >> 5) & 0x07  # Extract major type (bits 5-7)
                
                # Check if this looks like CBOR data
                # CBOR major types 0-7 are valid
                if major_type <= 7:
                    # Additional check: CBOR data often has specific patterns
                    # For example, byte strings (type 2) start with 0x40-0x57 for short strings
                    # Arrays (type 4) start with 0x80-0x97 for short arrays
                    # Maps (type 5) start with 0xA0-0xB7 for short maps
                    
                    if (0x40 <= byte_val <= 0x57) or (0x60 <= byte_val <= 0x77) or \
                       (0x80 <= byte_val <= 0x97) or (0xA0 <= byte_val <= 0xB7):
                        # This might be CBOR data
                        cbor_detections.append({
                            'offset': search_start + offset,
                            'major_type': major_type,
                            'type_name': self.CBOR_MAJOR_TYPES.get(major_type, 'unknown'),
                            'byte_value': byte_val
                        })
                        
                        # Limit detections to prevent excessive output
                        if len(cbor_detections) >= 10:
                            break
            
            if cbor_detections:
                metadata['C2PA:HasCBORMetadata'] = True
                metadata['C2PA:CBORDetectionCount'] = len(cbor_detections)
                
                # Extract first CBOR detection details
                first_detection = cbor_detections[0]
                metadata['C2PA:CBOROffset'] = first_detection['offset']
                metadata['C2PA:CBORMajorType'] = first_detection['major_type']
                metadata['C2PA:CBORTypeName'] = first_detection['type_name']
                metadata['C2PA:CBORByteValue'] = first_detection['byte_value']
        
        except Exception:
            pass
        
        return metadata

