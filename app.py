from flask import Flask, render_template, request, jsonify
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from typing import List, Dict

# Load API Keys
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

if not GEMINI_API_KEY or not SERPER_API_KEY:
    print("❌ Please set GEMINI_API_KEY and SERPER_API_KEY in your .env file")
    exit()

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Helper Functions
def search_products_serper(query: str, num_results: int = 10) -> List[Dict]:
    """Search for products using Serper API"""
    url = "https://google.serper.dev/shopping"
    payload = json.dumps({
        "q": query,
        "gl": "us",
        "hl": "en",
        "num": num_results
    })
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('shopping', [])
    except Exception as e:
        print(f"Error fetching products: {str(e)}")
        return []

def get_ai_recommendations(products: List[Dict], user_preferences: str, budget_range: str, category: str) -> str:
    """Get AI-powered product recommendations using Gemini"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        products_text = ""
        for i, product in enumerate(products[:10], 1):
            products_text += f"""
Product {i}:
- Title: {product.get('title', 'N/A')}
- Price: {product.get('price', 'N/A')}
- Rating: {product.get('rating', 'N/A')}
- Reviews: {product.get('reviewsCount', 'N/A')}
- Source: {product.get('source', 'N/A')}
- Link: {product.get('link', 'N/A')}
"""
        
        prompt = f"""
You are an expert product recommendation assistant. Based on the following user preferences and product data, provide personalized recommendations.

User Preferences: {user_preferences}
Budget Range: {budget_range}
Category: {category}

Available Products:
{products_text}

Please analyze these products and provide:
1. Top 3-5 most suitable recommendations based on user preferences
2. Brief explanation for each recommendation
3. Highlight key features that match user needs
4. Include price and where to buy
5. Format as clean, structured recommendations with HTML formatting

Focus on value, quality, and matching user requirements.
"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"

def filter_by_budget(products: List[Dict], budget_range: str) -> List[Dict]:
    """Filter products by budget range"""
    if budget_range == "No preference":
        return products
    
    budget_ranges = {
        "Under $100": (0, 100),
        "$100 - $300": (100, 300),
        "$300 - $500": (300, 500),
        "$500 - $1000": (500, 1000),
        "Over $1000": (1000, float('inf'))
    }
    
    if budget_range not in budget_ranges:
        return products
    
    min_price, max_price = budget_ranges[budget_range]
    filtered = []
    
    for product in products:
        price_str = product.get('price', '')
        if price_str:
            # Extract numeric price
            price_num = ''.join(filter(str.isdigit, price_str.replace(',', '').replace('.', '')))
            if price_num:
                try:
                    price = float(price_num) / 100 if len(price_num) > 2 else float(price_num)
                    if min_price <= price <= max_price:
                        filtered.append(product)
                except:
                    filtered.append(product)
            else:
                filtered.append(product)
    
    return filtered

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    
    user_query = data.get('query', '')
    category = data.get('category', 'Other')
    budget_range = data.get('budget_range', 'No preference')
    num_results = data.get('num_results', 10)
    brand_preference = data.get('brand_preference', '')
    feature_priority = data.get('feature_priority', [])
    
    if not user_query.strip():
        return jsonify({'error': 'Please enter a search query'}), 400
    
    # Create enhanced query
    enhanced_query = user_query
    if category != "Other":
        enhanced_query = f"{category} {enhanced_query}"
    if brand_preference:
        enhanced_query = f"{enhanced_query} {brand_preference}"
    
    # Search products
    products = search_products_serper(enhanced_query, num_results)
    
    if not products:
        return jsonify({'error': 'No products found. Try adjusting your search query.'}), 404
    
    # Filter by budget
    filtered_products = filter_by_budget(products, budget_range)
    
    # Build enhanced preferences
    preferences_text = user_query
    if feature_priority:
        preferences_text += f". Important features: {', '.join(feature_priority)}"
    if brand_preference:
        preferences_text += f". Preferred brand: {brand_preference}"
    
    # Get AI recommendations
    ai_recommendations = get_ai_recommendations(
        filtered_products, 
        preferences_text, 
        budget_range, 
        category
    )
    
    # Calculate statistics
    avg_rating = 0
    if filtered_products:
        ratings = [float(p.get('rating', 0)) for p in filtered_products if p.get('rating')]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
    
    return jsonify({
        'success': True,
        'products_found': len(products),
        'products_after_filter': len(filtered_products),
        'avg_rating': round(avg_rating, 1),
        'budget_range': budget_range,
        'ai_recommendations': ai_recommendations,
        'products': filtered_products
    })

# === Run the App ===
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))