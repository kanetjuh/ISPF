import sys
import time
import platform
import subprocess
import re
import os
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import Select
import ipaddress

CREDENTIALS_FILE = "credentials.txt"
SETTINGS_FILE = "settings.json"

def log(message, status="!"):
    status_symbols = {
        "!": "\033[93m[!]\033[0m",  # Yellow
        "+": "\033[92m[+]\033[0m",  # Green
        "-": "\033[91m[-]\033[0m",  # Red
        "✓": "\033[92m[✓]\033[0m"  # Green checkmark
    }
    print(f"{status_symbols.get(status, '[!]')} {message}")

def get_default_gateway():
    os_name = platform.system().lower()
    log("Retrieving IP settings", "!")

    if 'windows' in os_name:
        command = "ipconfig"
    elif 'linux' in os_name or 'darwin' in os_name:  # darwin is macOS
        command = "netstat -r"
    else:
        raise NotImplementedError("Unsupported operating system")

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout
        
        if 'windows' in os_name:
            log("Command output received", "+")
            match = re.search(r"Default Gateway[.\s]*:\s*([\d.]+)", output)
        else:
            log("Command output received", "+")
            match = re.search(r"default\s*([\d.]+)", output)
        
        if match:
            return match.group(1)
        else:
            raise ValueError("Default gateway not found in command output")
    except Exception as e:
        log(f"Error: {e}", "-")
        return None

def setup_webdriver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=1")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def wait_for_login_page(driver, url):
    log(f"Attempting to navigate to {url}", "!")
    try:
        driver.get(url)
        
        # Wait for the specific div that indicates the modem info
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "cardpage"))
        )
        
        # Extract and log the modem info
        modem_info = driver.find_element(By.CSS_SELECTOR, "#cardpage h3").text
        log(f"Modem Info: {modem_info}", "+")
        
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        
        log("Login form detected", "+")
        return True
    except Exception as e:
        log(f"Error navigating to the login page: {e}", "-")
        driver.save_screenshot("login_page_error.png")
        return False

def perform_login(driver, username, password):
    try:
        log("Attempting to locate username and password fields", "!")
        username_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        password_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "userpassword"))
        )
        
        log("Filling in credentials", "!")
        username_field.clear()
        username_field.send_keys(username)
        
        password_field.clear()
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)
        
        log("Login attempt submitted", "+")
        
        WebDriverWait(driver, 30).until(
            EC.url_changes("https://192.168.1.1/login")
        )
        
        current_url = driver.current_url
        if current_url == "https://192.168.1.1/":
            log(f"Login successful, redirected to {current_url}", "+")
            log("Successfully logged in\n", "+")
            save_credentials(username, password)
            return True
        else:
            log(f"Login failed or redirection issue. Current URL: {current_url}", "-")
            driver.save_screenshot("login_error.png")
            
            try:
                response = driver.execute_script(
                    "return window.performance.getEntriesByType('resource').map(r => r.toJSON());"
                )
                for entry in response:
                    if 'cgi-bin/loginAccountLevel' in entry['name']:
                        log(f"Login Response: {entry['responseText']}", "-")
                        break
            except Exception as e:
                log(f"Error checking login response: {e}", "-")
            
            if not current_url.endswith("/"):
                driver.get("https://192.168.1.1/")
                log("Manually redirected to the main page", "+")
                
            return False
    except Exception as e:
        log(f"Error during login: {e}", "-")
        driver.save_screenshot("login_error.png")
        return False

def input_password():
    password = input("Enter your password: ")
    return password

def save_credentials(username, password):
    with open(CREDENTIALS_FILE, "w") as file:
        file.write(f"{username}\n{password}")

def load_credentials():
    if os.path.isfile(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as file:
            lines = file.readlines()
            if len(lines) == 2:
                return lines[0].strip(), lines[1].strip()
    return None, None

def load_settings():
    """Load settings from the settings file."""
    if os.path.isfile(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                print("Error loading settings. Using defaults.")
                return {}
    return {}

def wait_for_system_information(driver):
    """Wait for the system information to be fully loaded."""
    log("Waiting for system information to load...", "!")
    
    # Define a timeout for waiting
    timeout = 60
    
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "card_sys"))
        )
        log("System information loaded", "+")
    except Exception as e:
        log(f"Error while waiting for system information: {e}", "-")
        driver.save_screenshot("system_information_error.png")
        return False
    return True

