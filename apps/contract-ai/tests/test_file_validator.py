# -*- coding: utf-8 -*-
"""
Tests for file_validator.py - Security critical module
"""
import pytest
import os
import tempfile
from pathlib import Path

from src.utils.file_validator import (
    FileValidationError,
    validate_filename,
    validate_file_size,
    validate_mime_type,
    sanitize_filename,
    save_uploaded_file_securely,
    is_allowed_extension
)


class TestFilenameValidation:
    """Test filename validation and sanitization"""

    def test_valid_filename(self):
        """Test valid filenames pass validation"""
        valid_names = [
            "contract.docx",
            "agreement_2024.pdf",
            "document-final.xml",
            "file123.txt"
        ]
        for name in valid_names:
            assert validate_filename(name) == True

    def test_path_traversal_attack(self):
        """Test path traversal patterns are rejected"""
        malicious_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "test/../../../secret.txt",
            "normal..hidden",
        ]
        for name in malicious_names:
            with pytest.raises(FileValidationError, match="path traversal"):
                validate_filename(name)

    def test_null_byte_attack(self):
        """Test null byte injection is rejected"""
        with pytest.raises(FileValidationError, match="null bytes"):
            validate_filename("contract\x00.pdf")

    def test_hidden_files_rejected(self):
        """Test hidden files (starting with .) are rejected"""
        with pytest.raises(FileValidationError, match="hidden file"):
            validate_filename(".htaccess")

    def test_path_separators_rejected(self):
        """Test path separators in filename are rejected"""
        bad_names = [
            "path/to/file.pdf",
            "path\\to\\file.docx",
        ]
        for name in bad_names:
            with pytest.raises(FileValidationError):
                validate_filename(name)

    def test_invalid_windows_chars_rejected(self):
        """Test invalid Windows characters are rejected"""
        bad_names = [
            "file<test>.docx",
            "file:name.pdf",
            "file|pipe.txt",
            "file?question.xml",
            'file"quote.docx',
            "file*star.pdf",
        ]
        for name in bad_names:
            with pytest.raises(FileValidationError, match="invalid characters"):
                validate_filename(name)

    def test_filename_too_long(self):
        """Test very long filenames are rejected"""
        long_name = "a" * 300 + ".pdf"
        with pytest.raises(FileValidationError, match="too long"):
            validate_filename(long_name)

    def test_empty_filename(self):
        """Test empty filename is rejected"""
        with pytest.raises(FileValidationError, match="empty"):
            validate_filename("")


class TestFilenameSanitization:
    """Test filename sanitization"""

    def test_sanitize_removes_path_traversal(self):
        """Test sanitization removes path traversal"""
        assert sanitize_filename("../test.pdf") == "test.pdf"
        assert sanitize_filename("../../etc/passwd") == "passwd"

    def test_sanitize_removes_special_chars(self):
        """Test sanitization removes special characters"""
        assert sanitize_filename("file<test>.pdf") == "filetest.pdf"
        assert sanitize_filename("file:name.docx") == "filename.docx"

    def test_sanitize_preserves_valid_chars(self):
        """Test sanitization preserves valid characters"""
        assert sanitize_filename("valid-file_123.pdf") == "valid-file_123.pdf"

    def test_sanitize_handles_unicode(self):
        """Test sanitization handles unicode correctly"""
        result = sanitize_filename("договор_2024.pdf")
        assert ".pdf" in result
        assert len(result) > 0


class TestFileSizeValidation:
    """Test file size validation"""

    def test_valid_file_size(self):
        """Test valid file sizes pass"""
        valid_sizes = [100, 1024, 1024 * 1024, 10 * 1024 * 1024]
        for size in valid_sizes:
            assert validate_file_size(size) == True

    def test_file_too_small(self):
        """Test files smaller than minimum are rejected"""
        with pytest.raises(FileValidationError, match="too small"):
            validate_file_size(5)  # Less than MIN_FILE_SIZE_BYTES (10)

    def test_file_too_large(self):
        """Test files larger than maximum are rejected"""
        max_size = 50 * 1024 * 1024  # 50 MB
        with pytest.raises(FileValidationError, match="too large"):
            validate_file_size(max_size + 1)

    def test_negative_size_rejected(self):
        """Test negative file size is rejected"""
        with pytest.raises(FileValidationError):
            validate_file_size(-100)

    def test_custom_limits(self):
        """Test custom size limits work"""
        # Custom max size
        assert validate_file_size(100, max_size=200) == True

        with pytest.raises(FileValidationError):
            validate_file_size(300, max_size=200)


class TestMimeTypeValidation:
    """Test MIME type validation"""

    def test_allowed_mime_types(self):
        """Test allowed MIME types pass validation"""
        allowed_types = [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
            "application/msword",  # DOC
            "application/pdf",
            "application/xml",
            "text/xml",
            "text/plain",
        ]

        for mime_type in allowed_types:
            assert validate_mime_type(mime_type) == True

    def test_disallowed_mime_types(self):
        """Test disallowed MIME types are rejected"""
        bad_types = [
            "application/x-executable",
            "application/x-sh",
            "application/javascript",
            "text/html",
            "image/jpeg",  # Not allowed by default
            "video/mp4",
        ]

        for mime_type in bad_types:
            with pytest.raises(FileValidationError, match="not allowed"):
                validate_mime_type(mime_type)


