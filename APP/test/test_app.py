import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*60)
print("Testing Modular APP Structure")
print("="*60)

# Test imports
print("\n1. Testing imports...")
try:
    from scrapping.search import search_website, search_with_google, get_wikipedia_urls
    print("   ✓ scrapping.search imports successful")
except Exception as e:
    print(f"   ✗ scrapping.search import failed: {e}")

try:
    from scrapping.extract import extract_content
    print("   ✓ scrapping.extract imports successful")
except Exception as e:
    print(f"   ✗ scrapping.extract import failed: {e}")

try:
    from Agents.agent_state import ResearchState
    print("   ✓ Agents.agent_state imports successful")
except Exception as e:
    print(f"   ✗ Agents.agent_state import failed: {e}")

try:
    from Agents.Agents import planning_agent, search_agent, extraction_agent, summarization_agent, saving_agent
    print("   ✓ Agents.Agents imports successful")
except Exception as e:
    print(f"   ✗ Agents.Agents import failed: {e}")

try:
    from Agents.workflow import build_research_workflow
    print("   ✓ Agents.workflow imports successful")
except Exception as e:
    print(f"   ✗ Agents.workflow import failed: {e}")

try:
    from document_gen import save_to_json, save_to_pdf, clean_text_for_pdf
    print("   ✓ document_gen imports successful")
except Exception as e:
    print(f"   ✗ document_gen import failed: {e}")

try:
    from research import research
    print("   ✓ research imports successful")
except Exception as e:
    print(f"   ✗ research import failed: {e}")

# Test workflow building
print("\n2. Testing workflow build...")
try:
    app = build_research_workflow()
    print("   ✓ Workflow built successfully")
except Exception as e:
    print(f"   ✗ Workflow build failed: {e}")

# Test research function (with a simple query)

print("\n3. Testing research function...")
print("   Running quick research query...")
try:
    result = research("What is Python programming?")
    print(f"   ✓ Research completed successfully!")
    print(f"   ✓ JSON: {result['json_path']}")
    print(f"   ✓ PDF: {result['pdf_path']}")
    print(f"\n   Summary preview:\n   {result['summary'][:200]}...")
except Exception as e:
    print(f"   ✗ Research failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Test Complete!")
print("="*60)