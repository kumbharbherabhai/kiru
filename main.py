from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import csv
import random
from webdriver_manager.chrome import ChromeDriverManager
import os
import json

# ---------------- Setup Selenium ----------------
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--incognito")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument('--disable-blink-features=AutomationControlled')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ---------------- Open only 1 tab (you will open the 2nd one manually) ----------------
driver.get("about:blank")  # This is a dummy tab (left side)

print("➡️ कृपया Chrome में मैन्युअल रूप से एक नया टैब (Ctrl+T) खोलें और Shopee कैटेगरी पेज पर जाएँ।")
input("Shopee कैटेगरी पेज दूसरे टैब में खुलने के बाद यहाँ Enter दबाएँ...")

# ---------------- CSV setup ----------------
csv_file = "product_links.csv"
# Ensure the file is writable, create it if it doesn't exist.
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Product Link"])

# ---------------- API responses folder setup ----------------
data_folder = "api_responses"
os.makedirs(data_folder, exist_ok=True)

# ---------------- Scraping loop ----------------
while True:
    input("➡️ वर्तमान कैटेगरी टैब को स्क्रैप करने के लिए Enter दबाएँ...")

    try:
        # Always use the latest tab (the manual one)
        manual_tab = driver.window_handles[-1]
        driver.switch_to.window(manual_tab)
        print(f"✅ Active Tab URL: {driver.current_url}")

        # =========================================================================
        # STEP 1: सबसे पहले सभी प्रोडक्ट लिंक इकट्ठा करें
        # =========================================================================
        print("⏳ पेज को नीचे स्क्रॉल किया जा रहा है ताकि सभी प्रोडक्ट्स लोड हो सकें...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 4))
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        print("✅ स्क्रॉलिंग पूरी हुई।")

        product_elements = driver.find_elements(By.XPATH,
            '//div[contains(@class,"h-full") and .//a[@class="contents"]]/a[@class="contents"]'
        )

        # सभी लिंक को एक लिस्ट में स्टोर करें
        product_links = []
        for elem in product_elements:
            href = elem.get_attribute('href')
            if href:
                product_links.append(href)

        print(f"✅ कुल {len(product_links)} प्रोडक्ट लिंक मिले। अब इन्हें प्रोसेस किया जाएगा।")

        # सभी लिंक को एक साथ CSV में सेव करें
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for link in product_links:
                writer.writerow([link])
        print(f"✅ सभी {len(product_links)} लिंक '{csv_file}' में सेव कर दिए गए हैं।")

        # =========================================================================
        # STEP 2: अब एक-एक करके हर लिंक को प्रोसेस करें
        # =========================================================================
        for index, link in enumerate(product_links):
            print(f"\n🔄 प्रोसेस हो रहा है लिंक {index + 1}/{len(product_links)}: {link}")
            try:
                # प्रोडक्ट पेज पर जाएँ
                driver.get(link)
                time.sleep(random.uniform(2, 4))  # पेज लोड होने के लिए रुकें

                # इंसान की तरह थोड़ा स्क्रॉल करें
                driver.execute_script("window.scrollBy(0, Math.random() * 400 + 200);")
                time.sleep(random.uniform(1, 2))

                # URL से shop_id और item_id निकालें
                current_url = driver.current_url
                if '-i.' in current_url:
                    parts = current_url.split('-i.')[1].split('.')
                    if len(parts) >= 2:
                        shop_id = parts[0]
                        item_id = parts[1].split('?')[0]
                    else:
                        print(f"❌ इस URL से ID पार्स नहीं हो सकी: {current_url}")
                        continue
                else:
                    print(f"❌ अमान्य प्रोडक्ट URL फॉर्मेट: {current_url}")
                    continue

                # API URL बनाएँ
                api_url = f"https://shopee.tw/api/v4/pdp/get_pc?item_id={item_id}&shop_id={shop_id}&offset_in_minutes=330&detail_level=0"

                # JavaScript का उपयोग करके API डेटा प्राप्त करें
                script = f"""
                var callback = arguments[arguments.length - 1];
                fetch('{api_url}')
                    .then(res => {{
                        if (!res.ok) {{
                            throw new Error('Network response was not ok');
                        }}
                        return res.json();
                    }})
                    .then(data => callback(JSON.stringify(data)))
                    .catch(err => callback('error: ' + err.message));
                """
                response_str = driver.execute_async_script(script)

                if response_str.startswith('error'):
                    print(f"❌ आइटम {item_id} के लिए API से डेटा लाने में त्रुटि: {response_str}")
                else:
                    try:
                        data = json.loads(response_str)
                        file_path = os.path.join(data_folder, f"{shop_id}_{item_id}.json")
                        with open(file_path, 'w', encoding='utf-8') as json_f:
                            json.dump(data, json_f, ensure_ascii=False, indent=4)
                        print(f"✅ आइटम {item_id} का API रिस्पॉन्स सेव किया गया -> {file_path}")
                    except json.JSONDecodeError:
                        print(f"❌ आइटम {item_id} के लिए अमान्य JSON रिस्पॉन्स मिला।")

                # *** Rate Limit: 1 मिनट में 7 लिंक से ज्यादा नहीं ***
                # हर लिंक के बाद 8-10 सेकंड रुकें (60 सेकंड / 7 लिंक ≈ 8.5 सेकंड प्रति लिंक)
                print("⏳ रेट लिमिट के लिए थोड़ा इंतज़ार...")
                time.sleep(random.uniform(8, 10))

            except Exception as inner_e:
                print(f"❌ इस लिंक को प्रोसेस करते समय त्रुटि हुई '{link}': {inner_e}")
                continue # अगर कोई एरर आए तो अगले लिंक पर जाएँ

    except Exception as e:
        print(f"❌ एक बड़ी त्रुटि हुई: {e}, अगली कोशिश पर जा रहे हैं...")

    cont = input("\nक्या आप दूसरी कैटेगरी स्क्रैप करना चाहते हैं? (yes/no): ")
    if cont.lower() != "yes":
        break

# ---------------- Finish ----------------
driver.quit()
print("\n🎉 काम पूरा हुआ! CSV और API रिस्पॉन्स सेव कर दिए गए हैं।")