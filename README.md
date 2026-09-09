# 🛡️ JobGuard — AI-Powered Job Scam & Fraud Detection Platform

> **Protecting job seekers from fraudulent opportunities with AI-powered analysis, verification, and evidence-based recommendations.**

JobGuard is an AI-powered platform designed to help users evaluate potentially fraudulent job opportunities before applying, sharing personal information, or making payments.

The platform analyzes job postings, recruiter messages, offer letters, emails, URLs, PDFs, and images using a multi-stage investigation pipeline combining deterministic scam-signal detection, NLP/ML analysis, company and domain verification, retrieval-augmented generation (RAG), and LLM-based reasoning.

JobGuard also provides a **Job Discovery** feature that retrieves relevant job opportunities through the Adzuna Jobs API based on the user's role, location, and experience.

---

## 🚀 Why JobGuard?

Online job scams can use legitimate-looking company names, convincing job descriptions, fake recruiters, urgency, payment requests, and misleading websites.

Traditional keyword-based scam detectors often provide only a simple "scam/not scam" result without explaining the evidence.

JobGuard takes an evidence-based approach:

* Identifies suspicious signals.
* Analyzes the language and semantic content of the opportunity.
* Verifies company, recruiter, and domain information.
* Retrieves relevant scam-pattern knowledge.
* Uses an LLM to reason over the collected evidence.
* Provides an understandable assessment and recommended actions.
* Helps users discover job opportunities through a separate job-search pipeline.

---

## ✨ Key Features

### 🔍 Multi-Stage Scam Investigation

JobGuard uses a five-stage investigation pipeline:

```text
User Input
    ↓
Input Processing
    ↓
Gate 1 — Scam Signal Detection
    ↓
Gate 2 — ML/NLP Analysis
    ↓
Gate 3 — Company / Recruiter / Domain Verification
    ↓
Gate 4 — Scam Knowledge Retrieval (RAG)
    ↓
Gate 5 — LLM Evidence Reasoning
    ↓
Final Assessment
```

### Gate 1 — Hard Scam Signal Detection

A deterministic evidence-extraction layer identifies signals such as:

* Payment requests
* UPI/payment requests
* OTP requests
* Urgency or pressure
* Guaranteed-job claims
* WhatsApp-only recruitment
* Suspicious recruitment contact patterns
* Personal email usage
* Other predefined scam indicators

Gate 1 extracts evidence and does **not** independently produce the final verdict.

### Gate 2 — ML/NLP Analysis

JobGuard uses:

* Sentence Transformers
* `all-MiniLM-L6-v2`
* Gaussian Naive Bayes
* Semantic embeddings

The ML layer provides supporting evidence based on learned patterns.

The ML result is not treated as definitive proof of fraud.

### Gate 3 — Company, Recruiter & Domain Verification

JobGuard evaluates available information about:

* Company identity
* Recruiter email
* Company/recruiter consistency
* Domain information
* DNS availability
* HTTPS availability
* Website consistency

Verification results can be:

* `VERIFIED`
* `UNKNOWN`
* Other applicable verification states

Unknown information is treated as unknown rather than automatically being considered suspicious.

### Gate 4 — RAG-Based Scam Knowledge Retrieval

JobGuard maintains a local knowledge base containing information about Indian job-scam patterns.

The system:

```text
Investigation Input
       ↓
Embedding
       ↓
Vector Similarity Search
       ↓
Relevant Knowledge
       ↓
Evidence for Final Reasoning
```

The RAG layer provides contextual evidence and does not independently determine the final verdict.

### Gate 5 — LLM Evidence Reasoning

The final reasoning layer uses Google's Gemini model to analyze the evidence collected from the previous stages.

The LLM considers:

* Scam signals
* ML evidence
* Verification results
* Retrieved scam knowledge
* Contradicting evidence
* Missing information

The final assessment can be:

* ⚠️ `SUSPICIOUS`
* ✅ `NOT_SUSPICIOUS`
* ◐ `INCONCLUSIVE`

