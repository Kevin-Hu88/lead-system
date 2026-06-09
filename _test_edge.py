# -*- coding: utf-8 -*-
"""Check if Edge is available for Selenium"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options
    
    opts = Options()
    # Use user's Edge profile to reuse login
    import os
    edge_profile = os.path.expanduser("~") + r"\AppData\Local\Microsoft\Edge\User Data"
    if os.path.exists(edge_profile):
        print("Edge profile found:", edge_profile)
        opts.add_argument(f"--user-data-dir={edge_profile}")
        opts.add_argument("--profile-directory=Default")
    
    driver = webdriver.Edge(options=opts)
    print("Edge WebDriver launched successfully!")
    
    # Test navigation
    driver.get("https://www.douyin.com")
    import time
    time.sleep(3)
    
    title = driver.title
    print("Title:", title)
    
    # Check if logged in
    body = driver.find_element_by_tag_name("body").text
    if "登录" in body[:500]:
        print("Not logged in")
    else:
        print("Logged in!")
    
    driver.quit()
    
except Exception as e:
    print("Edge not available:", e)
    print("\nTrying to use Chrome with Edge profile...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        opts = Options()
        import os
        edge_profile = os.path.expanduser("~") + r"\AppData\Local\Microsoft\Edge\User Data"
        if os.path.exists(edge_profile):
            opts.add_argument(f"--user-data-dir={edge_profile}")
            opts.add_argument("--profile-directory=Default")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            
            driver = webdriver.Chrome(options=opts)
            print("Chrome with Edge profile launched!")
            driver.get("https://www.douyin.com")
            import time
            time.sleep(3)
            print("Title:", driver.title)
            driver.quit()
        else:
            print("Edge profile not found")
    except Exception as e2:
        print("Chrome with Edge profile failed:", e2)
