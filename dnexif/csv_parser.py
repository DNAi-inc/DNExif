# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
CSV (Comma-Separated Values) file metadata parser

This module handles reading metadata from CSV files.
CSV files are simple text files with comma-separated values.

Copyright 2025 DNAi inc.
"""

import csv
from typing import Dict, Any, Optional
from pathlib import Path

try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

from dnexif.exceptions import MetadataReadError


class CSVParser:
    """
    Parser for CSV (Comma-Separated Values) metadata.
    
    CSV files are simple text files with comma-separated values.
    Structure:
    - Header row (optional) with column names
    - Data rows with comma-separated values
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize CSV parser.
        
        Args:
            file_path: Path to CSV file
            file_data: CSV file data bytes
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
        Parse CSV metadata.
        
        Returns:
            Dictionary of CSV metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) == 0:
                raise MetadataReadError("Invalid CSV file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'CSV'
            metadata['File:FileTypeExtension'] = 'csv'
            metadata['File:MIMEType'] = 'text/csv'
            
            # Detect encoding
            encoding = 'utf-8'
            if HAS_CHARDET:
                try:
                    detected = chardet.detect(file_data)
                    encoding = detected.get('encoding', 'utf-8')
                    confidence = detected.get('confidence', 0.0)
                    metadata['CSV:Encoding'] = encoding
                    metadata['CSV:EncodingConfidence'] = confidence
                except Exception:
                    metadata['CSV:Encoding'] = encoding
            else:
                # Try common encodings
                for enc in ['utf-8', 'utf-16-le', 'latin-1']:
                    try:
                        file_data.decode(enc)
                        encoding = enc
                        break
                    except UnicodeDecodeError:
                        continue
                metadata['CSV:Encoding'] = encoding
            
            # Decode file content
            try:
                content = file_data.decode(encoding)
            except UnicodeDecodeError:
                try:
                    content = file_data.decode('utf-8', errors='ignore')
                    metadata['CSV:Encoding'] = 'utf-8'
                except Exception:
                    content = file_data.decode('latin-1', errors='ignore')
                    metadata['CSV:Encoding'] = 'latin-1'
            
            # Try to detect delimiter
            sample = content[:1024] if len(content) > 1024 else content
            delimiter = ','
            sniffer = csv.Sniffer()
            try:
                delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
                metadata['CSV:Delimiter'] = delimiter
            except Exception:
                metadata['CSV:Delimiter'] = delimiter
            
            # Parse CSV
            try:
                reader = csv.reader(content.splitlines(), delimiter=delimiter)
                rows = list(reader)
            except Exception:
                # Try with different delimiter
                try:
                    reader = csv.reader(content.splitlines(), delimiter=';')
                    rows = list(reader)
                    delimiter = ';'
                    metadata['CSV:Delimiter'] = delimiter
                except Exception:
                    reader = csv.reader(content.splitlines(), delimiter='\t')
                    rows = list(reader)
                    delimiter = '\t'
                    metadata['CSV:Delimiter'] = delimiter
            
            if not rows:
                metadata['CSV:RowCount'] = 0
                metadata['CSV:ColumnCount'] = 0
                if self.file_path:
                    import os
                    file_size = os.path.getsize(self.file_path)
                    metadata['File:FileSize'] = file_size
                    metadata['File:FileSizeBytes'] = file_size
                return metadata
            
            # Count rows and columns
            row_count = len(rows)
            column_count = max(len(row) for row in rows) if rows else 0
            
            metadata['CSV:RowCount'] = row_count
            metadata['CSV:ColumnCount'] = column_count
            
            # Check if first row is header
            has_header = False
            if row_count > 0:
                # Try to detect if first row is header (contains non-numeric values)
                first_row = rows[0]
                if first_row:
                    try:
                        # If first row contains mostly non-numeric values, it's likely a header
                        non_numeric_count = sum(1 for cell in first_row if cell and not cell.replace('.', '').replace('-', '').replace('+', '').isdigit())
                        if non_numeric_count > len(first_row) * 0.5:
                            has_header = True
                    except Exception:
                        pass
            
            if has_header and row_count > 0:
                header_row = rows[0]
                metadata['CSV:HasHeader'] = True
                metadata['CSV:HeaderRowCount'] = 1
                
                # Extract column names
                for i, col_name in enumerate(header_row[:50], 1):  # Limit to 50 columns
                    if col_name:
                        metadata[f'CSV:Column{i}:Name'] = col_name
                
                # Data rows start from row 2
                data_row_count = row_count - 1
                if data_row_count > 0:
                    metadata['CSV:DataRowCount'] = data_row_count
            else:
                metadata['CSV:HasHeader'] = False
                metadata['CSV:DataRowCount'] = row_count
            
            # Extract sample data (first few rows)
            sample_rows = min(5, row_count)
            for i in range(sample_rows):
                row = rows[i]
                if row:
                    row_data = delimiter.join(str(cell)[:50] for cell in row[:10])  # Limit to 10 columns, 50 chars per cell
                    if len(row_data) > 200:
                        row_data = row_data[:200] + '...'
                    metadata[f'CSV:Row{i+1}'] = row_data
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            else:
                metadata['File:FileSize'] = len(file_data)
                metadata['File:FileSizeBytes'] = len(file_data)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse CSV metadata: {str(e)}")

