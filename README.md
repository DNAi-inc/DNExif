# DNExif

A powerful **100% pure Python** metadata manager for reading and writing metadata from image files.

## Overview

DNExif is a complete native Python implementation with **NO external dependencies**. All metadata parsing is done by directly reading binary file structures in pure Python.

It provides comprehensive metadata extraction and manipulation capabilities, supporting multiple metadata standards including EXIF, IPTC, and XMP across various image formats.

**Key Features:**
- 100% Pure Python - No external dependencies
- Direct binary parsing - No wrappers or subprocess calls
- Clean, intuitive API
- Supports EXIF, IPTC, and XMP metadata
- Metadata normalization and conflict resolution
- Privacy-focused metadata stripping with PII detection
- Metadata diffing and comparison tools
- Image hash calculation for integrity verification
- Batch processing capabilities
- Support for 120+ file formats

## Features

### Core Metadata Support
- **EXIF Metadata**: Read and write EXIF data from JPEG, TIFF, and RAW files
- **IPTC Metadata**: Support for IPTC metadata standards
- **XMP Metadata**: XML-based metadata support
- **MakerNote Parsing**: Manufacturer-specific metadata (Canon, Nikon, Sony, Fujifilm, Olympus, Panasonic, Pentax, Samsung, and more)
- **DICOM Support**: Comprehensive medical imaging metadata support with 5,200+ DICOM data elements, private tag registry, and full DICOM Standard PS3.6 compliance

### Advanced Features
- **Metadata Normalization**: Resolve conflicts between multiple metadata sources, choose best timestamps, and unify date fields
- **Privacy & Stripping**: Remove sensitive metadata with configurable presets (minimal, standard, strict) and PII detection
- **Metadata Diffing**: Compare metadata between files and generate detailed diff reports
- **Image Hash Calculation**: Calculate and embed image data hashes for integrity verification
- **Batch Operations**: Process multiple files efficiently with batch read/write operations
- **Metadata Utilities**: Copy, merge, filter, and summarize metadata across files

### Format Support
- **120+ File Formats**: Images, RAW, video, audio, documents, medical imaging, GPS data, and more
- **Read Support**: Comprehensive metadata extraction from all supported formats
- **Write Support**: Full write support for JPEG, TIFF, PNG, WebP, GIF, HEIC, and many RAW formats

### Developer Experience
- **Clean API**: Simple, intuitive Python API with context manager support
- **Command-Line Interface**: CLI tool with standard metadata syntax
- **Type Hints**: Full type annotation support for better IDE integration
- **Error Handling**: Comprehensive exception hierarchy for robust error handling

## Installation

DNExif is available directly from GitHub. Install using pip:

```bash
pip install git+https://github.com/DNAi-inc/dnexif.git
```

Or clone the repository and install:

```bash
git clone https://github.com/DNAi-inc/dnexif.git
cd dnexif
pip install .
```

## Quick Start

### Python API

#### Basic Usage

```python
from dnexif import DNExif

# Read metadata from an image
with DNExif('image.jpg') as exif:
    # Get all metadata
    metadata = exif.get_all_metadata()
    
    # Get specific EXIF tag
    camera = exif.get_tag('EXIF:Make')
    model = exif.get_tag('EXIF:Model')
    
    # Write metadata
    exif.set_tag('EXIF:Artist', 'Your Name')
    exif.save()
```

#### Advanced Features

```python
from dnexif import (
    DNExif,
    normalize_metadata,
    strip_metadata,
    PrivacyPreset,
    PriorityConfig,
    diff_metadata,
    batch_read_metadata,
    calculate_image_data_hash
)

# Metadata normalization
normalized = normalize_metadata(metadata, priority_config=PriorityConfig())

# Privacy-focused metadata stripping
stripped_metadata = strip_metadata(
    metadata,
    preset=PrivacyPreset.STRICT  # or MINIMAL, STANDARD
)

# Compare metadata between files
diff_result = diff_metadata(metadata1, metadata2)

# Batch processing
files = ['image1.jpg', 'image2.jpg', 'image3.jpg']
all_metadata = batch_read_metadata(files)

# Image hash calculation
hash_value = calculate_image_data_hash('image.jpg')
```

