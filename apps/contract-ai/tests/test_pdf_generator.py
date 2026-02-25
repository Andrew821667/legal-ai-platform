# -*- coding: utf-8 -*-
"""
Tests for pdf_generator.py - PDF Generation
"""
import pytest
import os
import tempfile
from pathlib import Path

from src.utils.pdf_generator import PDFGenerator


class TestPDFGeneratorInit:
    """Test PDF generator initialization"""

    def test_create_generator_default_config(self):
        """Test creating generator with default config"""
        generator = PDFGenerator()

        assert generator is not None
        assert generator.page_size is not None
        assert generator.styles is not None

    def test_create_generator_custom_config(self):
        """Test creating generator with custom config"""
        config = {
            'page_size': 'letter',
            'font_name': 'Helvetica'
        }

        generator = PDFGenerator(config=config)

        assert generator is not None

    def test_styles_created(self):
        """Test PDF styles are created"""
        generator = PDFGenerator()

        assert 'Title' in generator.styles
        assert 'Heading1' in generator.styles
        assert 'Heading2' in generator.styles
        assert 'Normal' in generator.styles


class TestContractReportGeneration:
    """Test contract report PDF generation"""

    def test_generate_simple_report(self, tmp_path):
        """Test generating simple contract report"""
        generator = PDFGenerator()

        output_path = tmp_path / "test_report.pdf"

        data = {
            'summary': 'Test contract analysis',
            'statistics': {
                'Total Risks': 5,
                'Critical Risks': 1,
                'Status': 'Reviewed'
            },
            'risks': [],
            'recommendations': []
        }

        metadata = {
            'Contract': 'Test Contract',
            'Date': '2024-01-15'
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Test Contract Report',
            data=data,
            metadata=metadata
        )

        # Check file was created
        assert os.path.exists(result)
        assert os.path.exists(output_path)

        # Check file is not empty
        assert os.path.getsize(output_path) > 0

    def test_generate_report_with_risks(self, tmp_path):
        """Test generating report with risks section"""
        generator = PDFGenerator()

        output_path = tmp_path / "report_with_risks.pdf"

        risks = [
            {
                'severity': 'critical',
                'type': 'financial',
                'description': 'High penalty clause',
                'impact': 'Significant financial exposure',
                'recommendation': 'Negotiate lower penalties'
            },
            {
                'severity': 'high',
                'type': 'legal',
                'description': 'Unclear liability terms',
                'impact': 'Legal uncertainty',
                'recommendation': 'Clarify liability scope'
            }
        ]

        data = {
            'summary': 'Contract has several risks',
            'statistics': {},
            'risks': risks,
            'recommendations': []
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Risk Analysis Report',
            data=data
        )

        assert os.path.exists(result)
        assert os.path.getsize(output_path) > 100  # Should have content

    def test_generate_report_with_many_risks(self, tmp_path):
        """Test report generation with many risks (pagination)"""
        generator = PDFGenerator()

        output_path = tmp_path / "report_many_risks.pdf"

        # Create 150 risks (exceeds MAX_RISKS_IN_REPORT)
        risks = []
        for i in range(150):
            risks.append({
                'severity': 'medium',
                'type': 'operational',
                'description': f'Risk number {i+1}',
                'impact': f'Impact {i+1}',
                'recommendation': f'Recommendation {i+1}'
            })

        data = {
            'summary': 'Many risks found',
            'statistics': {'Total Risks': len(risks)},
            'risks': risks,
            'recommendations': []
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Comprehensive Risk Report',
            data=data
        )

        # Should succeed and limit risks shown
        assert os.path.exists(result)

    def test_generate_report_with_recommendations(self, tmp_path):
        """Test report with recommendations section"""
        generator = PDFGenerator()

        output_path = tmp_path / "report_recommendations.pdf"

        recommendations = [
            'Review payment terms with legal team',
            'Negotiate shorter delivery timelines',
            'Add quality assurance clauses',
            'Include force majeure provisions'
        ]

        data = {
            'summary': 'Review needed',
            'statistics': {},
            'risks': [],
            'recommendations': recommendations
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Contract Recommendations',
            data=data
        )

        assert os.path.exists(result)

    def test_generate_report_with_metadata(self, tmp_path):
        """Test report generation with metadata table"""
        generator = PDFGenerator()

        output_path = tmp_path / "report_metadata.pdf"

        metadata = {
            'Contract ID': '12345',
            'Type': 'Supply Agreement',
            'Date': '2024-01-15',
            'Parties': 'Company A and Company B',
            'Status': 'Under Review'
        }

        data = {
            'summary': 'Contract review summary',
            'statistics': {},
            'risks': [],
            'recommendations': []
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Contract Metadata Report',
            data=data,
            metadata=metadata
        )

        assert os.path.exists(result)


