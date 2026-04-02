"""
Web Search & Scraping Service Wrapper.
Provides tools for querying multiple web search engines (Tavily, Serper, Brave) 
with automatic failover, and scraping targeted webpages using BeautifulSoup.
"""
import sys
import dotenv
dotenv.load_dotenv()

from tavily import TavilyClient
import requests
import os
from bs4 import BeautifulSoup

def Tavily(query):
    try: 
        tavily_client = TavilyClient()
        response = tavily_client.search(query, limit=5)['results']
        return response

    except Exception as e:
        # pass # "Tavily failed with Error:", e)
        return f"ERROR"
    

def Serper(query):
    api_key = os.getenv("SERPER_API_KEY")
    url = "https://google.serper.dev/search"

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "q": query,
        "count": 5
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        results = response.json()
        
        output = []
        for item in results.get("organic", [])[:3]:
            output.append({
                "url": item.get("link"),
                "title": item.get("title"),
                "content": item.get("snippet")
            })
        if output:
            return output
        else:
            # pass # "Serper failed with Error : No Results Found")
            return("ERROR")

    except Exception as e:
        # pass # f"Serper failed with Error: {e}")
        return f"ERROR"
    

def Brave(query):
    api_key = os.getenv("BRAVE_API_KEY")
    url = "https://api.search.brave.com/res/v1/web/search"

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key
    }

    params = {
        "q": query,
        "count": 5
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        output = []
        for item in data.get("web", {}).get("results", []):
            output.append({
                "url": item.get("url"),
                "title": item.get("title"),
                "content": item.get("description")
            })

        if output:
            return output
        else:
            # pass # "Brave failed with Error : No Results Found")
            return("ERROR")
        
    except Exception as e:
        # pass # f"Brave failed with Error: {e}")
        return f"ERROR"
    


def WebSearch(query):
    tavily_results = Tavily(query)
    if tavily_results == "ERROR":
        brave_results = Brave(query)
        if brave_results == "ERROR":
            serper_results = Serper(query)
            if serper_results == "ERROR":
                return "ERROR"
            return serper_results
        else:
            return brave_results
    else:
        return tavily_results
    

# Scraping Function using BeautifulSoup to scrape the whole website
def scrape_page(url):
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")

        paragraphs = [p.get_text() for p in soup.find_all("p")]
        text = "\n".join(paragraphs)
        
        return text if text.strip() else "ERROR"
    except Exception as e:
        return "ERROR"