def send_webhook_data(driver):
    """Extract information from the div and send it via webhook."""
    settings = load_settings()

    if not settings.get('discord_webhook'):
        log("No webhook URL set in settings. Skipping webhook send.", "-")
        return

    try:
        system_info_div = driver.find_element(By.ID, "card_sys")
        
        data = {
            'model_name': system_info_div.find_element(By.ID, "card_sysinfo_modelname").text,
            'firmware_version': system_info_div.find_element(By.ID, "card_sysinfo_fwversion").text,
            'uptime': system_info_div.find_element(By.ID, "card_sysinfo_systime").text,
            'mac_address': system_info_div.find_element(By.ID, "card_sysinfo_macaddr").text,
            'ethernet_wan': system_info_div.find_element(By.ID, "card_sysinfo_wan").text
        }

        # Wait and print with rotating icon until all required information is retrieved
        while data['uptime'] == '0 dagen 0 uur 0 minuten 0 seconden' or not data['firmware_version'] or not data['mac_address']:
            for icon in "\\|/-":
                sys.stdout.write(f"\r\033[90m[\033[93m\033[5m{icon}\033[25m\033[90m] Awaiting complete information...\033[0m")
                sys.stdout.flush()
                time.sleep(0.1)

                # Re-fetch the data to check if it's updated
                system_info_div = driver.find_element(By.ID, "card_sys")
                data = {
                    'model_name': system_info_div.find_element(By.ID, "card_sysinfo_modelname").text,
                    'firmware_version': system_info_div.find_element(By.ID, "card_sysinfo_fwversion").text,
                    'uptime': system_info_div.find_element(By.ID, "card_sysinfo_systime").text,
                    'mac_address': system_info_div.find_element(By.ID, "card_sysinfo_macaddr").text,
                    'ethernet_wan': system_info_div.find_element(By.ID, "card_sysinfo_wan").text
                }
                
                if not (data['uptime'] == '0 dagen 0 uur 0 minuten 0 seconden' or not data['firmware_version'] or not data['mac_address']):
                    break
        
        # Clear the line after the information is complete
        sys.stdout.write("\r\033[0m\033[K")  # \033[K clears the line from the cursor to the end

        # Log final information
        log("System information retrieved. Waiting before proceeding to device list.", "✓")
        time.sleep(2)  # Wait before proceeding

        log("Retrieving list of connected devices...", "!")
        
        # Wait for any potential loading overlay to disappear
        WebDriverWait(driver, 30).until(
            EC.invisibility_of_element((By.ID, "LoadingBox"))
        )
        
        # Click on the specific div inside the parent
        div_to_click = driver.find_element(By.CSS_SELECTOR, "div#card_cnt")
        div_to_click.click()
        
        # Wait for the loading to disappear
        WebDriverWait(driver, 30).until(
            EC.invisibility_of_element((By.ID, "LoadingBox"))
        )
        
        # Click on the 'Lijst' tab
        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "li.nav-item a#tab_List_Tab"))
        ).click()
        
        # Wait until the 'Lijst' tab content is present
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "tab_List"))
        )
        
        # Take a screenshot of the list of devices
        device_list_div = driver.find_element(By.ID, "tab_List")
        screenshot_path = "device_list.png"
        device_list_div.screenshot(screenshot_path)
        
        log("Device list screenshot taken and saved.", "+")

        # Prepare the payload
        payload = {
            "username": f"Zyxel - ({data['model_name']})",
            # "content": "Here is the system information and device list.",
            "avatar_url": "https://i0.wp.com/www.appletips.nl/wp-content/uploads/2023/09/odido.png?fit=468%2C468&ssl=1",
            "embeds": [
                {
                    "title": "System Information",
                    "description": (
                        f"**Model Name**: {data['model_name']}\n"
                        f"**Firmware Version**: {data['firmware_version']}\n"
                        f"**Uptime**: {data['uptime']}\n"
                        f"**MAC Address**: {data['mac_address']}\n"
                        f"**Ethernet WAN**: {data['ethernet_wan']}"
                    ),
                    "color": 0xe83e8c  # Hex color #e83e8c
                }
            ]
        }

        # Send the request with the file attachment and embed
        with open(screenshot_path, "rb") as file:
            files = {
                "file": ("device_list.png", file, "image/png")
            }
            data = {
                "payload_json": json.dumps(payload)
            }
            response = requests.post(settings.get('discord_webhook'), data=data, files=files)
        
        if 200 <= response.status_code < 300:
            log(f"Webhook sent successfully. Status code: {response.status_code}", "+")
        else:
            log(f"Failed to send webhook. Status code: {response.status_code}, response:\n{response.text}", "-")
    
    except Exception as e:
        log(f"Error sending webhook data: {e}", "-")

