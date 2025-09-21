from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
import json
import random

def extract_price(price_text):
    """Extract numeric price value from price text"""
    try:
        price_text = price_text.replace(',', '')
        if 'Cr' in price_text:
            return float(re.findall(r'([\d.]+)', price_text)[0]) * 10000000
        elif 'Lac' in price_text:
            return float(re.findall(r'([\d.]+)', price_text)[0]) * 100000
        else:
            return float(re.findall(r'([\d.]+)', price_text)[0])
    except:
        return None

def extract_area(area_text):
    """Extract numeric area value from area text"""
    try:
        value = re.findall(r'([\d,]+\.?\d*)', area_text)[0].replace(',', '')
        if 'sqft' in area_text.lower() or 'sq ft' in area_text.lower():
            return float(value)
        elif 'sqyrd' in area_text.lower() or 'sq yrd' in area_text.lower():
            return float(value) * 9  # Convert sq yard to sq ft
        else:
            return float(value)
    except:
        return None

def extract_bhk(title):
    """Extract number of BHK from title"""
    try:
        bhk = re.findall(r'(\d+)\s*BHK', title)
        return int(bhk[0]) if bhk else None
    except:
        return None

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return None
    return ' '.join(text.strip().split())

def scroll_and_wait(driver, wait_time=2):
    """Scroll to bottom and check if new content loaded"""
    try:
        # Get current height
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Wait for new content to load
        time.sleep(wait_time)
        
        # Calculate new scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        return new_height != last_height  # Returns True if more content loaded
    except Exception as e:
        print(f"Error during scrolling: {str(e)}")
        return False

# Configuration
MAX_PROPERTIES = 1000  # Target number of properties
MAX_SCROLL_ATTEMPTS = 200  # Maximum scroll attempts
SCROLL_WAIT_TIME = 3  # Seconds to wait after each scroll

# Configure webdriver
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_page_load_timeout(30)

# Initialize tracking variables
processed_ids = set()
data = []
scroll_count = 0
total_new_listings = 0

print("\nStarting infinite scroll data collection...")
print(f"Target: {MAX_PROPERTIES} properties")