class TestDisagreementLetterGeneration:
    """Test disagreement letter PDF generation"""

    def test_generate_simple_letter(self, tmp_path):
        """Test generating simple disagreement letter"""
        generator = PDFGenerator()

        output_path = tmp_path / "disagreement_letter.pdf"

        disagreement_data = {
            'contract_id': 'CONTRACT-123',
            'id': 1
        }

        objections = [
            {
                'section': 'Clause 5.2',
                'issue': 'Payment terms are too strict',
                'legal_basis': 'Article 314 Civil Code',
                'alternative': 'Suggest 30-day payment term',
                'priority': 'high'
            }
        ]

        result = generator.generate_disagreement_letter(
            output_path=str(output_path),
            disagreement_data=disagreement_data,
            objections=objections
        )

        assert os.path.exists(result)
        assert os.path.getsize(output_path) > 0

    def test_generate_letter_multiple_objections(self, tmp_path):
        """Test letter with multiple objections"""
        generator = PDFGenerator()

        output_path = tmp_path / "letter_multiple.pdf"

        disagreement_data = {
            'contract_id': 'CONTRACT-456',
            'id': 2
        }

        objections = [
            {
                'section': 'Clause 3.1',
                'issue': 'Delivery timeline unrealistic',
                'legal_basis': '',
                'alternative': 'Propose 60-day delivery',
                'priority': 'critical'
            },
            {
                'section': 'Clause 7.5',
                'issue': 'Penalty too high',
                'legal_basis': 'Market standards',
                'alternative': 'Reduce to 0.1% per day',
                'priority': 'high'
            },
            {
                'section': 'Clause 10.2',
                'issue': 'Unclear termination conditions',
                'legal_basis': '',
                'alternative': 'Add specific termination events',
                'priority': 'medium'
            }
        ]

        result = generator.generate_disagreement_letter(
            output_path=str(output_path),
            disagreement_data=disagreement_data,
            objections=objections
        )

        assert os.path.exists(result)
        # Should be larger with more content
        assert os.path.getsize(output_path) > 1000


class TestPDFElements:
    """Test individual PDF element creation"""

    def test_create_statistics_table(self):
        """Test statistics table creation"""
        generator = PDFGenerator()

        stats = {
            'Total Contracts': 100,
            'Reviewed': 85,
            'Pending': 15
        }

        table = generator._create_statistics_table(stats)

        assert table is not None

    def test_create_metadata_table(self):
        """Test metadata table creation"""
        generator = PDFGenerator()

        metadata = {
            'Field 1': 'Value 1',
            'Field 2': 'Value 2'
        }

        table = generator._create_metadata_table(metadata)

        assert table is not None

    def test_create_risks_section(self):
        """Test risks section creation"""
        generator = PDFGenerator()

        risks = [
            {
                'severity': 'high',
                'type': 'financial',
                'description': 'Risk description',
                'impact': 'Impact description',
                'recommendation': 'Recommendation'
            }
        ]

        elements = generator._create_risks_section(risks)

        assert len(elements) > 0

    def test_create_recommendations_section(self):
        """Test recommendations section creation"""
        generator = PDFGenerator()

        recommendations = [
            {'text': 'Recommendation 1'},
            {'text': 'Recommendation 2'}
        ]

        elements = generator._create_recommendations_section(recommendations)

        assert len(elements) > 0

    def test_create_footer(self):
        """Test footer creation"""
        generator = PDFGenerator()

        footer = generator._create_footer()

        assert footer is not None


class TestUnicodeSupport:
    """Test unicode and Russian text support"""

    def test_russian_text_in_report(self, tmp_path):
        """Test Russian text in PDF report"""
        generator = PDFGenerator()

        output_path = tmp_path / "russian_report.pdf"

        data = {
            'summary': 'Договор требует внимания юриста',
            'statistics': {
                'Всего рисков': 5,
                'Критических': 1,
                'Статус': 'На проверке'
            },
            'risks': [
                {
                    'severity': 'высокий',
                    'type': 'финансовый',
                    'description': 'Высокие штрафы',
                    'impact': 'Финансовые потери',
                    'recommendation': 'Пересмотреть условия'
                }
            ],
            'recommendations': ['Рекомендация 1', 'Рекомендация 2']
        }

        # Should not raise exception
        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Анализ договора',
            data=data
        )

        assert os.path.exists(result)

    def test_mixed_language_content(self, tmp_path):
        """Test mixed English and Russian content"""
        generator = PDFGenerator()

        output_path = tmp_path / "mixed_report.pdf"

        data = {
            'summary': 'Contract analysis / Анализ договора',
            'statistics': {
                'Total/Всего': 10,
                'Status/Статус': 'Review/Проверка'
            },
            'risks': [],
            'recommendations': []
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Mixed Language Report',
            data=data
        )

        assert os.path.exists(result)