def wait_for_system_information(driver):
    """Wait for the system information to load and print progress."""
    log("Waiting for system information to load...", "!")
    try:
        system_info_div = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "card_sys"))
        )
        
        data = {
            'model_name': system_info_div.find_element(By.ID, "card_sysinfo_modelname").text,
            'firmware_version': system_info_div.find_element(By.ID, "card_sysinfo_fwversion").text,
            'uptime': system_info_div.find_element(By.ID, "card_sysinfo_systime").text,
            'mac_address': system_info_div.find_element(By.ID, "card_sysinfo_macaddr").text,
            'ethernet_wan': system_info_div.find_element(By.ID, "card_sysinfo_wan").text
        }

        while data['uptime'] == '0 dagen 0 uur 0 minuten 0 seconden' or not data['firmware_version'] or not data['mac_address']:
            for icon in "\\|/-":
                sys.stdout.write(f"\r\033[90m[\033[93m\033[5m{icon}\033[25m\033[90m] Awaiting complete system information...\033[0m")
                sys.stdout.flush()
                time.sleep(0.1)

                # Re-fetch the data to check if it's updated
                system_info_div = driver.find_element(By.ID, "card_sys")
                data = {
                    'model_name': system_info_div.find_element(By.ID, "card_sysinfo_modelname").text,
                    'firmware_version': system_info_div.find_element(By.ID, "card_sysinfo_fwversion").text,
                    'uptime': system_info_div.find_element(By.ID, "card_sysinfo_systime").text,
                    'mac_address': system_info_div.find_element(By.ID, "card_sysinfo_macaddr").text,
                    'ethernet_wan': system_info_div.find_element(By.ID, "card_sysinfo_wan").text
                }
                
                if not (data['uptime'] == '0 dagen 0 uur 0 minuten 0 seconden' or not data['firmware_version'] or not data['mac_address']):
                    break
        
        sys.stdout.write("\r\033[0m\033[K")  # \033[K clears the line from the cursor to the end
        log("System information loaded", "+")
        
        return data
    
    except Exception as e:
        log(f"Error waiting for system information: {e}", "-")
        driver.save_screenshot("system_info_error.png")
        return None

def wait_for_element_to_be_clickable(driver, by, value, timeout=30):
    """Wait for an element to be clickable."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
        return element
    except TimeoutException:
        log(f"Element not clickable after {timeout} seconds: {value}", "-")
        return None

def click_element(driver, by, value):
    """Click an element with a fallback to JavaScript click."""
    element = wait_for_element_to_be_clickable(driver, by, value)
    if element:
        try:
            element.click()
            log(f"Clicked on element: {value}", "+")
        except Exception as e:
            log(f"Click failed using Selenium: {e}", "-")
            # Fallback to JavaScript click
            driver.execute_script("arguments[0].click();", element)
            log(f"Clicked on element using JavaScript: {value}", "+")
    else:
        log(f"Element not found or not clickable: {value}", "-")


def get_ipv4_address():
    """Retrieve the local machine's IPv4 address."""
    import socket
    try:
        hostname = socket.gethostname()
        ipv4_address = socket.gethostbyname(hostname)
        return ipv4_address
    except Exception as e:
        log(f"Error retrieving IPv4 address: {e}", "-")
        return None

def fill_text_input(driver, by, value, text):
    """Fill text input fields."""
    element = wait_for_element_to_be_clickable(driver, by, value)
    if element:
        element.clear()
        element.send_keys(text)
        log(f"Filled in text field '{value}' with '{text}'", "+")

def fill_ip_fields(driver, ip):
    """Fill in IPv4 address fields."""
    ip_parts = ip.split('.')
    for i, part in enumerate(ip_parts):
        if i < 4:
            field = driver.find_element(By.ID, f"a_srvAddr_{i+1}")
            field.clear()
            field.send_keys(part)
    log(f"Filled in IP address fields with '{ip}'", "+")

def select_protocol(driver):
    """Select the protocol (TCP, UDP, or BOTH) from the dropdown menu."""
    log("Selecting the protocol", "!")
    protocol = input("Enter protocol (TCP/UDP/BOTH): ").strip().upper()
    
    if protocol not in ["TCP", "UDP", "BOTH"]:
        log("Invalid protocol selected (Not in list)", "-")
        return False
    
    try:
        # Find the select element by its ID
        select_element = Select(driver.find_element(By.ID, "port_fwd_protocol"))
        
        # Select the protocol based on the user's input
        if protocol == "TCP":
            select_element.select_by_value("TCP")
        elif protocol == "UDP":
            select_element.select_by_value("UDP")
        elif protocol == "BOTH":
            select_element.select_by_value("ALL")

        
        log(f"Selected protocol: {protocol}", "+")
        
        # Click the OK button to confirm
        ok_button = driver.find_element(By.CSS_SELECTOR, "button#ok")
        ok_button.click()
        log("Clicked OK button", "+")
        return True
    except Exception as e:
        log(f"Error selecting protocol: {e}", "-")
        driver.save_screenshot("protocol_selection_error.png")
        return False