try:
    # Load initial page
    url = "https://www.magicbricks.com/property-for-sale/residential-real-estate?bedroom=&proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment,Residential-House,Villa&cityName=New-Delhi"
    driver.get(url)
    wait = WebDriverWait(driver, 30)

    # Main scraping loop
    while len(data) < MAX_PROPERTIES and scroll_count < MAX_SCROLL_ATTEMPTS:
        # Get current listings
        listings = driver.find_elements(By.CSS_SELECTOR, ".mb-srp__list")
        print(f"\nScroll #{scroll_count + 1}")
        print(f"Current listings found: {len(listings)}")
        print(f"Processed so far: {len(data)}")
        
        # Get JSON-LD data
        try:
            script_tag = driver.find_element(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
            json_text = script_tag.get_attribute('innerHTML')
            json_ld_data = json.loads(json_text)
        except Exception as e:
            print(f"Error parsing JSON-LD data: {str(e)}")
            json_ld_data = {}
        
        # Process listings
        new_listings = 0
        for i, listing in enumerate(listings, 1):
            try:
                # Get listing ID
                listing_id = listing.get_attribute('id').replace('cardid', '')
                
                # Skip if already processed
                if listing_id in processed_ids:
                    continue
                
                processed_ids.add(listing_id)  # Mark as processed
                
                # Extract basic details
                title = clean_text(listing.find_element(By.CSS_SELECTOR, ".mb-srp__card--title").text)
                price = clean_text(listing.find_element(By.CSS_SELECTOR, ".mb-srp__card__price--amount").text)
                area = clean_text(listing.find_element(By.CSS_SELECTOR, ".mb-srp__card__summary--value").text)
                
                # Get optional fields
                locality = None
                try:
                    locality = clean_text(listing.find_element(By.CSS_SELECTOR, ".mb-srp__card__society--name").text)
                except Exception:
                    pass
                    
                address = None
                try:
                    address = clean_text(listing.find_element(By.CSS_SELECTOR, ".mb-srp__card--address").text)
                except Exception:
                    pass
                
                # Get additional details
                additional_info = {}
                try:
                    details = listing.find_elements(By.CSS_SELECTOR, ".mb-srp__card__summary__list--item")
                    additional_info = {
                        clean_text(d.find_element(By.CSS_SELECTOR, "label").text): 
                        clean_text(d.text.replace(d.find_element(By.CSS_SELECTOR, "label").text, ""))
                        for d in details
                    }
                except Exception:
                    pass
                
                # Get structured data from JSON-LD
                json_info = json_ld_data.get(listing_id, {})
                
                # Create property data dictionary
                property_data = {
                    "listing_id": listing_id,
                    "title": title,
                    "bhk": extract_bhk(title),
                    "price_text": price,
                    "price": extract_price(price),
                    "area_text": area,
                    "area_sqft": extract_area(area),
                    "locality": locality,
                    "address": address,
                    "url": json_info.get('url'),
                    "property_type": json_info.get('name', '').split(' ')[0] if json_info.get('name') else None
                }
                
                # Add additional details
                property_data.update(additional_info)
                
                # Save the data
                data.append(property_data)
                new_listings += 1
                print(f"--> Successfully scraped: {title[:70]}...")
                
            except Exception as e:
                print(f"Error processing listing #{i}: {str(e)}")
                continue
        
        total_new_listings += new_listings
        print(f"New listings in this scroll: {new_listings}")
        print(f"Total listings collected: {len(data)}")
        
        # Break if we've reached the target
        if len(data) >= MAX_PROPERTIES:
            print("\nReached target number of properties.")
            break
        
        # Try to load more content
        print("\nScrolling to load more content...")
        more_content = scroll_and_wait(driver, SCROLL_WAIT_TIME)
        scroll_count += 1
        
        if not more_content:
            print("\nNo new content loaded after scrolling.")
            break
        
        # Add a random delay between scrolls
        time.sleep(1 + random.random())

except Exception as e:
    print(f"\nFatal error during scraping: {str(e)}")
    
finally:
    print(f"\nFinished scraping process:")
    print(f"Total scrolls performed: {scroll_count}")
    print(f"Total listings collected: {len(data)}")
    print(f"Unique properties found: {len(processed_ids)}")
    
    if data:
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Clean and organize columns
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['area_sqft'] = pd.to_numeric(df['area_sqft'], errors='coerce')
        
        # Calculate price per sq ft
        df['price_per_sqft'] = df['price'] / df['area_sqft']
        
        # Reorder columns
        desired_order = ['listing_id', 'title', 'bhk', 'price', 'price_text', 'area_sqft', 
                        'area_text', 'price_per_sqft', 'property_type', 'locality', 
                        'address', 'url']
        
        # Get remaining columns (additional details that may vary)
        remaining_cols = [col for col in df.columns if col not in desired_order]
        final_order = desired_order + remaining_cols
        
        # Reorder and save
        df = df[final_order]
        df.to_csv("magicbricks_delhi1.csv", index=False)
        
        print("\n✅ Successfully created magicbricks_delhi.csv")
        print("\nDataset Statistics:")
        print(f"Total Properties: {len(df)}")
        print(f"Average Price: ₹{df['price'].mean():,.2f}")
        print(f"Average Area: {df['area_sqft'].mean():,.2f} sq ft")
        print(f"Average Price/sq ft: ₹{df['price_per_sqft'].mean():,.2f}")
        print(f"\nProperty Types:\n{df['property_type'].value_counts()}")
        print(f"\nBHK Distribution:\n{df['bhk'].value_counts().sort_index()}")
        
        print("\nDataset Preview:")
        print(df[['title', 'bhk', 'price', 'area_sqft', 'locality']].head())
        
        print("\nMissing Values Summary:")
        print(df.isnull().sum())
    else:
        print("❌ No data was scraped, so no CSV file was created.")

# Clean up
driver.quit()