The confidence value represents the model's confidence in the assessment and should not be interpreted as a guaranteed probability that a listing is fraudulent.

---

# 💼 Job Discovery

JobGuard also includes a separate job-discovery feature.

Users can provide:

* Desired role
* Location
* Experience level

The system retrieves job listings through the Adzuna Jobs API and processes them before displaying relevant opportunities.

### Job Discovery Pipeline

```text
Role + Location + Experience
              ↓
           jobs.js
              ↓
      Flask /api/jobs/search
              ↓
       job_discovery/service.py
              ↓
       adzuna_client.py
              ↓
          Adzuna API
              ↓
        JobListing Model
              ↓
         job_filter.py
              ↓
      Filter + Deduplicate
              ↓
            Rank
              ↓
          Top Jobs
              ↓
         jobs.js
              ↓
       sessionStorage
              ↓
          /jobs page
              ↓
       job-results.js
              ↓
         Job Cards
```

The discovery feature is separate from the scam investigation pipeline.

---

# 🧠 Architecture

## Scam Detection Architecture

```text
                         ┌───────────────────┐
                         │    User Input     │
                         │ Text / URL / PDF  │
                         │ Image / Message   │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ Input Processing  │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │      Gate 1       │
                         │ Scam Signals      │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │      Gate 2       │
                         │ ML / NLP Analysis │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │      Gate 3       │
                         │ Verification      │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │      Gate 4       │
                         │ Local RAG         │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │      Gate 5       │
                         │ Gemini Reasoning  │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ Final Assessment  │
                         │ + Recommendations │
                         └───────────────────┘
```

---

# 🛠️ Technology Stack

## Backend

* Python
* Flask
* REST API
* Gunicorn

## Machine Learning / NLP

* Scikit-learn
* Sentence Transformers
* Hugging Face
* `all-MiniLM-L6-v2`
* Gaussian Naive Bayes
* NumPy
* Joblib

## Generative AI

* Google Gemini API
* `google-genai`

## RAG

* Sentence Transformer embeddings
* Vector similarity search
* Local scam knowledge base

## Document Processing

* PyMuPDF
* Pillow
* Tesseract OCR
* Pytesseract

## Frontend

* HTML5
* CSS3
* JavaScript
* Browser Session Storage

---

# 📁 Project Structure

```text
job-scam-detector/
│
├── agent/
│   ├── graph.py
│   └── nodes/
│       ├── _extractors.py
│       ├── gate1_flag_extractor.py
│       ├── gate2_ml_analyzer.py
│       ├── gate3_verifier.py
│       ├── gate4_rag.py
│       ├── gate5_llm.py
│       └── input_processor.py
│
├── data/
│   ├── final_classifier.pkl
│   ├── model_metadata.pkl
│   └── processed/
│       └── external_validation.json
│
├── job_discovery/
│   ├── __init__.py
│   ├── adzuna_client.py
│   ├── job_filter.py
│   ├── models.py
│   └── service.py
│
├── rag/
│   ├── data/
│   │   ├── documents.json
│   │   ├── embeddings.npy
│   │   └── knowledge_base.json
│   ├── ingest.py
│   └── retriever.py
│
├── tests/
│   ├── initial_test_input_processor.py
│   ├── test_gate1_flag_extractor.py
│   ├── test_gate2_ml_analyzer.py
│   ├── test_gate3_verifier.py
│   ├── test_gate4_rag_retriever.py
│   ├── test_gate5_llm.py
│   ├── test_pipeline_gate5.py
│   └── test_pipeline_gates_1_to_4.py
│
├── web/
│   ├── templates/
│   │   ├── index.html
│   │   ├── jobs.html
│   │   └── results.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           ├── app.js
│           ├── jobs.js
│           └── job-results.js
│
├── .env
├── .gitignore
├── app.py
├── README.md
└── requirements.txt
```
---

# ⚙️ Local Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Aqifcodes/JobGuard.git
cd JobGuard
````

### 2. Create and Activate a Virtual Environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

