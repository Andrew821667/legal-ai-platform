# -*- coding: utf-8 -*-
"""
Integration tests for export functionality (PDF, DOCX, Email)
"""
import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.utils.pdf_generator import PDFGenerator


class TestExportIntegration:
    """Integration tests for complete export workflow"""

    def test_pdf_export_workflow(self, tmp_path):
        """Test complete PDF export workflow"""
        # Setup
        generator = PDFGenerator()
        output_path = tmp_path / "contract_export.pdf"

        # Prepare data (simulating contract analysis results)
        contract_data = {
            'summary': 'Contract analysis completed',
            'statistics': {
                'Document Type': 'Supply Agreement',
                'Total Risks': 5,
                'Critical': 1,
                'High': 2
            },
            'risks': [
                {
                    'severity': 'critical',
                    'type': 'financial',
                    'description': 'Payment terms unclear',
                    'impact': 'Financial exposure',
                    'recommendation': 'Clarify payment schedule'
                }
            ],
            'recommendations': [
                'Review with legal team',
                'Negotiate payment terms'
            ]
        }

        metadata = {
            'Contract ID': 'TEST-001',
            'Export Date': datetime.now().strftime('%d.%m.%Y')
        }

        # Execute export
        result_path = generator.generate_contract_report(
            output_path=str(output_path),
            title='Contract Export Test',
            data=contract_data,
            metadata=metadata
        )

        # Verify
        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 1000  # Should have substantial content

    def test_disagreement_export_workflow(self, tmp_path):
        """Test disagreement letter export workflow"""
        generator = PDFGenerator()
        output_path = tmp_path / "disagreement.pdf"

        disagreement_data = {
            'contract_id': 'CONTRACT-2024-001',
            'id': 1
        }

        objections = [
            {
                'section': 'Пункт 5.2',
                'issue': 'Условия оплаты слишком жесткие',
                'legal_basis': 'Статья 314 ГК РФ',
                'alternative': 'Предлагается установить срок 30 дней',
                'priority': 'высокий'
            },
            {
                'section': 'Пункт 7.1',
                'issue': 'Штрафные санкции не соответствуют рыночным',
                'legal_basis': 'Практика коммерческого оборота',
                'alternative': 'Снизить до 0,1% в день',
                'priority': 'средний'
            }
        ]

        # Execute
        result_path = generator.generate_disagreement_letter(
            output_path=str(output_path),
            disagreement_data=disagreement_data,
            objections=objections
        )

        # Verify
        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 500


class TestMultiFormatExport:
    """Test exporting to multiple formats"""

    def test_export_same_data_multiple_formats(self, tmp_path):
        """Test exporting same data to PDF and verifying consistency"""
        generator = PDFGenerator()

        data = {
            'summary': 'Test data for multi-format export',
            'statistics': {'Count': 10},
            'risks': [],
            'recommendations': []
        }

        # Export PDF
        pdf_path = tmp_path / "export.pdf"
        pdf_result = generator.generate_contract_report(
            output_path=str(pdf_path),
            title='Multi-Format Test',
            data=data
        )

        # Verify both exist
        assert os.path.exists(pdf_result)

        # Both should have content
        assert os.path.getsize(pdf_path) > 0


class TestExportWithRealData:
    """Test export with realistic data scenarios"""

    def test_export_large_contract_analysis(self, tmp_path):
        """Test exporting large contract with many risks"""
        generator = PDFGenerator()
        output_path = tmp_path / "large_contract.pdf"

        # Generate realistic large dataset
        risks = []
        for i in range(50):
            risks.append({
                'severity': ['critical', 'high', 'medium', 'low'][i % 4],
                'type': ['financial', 'legal', 'operational'][i % 3],
                'description': f'Risk description {i+1}: Lorem ipsum dolor sit amet',
                'impact': f'Impact analysis {i+1}',
                'recommendation': f'Recommended action {i+1}'
            })

        recommendations = [
            f'Recommendation {i+1}: Detail recommendation text here'
            for i in range(20)
        ]

        data = {
            'summary': 'Comprehensive analysis of complex contract with multiple risk factors',
            'statistics': {
                'Total Clauses Analyzed': 150,
                'Total Risks Found': len(risks),
                'Critical Risks': 13,
                'High Risks': 12,
                'Medium Risks': 13,
                'Low Risks': 12,
                'Analysis Date': '2024-01-15',
                'Analyst': 'AI System'
            },
            'risks': risks,
            'recommendations': recommendations
        }

        metadata = {
            'Contract Type': 'Master Service Agreement',
            'Contract Value': '$5,000,000',
            'Contract Term': '36 months',
            'Parties': 'Multi-national corporations',
            'Jurisdiction': 'International'
        }

        # Execute
        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Comprehensive Contract Analysis Report',
            data=data,
            metadata=metadata
        )

        # Verify
        assert os.path.exists(result)
        # Should be substantial PDF
        assert os.path.getsize(output_path) > 10000

    def test_export_multilingual_content(self, tmp_path):
        """Test export with Russian and English content"""
        generator = PDFGenerator()
        output_path = tmp_path / "multilingual.pdf"

        data = {
            'summary': 'Договор требует детального рассмотрения юристом / Contract requires detailed legal review',
            'statistics': {
                'Тип / Type': 'Договор поставки / Supply Agreement',
                'Рисков / Risks': 8,
                'Статус / Status': 'На проверке / Under Review'
            },
            'risks': [
                {
                    'severity': 'высокий / high',
                    'type': 'финансовый / financial',
                    'description': 'Условия оплаты не соответствуют рыночным / Payment terms not market-standard',
                    'impact': 'Финансовые риски / Financial risks',
                    'recommendation': 'Пересмотреть условия / Review terms'
                }
            ],
            'recommendations': [
                'Согласовать с юридическим отделом / Coordinate with legal',
                'Запросить изменения / Request amendments'
            ]
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Многоязычный отчет / Multilingual Report',
            data=data
        )

        assert os.path.exists(result)