class TestErrorHandling:
    """Test error handling"""

    def test_invalid_output_path(self):
        """Test handling of invalid output path"""
        generator = PDFGenerator()

        # Invalid path
        with pytest.raises(Exception):
            generator.generate_contract_report(
                output_path="/nonexistent/directory/report.pdf",
                title="Test",
                data={}
            )

    def test_empty_data(self, tmp_path):
        """Test generation with empty data"""
        generator = PDFGenerator()

        output_path = tmp_path / "empty_report.pdf"

        data = {
            'summary': '',
            'statistics': {},
            'risks': [],
            'recommendations': []
        }

        # Should still generate valid PDF
        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Empty Report',
            data=data
        )

        assert os.path.exists(result)

    def test_missing_data_fields(self, tmp_path):
        """Test generation with missing data fields"""
        generator = PDFGenerator()

        output_path = tmp_path / "partial_report.pdf"

        # Missing some fields
        data = {
            'summary': 'Summary only'
            # Missing statistics, risks, recommendations
        }

        # Should handle gracefully
        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Partial Report',
            data=data
        )

        assert os.path.exists(result)


class TestPageFormatting:
    """Test PDF page formatting"""

    def test_a4_page_size(self, tmp_path):
        """Test A4 page size"""
        config = {'page_size': 'A4'}
        generator = PDFGenerator(config=config)

        output_path = tmp_path / "a4_report.pdf"

        data = {'summary': 'Test', 'statistics': {}, 'risks': [], 'recommendations': []}

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='A4 Report',
            data=data
        )

        assert os.path.exists(result)

    def test_letter_page_size(self, tmp_path):
        """Test Letter page size"""
        config = {'page_size': 'letter'}
        generator = PDFGenerator(config=config)

        output_path = tmp_path / "letter_report.pdf"

        data = {'summary': 'Test', 'statistics': {}, 'risks': [], 'recommendations': []}

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Letter Report',
            data=data
        )

        assert os.path.exists(result)


class TestRealWorldScenarios:
    """Test real-world usage scenarios"""

    def test_comprehensive_contract_report(self, tmp_path):
        """Test generating comprehensive contract report"""
        generator = PDFGenerator()

        output_path = tmp_path / "comprehensive_report.pdf"

        data = {
            'summary': 'Detailed analysis of supply contract reveals several areas requiring attention.',
            'statistics': {
                'Contract Type': 'Supply Agreement',
                'Total Clauses': 25,
                'Risks Identified': 8,
                'Critical Risks': 2,
                'High Risks': 3,
                'Medium Risks': 3,
                'Review Status': 'Completed'
            },
            'risks': [
                {
                    'severity': 'critical',
                    'type': 'financial',
                    'description': 'Payment guarantee not specified',
                    'impact': 'High risk of non-payment',
                    'recommendation': 'Add bank guarantee clause'
                },
                {
                    'severity': 'high',
                    'type': 'operational',
                    'description': 'Delivery timeline too aggressive',
                    'impact': 'Risk of penalties for late delivery',
                    'recommendation': 'Negotiate 60-day timeline'
                }
            ],
            'recommendations': [
                'Engage legal counsel for final review',
                'Negotiate payment guarantee terms',
                'Extend delivery timeline to 60 days',
                'Add quality inspection clauses',
                'Include force majeure provisions'
            ]
        }

        metadata = {
            'Contract ID': 'SUPPLY-2024-001',
            'Date Created': '2024-01-15',
            'Parties': 'Acme Corp and Suppliers Ltd',
            'Value': '$500,000',
            'Term': '12 months'
        }

        result = generator.generate_contract_report(
            output_path=str(output_path),
            title='Supply Contract - Comprehensive Analysis',
            data=data,
            metadata=metadata
        )

        assert os.path.exists(result)
        # Should be substantial file
        assert os.path.getsize(output_path) > 5000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
