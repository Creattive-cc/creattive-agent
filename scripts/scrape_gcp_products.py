
import sys
import httpx
from bs4 import BeautifulSoup
import json
from pathlib import Path
import shutil
from collections import defaultdict

def main():
    """
    Scrapes the Google Cloud products page, extracts product information,
    and saves it to a markdown file.
    """
    url = "https://cloud.google.com/products?hl=pt-br"
    output_path = Path("knowledge/gcp_catalog.md")
    chroma_db_path = Path("data/chroma")

    print(f"1. Fetching URL: {url}")
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e}")
        return
    except httpx.RequestError as e:
        print(f"An error occurred while requesting the page: {e}")
        return

    print("2. Parsing HTML content...")
    soup = BeautifulSoup(response.text, "html.parser")

    # --- Data Extraction Logic ---
    products_data = None
    print("3. Searching for product data in 'AF_initDataCallback'...")

    data_script = None
    for script in soup.find_all("script"):
        if script.string and "AF_initDataCallback" in script.string:
            data_script = script.string
            break
    
    if data_script:
        print("Found AF_initDataCallback script.")
        try:
            import pdb; pdb.set_trace()
            # Extract the JSON object from the function call
            json_str = data_script.split("AF_initDataCallback(", 1)[1].rsplit(")", 1)[0]
            data = json.loads(json_str)
            print(f"Data keys: {data.keys()}")
            sys.stdout.flush()
            
            # The actual product list is in data['data'][0]
            # It's a list of lists.
            # raw_products = data['data'][0]
            # print(f"Found {len(raw_products)} raw product entries.")

            processed_products = []
            for item in raw_products:
                try:
                    # Based on inspection of the data structure
                    name = item[6]
                    description = item[7]
                    category = item[19]

                    if name and description and category:
                        processed_products.append({
                            "name": name,
                            "description": description,
                            "cloud_offering": category,
                        })
                except (IndexError, TypeError):
                    # Ignore items that don't have the expected structure
                    continue
            
            if processed_products:
                products_data = processed_products
                print(f"Successfully processed {len(products_data)} products.")

        except (IndexError, json.JSONDecodeError, KeyError) as e:
            print(f"Error processing AF_initDataCallback data: {e}")

    if not products_data:
        print("Failed to extract product data from the page. Exiting.")
        return

    print("4. Processing extracted product data...")
    # Group products by category
    products_by_category = defaultdict(list)
    for product in products_data:
        # Adjust field names based on the actual JSON structure
        category_name = product.get("cloud_offering", product.get("category", "Outras Ferramentas"))
        products_by_category[category_name].append({
            "name": product.get("name", "N/A"),
            "description": product.get("description", "N/A"),
        })

    print(f"5. Writing data to {output_path}...")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("""# Catálogo de Produtos do Google Cloud Platform (GCP)

""")
        f.write("""Este documento contém uma lista de produtos e serviços oferecidos pelo GCP, extraída da página oficial.

""")

        # Sort categories for consistent output
        sorted_categories = sorted(products_by_category.keys())

        for category in sorted_categories:
            f.write(f"## {category}\n\n")
            # Sort products within the category for consistent output
            sorted_products = sorted(products_by_category[category], key=lambda p: p['name'])
            for product in sorted_products:
                f.write(f"### {product['name']}\n")
                f.write(f"{product['description']}\n\n")

    print(f"Successfully wrote {len(products_data)} products to {output_path}.")

    print(f"6. Deleting old ChromaDB index at {chroma_db_path}...")
    if chroma_db_path.exists() and chroma_db_path.is_dir():
        try:
            shutil.rmtree(chroma_db_path)
            print("ChromaDB index deleted successfully.")
        except OSError as e:
            print(f"Error deleting ChromaDB index: {e}")
    else:
        print("ChromaDB index not found, skipping deletion.")

if __name__ == "__main__":
    main()
