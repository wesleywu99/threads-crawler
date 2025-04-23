import json
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from parsel import Selector
import sys
import io
from flask import Flask, request, jsonify
import atexit

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Initialize Flask app
app = Flask(__name__)

# Global variables for browser management
playwright = None
browser = None
page = None
browser_initialized = False

def init_browser():
    """Initialize Playwright browser"""
    global playwright, browser, page, browser_initialized
    
    if not browser_initialized:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)  # Headless mode for server environment
        page = browser.new_page()
        browser_initialized = True
        print("Browser initialized")

def close_browser():
    """Close browser and Playwright instance"""
    global playwright, browser, page, browser_initialized
    
    if page:
        page.close()
    if browser:
        browser.close()
    if playwright:
        playwright.stop()
    
    browser_initialized = False
    print("Browser closed")

def login_instagram():
    """Login to Instagram account"""
    global page
    
    try:
        page.goto("https://www.threads.net/login")
        print("Threads login page")
        
        page.wait_for_selector('input[placeholder="用戶名稱、手機號碼或電子郵件地址"]', timeout=10000)
        
        page.fill('input[placeholder="用戶名稱、手機號碼或電子郵件地址"]', 'wesllllwyywu')
        page.fill('input[placeholder="密碼"]', 'Fimmick@123')
        
        page.click('text="登入"')
        
        page.wait_for_load_state('networkidle')
        
        print("Instagram login successful")
        return True
        
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return False

def search_threads_result(keyword, pages=1):
    """
    Search for keywords on Threads platform and get results
    
    Args:
        keyword: Keyword to search
        pages: Number of pages to load
        
    Returns:
        List containing search results
    """
    global page
    
    url = f"https://www.threads.net/search?q={keyword}&&filter=recent"
    page.goto(url)
    print(f"Visiting search page: {url}")
    
    page.wait_for_load_state('networkidle')
    
    # Inject JavaScript code for AJAX tracking
    ajax_injection_code = """
        (function() {
            const originalXHR = window.XMLHttpRequest;
            const originalFetch = window.fetch;

            function CustomXHR() {
                const xhr = new originalXHR();
                const request = {
                    method: '',
                    url: '',
                    data: null,
                    headers: {}
                };

                const originalOpen = xhr.open;
                xhr.open = function(method, url) {
                    request.method = method;
                    request.url = url;
                    originalOpen.apply(xhr, arguments);
                };

                const originalSetRequestHeader = xhr.setRequestHeader;
                xhr.setRequestHeader = function(header, value) {
                    request.headers[header] = value;
                    originalSetRequestHeader.call(xhr, header, value);
                };

                const originalSend = xhr.send;
                xhr.send = function(data) {
                    request.data = data;

                    xhr.addEventListener('readystatechange', function() {
                        if (xhr.readyState === 4) {
                            const response = {
                                status: xhr.status,
                                statusText: xhr.statusText,
                                url: xhr.responseURL,
                                response: xhr.response,
                                headers: xhr.getAllResponseHeaders()
                            };

                            handleRequestComplete(request, response);
                        }
                    });
                    originalSend.apply(xhr, arguments);
                };
                return xhr;
            }

            window.fetch = function(input, init = {}) {
                const request = {
                    method: init.method || 'GET',
                    url: typeof input === 'string' ? input : input.url,
                    headers: init.headers || {},
                    data: init.body
                };

                return originalFetch(input, init).then(response => {
                    response.clone().text().then(body => {
                        const fetchResponse = {
                            status: response.status,
                            statusText: response.statusText,
                            url: response.url,
                            response: body,
                            headers: Object.fromEntries(response.headers.entries())
                        };

                        handleRequestComplete(request, fetchResponse);
                    });
                    return response;
                });
            };

            window.XMLHttpRequest = CustomXHR;

            window._thread_data = [];

            function handleRequestComplete(request, response) {
                if (response.response.indexOf("searchResults") === -1)  {return;}
                window._thread_data.push(response.response);
            }
        })();
    """
    page.evaluate(ajax_injection_code)
    
    for i in range(pages):
        try:
            print(f"Getting page {i+1}...")
            
            page.wait_for_selector("[data-pressable-container=true]", timeout=30000)
            
            time.sleep(1)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            
            time.sleep(4)
            
        except Exception as e:
            print(f"Timeout waiting for element: {str(e)}")
            return None
    
    # Get page data
    thread_data = page.evaluate("window._thread_data")
    
    # Extract important data from HTML
    relevant_datasets = []
    selector = Selector(page.content())
    hidden_datasets = selector.css('script[type="application/json"][data-sjs]::text').getall()
    
    for dataset in hidden_datasets:
        if '"ScheduledServerJS"' not in dataset or "thread_items" not in dataset:
            continue
        
        try:
            json_data = json.loads(dataset)
            edges = json_data['require'][0][3][0]['__bbox']['require'][0][3][1]['__bbox']['result']['data']['searchResults']['edges']
            relevant_datasets.extend(edges)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Error parsing dataset: {str(e)}")
            continue
    
    # Extract data from AJAX responses
    for dataset in thread_data:
        if "searchResults" not in dataset:
            continue
        
        try:
            json_data = json.loads(dataset)
            edges = json_data["data"]["searchResults"]["edges"]
            relevant_datasets.extend(edges)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing AJAX data: {str(e)}")
            continue
    
    return relevant_datasets

