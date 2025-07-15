from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import weaviate
from weaviate.classes.query import MetadataQuery
from sentence_transformers import SentenceTransformer
import time
import os
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse
import hashlib
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Website Search API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

API_KEY = os.getenv("WEAVIATE_API_KEY")
WEAVIATE_URL = os.getenv("WEAVIATE_CLUSTER_URL")
model = SentenceTransformer('all-MiniLM-L6-v2')
weaviate_client = None

class SearchRequest(BaseModel):
    query: str
    website: str

class SearchResult(BaseModel):
    score: float
    url: str
    content: str
    html_snippet: Optional[str] = None

class SearchResponse(BaseModel):
    results: List[SearchResult]
    time: float
    total_chunks: int

@app.on_event("startup")
async def startup_event():
    global weaviate_client
    try:
        weaviate_client = weaviate.connect_to_weaviate_cloud(
            cluster_url=WEAVIATE_URL,
            auth_credentials=weaviate.auth.AuthApiKey(API_KEY)
        )
        logger.info("Weaviate client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Weaviate client: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    global weaviate_client
    if weaviate_client:
        weaviate_client.close()
        logger.info("Weaviate client closed")

async def fetch_url_content(session: aiohttp.ClientSession, url: str) -> tuple[str, str]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                content = await response.text()
                return url, content
            else:
                logger.warning(f"Failed to fetch {url}: Status {response.status}")
                return url, ""
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return url, ""

async def get_website_links(base_url: str, max_pages: int = 1000) -> List[str]:
    try:
        async with aiohttp.ClientSession() as session:
            _, content = await fetch_url_content(session, base_url)
            if not content:
                return [base_url]
            
            soup = BeautifulSoup(content, 'html.parser')
            links = set([base_url])
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    full_url = urljoin(base_url, href)
                elif href.startswith(base_url):
                    full_url = href
                else:
                    continue

                if not any(skip in full_url.lower() for skip in ['#', 'javascript:', 'mailto:', '.pdf', '.jpg', '.png', '.gif']):
                    links.add(full_url)
                
                if len(links) >= max_pages:
                    break
            
            return list(links)
    except Exception as e:
        logger.error(f"Error getting links from {base_url}: {e}")
        return [base_url]

def clean_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "meta", "link", "nav", "header", "footer"]):
        tag.decompose()
    return soup

def chunk_text(text: str, max_tokens: int = 500) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_tokens):
        chunk = ' '.join(words[i:i + max_tokens])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def get_collection_name(base_url: str) -> str:
    import re
    parsed = urlparse(base_url)
    domain = parsed.netloc.replace('.', '_').replace('-', '_')
    domain = re.sub(r'[^a-zA-Z0-9_]', '', domain)
    if not domain or not domain[0].isalpha():
        domain = 'website_' + domain
    return f"Website_{domain}"[:50]

async def index_website_content(urls: List[str], collection_name: str) -> int:
    try:
        collection = None
        try:
            weaviate_client.collections.delete(collection_name)
            logger.info(f"Deleted existing collection {collection_name}")
        except:
            pass
        
        try:
            weaviate_client.collections.create(
                name=collection_name,
                vectorizer_config=weaviate.classes.config.Configure.Vectorizer.none(),
                properties=[
                    weaviate.classes.config.Property(name="content", data_type=weaviate.classes.config.DataType.TEXT),
                    weaviate.classes.config.Property(name="url", data_type=weaviate.classes.config.DataType.TEXT),
                    weaviate.classes.config.Property(name="html_snippet", data_type=weaviate.classes.config.DataType.TEXT),
                    weaviate.classes.config.Property(name="page_title", data_type=weaviate.classes.config.DataType.TEXT),
                ]
            )
            logger.info(f"Created new collection {collection_name}")
        except Exception as create_error:
            if "already exists" in str(create_error):
                logger.info(f"Collection {collection_name} already exists, using existing collection")
            else:
                raise create_error
        
        collection = weaviate_client.collections.get(collection_name)

        async with aiohttp.ClientSession() as session:
            tasks = [fetch_url_content(session, url) for url in urls]
            results = await asyncio.gather(*tasks)

        total_chunks = 0
        
        with collection.batch.dynamic() as batch:
            for url, html_content in results:
                if not html_content:
                    continue
                
                soup = clean_html(html_content)
                text = soup.get_text(separator=' ', strip=True)
                
                title_tag = soup.find('title')
                page_title = title_tag.get_text().strip() if title_tag else ""
                
                chunks = chunk_text(text, max_tokens=500)
                
                for chunk in chunks:
                    if len(chunk.strip()) > 50:
                        embedding = model.encode(chunk).tolist()
                        html_snippet = str(soup)[:1000]
                        
                        batch.add_object(
                            properties={
                                "content": chunk,
                                "url": url,
                                "html_snippet": html_snippet,
                                "page_title": page_title
                            },
                            vector=embedding
                        )
                        total_chunks += 1

        logger.info(f"Indexed {total_chunks} chunks from {len(urls)} pages")
        return total_chunks
        
    except Exception as e:
        logger.error(f"Error indexing website content: {e}")
        raise

async def search_content(query: str, collection_name: str, top_k: int = 10) -> List[SearchResult]:
    try:
        collection = weaviate_client.collections.get(collection_name)
        query_embedding = model.encode(query).tolist()
        
        results = collection.query.near_vector(
            near_vector=query_embedding,
            limit=top_k,
            return_metadata=MetadataQuery(distance=True)
        )
        
        search_results = []
        for obj in results.objects:
            score = round(1 - obj.metadata.distance, 3)
            result = SearchResult(
                score=score,
                url=obj.properties['url'],
                content=obj.properties['content'][:300] + "..." if len(obj.properties['content']) > 300 else obj.properties['content'],
                html_snippet=obj.properties.get('html_snippet', '')[:500]
            )
            search_results.append(result)
        
        return search_results
        
    except Exception as e:
        logger.error(f"Error searching content: {e}")
        raise

@app.post("/search", response_model=SearchResponse)
async def search_website(data: SearchRequest):
    try:
        start_time = time.perf_counter()
        
        # Validate inputs
        if not data.website or not data.query:
            raise HTTPException(status_code=400, detail="Website URL and query are required")
        
        # Normalize URL
        if not data.website.startswith(('http://', 'https://')):
            data.website = 'https://' + data.website
        
        # Get collection name
        collection_name = get_collection_name(data.website)
        
        # Get website links
        logger.info(f"Fetching links from {data.website}")
        urls = await get_website_links(data.website, max_pages=1500)
        
        # Index content
        logger.info(f"Indexing {len(urls)} pages")
        total_chunks = await index_website_content(urls, collection_name)
        
        # Search content
        logger.info(f"Searching for: {data.query}")
        results = await search_content(data.query, collection_name, top_k=10)
        
        end_time = time.perf_counter()
        duration = round(end_time - start_time, 2)
        
        return SearchResponse(
            results=results,
            time=duration,
            total_chunks=total_chunks
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/clear-collections")
async def clear_all_collections():
    try:
        collections = weaviate_client.collections.list_all()
        deleted_count = 0
        for collection in collections:
            if collection.name.startswith("Website_"):
                try:
                    weaviate_client.collections.delete(collection.name)
                    deleted_count += 1
                    logger.info(f"Deleted collection: {collection.name}")
                except Exception as e:
                    logger.error(f"Failed to delete collection {collection.name}: {e}")
        
        return {"message": f"Deleted {deleted_count} collections"}
    except Exception as e:
        logger.error(f"Error clearing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)