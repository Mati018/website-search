# Website Search Application

A powerful AI-powered website search application that crawls and indexes website content using semantic search. Built with FastAPI backend and React frontend, leveraging Weaviate vector database and Sentence Transformers for intelligent content search.

## Features

- 🔍 **Semantic Search**: AI-powered search using sentence transformers
- 🕷️ **Web Crawling**: Automatically crawls and indexes website content
- 📊 **Vector Database**: Uses Weaviate for efficient similarity search
- 🚀 **Fast API**: High-performance backend with async processing
- 💻 **Modern UI**: Responsive React frontend with Tailwind CSS
- 🐳 **Docker Support**: Multiple deployment options
- 🔄 **Real-time Results**: Live search with relevance scoring

## Tech Stack

**Backend:**
- FastAPI (Python web framework)
- Weaviate (Vector database)
- Sentence Transformers (AI embeddings)
- BeautifulSoup (Web scraping)
- Asyncio/Aiohttp (Async processing)

**Frontend:**
- React
- Tailwind CSS
- Lucide React (Icons)
- Vite (Build tool)

## Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (for containerized setup)
- Weaviate Cloud account or local Weaviate instance

## Environment Variables

Create a `.env` file in the root directory:

```env
WEAVIATE_API_KEY=your_weaviate_api_key_here
WEAVIATE_CLUSTER_URL=your_weaviate_cluster_url_here
```

## Setup Methods

### Method 1: Docker Compose (Recommended)

#### Project Structure
```
website-search/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── .env
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── tailwind.config.js
├── docker-compose.yml
├── .env
└── README.md
```

#### Quick Start
```bash
# Clone or create the project
git clone <repository-url>
cd website-search

# Create environment file
cp .env
# Edit .env with your Weaviate credentials

# Start the application
docker-compose up --build

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

---

### Method 3: Local Development Setup

#### Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials
cp .env

# Run the backend
uvicorn main:app --reload
```

#### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

---
## API Endpoints

### POST /search
Search through website content.

**Request Body:**
```json
{
  "query": "your search query",
  "website": "https://example.com"
}
```

**Response:**
```json
{
  "results": [
    {
      "score": 0.95,
      "url": "https://example.com/page",
      "content": "relevant content snippet...",
      "html_snippet": "<div>HTML content...</div>"
    }
  ],
  "time": 2.5,
  "total_chunks": 150
}
```

### DELETE /clear-collections
Clear all indexed website collections.

**Response:**
```json
{
  "message": "Deleted 5 collections"
}
```

---

## Usage

1. **Start the application** using any of the setup methods above
2. **Open the frontend** in your browser (http://localhost:3000)
3. **Enter a website URL** (e.g., https://example.com)
4. **Enter your search query** (e.g., "pricing information")
5. **Click "Search Website"** to crawl and search the content
6. **View results** with relevance scores and content snippets

## Changelog

### v1.0.0
- Initial release
- Basic website crawling and search functionality
- Docker containerization
- React frontend with Tailwind CSS