### Command Line

```bash
# Read all metadata
dnexif image.jpg

# Read specific tag
dnexif -EXIF:Make image.jpg

# Write metadata
dnexif -EXIF:Artist="Your Name" image.jpg
```

## Supported Formats

DNExif supports **120+ file formats** across multiple categories:

### Image Formats
JPEG (.jpg, .jpeg, .jph, .jfif), TIFF (.tif, .tiff), PNG (.png), HEIC/HEIF (.heic, .heif), AVIF (.avif), JPEG XL (.jxl), BMP (.bmp), SVG (.svg), PSD (.psd), GIF (.gif), WebP (.webp), ICO (.ico), PCX (.pcx), TGA (.tga), and more

### RAW Formats
Canon (.cr2, .cr3, .crw), Nikon (.nef, .nrw), Sony (.arw, .srf, .sr2), Fujifilm (.raf), Olympus (.orf), Panasonic (.rw2), Pentax (.pef), Sigma (.x3f), Kodak (.dcr), Leica (.dng), and 30+ more RAW formats

### Video Formats
MP4 (.mp4), QuickTime (.mov), AVI (.avi), MKV (.mkv), WebM (.webm), M4V (.m4v), 3GP (.3gp), and more

### Audio Formats
MP3 (.mp3), WAV (.wav), FLAC (.flac), AAC (.aac), OGG (.ogg), M4A (.m4a), WMA (.wma), Opus (.opus), DSF (.dsf)

### Document Formats
PDF (.pdf), and more

### Specialized Formats
- **Medical Imaging**: DICOM (.dcm, .dicom) - **Extensive Support**: 5,200+ DICOM data elements, private tag registry (GE Medical Systems, etc.), full DICOM Standard PS3.6 compliance, sequence parsing, big/little-endian support, and binary block formatting
- **GPS Data**: GPX (.gpx), KML (.kml)
- **Thermal Imaging**: FLIR SEQ (.seq)
- **Astronomical**: XISF (.xisf), FITS (.fts)
- **HDR Images**: PFM (.pfm), HDR (.hdr), EXR (.exr)
- **Archives**: ZIP (.zip), RAR (.rar), 7Z (.7z)
- **Network Capture**: PCAP (.pcap, .pcapng)
- **Windows Formats**: EXE (.exe), DLL (.dll), LNK (.lnk), URL (.url)
- **Fonts**: WOFF (.woff), WOFF2 (.woff2)

For a complete list, see the `SUPPORTED_FORMATS` constant in `dnexif/core.py`.

## Supported Metadata Standards

- **EXIF**: Exchangeable Image File Format
- **IPTC**: International Press Telecommunications Council
- **XMP**: Extensible Metadata Platform
- **DICOM**: Digital Imaging and Communications in Medicine - Comprehensive support with 5,200+ data elements from DICOM Standard PS3.6, including:
  - Standard DICOM tags (all groups: 0002, 0008, 0010, 0018, 0020, 0028, 0040, etc.)
  - Private tag registry for manufacturer-specific tags (GE Medical Systems, Siemens, Philips, etc.)
  - Sequence (SQ) parsing for nested data structures
  - Big-endian and little-endian byte order support
  - Value Representation (VR) handling for all DICOM data types
  - UID name registry and formatting
  - Binary block formatting and extraction

## Testing

```bash
# Install test dependencies
pip install -e ".[test]"

# Run all tests
pytest tests/ -v
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black dnexif/

# Type checking
mypy dnexif/
```

## Implementation Details

DNExif is a **100% pure Python implementation** that:

- Parses EXIF data by directly reading TIFF/EXIF binary structures
- Extracts IPTC metadata from JPEG APP13 segments
- Reads XMP metadata from XML packets embedded in image files
- Supports both little-endian and big-endian byte orders
- Handles multiple IFD (Image File Directory) structures