class TestExtensionValidation:
    """Test file extension validation"""

    def test_allowed_extensions(self):
        """Test allowed extensions"""
        allowed = ["contract.docx", "file.pdf", "doc.xml", "data.txt"]
        for filename in allowed:
            assert is_allowed_extension(filename) == True

    def test_disallowed_extensions(self):
        """Test disallowed extensions"""
        disallowed = ["script.exe", "malware.sh", "code.py", "page.html"]
        for filename in disallowed:
            assert is_allowed_extension(filename) == False

    def test_case_insensitive(self):
        """Test extension check is case insensitive"""
        assert is_allowed_extension("FILE.DOCX") == True
        assert is_allowed_extension("file.PDF") == True

    def test_no_extension(self):
        """Test files without extension are rejected"""
        assert is_allowed_extension("README") == False


class TestSecureFileSaving:
    """Test secure file saving functionality"""

    def test_save_valid_file(self):
        """Test saving a valid file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_data = b"This is a test DOCX file content"
            filename = "test_contract.docx"

            result_path, saved_name, size = save_uploaded_file_securely(
                file_data=file_data,
                filename=filename,
                upload_dir=tmpdir
            )

            # Check file was saved
            assert os.path.exists(result_path)

            # Check filename was sanitized
            assert saved_name == filename

            # Check size is correct
            assert size == len(file_data)

            # Check content is correct
            with open(result_path, 'rb') as f:
                assert f.read() == file_data

    def test_save_file_with_malicious_name(self):
        """Test saving file with malicious filename"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_data = b"Content"
            malicious_name = "../../../etc/passwd"

            result_path, saved_name, size = save_uploaded_file_securely(
                file_data=file_data,
                filename=malicious_name,
                upload_dir=tmpdir
            )

            # Check file was saved in correct directory
            assert tmpdir in result_path

            # Check filename was sanitized
            assert ".." not in saved_name
            assert "/" not in saved_name

    def test_save_file_too_large(self):
        """Test saving file that exceeds size limit"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create data larger than max allowed
            file_data = b"x" * (51 * 1024 * 1024)  # 51 MB

            with pytest.raises(FileValidationError, match="too large"):
                save_uploaded_file_securely(
                    file_data=file_data,
                    filename="large.pdf",
                    upload_dir=tmpdir
                )

    def test_save_creates_directory_if_not_exists(self):
        """Test saving creates upload directory if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            upload_dir = os.path.join(tmpdir, "new", "nested", "dir")

            file_data = b"Test content"

            result_path, _, _ = save_uploaded_file_securely(
                file_data=file_data,
                filename="test.pdf",
                upload_dir=upload_dir
            )

            # Check directory was created
            assert os.path.exists(upload_dir)
            assert os.path.exists(result_path)

    def test_save_file_name_collision(self):
        """Test handling of filename collisions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = "contract.docx"

            # Save first file
            save_uploaded_file_securely(
                file_data=b"First",
                filename=filename,
                upload_dir=tmpdir
            )

            # Save second file with same name
            path2, name2, _ = save_uploaded_file_securely(
                file_data=b"Second",
                filename=filename,
                upload_dir=tmpdir
            )

            # Check second file has different name (timestamp added)
            assert name2 != filename
            assert "contract" in name2
            assert ".docx" in name2

    def test_save_empty_file_rejected(self):
        """Test empty files are rejected"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileValidationError, match="too small"):
                save_uploaded_file_securely(
                    file_data=b"",
                    filename="empty.pdf",
                    upload_dir=tmpdir
                )


class TestEdgeCases:
    """Test edge cases and security boundaries"""

    def test_unicode_filename_handling(self):
        """Test handling of unicode filenames"""
        unicode_names = [
            "договор.docx",
            "文档.pdf",
            "dökümént.xml",
        ]

        for name in unicode_names:
            sanitized = sanitize_filename(name)
            # Should not raise exception
            assert len(sanitized) > 0
            assert "." in sanitized  # Extension preserved

    def test_very_long_extension(self):
        """Test handling of very long extensions"""
        name = "file." + "x" * 100
        # Should handle gracefully
        sanitized = sanitize_filename(name)
        assert len(sanitized) <= 255

    def test_multiple_dots_in_filename(self):
        """Test filename with multiple dots"""
        name = "my.contract.final.v2.docx"
        assert validate_filename(name) == True
        assert sanitize_filename(name) == name

    def test_whitespace_in_filename(self):
        """Test handling of whitespace"""
        name = "my contract file.docx"
        # Spaces should be allowed
        assert validate_filename(name) == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
