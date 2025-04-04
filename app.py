from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import json
import time

app = Flask(__name__)

def extract_user_data(profile_id):
    intent_url = f"https://x.com/intent/user?user_id={profile_id}"

    chrome_options = Options()
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        driver.get(intent_url)
        time.sleep(90)  # Let the page load fully

        logs = driver.get_log('performance')
        user_data = None
        request_map = {}

        for entry in logs:
            message = json.loads(entry['message'])['message']
            if (message['method'] == 'Network.requestWillBeSent' and 
                'UserByRestId' in message['params']['request']['url'] and 
                message['params'].get('type') == 'XHR'):
                request_map[message['params']['requestId']] = True

        for entry in logs:
            message = json.loads(entry['message'])['message']
            if (message['method'] == 'Network.responseReceived' and 
                message['params']['requestId'] in request_map):
                request_id = message['params']['requestId']
                try:
                    body = driver.execute_cdp_cmd('Network.getResponseBody', 
                                                  {'requestId': request_id})
                    payload = json.loads(body['body'])
                    user_data = payload
                    break
                except Exception as e:
                    print(f"Error retrieving UserByRestId response: {e}")

        driver.quit()

        if not user_data:
            return None

        user_result = user_data.get('data', {}).get('user', {}).get('result', {})
        legacy = user_result.get('legacy', {})

        return {
            "capture_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "user_id": profile_id,
            "username": legacy.get("screen_name", "N/A"),
            "verified": user_result.get("is_blue_verified", "N/A"),
            "created_at": legacy.get("created_at", "N/A"),
            "description": legacy.get("description", "N/A")
        }

    except Exception as e:
        driver.quit()
        return {"error": str(e)}

@app.route('/user-info', methods=['GET'])
def get_user_info():
    profile_id = request.args.get('profile_id', '').strip()
    if not profile_id:
        return jsonify({"error": "Missing profile_id parameter"}), 400

    result = extract_user_data(profile_id)
    if not result:
        return jsonify({"error": "User data not found"}), 404

    return jsonify(result), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
