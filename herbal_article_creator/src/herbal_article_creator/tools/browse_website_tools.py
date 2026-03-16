import requests
import pdfplumber
import io
import re
from bs4 import BeautifulSoup
from crewai.tools import tool
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

@tool("browse_website_tool")
def browse_website_tool(url: str) -> str:
    """
    Reads the content of a given URL (HTML or PDF).
    It uses Selenium to render dynamic JavaScript content for HTML pages,
    then cleans the HTML by removing navigation, headers, footers, 
    and scripts, returning only the main content text.
    For PDFs, it extracts all text.
    """
    print(f"--- Browsing URL: {url} ---")
    driver = None
    try:
        # --- PART 1: URL PDF ---
        if url.lower().endswith('.pdf'):
            print("--- PDF detected, using requests... ---")
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            
            pdf_file = io.BytesIO(response.content)
            all_text = ""
            
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    all_text += page.extract_text() + "\n"
            
            print(f"--- Extracted {len(all_text)} chars from PDF ---")
            # text length PDF
            if len(all_text) > 30000:
                 print("--- PDF content too long, truncating ---")
                 all_text = all_text[:30000] + "\n... (content truncated)"
            return all_text

        # --- PART 2: HTML Webpage ---
        else:
            print("--- HTML site detected, using Selenium to render JavaScript... ---")
            
            options = Options()
            options.add_argument("--headless") # Not enable browser
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"user-agent={HEADERS['User-Agent']}") # fake browser

            # install/manage chrome drivers
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            driver.get(url)
            
            # Wait 5 seconds for JavaScript to load data.
            print("--- Waiting 5s for JS content to load... ---")
            time.sleep(5) 
            
            # Pull HTML "after" JavaScript has finished running.
            html_content = driver.page_source
            driver.quit() #Close your browser (very important!)
            
            # --- Use BeautifulSoup to "clean" the HTML that runs JS. ---
            soup = BeautifulSoup(html_content, 'lxml')
            
            # delete Tag
            for junk_tag in soup(['nav', 'footer', 'script', 'style', 'header', 'aside', 'form']):
                junk_tag.decompose()
            
            all_text = soup.get_text(separator='\n', strip=True)
            cleaned_text = re.sub(r'\n{3,}', '\n\n', all_text)
            
            print(f"--- Extracted {len(cleaned_text)} chars from (Cleaned, JS-Rendered) HTML ---")
            
            # length limit
            if len(cleaned_text) > 30000:
                print("--- HTML content too long, truncating ---")
                cleaned_text = cleaned_text[:30000] + "\n... (content truncated)"
                
            return cleaned_text

    except Exception as e:
        # close driver
        if driver:
            driver.quit()
        print(f"An unexpected error occurred while processing {url}: {e}")
        return f"Error: An unexpected error occurred. {e}"