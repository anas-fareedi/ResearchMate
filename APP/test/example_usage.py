import os
import sys
from research import research

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Example 1: Researching Quantum Computing")
print("-" * 60)
result1 = research("What are the latest developments in quantum computing?")
print("\n\nResults:")
print(f"✓ JSON saved to: {result1['json_path']}")
print(f"✓ PDF saved to: {result1['pdf_path']}")
print(f"\nSummary Preview:\n{result1['summary'][:300]}...")


print("\n\n" + "="*60)
print("Example 2: Climate Change Research with Custom Websites")
print("-" * 60)
custom_websites = [
    "https://www.nature.com",
    "https://en.wikipedia.org"
]
result2 = research(
    query="How does climate change affect ocean temperatures?",
    websites=custom_websites
)
print("\n\nResults:")
print(f"✓ JSON saved to: {result2['json_path']}")
print(f"✓ PDF saved to: {result2['pdf_path']}")
print(f"\nSummary Preview:\n{result2['summary'][:300]}...")


print("\n\n" + "="*60)
print("Example 3: AI and Machine Learning Research")
print("-" * 60)
result3 = research("What are transformer models in deep learning?")
print("\n\nResults:")
print(f"✓ JSON saved to: {result3['json_path']}")
print(f"✓ PDF saved to: {result3['pdf_path']}")
print(f"\nSummary Preview:\n{result3['summary'][:300]}...")


print("\n\n" + "="*60)
print("Interactive Mode")
print("="*60)
user_query = input("\nEnter your research question (or press Enter to skip): ")

if user_query.strip():
    print(f"\nResearching: {user_query}")
    result = research(user_query)
    
    print("\n\nResearch Complete!")
    print(f"✓ JSON: {result['json_path']}")
    print(f"✓ PDF: {result['pdf_path']}")
    print(f"\n📄 Summary:\n{result['summary']}")
else:
    print("Skipping interactive mode.")

print("\n\nAll examples complete! Check the 'research_outputs' folder for your files.")
