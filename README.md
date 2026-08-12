# Research Assistant 

### Frontend : https://researchmate.anasfareedi.in/

### Backend : https://researchmate-1yzg.onrender.com

### Langsmith : https://smith.langchain.com/o/548d39a3-d580-4f65-a929-f7cb81ee48bb/projects/p/ef5b9c1c-8ece-4343-afcc-c951f4ae9b67?timeModel=%7B%22duration%22%3A%221d%22%7D

An AI-powered research assistant that automatically searches the web, extracts content, and generates comprehensive summaries using Google's Gemini AI.

<img width="1245" height="877" alt="Screenshot 2026-04-11 201452" src="https://github.com/user-attachments/assets/c2d5aa91-5d75-4b9b-9bf4-54f1885ca7f8" />


## pending
### One deployed demo (or 60s screencast) reachable from README
### prepared project pitches (30s, 2min, 5min versions).
### Advanced scaling/infra — fix by documenting tradeoffs and showing a simple cost/latency estimate for your deployed app.


## tool for performing local RAG like operations https://www.ivorymind.com/

## Features ✨

- **Intelligent Query Planning**: Automatically extracts key search terms from your research question
- **Multi-Source Search**: Searches Google, Wikipedia, ArXiv, and ScienceDirect
- **Academic API Integration**: 
  - ArXiv API for open-access preprints
  - Elsevier API for ScienceDirect and Scopus (requires free API key)
  - Semantic Scholar Graph API (with API key)
- **Web Search API Integration**:
  - Tavily API for reliable web result discovery
- **Content Extraction**: Automatically extracts and cleans relevant content from web pages
- **AI Summarization**: Uses Google Gemini to synthesize information from multiple sources
- **Dual Output**: Generates both JSON and PDF reports with your research findings
- **PDF Q&A (RAG)**: Ask follow-up questions on generated reports using retrieval-augmented chat
- **Security Features**: 
  - URL validation to prevent SSRF attacks
  - Input sanitization
  - Rate limiting for respectful web scraping
  - Automatic retry logic for failed requests

## Installation 📦

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Reasech_assistant
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```
   GEMINI_API_KEY=your_gemini_key_here
  TAVILY_API_KEY=your_tavily_key_here
  SEMANTIC_SCHOLAR=your_semantic_scholar_key_here
   Elsevier_API_KEY=your_elsevier_key_here  # Optional but recommended
   ```
   
   **Get your API keys:**
   - Gemini API: https://makersuite.google.com/app/apikey
  - Tavily API: https://app.tavily.com/
  - Semantic Scholar API: https://www.semanticscholar.org/product/api
   - Elsevier API: https://dev.elsevier.com/ (free, for ScienceDirect/Scopus)
   
**Note**: `TAVILY_API_KEY` and `SEMANTIC_SCHOLAR` improve search quality and coverage. Elsevier API remains optional.

## Usage 🚀

### Basic Usage

```python
from research import research

# Simple research query
result = research("What are the latest developments in quantum computing?")

print(f"Summary: {result['summary']}")
print(f"JSON saved to: {result['json_path']}")
print(f"PDF saved to: {result['pdf_path']}")
```

### Advanced Usage with Custom Websites

```python
from research import research

result = research(
    query="Impact of climate change on marine ecosystems",
    websites=[
        "https://www.nature.com",
        "https://www.sciencedirect.com",
        "https://oceanservice.noaa.gov"
    ]
)
```

### Research on Academic Papers

```python
from research import research

result = research(
    query="Synthetic data generation using GANs",
    websites=[
        "https://www.arxiv.org",
        "https://www.sciencedirect.com",  # Uses Elsevier API
        "https://www.semanticscholar.com"
    ]
)
```

**Note**: For ScienceDirect, ensure you have `Elsevier_API_KEY` in your `.env` file. See [ELSEVIER_API_GUIDE.md](ELSEVIER_API_GUIDE.md) for setup instructions.

## Configuration ⚙️

Edit `APP/config.py` to customize:

- **LLM Settings**: Model, temperature, max tokens
- **Search Settings**: Max URLs, timeouts, content length
- **Output Settings**: File formats, PDF styling
- **Rate Limiting**: Requests per second, retry attempts

### Local PDF Persistence

Generated and uploaded PDFs are saved directly to the local `research_outputs/` directory.

The API supports the following endpoints:

- `POST /research`: generates local JSON and PDF outputs under the `research_outputs/` folder.
- `POST /upload-pdf`: upload an external PDF for local storage and Q&A.
- `GET /documents`: list all locally saved PDFs.
- `POST /qa`: ask questions using a local `pdf_path` or `document_id`.

## Architecture 🏗️

The research assistant uses a LangGraph workflow with 5 sequential agents:

1. **Planning Agent**: Analyzes query and extracts search terms
2. **Search Agent**: Finds relevant URLs from multiple sources
3. **Extraction Agent**: Scrapes and cleans content from URLs
4. **Summarization Agent**: Uses AI to synthesize findings
5. **Saving Agent**: Generates JSON and PDF reports

See `ARCHITECTURE.txt` for detailed flow diagrams.

## Output 📄

Results are saved to the `research_outputs/` directory:

- **JSON file**: Complete data including all sources and metadata
- **PDF file**: Formatted report with summary and source content

After each run, you can start an interactive Q&A chat over the generated PDF.
The chatbot retrieves relevant report chunks and answers using Gemini.

## PDF Q&A Chat (RAG) 💬

When the run finishes, the app prompts:

```text
Start Q&A chat on generated PDF? (y/n):
```

Type `y` to enter chat mode, then ask questions such as:

- What are the key findings from this report?
- Which sources discuss privacy in GAN-generated synthetic data?
- Summarize the main limitations in 5 bullet points.

Type `exit` or `quit` to end chat.

## Security Features 🔒

- **SSRF Protection**: Validates all URLs to prevent access to private networks
- **Input Sanitization**: Cleans and validates all user inputs
- **Rate Limiting**: Respects website resources with built-in delays
- **Retry Logic**: Handles transient failures gracefully
- **Error Logging**: Comprehensive logging for debugging

## Error Handling 🛡️

The assistant includes robust error handling:

- Network failures trigger automatic retries
- Invalid URLs are skipped with warnings
- Missing API keys show helpful error messages
- Partial failures still generate output with available data

## Limitations ⚠️

- Some websites may block automated access
- AI summaries depend on Gemini API availability
- Content extraction quality varies by website structure
- Rate limiting may slow down large research tasks

## Troubleshooting 🔧

**No content extracted**: Some websites block scrapers. Try different websites or use Wikipedia.

**API errors**: Verify your `GEMINI_API_KEY` is set correctly in `.env`

**Timeout errors**: Increase `request_timeout` in `config.py`

**Missing dependencies**: Run `pip install -r requirements.txt` again

## Contributing 🤝

Contributions welcome! Please ensure:

- All tests pass
- Code follows existing style
- Security best practices are maintained
- Documentation is updated

## License 📝

See LICENSE file for details.

## Acknowledgments 🙏

- Google Gemini for AI summarization
- LangChain & LangGraph for workflow orchestration
- BeautifulSoup for web scraping
- FPDF for PDF generation
