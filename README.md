# Financial AI Chat Assistant

**Version:** 1.0.0
**Date:** May 8, 2025

## Description

The Financial AI Chat Assistant is a web-based application that allows users to upload Excel (.xlsx, .xls) or CSV (.csv) files and interact with an AI model (powered by Azure OpenAI) to analyze the data. The AI receives a detailed summary of the uploaded file and can answer questions, perform analyses based on user instructions, and provide insights from the data. The application features a chat interface with client-side file staging and Markdown rendering for AI responses.

## Features

* **File Upload:** Supports Excel (.xlsx, .xls) and CSV (.csv) file uploads.
* **Client-Side File Staging:** Users can select a file, see its name, and remove/replace it before sending it for analysis with a message.
* **AI-Powered Data Analysis:** Leverages an Azure OpenAI model (e.g., GPT-4o) for data interpretation and answering questions.
* **Dynamic Data Summarization:**
    * The backend processes the uploaded file using Pandas.
    * A comprehensive summary is generated for the AI, including:
        * File metadata (name, type, sheet information for Excel).
        * Dataframe info (`df.info()`: column names, data types, non-null counts).
        * Statistical summaries (`df.describe()` for numerical and object columns).
        * An adaptive number of the first N rows of the data (`df.head(N).to_string()`), adjusted to fit within a character limit to optimize token usage.
* **Interactive Chat Interface:**
    * Users type messages and can optionally send a staged file along with their message.
    * Conversation history is maintained for contextual understanding by the AI.
    * AI responses are displayed in the chat.
* **Markdown Rendering:** AI responses containing Markdown (for bolding, italics, lists, tables, etc.) are rendered nicely in the chat interface using Marked.js.
* **Prompt Engineering:** The AI's system prompt is engineered to guide its analytical behavior and output formatting.

## Tech Stack

* **Backend:**
    * Python 3.x
    * Flask (web framework)
    * `openai` (Azure OpenAI Python SDK)
    * `pandas` (data analysis and manipulation)
    * `openpyxl` (for reading .xlsx files)
    * `python-dotenv` (for managing environment variables)
* **Frontend:**
    * HTML5
    * CSS3
    * JavaScript (ES6+)
    * Marked.js (for client-side Markdown rendering, via CDN)
* **AI Service:**
    * Azure OpenAI Service (configurable endpoint and deployment)

## Prerequisites

* Python 3.7+
* `pip` (Python package installer)
* An active Azure OpenAI Service subscription with a deployed model (e.g., GPT-4o).
    * You will need the Endpoint URL, API Key, and Deployment Name.

## Setup and Installation

1.  **Clone the Repository (or create project files):**
    If this were a Git repository:
    ```bash
    git clone <repository-url>
    cd financial-chat-app
    ```
    Otherwise, ensure you have the project files (`app.py`, `templates/index.html`, `.env.example` or create `.env`).

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    Create a `requirements.txt` file with the following content:
    ```txt
    Flask
    openai
    python-dotenv
    pandas
    openpyxl
    ```
    Then install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables:**
    Create a `.env` file in the root directory of the project by copying `.env.example` (if provided) or creating it manually. Add your Azure OpenAI service credentials:
    ```env
    ENDPOINT_URL="YOUR_AZURE_OPENAI_ENDPOINT"
    AZURE_OPENAI_API_KEY="YOUR_AZURE_OPENAI_API_KEY"
    DEPLOYMENT_NAME="YOUR_AZURE_OPENAI_DEPLOYMENT_NAME"
    ```
    Replace the placeholder values with your actual credentials.

## Running the Application

1.  **Activate the virtual environment** (if you created one):
    ```bash
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

2.  **Run the Flask Application:**
    ```bash
    python app.py
    ```

3.  **Access the Application:**
    Open your web browser and navigate to `http://127.0.0.1:5000/`.

## File Structure