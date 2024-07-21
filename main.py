import os
import subprocess
import json

SETTINGS_FILE = "settings.json"

def run_provider_script(provider_script):
    try:
        result = subprocess.run(["python", provider_script], shell=True)
        if result.returncode != 0:
            print(f"Error: Script {provider_script} exited with code {result.returncode}")
    except Exception as e:
        print(f"Failed to run script {provider_script}: {e}")

def interpolate_color(start_color, end_color, factor):
    """Interpolate between two colors with a factor."""
    start_rgb = [int(start_color[i:i+2], 16) for i in (1, 3, 5)]
    end_rgb = [int(end_color[i:i+2], 16) for i in (1, 3, 5)]
    interpolated_rgb = [
        int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * factor) for i in range(3)
    ]
    return f"\033[38;2;{interpolated_rgb[0]};{interpolated_rgb[1]};{interpolated_rgb[2]}m"

def print_ascii_art_with_gradient():
    ascii_art = rf"""
$$$$$$$\                       $$\     $$$$$$$\  $$\ $$\            $$\     
$$  __$$\                      $$ |    $$  __$$\ \__|$$ |           $$ |    
$$ |  $$ | $$$$$$\   $$$$$$\ $$$$$$\   $$ |  $$ |$$\ $$ | $$$$$$\ $$$$$$\   
$$$$$$$  |$$  __$$\ $$  __$$\\_$$  _|  $$$$$$$  |$$ |$$ |$$  __$$\\_$$  _|  
$$  ____/ $$ /  $$ |$$ |  \__| $$ |    $$  ____/ $$ |$$ |$$ /  $$ | $$ |    
$$ |      $$ |  $$ |$$ |       $$ |$$\ $$ |      $$ |$$ |$$ |  $$ | $$ |$$\ 
$$ |      \$$$$$$  |$$ |       \$$$$  |$$ |      $$ |$$ |\$$$$$$  | \$$$$  |
\__|       \______/ \__|        \____/ \__|      \__|\__| \______/   \____/ 
                                                                                                                                                 
                            Version:  0.1.0-beta1    
                             © ISPP 2024 - kanus                                                 
                                        
    """
    # Gradient colors
    start_color = "#0000FF"  # Blue
    end_color = "#800080"    # Purple
    
    # Split ASCII art into lines
    lines = ascii_art.strip().split("\n")
    max_length = max(len(line) for line in lines)

    for i, line in enumerate(lines):
        for j in range(len(line)):
            factor = j / max_length
            color = interpolate_color(start_color, end_color, factor)
            print(color + line[j], end='')
        print("\033[0m")  # Reset color to default

def colorize_text(text, start_color, end_color):
    """Colorize text with a gradient from start_color to end_color."""
    colored_text = ''
    for i, char in enumerate(text):
        factor = i / (len(text) - 1)
        color = interpolate_color(start_color, end_color, factor)
        colored_text += color + char
    return colored_text + "\033[0m"  # Reset color to default

def display_country_menu(default_country=None):
    """Display the country selection menu with numeric options only."""
    countries = {
        "1": ("Netherlands", "NL"),
        "2": ("Another Country", "AC"),  # Use "AC" as a placeholder symbol
        "nl": ("Netherlands", "NL"),
        "ac": ("Another Country", "AC")
    }

    print("Select your country by number:\n")
    for number, (country, symbol) in countries.items():
        if number.isdigit():  # Only print numeric options
            prefix = "*" if default_country == country else " "
            print(f"[{number}] - {country} ({symbol}) {prefix}")
    print("\n[0] - Go back")  # Option to go back
    
    return countries

def display_provider_menu(country, default_provider=None):
    """Display the provider selection menu based on the selected country."""
    providers = {
        "Netherlands": {
            "1": [("Odido", "Tele2")],
        },
        "Another Country": {
            "1": ["test"]
        }
    }

    country_providers = providers.get(country, {})
    print("\nSelect your provider by number or name:\n")

    # Generate a unique number for each provider
    provider_number = 1
    for number, names in country_providers.items():
        for name in names:
            if isinstance(name, tuple):  # Handle aliases
                primary_name, alias = name
                prefix = "*" if default_provider == primary_name else " "
                print(f"[{provider_number}] - {primary_name} (Formerly known as {alias}) {prefix}")
            else:
                prefix = "*" if default_provider == name else " "
                print(f"[{provider_number}] - {name} {prefix}")
            provider_number += 1

    print("\n[0] - Go Back")  # Option to go back

    # Return a map of provider numbers to names for later use
    provider_map = {i+1: names for i, names in enumerate([item for sublist in country_providers.values() for item in sublist])}
    return provider_map

def clear_console():
    """Clear the console screen."""
    os.system("cls" if os.name == "nt" else "clear")

def normalize_input(user_input):
    """Normalize user input for case-insensitive matching."""
    return user_input.strip().lower()

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

def save_settings(settings):
    """Save settings to the settings file."""
    with open(SETTINGS_FILE, "w") as file:
        json.dump(settings, file, indent=4)

