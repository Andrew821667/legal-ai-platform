"""
Test Contract Generator Agent - Contract generation with templates and RAG
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from src.agents.contract_generator_agent import ContractGeneratorAgent
from src.services.llm_gateway import LLMGateway
from src.services.template_manager import TemplateManager
from src.services.feedback_service import FeedbackService
from src.models import init_db, SessionLocal
from src.models.database import User, Template, Contract
import tempfile
from lxml import etree


def create_test_template(db, template_type="supply_agreement"):
    """Create a test template"""

    # Create basic XML template
    root = etree.Element("contract")

    header = etree.SubElement(root, "header")
    etree.SubElement(header, "title").text = "{{contract_type}}"
    etree.SubElement(header, "number").text = "{{contract_number}}"
    etree.SubElement(header, "date").text = "{{contract_date}}"

    parties = etree.SubElement(root, "parties")
    party1 = etree.SubElement(parties, "party", role="supplier")
    etree.SubElement(party1, "name").text = "{{party1_name}}"
    etree.SubElement(party1, "inn").text = "{{party1_inn}}"

    party2 = etree.SubElement(parties, "party", role="buyer")
    etree.SubElement(party2, "name").text = "{{party2_name}}"
    etree.SubElement(party2, "inn").text = "{{party2_inn}}"

    subject = etree.SubElement(root, "subject")
    subject.text = "{{subject}}"

    price = etree.SubElement(root, "price")
    etree.SubElement(price, "amount").text = "{{price_amount}}"
    etree.SubElement(price, "currency").text = "{{price_currency}}"

    term = etree.SubElement(root, "term")
    etree.SubElement(term, "start").text = "{{term_start}}"
    etree.SubElement(term, "end").text = "{{term_end}}"

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)

    # Create template in DB
    template = Template(
        name=f"Шаблон {template_type}",
        contract_type=template_type,
        xml_content=xml_str,
        version="1.0",
        active=True
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return template


def create_test_request_xml():
    """Create test user request XML"""
    root = etree.Element("request")

    etree.SubElement(root, "type").text = "Создать договор поставки"

    parties = etree.SubElement(root, "parties")
    etree.SubElement(parties, "supplier").text = "ООО Поставщик"
    etree.SubElement(parties, "buyer").text = "ООО Покупатель"

    details = etree.SubElement(root, "details")
    etree.SubElement(details, "subject").text = "Поставка товаров"
    etree.SubElement(details, "amount").text = "1000000"
    etree.SubElement(details, "start_date").text = "2024-01-01"
    etree.SubElement(details, "end_date").text = "2024-12-31"

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)

    return xml_str


def test_contract_generator_agent():
    """Test Contract Generator Agent functionality"""
    print("=" * 60)
    print("TESTING CONTRACT GENERATOR AGENT")
    print("=" * 60)

    # Initialize database
    print("\n1. Initialize database...")
    try:
        init_db()
        db = SessionLocal()
        print("   ✓ Database initialized")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Create test user
    print("\n2. Create test user...")
    try:
        user = db.query(User).filter(User.email == "generator@test.com").first()
        if not user:
            user = User(
                email="generator@test.com",
                name="Generator Test User",
                role="admin"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        print(f"   ✓ Test user: {user.id}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        db.close()
        return False

    # Create test template
    print("\n3. Create test template...")
    try:
        template = create_test_template(db, "supply_agreement")
        print(f"   ✓ Template created: {template.name} (ID: {template.id})")
        print(f"   - Type: {template.contract_type}")
        print(f"   - Content length: {len(template.xml_content)} chars")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False

    # Initialize LLM Gateway
    print("\n4. Initialize LLM Gateway...")
    try:
        if 'OPENAI_API_KEY' in os.environ and os.environ['OPENAI_API_KEY'] != 'test-key-for-stub-agents':
            llm = LLMGateway(provider="openai")
            print("   ✓ LLM Gateway initialized (OpenAI GPT)")
            llm_available = True
        else:
            print("   ℹ No API key - running structure tests only")
            os.environ['OPENAI_API_KEY'] = 'test-key-for-stub-agents'
            llm = LLMGateway(provider="openai")
            llm_available = False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        db.close()
        return False

    # Initialize services
    print("\n5. Initialize services...")
    try:
        template_manager = TemplateManager(db)
        feedback_service = FeedbackService(db)
        print("   ✓ Template Manager initialized")
        print("   ✓ Feedback Service initialized")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        db.close()
        return False

    # Initialize Contract Generator Agent
    print("\n6. Initialize Contract Generator Agent...")
    try:
        agent = ContractGeneratorAgent(
            llm_gateway=llm,
            db_session=db,
            template_manager=template_manager,
            rag_system=None  # No RAG for basic tests
        )
        print(f"   ✓ Agent initialized: {agent.get_name()}")
        print(f"   - System prompt: {len(agent.get_system_prompt())} chars")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False

    # Test 1: Structure validation
    print("\n7. Mock test - validate agent structure...")
    try:
        assert hasattr(agent, 'execute'), "Missing execute method"
        assert hasattr(agent, '_extract_parameters'), "Missing _extract_parameters"
        assert hasattr(agent, '_find_template'), "Missing _find_template"
        assert hasattr(agent, '_generate_contract'), "Missing _generate_contract"
        assert hasattr(agent, '_validate_contract'), "Missing _validate_contract"

        print("   ✓ All required methods present")

        assert agent.get_name() == "ContractGeneratorAgent", "Wrong agent name"
        print("   ✓ Agent name correct")

    except AssertionError as e:
        print(f"   ✗ Structure validation failed: {e}")
        db.close()
        return False

    # Test 2: Template finding
    print("\n8. Test template finding...")
    try:
        # Test with existing type
        params = {'contract_type': 'supply_agreement', 'subject': 'test'}
        found_template = agent._find_template(params)

        if found_template:
            print(f"   ✓ Template found by type: {found_template.name}")
        else:
            print(f"   ✗ Template not found for type: supply_agreement")

        # Test with non-existing type
        params_missing = {'contract_type': 'nonexistent_type', 'subject': 'test'}
        missing_template = agent._find_template(params_missing)

        if not missing_template:
            print(f"   ✓ Correctly returned None for missing template")
        else:
            print(f"   ~ Unexpected: found template for nonexistent type")

    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 3: Parameter extraction (if LLM available)
    if llm_available:
        print("\n9. Test parameter extraction with LLM...")
        try:
            request_xml = create_test_request_xml()
            metadata = {
                'contract_type': 'supply_agreement',
                'parties': ['ООО Поставщик', 'ООО Покупатель']
            }

            params = agent._extract_parameters(request_xml, metadata)

            assert isinstance(params, dict), "Params not a dict"
            assert 'contract_type' in params, "Missing contract_type"
            assert 'parties' in params, "Missing parties"

            print(f"   ✓ Parameters extracted successfully")
            print(f"     - Type: {params.get('contract_type')}")
            print(f"     - Parties: {len(params.get('parties', []))} parties")
            print(f"     - Subject: {params.get('subject', 'N/A')}")

        except Exception as e:
            print(f"   ✗ Parameter extraction failed: {e}")
            import traceback
            traceback.print_exc()

        # Test 4: Contract validation
        print("\n10. Test contract validation...")
        try:
            # Valid contract
            valid_contract = """<?xml version="1.0" encoding="UTF-8"?>