All metadata parsing is done natively by reading and interpreting binary file formats.

## Known Limitations

### Format-Specific Limitations

1. **CR2 Format (Canon RAW)**: Sub-IFD parsing needs improvement. Some MakerNote tags may not be extracted correctly.

2. **CRW Format (Canon RAW)**: HEAP-based format parsing needs implementation. CRW uses a proprietary HEAP-based format that requires special parsing.

3. **MOS Format (Leaf RAW)**: Parser improvements needed. Some metadata blocks may not be extracted.

4. **DCR Format (Kodak RAW)**: Parser improvements needed. Some tag values may not be decoded correctly.

### General Limitations

1. **PROCESSING_SOFTWARE Tag**: DNExif always adds a `PROCESSING_SOFTWARE` tag to indicate DNExif processed the file (any type of file). This is intentional and helps track which tool processed the file.

2. **MakerNote Parsing**: Some MakerNote parsers may miss metadata in unusual locations if the length parameter is too small. The parser uses heuristics to determine metadata block sizes, which may not always be accurate.

3. **Tag Descriptions**: Tag descriptions may change in minor updates as we improve format compatibility.

4. **Memory Usage**: For very large files (>100MB), memory usage may be higher due to Python's memory management. Consider using read-only mode for large files when possible.

5. **Performance**: DNExif may be slower for some operations, especially batch processing of many files. This is expected for a pure Python implementation.

6. **Writing Support**: While reading is supported for all 122 formats, writing support is more limited. JPEG, TIFF, PNG, WebP, GIF, and some RAW formats have full write support. Other formats may have limited or no write support.

### Format Capabilities

DNExif extracts comprehensive metadata from supported formats:

- **HEIC/HEIF**: Extracts 172/162 tags
- **ARW (Sony RAW)**: Extracts 302 tags
- **NEF (Nikon RAW)**: Extracts 239 tags
- **RAF (Fujifilm RAW)**: Extracts 151 tags
- **DS_Store**: Extracts 31 tags

DNExif extracts comprehensive metadata from all supported formats, providing detailed information for various use cases.

## License

**Dual-Licensed**: DNExif is available under two license options:

### DNAi Free License v1.1

For **non-commercial use** (personal, academic, educational, research, development, testing, or evaluation):

- Free to use, modify, and distribute
- Non-commercial use only
- Must include license and copyright notices
- No commercial use (requires commercial license)

See `LICENSE` file for full terms.

### DNAi Commercial License v1.1

For **commercial use** (business, production, SaaS, commercial products):

- Commercial use permitted
- Integration into commercial products
- Internal business use
- Distribution in commercial products
- Cannot redistribute as standalone product
- Cannot provide as standalone hosted service

**Commercial licenses are available from DNAi inc.** Contact DNAi for commercial licensing options.

See `LICENSE-COMMERCIAL` file for full terms.

### License Precedence

If you have obtained a commercial subscription, purchased a commercial license, or otherwise entered into a commercial agreement with DNAi inc., your use of the Software is governed exclusively by the **DNAi Commercial License v1.1**, which supersedes any other license text.

**Copyright © 2025 DNAi inc.** All rights reserved.

## API Reference

For complete API documentation, see [tests/API.md](tests/API.md).

### Key Modules

- **`dnexif.core`**: Main DNExif class for reading/writing metadata
- **`dnexif.metadata_normalizer`**: Metadata normalization and conflict resolution
- **`dnexif.metadata_stripper`**: Privacy-focused metadata removal
- **`dnexif.metadata_diff`**: Metadata comparison and diffing
- **`dnexif.image_hash_calculator`**: Image hash calculation
- **`dnexif.metadata_utils`**: Batch operations and utilities
- **`dnexif.advanced_features`**: Advanced metadata manipulation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

**Note**: By contributing, you grant DNAi inc. a perpetual right to incorporate your contributions into both free and commercial editions of the software (as per the DNAi Free License v1.1, Section 3(e)).