def settings_menu():
    """Display and manage settings."""
    settings = load_settings()
    
    while True:
        clear_console()
        print_ascii_art_with_gradient()
        print("Settings Menu\n")
        print("1. Change Country Settings")
        print("2. Change Provider Settings")
        print("3. Toggle Discord Webhook")
        print("[0] - Back to Main Menu\n")
        
        choice = normalize_input(input("Enter your choice: "))
        
        if choice == "0":
            break
        
        if choice == "1":
            # Change country settings
            while True:
                clear_console()
                print_ascii_art_with_gradient()
                print("Change Country Settings\n")
                print("Select default country:")
                countries = display_country_menu()
                country_choice = normalize_input(input("Enter the number corresponding to your country: "))
                if country_choice.isdigit() and country_choice in countries:
                    country_name, _ = countries[country_choice]
                    settings['default_country'] = country_name
                    print(f"Default country set to: {country_name}")
                    save_settings(settings)
                    input("Press Enter to continue...")
                    break
                elif country_choice == "0":
                    break
                else:
                    print("Invalid country choice.")
        
        elif choice == "2":
            # Change provider settings
            default_country = settings.get('default_country')
            if not default_country:
                print("Default country not set. Please set the country first.")
                continue
            
            while True:
                clear_console()
                print_ascii_art_with_gradient()
                country_providers = display_provider_menu(default_country)
                print("Change Provider Settings\n")
                print("Select provider to set as default:")
                choice = normalize_input(input("Enter the number or name corresponding to your provider: "))
                selected_provider = None
                
                if choice.isdigit():
                    choice_number = int(choice)
                    selected_provider = country_providers.get(choice_number)
                else:
                    for name in country_providers.values():
                        if isinstance(name, list):
                            for provider_name in name:
                                if normalize_input(provider_name) == choice:
                                    selected_provider = provider_name
                                    break
                    if selected_provider:
                        break
                
                if selected_provider:
                    settings['default_provider'] = selected_provider
                    print(f"Default provider set to: {selected_provider}")
                    save_settings(settings)
                    input("Press Enter to continue...")
                    break
                elif choice == "0":
                    break
                else:
                    print("Invalid provider choice.")
        
        elif choice == "3":
            # Toggle Discord Webhook
            while True:
                clear_console()
                print_ascii_art_with_gradient()
                discord_webhook = settings.get('discord_webhook')
                if discord_webhook:
                    print(f"Discord Webhook is currently set to: {discord_webhook}")
                else:
                    print("Discord Webhook is currently not set.")
                
                toggle_choice = normalize_input(input("Enable Discord Webhook? (yes/no): "))
                if toggle_choice == "yes":
                    webhook_url = normalize_input(input("Enter the Discord webhook URL: "))
                    if webhook_url:
                        settings['discord_webhook'] = webhook_url
                        print(f"Discord Webhook set to: {webhook_url}")
                    else:
                        print("No URL provided. Discord webhook will be disabled.")
                        settings['discord_webhook'] = None
                elif toggle_choice == "no":
                    settings['discord_webhook'] = None
                    print("Discord Webhook has been disabled.")
                elif toggle_choice == "0":
                    break
                else:
                    print("Invalid choice. Please enter 'yes' or 'no'.")
                
                save_settings(settings)
                input("Press Enter to continue...")
                break

        else:
            print("Invalid choice. Please try again.")
        
        save_settings(settings)

def main():
    # Load settings at startup
    settings = load_settings()
    
    base_paths = {
        "Netherlands": "nl_NL",
        "Another Country": "AnotherCountry"
    }
    
    default_country = settings.get('default_country')
    default_provider = settings.get('default_provider')

    while True:
        clear_console()
        print_ascii_art_with_gradient()
        
        print("Main Menu\n")
        print("1. Select Country and Provider")
        print("2. Settings")
        print("[0] - Exit\n")
        
        choice = normalize_input(input("Enter your choice: "))
        
        if choice == "0":
            print("Exiting...")
            break
        
        if choice == "1":
            while True:
                clear_console()
                print_ascii_art_with_gradient()
                
                countries = display_country_menu(default_country)
                country_choice = normalize_input(input("Enter the number corresponding to your country (or press Enter to use default): "))
                
                if country_choice == "":
                    if default_country:
                        # Automatically select default country
                        for number, (country, _) in countries.items():
                            if country == default_country:
                                country_choice = number
                                break
                    else:
                        print("No default country set. Please select a country.")
                        continue
                
                if country_choice == "0":
                    break
                
                country = None
                if country_choice.isdigit():
                    country = countries.get(country_choice)
                else:
                    for key, value in countries.items():
                        if country_choice in key or country_choice in value[0].lower():
                            country = value
                            break
                
                if not country:
                    print("Invalid choice. Please try again.")
                    continue

                country_name, _ = country
                provider_base_path = base_paths.get(country_name)

                while True:
                    clear_console()
                    print_ascii_art_with_gradient()
                    
                    country_providers = display_provider_menu(country_name, default_provider)
                    
                    provider_choice = normalize_input(input("Enter the number or name corresponding to your provider: "))
                    
                    if provider_choice == "0":
                        break
                    
                    selected_script = None
                    
                    if provider_choice.isdigit():
                        choice_number = int(provider_choice)
                        if choice_number in country_providers:
                            for provider_name in country_providers[choice_number]:
                                script_path = os.path.join(provider_base_path, f"{provider_name.lower()}.py")
                                if os.path.isfile(script_path):
                                    selected_script = script_path
                                    break
                    else:
                        for provider_name in country_providers.values():
                            if isinstance(provider_name, list):
                                for name in provider_name:
                                    if normalize_input(name) == provider_choice:
                                        script_path = os.path.join(provider_base_path, f"{name.lower()}.py")
                                        if os.path.isfile(script_path):
                                            selected_script = script_path
                                            break
                            if selected_script:
                                break
                    
                    if selected_script:
                        clear_console()
                        print_ascii_art_with_gradient()
                        run_provider_script(selected_script)
                        input("Press Enter to return to the provider menu...")
                    else:
                        print("Invalid choice or script not found. Please try again.")
        
        elif choice == "2":
            settings_menu()
            # Reload settings after changes
            settings = load_settings()
            default_country = settings.get('default_country')
            default_provider = settings.get('default_provider')
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()