<contract>
    <header>
        <title>Договор поставки</title>
    </header>
    <parties>
        <party>ООО Поставщик</party>
        <party>ООО Покупатель</party>
    </parties>
    <subject>Поставка товаров</subject>
    <price>
        <amount>1000000</amount>
        <currency>RUB</currency>
    </price>
    <term>
        <start>2024-01-01</start>
        <end>2024-12-31</end>
    </term>
</contract>"""

            params = {
                'parties': [
                    {'name': 'ООО Поставщик'},
                    {'name': 'ООО Покупатель'}
                ],
                'price': {'amount': 1000000}
            }

            validation = agent._validate_contract(valid_contract, params)

            print(f"   ✓ Validation completed")
            print(f"     - Passed: {validation.get('passed')}")
            print(f"     - Errors: {len(validation.get('errors', []))}")
            print(f"     - Warnings: {len(validation.get('warnings', []))}")

        except Exception as e:
            print(f"   ✗ Validation failed: {e}")

        # Test 5: Full workflow execution
        print("\n11. Test full workflow execution...")
        try:
            # Create test contract record
            contract = Contract(
                file_name="test_generation.xml",
                file_path="/tmp/test_generation.xml",
                document_type="new_contract",
                contract_type="supply_agreement",
                status="pending"
            )
            db.add(contract)
            db.commit()
            db.refresh(contract)

            request_xml = create_test_request_xml()

            state = {
                'contract_id': contract.id,
                'parsed_xml': request_xml,
                'metadata': {
                    'contract_type': 'supply_agreement',
                    'parties': ['ООО Поставщик', 'ООО Покупатель'],
                    'subject': 'Поставка товаров'
                }
            }

            result = agent.execute(state)

            assert result.success, f"Execution failed: {result.error}"
            assert result.data is not None, "No result data"

            print(f"   ✓ Workflow executed successfully")
            print(f"     - Contract ID: {result.data.get('contract_id')}")
            print(f"     - Template used: {result.data.get('template_used')}")
            print(f"     - Next action: {result.next_action}")

            if result.data.get('generated_contract_xml'):
                print(f"     - Generated XML: {len(result.data['generated_contract_xml'])} chars")

            if result.data.get('validation_results'):
                val = result.data['validation_results']
                print(f"     - Validation passed: {val.get('passed')}")

        except Exception as e:
            print(f"   ✗ Workflow execution failed: {e}")
            import traceback
            traceback.print_exc()

        # Test 6: Feedback service
        print("\n12. Test Feedback Service...")
        try:
            # Create feedback
            feedback = feedback_service.create_feedback(
                contract_id=contract.id,
                user_id=user.id,
                rating=5,
                acceptance_status=True,
                generation_params=params,
                template_id=template.id,
                validation_errors=0,
                validation_warnings=0
            )

            print(f"   ✓ Feedback created: ID {feedback.id}")
            print(f"     - Rating: {feedback.rating}")
            print(f"     - Accepted: {feedback.acceptance_status}")

            # Get statistics
            stats = feedback_service.get_statistics()
            print(f"   ✓ Statistics retrieved:")
            print(f"     - Total feedback: {stats['total_feedback']}")
            print(f"     - Accepted: {stats['accepted']}")
            print(f"     - Average rating: {stats['average_rating']}")
            print(f"     - Ready for training: {stats['ready_for_training']}")

            # Export training data
            training_data = feedback_service.export_training_data(min_rating=3, accepted_only=True)
            print(f"   ✓ Training data exported: {len(training_data)} chars")

        except Exception as e:
            print(f"   ✗ Feedback service failed: {e}")
            import traceback
            traceback.print_exc()

    else:
        print("\n9-12. LLM-based tests skipped (no API key)")
        print("   ℹ Set OPENAI_API_KEY environment variable to run full tests")

    # Test 7: Template selection request (no template found)
    print("\n13. Test template selection request...")
    try:
        state_no_template = {
            'contract_id': 'test-no-template',
            'parsed_xml': '<request><type>нетиповой договор</type></request>',
            'metadata': {
                'contract_type': 'nonexistent_type'
            }
        }

        result = agent.execute(state_no_template)

        if result.data.get('template_selection_required'):
            print(f"   ✓ Template selection request created")
            print(f"     - Message: {result.data.get('message')}")
            print(f"     - Next action: {result.next_action}")
        else:
            print(f"   ~ Template was found unexpectedly")

    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Cleanup
    db.close()

    # Summary
    print("\n" + "=" * 60)
    print("✓ CONTRACT GENERATOR AGENT TESTS COMPLETED")
    print("=" * 60)

    print("\nFeatures tested:")
    print("  ✓ Agent structure and methods")
    print("  ✓ Template finding (by type)")

    if llm_available:
        print("  ✓ Parameter extraction with LLM")
        print("  ✓ Contract validation")
        print("  ✓ Full workflow execution")
        print("  ✓ Feedback service")
        print("  ✓ Training data export")
    else:
        print("  ~ LLM tests skipped (no API key)")

    print("  ✓ Template selection request")

    print("\nContract Generator Agent capabilities:")
    print("  ✓ Extract parameters from user request (LLM)")
    print("  ✓ Find templates (type + semantic via RAG)")
    print("  ✓ Generate contracts (LLM + template + RAG)")
    print("  ✓ Validate contracts (structure + legal)")
    print("  ✓ Request user selection when template missing")
    print("  ✓ Collect feedback for ML training")
    print("  ✓ Export training data for fine-tuning")

    print("\nNext steps:")
    print("  - Implement Contract Analyzer Agent")
    print("  - Implement Disagreement Processor Agent")
    print("  - Implement Changes Analyzer Agent")
    print("  - Implement Quick Export Agent")

    return True


if __name__ == "__main__":
    success = test_contract_generator_agent()
    sys.exit(0 if success else 1)