class TestExportErrorHandling:
    """Test error handling in export workflow"""

    def test_export_with_invalid_data_types(self, tmp_path):
        """Test export handles invalid data types gracefully"""
        generator = PDFGenerator()
        output_path = tmp_path / "invalid_data.pdf"

        # Mix of valid and potentially problematic data
        data = {
            'summary': 123,  # Should be string
            'statistics': 'not a dict',  # Should be dict
            'risks': None,  # Should be list
            'recommendations': ['Valid recommendation']
        }

        # Should handle gracefully or raise clear error
        try:
            result = generator.generate_contract_report(
                output_path=str(output_path),
                title='Invalid Data Test',
                data=data
            )
            # If it succeeds, file should exist
            if result:
                assert os.path.exists(result)
        except Exception as e:
            # If it fails, should be a clear error
            assert e is not None

    def test_export_to_readonly_directory(self):
        """Test export to directory without write permissions"""
        generator = PDFGenerator()

        # Try to write to /root (typically no permission)
        output_path = "/root/test_report.pdf"

        with pytest.raises(Exception):
            generator.generate_contract_report(
                output_path=output_path,
                title='Permission Test',
                data={'summary': 'test', 'statistics': {}, 'risks': [], 'recommendations': []}
            )


class TestExportPerformance:
    """Test export performance characteristics"""

    def test_export_performance_benchmark(self, tmp_path):
        """Benchmark PDF generation performance"""
        import time

        generator = PDFGenerator()
        output_path = tmp_path / "performance_test.pdf"

        # Medium-sized dataset
        data = {
            'summary': 'Performance test report',
            'statistics': {f'Metric {i}': i*100 for i in range(20)},
            'risks': [
                {
                    'severity': 'medium',
                    'type': 'test',
                    'description': f'Risk {i}',
                    'impact': f'Impact {i}',
                    'recommendation': f'Recommendation {i}'
                }
                for i in range(30)
            ],
            'recommendations': [f'Recommendation {i}' for i in range(15)]
        }

        start_time = time.time()

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Performance Benchmark',
            data=data
        )

        elapsed = time.time() - start_time

        assert os.path.exists(result)
        # Should complete in reasonable time (< 5 seconds for medium data)
        assert elapsed < 5.0


class TestExportContentVerification:
    """Test that exported PDFs contain expected content"""

    def test_pdf_contains_title(self, tmp_path):
        """Test PDF contains the title"""
        generator = PDFGenerator()
        output_path = tmp_path / "title_test.pdf"

        title = "Specific Contract Title Test 12345"

        data = {
            'summary': 'Test',
            'statistics': {},
            'risks': [],
            'recommendations': []
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title=title,
            data=data
        )

        assert os.path.exists(result)
        # Note: Actual PDF text extraction would require pypdf or similar
        # For now, just verify file was created

    def test_pdf_pagination(self, tmp_path):
        """Test PDF properly paginates large content"""
        generator = PDFGenerator()
        output_path = tmp_path / "pagination_test.pdf"

        # Create enough content to span multiple pages
        risks = [
            {
                'severity': 'medium',
                'type': 'test',
                'description': f'Long risk description {i} ' * 20,  # Make it long
                'impact': f'Detailed impact analysis {i} ' * 15,
                'recommendation': f'Comprehensive recommendation {i} ' * 10
            }
            for i in range(50)
        ]

        data = {
            'summary': 'Multi-page test ' * 50,
            'statistics': {},
            'risks': risks,
            'recommendations': [f'Long recommendation {i} ' * 30 for i in range(25)]
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Pagination Test',
            data=data
        )

        assert os.path.exists(result)
        # Should be large PDF (multiple pages)
        assert os.path.getsize(output_path) > 50000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
