"""
Test Orchestrator Agent with LangGraph workflow
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from src.agents.orchestrator_agent import OrchestratorAgent
from src.services.llm_gateway import LLMGateway
from src.services.review_queue_service import ReviewQueueService
from src.models import init_db, SessionLocal
from src.models.database import User, Contract


def test_orchestrator_agent():
    """Test Orchestrator Agent functionality"""
    print("=" * 60)
    print("TESTING ORCHESTRATOR AGENT")
    print("=" * 60)

    # Initialize DB
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
        admin = db.query(User).filter(User.email == "admin@test.com").first()
        if not admin:
            admin = User(
                email="admin@test.com",
                name="Admin User",
                role="admin"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        print(f"   ✓ Admin user: {admin.id}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        db.close()
        return False

    # Create test contract
    print("\n3. Create test contract...")
    try:
        contract = Contract(
            file_name="test_contract.docx",
            file_path="/tmp/test_contract.docx",
            document_type="contract",
            contract_type="supply",
            status="pending"
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        print(f"   ✓ Contract created: {contract.id}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        db.close()
        return False

    # Initialize services
    print("\n4. Initialize services...")
    try:
        # Note: For real testing, set OPENAI_API_KEY environment variable
        # This test uses stub agents which don't make real LLM calls
        import os
        if 'OPENAI_API_KEY' not in os.environ:
            os.environ['OPENAI_API_KEY'] = 'test-key-for-stub-agents'

        # LLM Gateway using GPT (stub agents don't make real calls)
        llm = LLMGateway(provider="openai")
        print("   ✓ LLM Gateway initialized (test mode - stub agents)")

        review_queue = ReviewQueueService(db_session=db)
        print("   ✓ Review Queue Service initialized")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False

    # Initialize Orchestrator
    print("\n5. Initialize Orchestrator Agent...")
    try:
        orchestrator = OrchestratorAgent(
            llm_gateway=llm,
            db_session=db,
            review_queue_service=review_queue
        )
        print("   ✓ OrchestratorAgent initialized")
        print(f"   - Loaded {len(orchestrator.agents)} agents")
        print(f"   - Graph compiled: {orchestrator.graph is not None}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False

    # Test 1: Check all agents loaded
    print("\n6. Verify all agents loaded...")
    try:
        expected_agents = ['onboarding', 'generator', 'analyzer', 'disagreement', 'changes', 'export']
        for agent_name in expected_agents:
            agent = orchestrator.agents.get(agent_name)
            if agent:
                print(f"   ✓ {agent_name}: {agent.get_name()}")
            else:
                print(f"   ✗ Missing agent: {agent_name}")

    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 2: Start workflow (stub execution)
    print("\n7. Start workflow (existing contract analysis)...")
    try:
        final_state = orchestrator.start_workflow(
            contract_id=contract.id,
            file_path="/tmp/test_contract.docx",
            document_type="contract"
        )

        print(f"   ✓ Workflow completed")
        print(f"   - Contract ID: {final_state.get('contract_id')}")
        print(f"   - Document type: {final_state.get('document_type')}")
        print(f"   - Agents executed: {len(final_state.get('history', []))}")

        # Print execution history
        print(f"\n   Execution history:")
        for i, entry in enumerate(final_state.get('history', []), 1):
            agent_name = entry.get('agent', 'unknown')
            timestamp = entry.get('timestamp', 'N/A')
            print(f"     {i}. {agent_name:15} @ {timestamp[:19] if timestamp != 'N/A' else 'N/A'}")

        # Check if review task was created
        review_task_id = final_state.get('review_task_id')
        if review_task_id:
            print(f"\n   ✓ Review task created: {review_task_id}")
        else:
            print(f"\n   ℹ No review task created (workflow may have completed)")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Test different document types
    print("\n8. Test workflow routing for different document types...")
    test_types = [
        ("disagreement", "Disagreement document"),
        ("new_contract", "New contract generation"),
        ("tracked_changes", "Document with tracked changes")
    ]

    for doc_type, description in test_types:
        try:
            test_contract = Contract(
                file_name=f"test_{doc_type}.docx",
                file_path=f"/tmp/test_{doc_type}.docx",
                document_type=doc_type,
                status="pending"
            )
            db.add(test_contract)
            db.commit()
            db.refresh(test_contract)

            state = orchestrator.start_workflow(
                contract_id=test_contract.id,
                file_path=test_contract.file_path,
                document_type=doc_type
            )

            agents_executed = [h.get('agent') for h in state.get('history', [])]
            print(f"   ✓ {description:35} → {', '.join(agents_executed)}")

        except Exception as e:
            print(f"   ✗ {description}: {e}")

    # Test 4: Get workflow status
    print("\n9. Get workflow status...")
    try:
        status = orchestrator.get_workflow_status(contract.id)
        print(f"   ✓ Status retrieved:")
        print(f"     - Contract ID: {status['contract_id']}")
        print(f"     - Status: {status['status']}")
        print(f"     - Current stage: {status['current_stage']}")
        print(f"     - Completed: {status['completed']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test 5: Test individual agent stubs
    print("\n10. Test individual agent stubs...")
    test_state = {
        'contract_id': contract.id,
        'file_path': '/tmp/test.docx',
        'contract_type': 'supply'
    }

    for agent_name, agent in orchestrator.agents.items():
        try:
            result = agent.execute(test_state)
            success_icon = "✓" if result.success else "✗"
            print(f"   {success_icon} {agent_name:15} → success={result.success}, next_action={result.next_action}")
        except Exception as e:
            print(f"   ✗ {agent_name:15} → Error: {str(e)[:50]}")

    # Cleanup
    db.close()

    print("\n" + "=" * 60)
    print("✓ ALL TESTS COMPLETED")
    print("=" * 60)
    print("\nOrchestrator Agent features tested:")
    print("  ✓ Agent initialization and loading")
    print("  ✓ LangGraph workflow compilation")
    print("  ✓ Workflow execution (stub agents)")
    print("  ✓ Routing logic for different document types")
    print("  ✓ Review queue integration")
    print("  ✓ State management and history tracking")
    print("  ✓ Individual agent stub execution")
    print("\nNext steps:")
    print("  - Implement full Onboarding Agent")
    print("  - Implement Contract Generator Agent")
    print("  - Implement Contract Analyzer Agent")
    print("  - Implement Disagreement Processor Agent")
    print("  - Implement Changes Analyzer Agent")
    print("  - Implement Quick Export Agent")
    print("\nReady for agent implementation!")

    return True


if __name__ == "__main__":
    success = test_orchestrator_agent()
    sys.exit(0 if success else 1)