JobGuard uses environment variables for its external API credentials.

### Gemini API Key

The Gemini API key is stored in the system environment.

Required variable:

```text
GEMINI_API_KEY
```

On Windows:

```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your_gemini_api_key", "User")
```

Restart the terminal or IDE after setting the variable.

### Adzuna API Credentials

Adzuna credentials are stored in a `.env` file in the project root.

Create `.env`:

```env
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
```
---

## Running the Application

Start the Flask application:

```bash
python app.py
```

The application will normally be available at:

```text
http://127.0.0.1:5000
```

Open the URL in your browser to use JobGuard.

---

## Testing

Run the complete test suite:

```bash
pytest
```

For detailed output:

```bash
pytest -v
```

---

# 🔎 Example Workflow

### Scam Investigation

A user can provide:

```text
Job posting
Recruiter message
Email
URL
PDF
Image
Offer letter
```

JobGuard processes the information through its investigation pipeline and returns:

```text
Assessment
Confidence
Reasons
Recommendations
```

### Job Discovery

A user selects:

```text
Role: Backend Developer
Location: Hyderabad
Experience: 1–3 years
```

JobGuard retrieves available listings and displays relevant opportunities with a **View Job & Apply** option.

---

# 📊 Assessment Types

| Assessment       | Meaning                                                                       |
| ---------------- | ----------------------------------------------------------------------------- |
| `SUSPICIOUS`     | Multiple meaningful indicators suggest that the opportunity deserves caution. |
| `NOT_SUSPICIOUS` | Available evidence does not indicate meaningful scam concerns.                |
| `INCONCLUSIVE`   | There is not enough reliable evidence to make a confident assessment.         |

JobGuard is an assistance tool and does not guarantee that a job opportunity is legitimate or fraudulent.

---

# 🛡️ Safety & Responsible Use

JobGuard is designed to support users when evaluating potentially suspicious opportunities.

Users should still independently verify important information before:

* Sharing sensitive personal information
* Making payments
* Sharing financial information
* Accepting an offer
* Signing documents
* Communicating with unfamiliar recruiters

An assessment from JobGuard should not be treated as legal, financial, employment, or security advice.

---

# 🔒 Security

JobGuard uses environment variables for external API credentials.

Never place API keys, passwords, access tokens, private keys, or other credentials directly in source code.

If a secret is accidentally committed:

1. Treat it as compromised.
2. Revoke or rotate the credential immediately.
3. Remove the secret from the repository/history where appropriate.
4. Generate a replacement credential.
5. Review access/activity logs.

---

# 🌐 External Services

## Google Gemini

Used for final evidence-based reasoning and recommendations.

## Adzuna

Used by the Job Discovery feature to retrieve available job listings through its API.

External service availability, API limits, pricing, and terms may change independently of this project.

---

# ⚠️ Limitations

JobGuard has some important limitations:

* No automated system can guarantee that a job listing is legitimate.
* Missing information may result in an `INCONCLUSIVE` assessment.
* ML predictions can contain errors.
* OCR quality depends on the quality of the uploaded document or image.

---

# 🚧 Future Improvements

Potential future improvements include:

* More scam datasets and continuously updated knowledge
* Improved multilingual support
* Browser extension integration
* Email & WhatsApp message analysis
* Production-scale vector database integration
---

# 📜 License

This project is licensed under the MIT License.

See the `LICENSE` file for details.

---

# 👨‍💻 Author

**Aqif**

B.Tech CSE (AI & ML)

GitHub: `https://github.com/Aqifcodes`

---

# ⭐ Acknowledgements

This project uses and builds upon several open-source technologies and external services, including:

* Sentence Transformers
* Hugging Face
* Google Gemini
* Adzuna
* PyMuPDF
* Tesseract OCR

---

## 📌 Disclaimer

JobGuard provides AI-assisted analysis and should not be considered a guarantee that a job opportunity is fraudulent or legitimate.

Always verify important employment opportunities through trusted channels before taking action.
