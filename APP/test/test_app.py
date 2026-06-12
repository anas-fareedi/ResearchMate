import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("="*60)
    print("Testing Modular APP Structure")
    print("="*60)

    print("\n1. Testing imports...")
    try:
        from scrapping.search import search_website, search_with_google, get_wikipedia_urls
        print("   [OK] scrapping.search imports successful")
    except Exception as e:
        print(f"   [FAIL] scrapping.search import failed: {e}")

    try:
        from scrapping.extract import extract_content
        print("   [OK] scrapping.extract imports successful")
    except Exception as e:
        print(f"   [FAIL] scrapping.extract import failed: {e}")

    try:
        from Agents.agent_state import ResearchState
        print("   [OK] Agents.agent_state imports successful")
    except Exception as e:
        print(f"   [FAIL] Agents.agent_state import failed: {e}")

    try:
        from Agents.Agents import planning_agent, search_agent, extraction_agent, summarization_agent, saving_agent
        print("   [OK] Agents.Agents imports successful")
    except Exception as e:
        print(f"   [FAIL] Agents.Agents import failed: {e}")

    try:
        from Agents.workflow import build_research_workflow
        print("   [OK] Agents.workflow imports successful")
    except Exception as e:
        print(f"   [FAIL] Agents.workflow import failed: {e}")

    try:
        from document_gen import save_to_json, save_to_pdf, clean_text_for_pdf
        print("   [OK] document_gen imports successful")
    except Exception as e:
        print(f"   [FAIL] document_gen import failed: {e}")

    try:
        from research import research
        print("   [OK] research imports successful")
    except Exception as e:
        print(f"   [FAIL] research import failed: {e}")

    print("\n2. Testing workflow build...")
    try:
        app = build_research_workflow()
        print("   [OK] Workflow built successfully")
    except Exception as e:
        print(f"   [FAIL] Workflow build failed: {e}")

    print("\n3. Testing research function...")
    print("   Running quick research query...")
    try:
        result = research("What is Python programming?")
        print(f"   [OK] Research completed successfully!")
        print(f"   [OK] JSON: {result['json_path']}")
        print(f"   [OK] PDF: {result['pdf_path']}")
        print(f"\n   Summary preview:\n   {result['summary'][:200]}...")
    except Exception as e:
        print(f"   [FAIL] Research failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)


if __name__ == "__main__":
    main()