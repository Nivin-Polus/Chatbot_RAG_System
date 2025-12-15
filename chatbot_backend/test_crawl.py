import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import sys

async def main():
    url = "https://policies.mit.edu/policies-procedures/70-general-employment-policies/74-benefits-faculty-and-staff-members"
    print(f"Testing deep extraction on {url}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Enable console logging from the browser
        page = await context.new_page()
        page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))
        
        print("\n--- Navigating ---")
        try:
            # Try looser wait strategy first to see if it loads at all
            response = await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            print(f"Status: {response.status}")
            
            # Wait a bit for JS
            await page.wait_for_timeout(2000)
            
            content = await page.content()
            print(f"HTML Length: {len(content)}")
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Check Title
            title = soup.title.string if soup.title else "No Title"
            print(f"Title: {title}")
            
            # Check Body Text
            body_text = soup.body.get_text(separator=' ', strip=True) if soup.body else ""
            print(f"Body Text Length: {len(body_text)}")
            print(f"Body Text Preview: {body_text[:200]}...")
            
            # Check formatting (h1, p)
            h1s = [h.get_text(strip=True) for h in soup.find_all('h1')]
            print(f"H1 Tags: {h1s}")
            
            ps = len(soup.find_all('p'))
            print(f"Paragraph tags count: {ps}")

            # Check if it looks like a blocked page
            if "access denied" in body_text.lower() or "captcha" in body_text.lower():
                print("WARNING: Possible Anti-Bot detection!")

        except Exception as e:
            print(f"FAILED: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
