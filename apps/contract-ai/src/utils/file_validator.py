# -*- coding: utf-8 -*-
"""
File Upload Validator - Security validation for uploaded files

Protects against:
- Path traversal attacks
- Malicious file extensions
- Oversized files
- MIME type mismatch
"""
import os
import re
import hashlib
from pathlib import Path
from typing import Tuple, Optional
from loguru import logger

# Security constants
ALLOWED_EXTENSIONS = {
    '.docx', '.doc', '.pdf', '.rtf', '.odt', '.xml', '.txt',
    '.xlsx', '.xls'  # For future spreadsheet support
}

ALLOWED_MIME_TYPES = {
    # Document types
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/msword',  # .doc
    'application/pdf',  # .pdf
    'application/rtf',  # .rtf
    'text/rtf',  # .rtf alternative
    'application/vnd.oasis.opendocument.text',  # .odt
    'application/xml',  # .xml
    'text/xml',  # .xml alternative
    'text/plain',  # .txt
    # Spreadsheet types (for future)
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'application/vnd.ms-excel',  # .xls
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MIN_FILE_SIZE = 10  # 10 bytes (avoid empty files)

# Dangerous patterns in filenames
DANGEROUS_PATTERNS = [
    r'\.\.',  # Path traversal
    r'[\\/]',  # Path separators
    r'[<>:"|?*]',  # Invalid characters in Windows
    r'^\.',  # Hidden files (starting with dot)
    r'\x00',  # Null bytes
]


class FileValidationError(Exception):
    """Custom exception for file validation errors"""
    pass


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks

    Args:
        filename: Original filename from upload

    Returns:
        Sanitized filename safe for filesystem

    Raises:
        FileValidationError: If filename is invalid
    """
    if not filename:
        raise FileValidationError("Filename is empty")

    # Get only the base name (remove any path components)
    filename = os.path.basename(filename)

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, filename):
            raise FileValidationError(f"Filename contains dangerous pattern: {filename}")

    # Remove any non-printable characters
    filename = ''.join(char for char in filename if char.isprintable())

    # Limit length
    if len(filename) > 255:
        # Keep extension, truncate name
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext

    if not filename:
        raise FileValidationError("Filename became empty after sanitization")

    return filename


def validate_file_extension(filename: str) -> str:
    """
    Validate file extension against whitelist

    Args:
        filename: Filename to validate

    Returns:
        Lowercase extension (e.g., '.docx')

    Raises:
        FileValidationError: If extension is not allowed
    """
    ext = Path(filename).suffix.lower()

    if not ext:
        raise FileValidationError("File has no extension")

    if ext not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        raise FileValidationError(
            f"File extension '{ext}' not allowed. Allowed: {allowed}"
        )

    return ext


def validate_file_size(file_size: int) -> None:
    """
    Validate file size is within acceptable range

    Args:
        file_size: Size in bytes

    Raises:
        FileValidationError: If size is invalid
    """
    if file_size < MIN_FILE_SIZE:
        raise FileValidationError(
            f"File too small ({file_size} bytes). Minimum: {MIN_FILE_SIZE} bytes"
        )

    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise FileValidationError(
            f"File too large ({actual_mb:.2f} MB). Maximum: {max_mb:.0f} MB"
        )


def validate_mime_type(file_content: bytes, expected_extension: str) -> None:
    """
    Validate MIME type matches file extension using magic bytes

    Args:
        file_content: First few bytes of file
        expected_extension: Expected file extension

    Raises:
        FileValidationError: If MIME type doesn't match
    """
    # Magic bytes for common file types
    magic_bytes = {
        '.pdf': b'%PDF',
        '.docx': b'PK\x03\x04',  # ZIP format (DOCX is zipped XML)
        '.xlsx': b'PK\x03\x04',  # ZIP format
        '.doc': b'\xD0\xCF\x11\xE0',  # OLE2 format
        '.xls': b'\xD0\xCF\x11\xE0',  # OLE2 format
        '.rtf': b'{\\rtf',
        '.xml': b'<?xml',
        '.txt': None,  # No magic bytes for plain text
        '.odt': b'PK\x03\x04',  # ZIP format
    }

    expected_magic = magic_bytes.get(expected_extension)

    # If no magic bytes defined, skip check
    if expected_magic is None:
        return

    # Check if file starts with expected magic bytes
    if not file_content.startswith(expected_magic):
        raise FileValidationError(
            f"File content doesn't match extension '{expected_extension}'. "
            f"Possible file type mismatch or corrupted file."
        )


def generate_safe_filepath(upload_dir: str, original_filename: str) -> Tuple[str, str]:
    """
    Generate safe filepath with hash to avoid collisions

    Args:
        upload_dir: Directory to save file
        original_filename: Original filename from upload

    Returns:
        Tuple of (full_path, safe_filename)
    """
    # Sanitize filename
    safe_name = sanitize_filename(original_filename)

    # Add hash to avoid collisions and track versions
    name, ext = os.path.splitext(safe_name)
    timestamp = hashlib.md5(str(os.urandom(16)).encode()).hexdigest()[:8]
    safe_name = f"{name}_{timestamp}{ext}"

    # Ensure upload directory exists
    os.makedirs(upload_dir, exist_ok=True)

    # Construct full path
    full_path = os.path.join(upload_dir, safe_name)

    # Double-check no path traversal occurred
    if not os.path.abspath(full_path).startswith(os.path.abspath(upload_dir)):
        raise FileValidationError("Path traversal detected in generated filepath")

    return full_path, safe_name


def validate_uploaded_file(
    file_data: bytes,
    filename: str,
    max_size: Optional[int] = None
) -> Tuple[str, int]:
    """
    Comprehensive validation of uploaded file

    Args:
        file_data: File content as bytes
        filename: Original filename
        max_size: Optional custom max size (defaults to MAX_FILE_SIZE)

    Returns:
        Tuple of (sanitized_filename, file_size)

    Raises:
        FileValidationError: If any validation fails
    """
    logger.info(f"Validating uploaded file: {filename}")

    # 1. Sanitize filename
    safe_filename = sanitize_filename(filename)
    logger.debug(f"Sanitized filename: {safe_filename}")

    # 2. Validate extension
    ext = validate_file_extension(safe_filename)
    logger.debug(f"Validated extension: {ext}")

    # 3. Validate size
    file_size = len(file_data)
    validate_file_size(file_size)
    logger.debug(f"Validated size: {file_size} bytes")

    # 4. Validate MIME type (magic bytes)
    if len(file_data) >= 10:  # Need at least 10 bytes for magic check
        validate_mime_type(file_data[:100], ext)
        logger.debug("MIME type validated")

    logger.info(f"File validation passed: {safe_filename} ({file_size} bytes)")

    return safe_filename, file_size


def save_uploaded_file_securely(
    file_data: bytes,
    filename: str,
    upload_dir: str,
    max_size: Optional[int] = None
) -> Tuple[str, str, int]:
    """
    Validate and save uploaded file securely

    Args:
        file_data: File content as bytes
        filename: Original filename
        upload_dir: Directory to save file
        max_size: Optional custom max size

    Returns:
        Tuple of (full_path, safe_filename, file_size)

    Raises:
        FileValidationError: If validation or saving fails
    """
    # Validate file
    safe_filename, file_size = validate_uploaded_file(file_data, filename, max_size)

    # Generate safe filepath
    full_path, final_filename = generate_safe_filepath(upload_dir, safe_filename)

    # Save file
    try:
        with open(full_path, 'wb') as f:
            f.write(file_data)
        logger.info(f"File saved securely: {full_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise FileValidationError(f"Failed to save file: {e}")

    return full_path, final_filename, file_size


__all__ = [
    'FileValidationError',
    'sanitize_filename',
    'validate_file_extension',
    'validate_file_size',
    'validate_mime_type',
    'validate_uploaded_file',
    'save_uploaded_file_securely',
    'ALLOWED_EXTENSIONS',
    'MAX_FILE_SIZE',
]
