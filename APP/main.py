import os
import sys
from research import research
from qa_chat import start_pdf_qa_chat
from utils import validate_api_key, sanitize_query, validate_websites, log_error
from config import API_CONFIG, OUTPUT_CONFIG

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Validate API keys at startup
try:
    GEMINI_API_KEY = validate_api_key(API_CONFIG["gemini_api_key"], "GEMINI_API_KEY")
except ValueError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# Validate Elsevier API key (optional but recommended for ScienceDirect access)
try:
    if API_CONFIG.get("elsevier_api_key"):
        ELSEVIER_API_KEY = validate_api_key(API_CONFIG["elsevier_api_key"], "Elsevier_API_KEY")
        print("✓ Elsevier API key detected - ScienceDirect search enabled")
    else:
        print("⚠️  Elsevier API key not found - ScienceDirect search will be limited")
        print("   Get your key from: https://dev.elsevier.com/")
except ValueError as e:
    print(f"WARNING: {e}")
    print("   ScienceDirect search may not work properly")

OUTPUT_DIR = OUTPUT_CONFIG.get("directory", "research_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


if __name__ == "__main__":
    try:
        # Example 1: Simple Wikipedia query (recommended for testing)
        # result = research("What are the latest developments in quantum computing?")
        
        # Example 2: Research with specific websites
        # result = research(
        #     query="Impact of climate change on marine ecosystems",
        #     websites=[
        #         "https://www.nature.com",
        #         "https://www.sciencedirect.com",
        #         "https://oceanservice.noaa.gov"
        #     ]
        # )

        # Example 3: ArXiv + ScienceDirect research papers (uses APIs)
        print("\n" + "="*70)
        print("RESEARCH ASSISTANT - Academic Paper Search")
        print("="*70)
        print("\nSearching multiple academic databases:")
        print("  • ArXiv (open access preprints)")
        print("  • ScienceDirect (via Elsevier API)")
        print("  • Wikipedia (background information)")
        print("\nQuery: Synthetic data generation using GANs")
        print("This will find actual research papers with abstracts.\n")
        
        result = research(
            # query="synthetic data generation using GANs",
            query="web3 and decentralized applications in healthcare",
            websites=[
                "https://www.arxiv.org",
                "https://www.sciencedirect.com",    
            ]
        )
        
        print("\n" + "="*70)
        print("RESEARCH COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"\nResults saved to:")
        print(f"  JSON: {result['json_path']}")
        print(f"  PDF:  {result['pdf_path']}")
        print("\nCheck the output files for detailed research findings.")

        # Optional Q&A chat over generated PDF report (RAG)
        try:
            start_chat = input("\nStart Q&A chat on generated PDF? (y/n): ").strip().lower()
            if start_chat in {"y", "yes"}:
                start_pdf_qa_chat(result['pdf_path'])
        except Exception as e:
            log_error(e, "Q&A chat startup prompt")
            print(f"\n  Could not start Q&A chat: {e}")
        
    except KeyboardInterrupt:
        print("\n\nResearch interrupted by user")
        sys.exit(0)
    except Exception as e:
        log_error(e, "Main execution error")
        print(f"\nERROR: {e}")
        print("\nTroubleshooting tips:")
        print("1. Ensure your .env file has a valid GEMINI_API_KEY")
        print("2. Check your internet connection")
        print("3. Some academic sites may block automated access")
        print("4. Try with Wikipedia-only queries first")
        sys.exit(1)