def process_thread_results(results):
    """Process results and extract relevant data fields"""
    processed_data = []
    unique_codes = set()
    
    for result in results:
        try:
            node = result['node']
            thread = node['thread']
            for item in thread['thread_items']:
                post = item['post']
                user = post['user']
                text_post_info = post['text_post_app_info']
                
                code = post['code']
                
                # Skip duplicates
                if code in unique_codes:
                    continue
                    
                unique_codes.add(code)
                
                post_url = f"https://www.threads.net/@{user['username']}/post/{code}"
                
                reshare_count = text_post_info.get('reshare_count', 0) or 0
                quote_count = text_post_info.get('quote_count', 0) or 0
                
                post_time = datetime.fromtimestamp(post['taken_at'])
                
                data_item = {
                    'Post Time': post_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'Username': user['username'],
                    'Content': post['caption']['text'] if post['caption'] else '',
                    'Likes': post['like_count'],
                    'Comments': text_post_info['direct_reply_count'],
                    'Reposts': text_post_info['repost_count'],
                    'Reshares': reshare_count,
                    'Quotes': quote_count,
                    'Accessibility Caption': post['accessibility_caption'] if post['accessibility_caption'] else '',
                    'Code': code
                }
                
                processed_data.append(data_item)
        except Exception as e:
            print(f"Error processing result: {str(e)}")
            continue
    
    # Sort by post time (descending)
    processed_data.sort(key=lambda x: datetime.strptime(x['Post Time'], '%Y-%m-%d %H:%M:%S'), reverse=True)
    
    return processed_data

@app.route('/api/search', methods=['GET'])
def search_api():
    """API endpoint to search Threads by keyword"""
    keyword = request.args.get('keyword', '')
    pages = int(request.args.get('pages', 3))
    
    if not keyword:
        return jsonify({'error': 'Keyword parameter is required'}), 400
    
    try:
        # Make sure browser is initialized
        init_browser()
        
        if not login_instagram():
            # Try to reinitialize browser if login fails
            close_browser()
            init_browser()
            if not login_instagram():
                return jsonify({'error': 'Failed to login to Threads'}), 500
        
        results = search_threads_result(keyword, pages)
        
        if results:
            processed_data = process_thread_results(results)
            return jsonify({
                'keyword': keyword,
                'count': len(processed_data),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data': processed_data
            })
        else:
            return jsonify({'error': 'No results found or an error occurred'}), 404
            
    except Exception as e:
        print(f"API error: {str(e)}")
        # Try to reinitialize browser on error
        try:
            close_browser()
            init_browser()
        except:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    is_browser_ok = browser_initialized
    return jsonify({
        'status': 'ok' if is_browser_ok else 'error',
        'browser_status': 'initialized' if is_browser_ok else 'not initialized',
        'message': 'Threads Search API service is running'
    })

@app.route('/', methods=['GET'])
def home():
    """Simple home page with API documentation"""
    return """
    <html>
        <head>
            <title>Threads Search API</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; color: #333; max-width: 800px; margin: 0 auto; }
                h1 { color: #2c3e50; }
                code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
                pre { background: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }
                .endpoint { margin-bottom: 30px; }
                .param { margin-left: 20px; }
            </style>
        </head>
        <body>
            <h1>Threads Search API</h1>
            <p>This API allows you to search for posts on Threads by keyword</p>
            
            <div class="endpoint">
                <h2>Search Endpoint</h2>
                <p><code>GET /api/search</code></p>
                <p>Parameters:</p>
                <div class="param">
                    <p><strong>keyword</strong> (required): The search term to find in Threads posts</p>
                    <p><strong>pages</strong> (optional): Number of pages to scrape (default: 3)</p>
                </div>
                <p>Example: <a href="/api/search?keyword=example&pages=2">/api/search?keyword=example&pages=2</a></p>
            </div>
            
            <div class="endpoint">
                <h2>Health Check Endpoint</h2>
                <p><code>GET /api/health</code></p>
                <p>Returns the current status of the service</p>
                <p>Example: <a href="/api/health">/api/health</a></p>
            </div>
        </body>
    </html>
    """

# Register cleanup function
atexit.register(close_browser)

if __name__ == "__main__":
    try:
        # Start the Flask app
        port = int(os.environ.get('PORT', 10000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"Startup error: {str(e)}")
        # Ensure browser is closed on error
        close_browser()