def navigate_to_nat_settings(driver):
    """Navigate to the NAT settings page and perform actions."""
    try:
        # Click the menu button
        click_element(driver, By.CSS_SELECTOR, "div#h_menu_list")
        
        # Click on the 'Netwerkinstelling' (Network Settings) item
        click_element(driver, By.CSS_SELECTOR, "li a[href='#network']")
        
        # Wait for the menu to be updated and ensure NAT link is clickable
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "ul#network"))
        )
        nat_item = wait_for_element_to_be_clickable(driver, By.CSS_SELECTOR, "li a[href='/NAT']")
        
        if nat_item:
            nat_item.click()
            log("Navigated to NAT settings", "+")
            
            # Click the 'Add Rule' button
            add_rule_button = wait_for_element_to_be_clickable(driver, By.CSS_SELECTOR, "div#portFwdAdd")
            if add_rule_button:
                add_rule_button.click()
                log("Clicked on 'Add Rule' button", "+")
                
                # Ask if user wants to enable the port forward now
                enable_now = input("Do you want to enable the port forward now? (yes/no): ").strip().lower()
                if enable_now == 'yes':
                    enable_switch = wait_for_element_to_be_clickable(driver, By.CSS_SELECTOR, "label#port_fwd_active")
                    if enable_switch:
                        enable_switch.click()
                        log("Enabled the port forward", "+")
                else:
                    log("Skipped enabling the port forward", "-")
                
                # Ask user for the rule name
                rule_name = input("Enter the name for the port forward rule: ").strip()
                fill_text_input(driver, By.ID, "srvName", rule_name)
                
                # Ask user for the start port
                start_port = input("Enter the start port: ").strip()
                fill_text_input(driver, By.ID, "eStart", start_port)
                
                # Ask user for the end port
                end_port = input("Enter the end port: ").strip()
                fill_text_input(driver, By.ID, "eEnd", end_port)
                
                # Ask if user wants to use the current PC's IP address
                use_current_ip = input("Do you want to use the current PC's IP address? (yes/no): ").strip().lower()
                if use_current_ip == 'yes':
                    ip_address = get_ipv4_address()
                    if ip_address:
                        fill_ip_fields(driver, ip_address)
                    else:
                        log("Failed to retrieve the current PC's IP address", "-")
                else:
                    # Ask user for IP address
                    manual_ip = input("Enter the IP address manually (format: xxx.xxx.xxx.xxx): ").strip()
                    fill_ip_fields(driver, manual_ip)
                
                select_protocol(driver)
                    # log("Invalid protocol selected. Skipping protocol selection.", "-")
                
                # Click the OK button
                ok_button = wait_for_element_to_be_clickable(driver, By.ID, "Network_NAT_PortForward_ApplyBtn")
                if ok_button:
                    ok_button.click()
                    log("Clicked on 'OK' button to apply the port forward", "+")
                
            else:
                log("Add Rule button not found or not clickable", "-")
        else:
            log("NAT settings link not found or not clickable", "-")
    
    except Exception as e:
        log(f"Error navigating to NAT settings: {e}", "-")
        driver.save_screenshot("nat_settings_error.png")

def main():
    try:
        default_gateway = get_default_gateway()
        if default_gateway:
            log(f"Default Gateway: {default_gateway}", "+")
            url = f"http://{default_gateway}/login"
            
            driver = setup_webdriver()
            
            if wait_for_login_page(driver, url):
                # Load saved credentials if available
                saved_username, saved_password = load_credentials()
                
                if saved_username and saved_password:
                    log("Using saved credentials", "+")
                    username = saved_username
                    password = saved_password
                else:
                    log("No saved credentials found. Please enter your credentials.", "!")
                    username = input("Enter your username: ").strip()
                    password = input_password()
                
                login_success = perform_login(driver, username, password)
                
                if login_success:
                    # Always wait for system information to load
                    system_data = wait_for_system_information(driver)
                    
                    # Check if webhook is enabled
                    settings = load_settings()
                    webhook_url = settings.get('discord_webhook')

                    if webhook_url:
                        if system_data:
                            # Prepare and send webhook if system data is available
                            send_webhook_data(driver)
                        else:
                            log("System information could not be retrieved. Skipping webhook.", "-")
                    
                    # Navigate to NAT settings
                    navigate_to_nat_settings(driver)
                    
                    if saved_username and saved_password and (saved_username != username or saved_password != password):
                        log("Credentials have been updated", "+")
                    else:
                        log("Browser will remain open for inspection")
                        time.sleep(60)  # Allow time for inspection
                    
                    log("Closing the browser")
                else:
                    log("Login failed. Skipping NAT settings.", "-")
                
                driver.quit()
            else:
                log("Failed to access the login page", "-")
        else:
            log("Failed to retrieve the default gateway", "-")
    except Exception as e:
        log(f"Unhandled exception: {e}", "-")

if __name__ == "__main__":
    main()
