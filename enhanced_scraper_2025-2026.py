import requests
from bs4 import BeautifulSoup
import json
import time
# NO REGEX IMPORT - COMPLETELY REMOVED
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import logging
import os
import sys
import threading

# COMPLETE LOGGING SUPPRESSION
import warnings
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Suppress ALL unnecessary logging
logging.basicConfig(level=logging.ERROR)  # Only show errors
logger = logging.getLogger(__name__)

# Suppress Flask request logging
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR)

# Suppress urllib3 warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

class EliteProspectsScraper:
    def __init__(self, headless=True, delay=3, max_teams=None, batch_size=5):
        self.delay = delay
        self.max_teams = max_teams
        self.batch_size = batch_size
        self.setup_driver(headless)
        self.base_url = "https://www.eliteprospects.com"
        self.progress_callback = None
        self.should_stop = False
        self.scraped_count = 0
        self.total_teams = 0
        self.live_teams = []  # Store completed teams for real-time updates

    def set_progress_callback(self, callback):
        """Set a callback function to report progress"""
        self.progress_callback = callback

    def stop_scraping(self):
        """Signal to stop scraping"""
        self.should_stop = True
        logger.info("Stop signal received")

    def report_progress(self, message, current=None, total=None, team_data=None):
        """Enhanced progress reporting with FIXED real-time data flow"""
        if current is not None and total is not None:
            progress_pct = (current / total) * 100 if total > 0 else 0
            # Only print major milestones to reduce noise
            if current == 1 or current == total or current % 3 == 0:
                print(f"📊 {message} ({current}/{total} - {progress_pct:.0f}%)")
        else:
            # Print important status messages
            if any(keyword in message.lower() for keyword in ['error', 'complete', 'starting', 'found', 'scraping']):
                print(f"🔄 {message}")

        # FIXED: Always send to callback for dashboard with live teams data
        if self.progress_callback:
            progress_data = {
                'message': message,
                'current': current or 0,
                'total': total or 0,
                'percentage': (current / total) * 100 if (current and total and total > 0) else 0,
                'completed': current == total if (current and total) else False,
                'live_teams': self.live_teams.copy()  # CRITICAL: Send current live teams
            }
            
            # Add current team being processed
            if team_data:
                progress_data['current_team'] = team_data
                
            self.progress_callback(progress_data)

    def setup_driver(self, headless=True):
        """Setup Chrome WebDriver with error suppression"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")

        # MAXIMUM Chrome error/warning suppression
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-webgl")
        chrome_options.add_argument("--disable-webgl2")
        chrome_options.add_argument("--disable-3d-apis")
        chrome_options.add_argument("--disable-accelerated-2d-canvas")
        chrome_options.add_argument("--disable-accelerated-video-decode")
        chrome_options.add_argument("--disable-gpu-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--quiet")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-images")
        
        # SPEED OPTIMIZATION: Disable image loading for faster scraping
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        chrome_options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.images": 2
        })
        
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor,TranslateUI,BlinkGenPropertyTrees")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")

        # Experimental options
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            # Suppress ALL Chrome output
            from selenium.webdriver.chrome.service import Service
            service = Service()
            service.log_path = os.devnull if os.name != 'nt' else 'NUL'
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)
            
            # Only print on successful initialization
            print("✅ Chrome driver ready")
            
        except Exception as e:
            print(f"❌ Chrome driver failed: {e}")
            raise

    def get_league_teams(self, league_url, season="2025-2026"):
        """Get all teams from a league page"""
        try:
            # Ensure league URL includes season
            if not league_url.endswith(f"/{season}"):
                league_url = f"{league_url}/{season}"

            print(f"🔍 Fetching teams from: {league_url}")
            print(f"   League: {self.extract_league_name(league_url)}")
            print(f"   Season: {season}")
            
            # Special diagnostic for EHL/EHLP
            league_name = self.extract_league_name(league_url)
            if league_name in ['EHL', 'EHLP']:
                print(f"\n{'='*60}")
                print(f"⚠️  DIAGNOSTIC MODE: {league_name}")
                print(f"{'='*60}")
                print(f"This league may have different page structure")
                print(f"Will attempt multiple XPath patterns...")
                print(f"{'='*60}\n")
            
            logger.debug(f"Scraping teams from league: {league_url}")
            
            # Try loading page up to 3 times
            max_retries = 3
            page_loaded = False
            
            for attempt in range(1, max_retries + 1):
                try:
                    # Set page load timeout to 30 seconds
                    self.driver.set_page_load_timeout(30)
                    
                    if attempt > 1:
                        print(f"\n🔄 Retry attempt {attempt}/{max_retries}")
                        time.sleep(3)  # Brief pause before retry
                    
                    print(f"🌐 Loading URL: {league_url}")
                    self.driver.get(league_url)
                    
                    # Get current URL to check for redirects
                    current_url = self.driver.current_url
                    if current_url != league_url:
                        print(f"⚠️  REDIRECT DETECTED:")
                        print(f"   Requested: {league_url}")
                        print(f"   Actual:    {current_url}")
                        
                        # Check if redirected to a 404 or error page
                        if '404' in current_url or 'not-found' in current_url.lower():
                            print(f"❌ Page not found (404)")
                            print(f"⚠️  This league/season combination might not exist on EliteProspects")
                            return []
                    
                    print(f"✅ Page loaded successfully")
                    
                    # Check page title
                    try:
                        page_title = self.driver.title
                        print(f"📄 Page title: {page_title}")
                        if '404' in page_title or 'Not Found' in page_title:
                            print(f"❌ Page title indicates error")
                            return []
                    except:
                        pass
                    
                    # Success!
                    page_loaded = True
                    break
                    
                except Exception as e:
                    print(f"❌ Attempt {attempt}/{max_retries} failed: {e}")
                    
                    if attempt < max_retries:
                        print(f"⏳ Waiting before retry...")
                        time.sleep(5)  # Wait 5 seconds before retry
                    else:
                        # Final attempt failed
                        print(f"\n{'='*60}")
                        print(f"❌ ALL {max_retries} ATTEMPTS FAILED")
                        print(f"{'='*60}")
                        print(f"⚠️  The page may be temporarily unavailable")
                        print(f"⚠️  OR the URL might be invalid")
                        print(f"⚠️  Try again later or check the URL manually")
                        print(f"{'='*60}\n")
                        return []
            
            if not page_loaded:
                return []
            
            time.sleep(self.delay)
            print(f"⏱️ Waited {self.delay}s for page to fully render")

            teams = []
            team_links = []
            successful_pattern = None

            # Try multiple XPath selectors for different league page structures
            self.report_progress(f"Searching for team links...")
            print(f"🔎 Trying multiple XPath patterns...")
            
            # Pattern 1: div[3] (works for NA3HL, NAHL, etc)
            if len(team_links) == 0:
                print(f"   Attempt 1: //section/div[3]/ul/li/span/a")
                try:
                    team_links = self.driver.find_elements(By.XPATH, "//section/div[3]/ul/li/span/a[contains(@href, '/team/')]")
                    if len(team_links) > 0:
                        successful_pattern = "Pattern 1 (div[3])"
                    print(f"   → Found {len(team_links)} teams")
                except Exception as e:
                    print(f"   → XPath error: {e}")
                    team_links = []
            
            # Pattern 2: div[2] (works for EHLP, USPHL Elite, etc)
            if len(team_links) == 0:
                print(f"   Attempt 2: //section/div[2]/ul/li/span/a")
                try:
                    team_links = self.driver.find_elements(By.XPATH, "//section/div[2]/ul/li/span/a[contains(@href, '/team/')]")
                    if len(team_links) > 0:
                        successful_pattern = "Pattern 2 (div[2]) - EHLP/Elite structure"
                    print(f"   → Found {len(team_links)} teams")
                except Exception as e:
                    print(f"   → XPath error: {e}")
                    team_links = []
            
            # Pattern 3: Any div position in section
            if len(team_links) == 0:
                print(f"   Attempt 3: //section//ul/li/span/a (any div)")
                try:
                    team_links = self.driver.find_elements(By.XPATH, "//section//ul/li/span/a[contains(@href, '/team/')]")
                    if len(team_links) > 0:
                        successful_pattern = "Pattern 3 (flexible div)"
                    print(f"   → Found {len(team_links)} teams")
                except Exception as e:
                    print(f"   → XPath error: {e}")
                    team_links = []
            
            # Pattern 4: Direct from content div (EHLP specific structure)
            if len(team_links) == 0:
                print(f"   Attempt 4: //div[contains(@class,'Layout_content')]//section//ul/li/span/a")
                try:
                    team_links = self.driver.find_elements(By.XPATH, "//div[contains(@class,'Layout_content')]//section//ul/li/span/a[contains(@href, '/team/')]")
                    if len(team_links) > 0:
                        successful_pattern = "Pattern 4 (Layout_content class)"
                    print(f"   → Found {len(team_links)} teams")
                except Exception as e:
                    print(f"   → XPath error: {e}")
                    team_links = []
            
            # Final fallback: Any team link on page
            if len(team_links) == 0:
                print(f"   Attempt 5: //a[contains(@href, '/team/')] (last resort)")
                try:
                    all_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/team/') and contains(@href, '/{season}')]".replace('{season}', season))
                    # Filter to only roster links (not stats, transactions, etc)
                    team_links = [link for link in all_links if '/stats' not in link.get_attribute('href') 
                                  and '/transactions' not in link.get_attribute('href')
                                  and '/schedule' not in link.get_attribute('href')]
                    if len(team_links) > 0:
                        successful_pattern = "Pattern 5 (fallback with filtering)"
                    print(f"   → Found {len(team_links)} team links (filtered)")
                except Exception as e:
                    print(f"   → XPath error: {e}")
                    team_links = []

            print(f"\n📋 Final result: {len(team_links)} team links found")
            if successful_pattern:
                print(f"✅ Success using: {successful_pattern}")
            logger.debug(f"Found {len(team_links)} potential team links")
            self.report_progress(f"Found {len(team_links)} teams")
            
            if len(team_links) == 0:
                print(f"\n{'='*60}")
                print(f"❌ NO TEAMS FOUND")
                print(f"{'='*60}")
                print(f"⚠️  Page might have different HTML structure")
                print(f"⚠️  Saving screenshot and HTML for debugging...")
                try:
                    import os
                    league_slug = league_url.split('/league/')[-1].replace('/', '_')
                    
                    # Save screenshot
                    screenshot_filename = f"league_page_{league_slug}.png"
                    screenshot_path = os.path.join(os.getcwd(), screenshot_filename)
                    self.driver.save_screenshot(screenshot_path)
                    print(f"📸 Screenshot saved to: {screenshot_path}")
                    
                    # Save HTML source
                    html_filename = f"league_page_{league_slug}.html"
                    html_path = os.path.join(os.getcwd(), html_filename)
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(self.driver.page_source)
                    print(f"📄 HTML source saved to: {html_path}")
                    print(f"   Open this file to inspect the page structure")
                    
                    print(f"📸 View screenshot: file://{screenshot_path}")
                    print(f"📄 View HTML: file://{html_path}")
                except Exception as e:
                    print(f"❌ Could not save debug files: {e}")
                print(f"{'='*60}\n")
                return []

            print(f"🔄 Processing {len(team_links)} team links...")
            processed_count = 0
            for idx, link in enumerate(team_links, 1):
                href = link.get_attribute('href')
                team_name = link.text.strip()

                if href and team_name and '/team/' in href:
                    # Extract team ID from URL - SIMPLE STRING METHOD
                    try:
                        # Find "/team/" and extract ID after it
                        team_start = href.find('/team/') + 6  # Length of '/team/'
                        team_end = href.find('/', team_start)
                        if team_end == -1:
                            team_end = len(href)
                        team_id = href[team_start:team_end]
                        
                        # Extract team slug - everything after team ID
                        slug_start = href.find('/', team_start) + 1
                        slug_end = href.find('/', slug_start)
                        if slug_end == -1:
                            slug_end = len(href)
                        team_slug = href[slug_start:slug_end] if slug_start < len(href) else team_name.lower().replace(' ', '-')
                        
                        if team_id.isdigit():  # Valid numeric team ID
                            # Construct proper team URL with season
                            team_url = f"https://www.eliteprospects.com/team/{team_id}/{team_slug}/{season}"

                            teams.append({
                                'id': team_id,
                                'name': team_name,
                                'url': team_url,
                                'league': self.extract_league_name(league_url)
                            })
                            processed_count += 1
                            if processed_count % 5 == 0:
                                print(f"  ✓ Processed {processed_count}/{len(team_links)} teams...")
                    except Exception as e:
                        # Skip this team if URL parsing fails
                        continue
            
            print(f"✅ Finished processing all team links - {len(teams)} teams extracted")

            # Remove duplicates
            unique_teams = []
            seen_ids = set()
            for team in teams:
                if team['id'] not in seen_ids and team['name']:
                    unique_teams.append(team)
                    seen_ids.add(team['id'])

            print(f"\n{'='*60}")
            print(f"🔹 Found {len(unique_teams)} unique teams:")
            print(f"{'='*60}")
            for i, team in enumerate(unique_teams[:10], 1):  # Show first 10
                print(f"   {i}. {team['name']}")
            if len(unique_teams) > 10:
                print(f"   ... and {len(unique_teams) - 10} more teams")
            print(f"{'='*60}\n")
            
            logger.info(f"Found {len(unique_teams)} unique teams")
            return unique_teams

        except Exception as e:
            print(f"❌ Error in get_league_teams: {e}")
            logger.error(f"Error scraping league teams: {e}")
            import traceback
            traceback.print_exc()
            return []

    def extract_league_name(self, league_url):
        """Extract league name from URL"""
        try:
            parts = league_url.split('/')
            for part in parts:
                if part and part not in ['https:', 'www.eliteprospects.com', 'league']:
                    # Remove season from league name using simple string methods
                    clean_part = part
                    # Remove common season patterns like "-2025-2026"
                    if '-2025-2026' in clean_part:
                        clean_part = clean_part.replace('-2025-2026', '')
                    elif '-2024-2025' in clean_part:
                        clean_part = clean_part.replace('-2024-2025', '')
                    elif '-2023-2024' in clean_part:
                        clean_part = clean_part.replace('-2023-2024', '')
                    elif '-2022-2023' in clean_part:
                        clean_part = clean_part.replace('-2022-2023', '')
                    return clean_part.upper()
            return "UNKNOWN"
        except:
            return "UNKNOWN"

    def scrape_team_roster(self, team_url, team_info=None):
        """Scrape team roster with real-time updates"""
        try:
            self.driver.get(team_url)
            time.sleep(self.delay + 2)

            players = []

            # Use XPath to find player elements
            player_elements = self.driver.find_elements(By.XPATH, 
                "//div[@class='Roster_player__e6EbP']/a[contains(@class,'TextLink_link__RhSiC')]")

            total_players = len(player_elements)
            print(f"🔍 Found {total_players} player elements in roster for {team_info.get('name', 'Unknown') if team_info else 'Unknown'}")
            
            if total_players == 0:
                print(f"⚠️ No roster players found for {team_info.get('name', 'Unknown') if team_info else 'Unknown'}")
                return []

            for i, player_elem in enumerate(player_elements):
                current_player = i + 1
                
                try:
                    player_name_raw = player_elem.text.strip()
                    
                    # Extract profile URL from the link
                    profile_url = ""
                    try:
                        profile_url = player_elem.get_attribute('href') or ""
                    except:
                        pass
                    
                    # AGGRESSIVE FILTERING: Clean all whitespace (including nbsp and other unicode)
                    cleaned_name = ''.join(player_name_raw.split())  # Removes ALL whitespace
                    
                    # Skip if the element is JUST "A" or "C" (captain designations) or single char
                    if cleaned_name in ['A', 'C', 'AC', 'CA', ''] or len(cleaned_name) <= 1:
                        print(f"     ⏭️ Skipping captain designation or too short: '{player_name_raw}' (cleaned: '{cleaned_name}')")
                        continue
                    
                    # Also check the raw name
                    if player_name_raw in ['A', 'C', '']:
                        print(f"     ⏭️ Skipping captain designation: '{player_name_raw}'")
                        continue
                    
                    # Remove captain designations from end of name
                    player_name = player_name_raw
                    if player_name.endswith(' A') or player_name.endswith(' C'):
                        player_name = player_name[:-2].strip()
                    
                    # Double-check after removal - check for single letters
                    cleaned_final = ''.join(player_name.split())
                    if cleaned_final in ['A', 'C', 'AC', 'CA', ''] or len(cleaned_final) <= 1:
                        print(f"     ⏭️ Skipping invalid name after cleanup: '{player_name_raw}' -> '{player_name}' (cleaned: '{cleaned_final}')")
                        continue
                    
                    # Extract position from parentheses in name
                    position_from_name = ''
                    if '(' in player_name and ')' in player_name:
                        paren_start = player_name.find('(')
                        paren_end = player_name.find(')', paren_start)
                        if paren_end > paren_start:
                            position_from_name = player_name[paren_start+1:paren_end].strip()
                            
                            # Skip goaltenders - we don't want (G) players
                            if position_from_name == 'G' or position_from_name == 'G/A':
                                print(f"     ⏭️ Skipping goaltender: '{player_name_raw}'")
                                continue
                            
                            # Skip (L) and (R) positions - these are not valid position designations
                            if position_from_name in ['L', 'R']:
                                print(f"     ⏭️ Skipping invalid position: '{player_name_raw}' (Position: {position_from_name})")
                                continue
                            
                            # Remove position from name
                            player_name = player_name[:paren_start].strip()

                    # Find parent row for additional data
                    parent_row = player_elem.find_element(By.XPATH, "./ancestor::tr")

                    # Extract data using XPath selectors
                    number = self.safe_extract_text(parent_row, 
                        ".//td[contains(@class,'SortTable_trow__T6wLH SortTable_right__s2qUT')]")
                    
                    age_text = self.safe_extract_text(parent_row,
                        ".//td[contains(@class,'SortTable_trow__T6wLH SortTable_hideMobile__X1I3z')][2]")
                    age = self.parse_age(age_text)

                    year_text = self.safe_extract_text(parent_row,
                        ".//td[contains(@class,'SortTable_trow__T6wLH SortTable_left__VX4mw')]//span[1]")
                    birth_year = self.parse_int(year_text) if year_text else self.calculate_birth_year(age)

                    hometown = self.safe_extract_text(parent_row,
                        ".//td[@class='SortTable_trow__T6wLH SortTable_hideMobile__X1I3z SortTable_left__VX4mw']/a[contains(@class,'TextLink_link__RhSiC')]")

                    height = self.safe_extract_text(parent_row,
                        ".//td[contains(@class,'SortTable_trow__T6wLH SortTable_hideMobile__X1I3z')][4]")

                    weight = self.safe_extract_text(parent_row,
                        ".//td[contains(@class,'SortTable_trow__T6wLH SortTable_hideMobile__X1I3z')][5]")

                    position = self.safe_extract_text(parent_row,
                        ".//td[contains(@class,'SortTable_trow__T6wLH SortTable_hideMobile__X1I3z SortTable_left__VX4mw')][2]")

                    # Extract shoots (L/R)
                    shoots = self.safe_extract_text(parent_row,
                        ".//td[contains(@class,'SortTable_trow__T6wLH SortTable_hideMobile__X1I3z')][6]")

                    if player_name:
                        # FINAL SAFETY CHECK - Aggressive cleaning to catch captain designations
                        final_cleaned = ''.join(player_name.split())  # Remove ALL whitespace
                        
                        # Block single letters and specific captain designations only
                        if final_cleaned in ['A', 'C', 'AC', 'CA', ''] or len(final_cleaned) <= 1:
                            print(f"     ⏭️ FINAL BLOCK: Invalid name '{player_name}' (cleaned: '{final_cleaned}')")
                            continue
                        
                        # Also check raw player_name
                        if player_name.upper().strip() in ['A', 'C', 'AC', 'CA']:
                            print(f"     ⏭️ FINAL BLOCK: Captain designation '{player_name}'")
                            continue
                        
                        # Use position from name if available, otherwise from table
                        final_position = position_from_name if position_from_name else position
                        
                        # Skip goaltenders - check both sources
                        if final_position and final_position.strip().upper() in ['G', 'G/A', 'GOALIE', 'GOALTENDER']:
                            print(f"     ⏭️ Skipping goaltender: {player_name} (Position: {final_position})")
                            continue
                        
                        # Skip invalid L/R positions - final safety check
                        if final_position and final_position.strip().upper() in ['L', 'R']:
                            print(f"     ⏭️ FINAL BLOCK: Invalid position {player_name} (Position: {final_position})")
                            continue
                        
                        # REAL-TIME OUTPUT: Show player as it's found
                        print(f"     ✓ {current_player}/{total_players}: {player_name} ({final_position})")
                        
                        player_data = {
                            'name': player_name,
                            'jersey': number,  # Jersey number from roster
                            'number': number,  # Keep 'number' for backwards compatibility
                            'position': final_position,
                            'shoots': shoots if shoots in ['L', 'R'] else '',
                            'age': age,
                            'birthYear': birth_year,
                            'height': height,
                            'weight': weight,
                            'hometown': hometown,
                            'profile_url': profile_url,  # EliteProspects profile link
                            'league': team_info.get('league', 'UNKNOWN') if team_info else 'UNKNOWN',
                            'season': team_info.get('season', '2025-2026') if team_info else '2025-2026',
                            # Default stats - will be updated later
                            'games': 0,
                            'goals': 0,
                            'assists': 0,
                            'points': 0,
                            'pim': 0,
                            'ppg': 0.0
                        }
                        players.append(player_data)
                        
                        # Send real-time update every 5 players
                        if len(players) % 5 == 0 or len(players) == total_players:
                            team_name = team_info.get('name', 'Unknown Team') if team_info else 'Unknown Team'
                            self.report_progress(
                                f"Finding players in {team_name}...",
                                team_data={'name': team_name, 'status': 'roster', 'players': players, 'current_count': len(players), 'total_count': total_players}
                            )

                except Exception as e:
                    print(f"     ❌ Error processing roster player {current_player}: {e}")
                    continue

            print(f"✅ Roster scrape completed: {len(players)} players")
            return players

        except Exception as e:
            print(f"❌ Roster scrape failed: {e}")
            return []

    def scrape_team_stats(self, team_url, team_info=None):
        """Scrape team statistics with real-time updates and retry logic"""
        
        team_name = team_info.get('name', 'Unknown') if team_info else 'Unknown'
        stats_url = f"{team_url}?tab=stats"
        
        # Try loading stats page up to 3 times
        max_retries = 3
        page_loaded = False
        
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Stats page retry {attempt}/{max_retries} for {team_name}")
                    time.sleep(3)  # Brief pause before retry
                
                self.driver.get(stats_url)
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(self.delay + 2)
                
                # Success!
                page_loaded = True
                if attempt > 1:
                    print(f"✅ Stats page loaded successfully on attempt {attempt}")
                break
                
            except TimeoutException:
                print(f"❌ Stats page timeout attempt {attempt}/{max_retries} for {team_name}")
                if attempt < max_retries:
                    print(f"⏳ Waiting before retry...")
                    time.sleep(5)  # Wait 5 seconds before retry
                else:
                    print(f"❌ All {max_retries} attempts failed - proceeding without stats")
                    return []
                    
            except Exception as e:
                print(f"❌ Stats page error attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    time.sleep(5)
                else:
                    return []
        
        if not page_loaded:
            return []

        try:
            stats = []

            # Find stats table using flexible XPath
            try:
                # Try main stats table location
                stats_table = self.driver.find_elements(By.XPATH, "//section//table")
                
                if not stats_table:
                    # Fallback to any table in main content
                    stats_table = self.driver.find_elements(By.XPATH, "//main//table")
                
                if stats_table:
                    stats_rows = stats_table[0].find_elements(By.XPATH, ".//tbody/tr")
                    if not stats_rows:
                        stats_rows = stats_table[0].find_elements(By.XPATH, ".//tr")
                else:
                    print(f"❌ Stats table not found for {team_name}")
                    return []
                
            except Exception as e:
                print(f"❌ Error finding stats table: {e}")
                return []
            
            # Filter to only valid player rows
            valid_rows = []
            for row in stats_rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 6:
                        for cell_idx in range(min(4, len(cells))):
                            cell_text = cells[cell_idx].text.strip()
                            if self.is_valid_player_name(cell_text):
                                valid_rows.append(row)
                                break
                except:
                    continue
            
            total_stats_players = len(valid_rows)
            print(f"🔍 Found {total_stats_players} valid stats rows for {team_name}")

            if total_stats_players == 0:
                print(f"❌ No valid stats found")
                return []

            for i, row in enumerate(valid_rows):
                current_player = i + 1
                
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 6:
                        continue
                    
                    # Find the player name
                    player_name = ""
                    player_position = ""
                    
                    for cell_idx in range(min(4, len(cells))):
                        cell_text = cells[cell_idx].text.strip()
                        if self.is_valid_player_name(cell_text):
                            if '(' in cell_text and ')' in cell_text:
                                paren_start = cell_text.find('(')
                                paren_end = cell_text.find(')', paren_start)
                                
                                if paren_end > paren_start:
                                    name_part = cell_text[:paren_start].strip()
                                    position_part = cell_text[paren_start+1:paren_end].strip()
                                    
                                    if len(name_part) >= 3:
                                        player_name = name_part
                                        player_position = position_part
                                    else:
                                        player_name = cell_text
                                        player_position = ""
                                else:
                                    player_name = cell_text
                                    player_position = ""
                            else:
                                player_name = cell_text
                                player_position = ""
                            break
                    
                    if not player_name:
                        continue
                    
                    # Extract stats from specific columns by position
                    # Typical EP stats layout: Name (0-1), Pos (2), GP (3), G (4), A (5), TP (6), +/- (7), PIM (8)
                    games = 0
                    goals = 0
                    assists = 0
                    points = 0
                    pim = 0
                    
                    try:
                        # Find cells with numeric content (stats columns)
                        # Look for cells with right-aligned class (indicates numeric data)
                        stat_cells = []
                        for cell in cells:
                            cell_class = cell.get_attribute('class') or ''
                            cell_text = cell.text.strip()
                            if 'right' in cell_class.lower() and cell_text:
                                # Try to parse as number
                                try:
                                    val = int(cell_text)
                                    stat_cells.append(val)
                                except ValueError:
                                    pass
                        
                        # Assign based on typical order: GP, G, A, TP, PIM
                        if len(stat_cells) >= 5:
                            games = stat_cells[0]
                            goals = stat_cells[1]
                            assists = stat_cells[2]
                            points = stat_cells[3]
                            pim = stat_cells[4]
                        elif len(stat_cells) >= 4:
                            # If missing PIM
                            games = stat_cells[0]
                            goals = stat_cells[1]
                            assists = stat_cells[2]
                            points = stat_cells[3]
                        
                    except Exception as e:
                        print(f"     ❌ Error extracting stats: {e}")

                    if player_name and len(player_name) > 1:
                        stats_data = {
                            'name': player_name,
                            'position': player_position,
                            'games': games,
                            'goals': goals,
                            'assists': assists,
                            'points': points,
                            'pim': pim
                        }
                        stats.append(stats_data)
                        
                        # Debug output for first few players
                        if len(stats) <= 3:
                            print(f"     ✓ {player_name}: GP={games} G={goals} A={assists} P={points}")

                except Exception as e:
                    print(f"     ❌ Error processing stats player {current_player}: {e}")
                    continue

            print(f"✅ Stats scrape completed: {len(stats)} players")
            return stats

        except Exception as e:
            print(f"❌ Stats scrape failed: {e}")
            return []

    def is_valid_player_name(self, text):
        """Enhanced player name validation - handles names with positions"""
        if not text or len(text) < 3:
            return False
        
        clean_text = text.strip()
        
        # If text has parentheses, validate the name part
        if '(' in clean_text and ')' in clean_text:
            paren_start = clean_text.find('(')
            name_part = clean_text[:paren_start].strip()
            
            if len(name_part) < 3:
                return False
            clean_text = name_part
        
        # Simple checks using string methods - NO REGEX!
        
        # Check 1: Reject if it's just numbers
        if clean_text.isdigit():
            return False
            
        # Check 2: Reject if it's numbers with period
        if clean_text.replace('.', '').isdigit():
            return False
            
        # Check 3: Reject common ordinals
        ordinal_endings = ['st', 'nd', 'rd', 'th']
        for ending in ordinal_endings:
            if clean_text.lower().endswith(ending):
                number_part = clean_text[:-2].strip()
                if number_part.isdigit():
                    return False
                    
        # Check 4: Reject common hockey stats abbreviations
        stats_abbrevs = ['GP', 'G', 'A', 'P', 'PIM', 'TOI', 'SV', 'SA', 'PLUS', 'MINUS', '+', '-']
        if clean_text.upper() in stats_abbrevs:
            return False
            
        # Check 5: Must contain at least 2 letters
        letter_count = sum(1 for c in clean_text if c.isalpha())
        if letter_count < 2:
            return False
            
        # Check 6: Reject if it's mostly symbols/numbers
        alpha_chars = sum(1 for c in clean_text if c.isalpha())
        total_chars = len(clean_text)
        if total_chars > 0 and (alpha_chars / total_chars) < 0.5:
            return False
            
        # Check 7: Must start with a letter
        if not clean_text[0].isalpha():
            return False
            
        # Check 8: Reject if it's too short after cleaning
        if len(clean_text) < 2:
            return False
            
        # Check 9: Common non-name patterns
        non_names = ['---', '###', '...', 'N/A', 'TBD', 'UNKNOWN']
        if clean_text.upper() in non_names:
            return False
            
        return True

    def safe_extract_text(self, element, xpath):
        """Safely extract text using XPath"""
        try:
            elements = element.find_elements(By.XPATH, xpath)
            return elements[0].text.strip() if elements else ""
        except:
            return ""

    def combine_roster_and_stats(self, roster, stats, team_info=None):
        """Combine roster and stats data with enhanced name matching"""
        combined = []
        
        season = team_info.get('season', '2025-2026') if team_info else '2025-2026'
        league = team_info.get('league', 'UNKNOWN') if team_info else 'UNKNOWN'

        print(f"🔗 Combining {len(roster)} roster players with {len(stats)} stats players")
        
        stats_matched = set()

        for i, roster_player in enumerate(roster):
            # Find matching stats
            stats_player = None
            for j, stat in enumerate(stats):
                if j not in stats_matched and self.names_match(roster_player['name'], stat['name']):
                    stats_player = stat
                    stats_matched.add(j)
                    break

            # Combine data
            player_data = roster_player.copy()
            player_data['season'] = season
            player_data['league'] = league
            
            if stats_player:
                games = stats_player.get('games', 0)
                points = stats_player.get('points', 0)
                ppg = round(points / games, 2) if games > 0 else 0.0
                
                player_data.update({
                    'games': games,
                    'goals': stats_player.get('goals', 0),
                    'assists': stats_player.get('assists', 0),
                    'points': points,
                    'pim': stats_player.get('pim', 0),
                    'ppg': ppg
                })
                
                # Handle position priority: stats position takes precedence if available
                stats_position = stats_player.get('position', '')
                if stats_position:
                    player_data['position'] = stats_position
                    
            else:
                # Default stats if not found
                player_data.update({
                    'games': 0,
                    'goals': 0,
                    'assists': 0,
                    'points': 0,
                    'pim': 0,
                    'ppg': 0.0
                })

            combined.append(player_data)

        # Add any unmatched stats-only players
        for j, stats_player in enumerate(stats):
            if j not in stats_matched:
                clean_name = self.clean_name_for_matching(stats_player['name'])
                
                games = stats_player.get('games', 0)
                points = stats_player.get('points', 0)
                ppg = round(points / games, 2) if games > 0 else 0.0
                
                player_data = {
                    'name': clean_name,
                    'number': "",
                    'position': stats_player.get('position', ''),
                    'shoots': '',
                    'age': 0,
                    'birthYear': 0,
                    'height': "",
                    'weight': "",
                    'hometown': "",
                    'season': season,
                    'league': league,
                    'games': games,
                    'goals': stats_player.get('goals', 0),
                    'assists': stats_player.get('assists', 0),
                    'points': points,
                    'pim': stats_player.get('pim', 0),
                    'ppg': ppg
                }
                combined.append(player_data)

        print(f"🔗 Final result: {len(combined)} combined players")
        return combined

    def scrape_team_complete(self, team_url, team_info=None):
        """FIXED: Scrape complete team data with proper real-time updates"""
        
        # Check stop signal before starting
        if self.should_stop:
            self.report_progress("🛑 Stopped")
            return []
        
        start_time = time.time()
        team_name = team_info.get('name', 'Unknown Team') if team_info else 'Unknown Team'
        
        print(f"\n🏒 Starting complete scrape for: {team_name}")
        
        try:
            # Update progress with current team being processed
            self.report_progress(
                f"Starting {team_name}...",
                team_data={'name': team_name, 'status': 'starting', 'players': []}
            )
            
            # Scrape roster
            roster = self.scrape_team_roster(team_url, team_info)
            
            if self.should_stop:
                self.report_progress("🛑 Stopped")
                return []
                
            # Scrape stats
            stats = self.scrape_team_stats(team_url, team_info)
            
            if self.should_stop:
                self.report_progress("🛑 Stopped")
                return []
                
            # Combine data
            combined_players = self.combine_roster_and_stats(roster, stats, team_info)
            total_time = time.time() - start_time
            
            # CRITICAL FIX: Immediately add completed team to live_teams
            completed_team = {
                'id': team_info.get('id', ''),
                'name': team_name,
                'league': team_info.get('league', 'UNKNOWN'),
                'season': team_info.get('season', '2025-2026'),
                'url': team_url,
                'players': combined_players
            }
            
            # Add to live teams list for real-time updates
            self.live_teams.append(completed_team)
            
            print(f"✅ COMPLETED {team_name}: {len(combined_players)} players in {total_time:.1f}s")
            print(f"📊 Live teams count: {len(self.live_teams)}")
            
            # Send completion update with the completed team
            self.report_progress(
                f"✅ Completed {team_name} - {len(combined_players)} players",
                team_data=completed_team
            )
            
            return combined_players
            
        except Exception as e:
            error_time = time.time() - start_time
            print(f"❌ ERROR scraping {team_name} after {error_time:.1f}s: {e}")
            self.report_progress(f"❌ Error with {team_name}: {str(e)}")
            return []

    def scrape_multiple_teams(self, team_urls, season="2025-2026"):
        """FIXED: Scrape multiple teams with proper real-time progress tracking"""
        all_teams = []
        
        # DON'T reset live_teams here - we want to accumulate across leagues
        # self.live_teams will persist across multiple league scrapes
        # Only reset when scraper is recreated or explicitly cleared

        # Apply team limit if specified
        if self.max_teams:
            team_urls = team_urls[:self.max_teams]
            self.report_progress(f"Limited to {self.max_teams} teams for this scrape")

        self.total_teams = len(team_urls)
        self.scraped_count = 0

        if self.total_teams == 0:
            self.report_progress("No teams to scrape")
            return []

        self.report_progress(f"Starting scrape of {self.total_teams} teams", 0, self.total_teams)

        # Calculate estimated time
        estimated_seconds = self.total_teams * (self.delay * 3 + 10)
        estimated_minutes = estimated_seconds / 60
        self.report_progress(f"Estimated time: {estimated_minutes:.1f} minutes")

        start_time = time.time()

        for i, team_info in enumerate(team_urls):
            if self.should_stop:
                self.report_progress("Scraping stopped by user", i, self.total_teams)
                break

            try:
                current_num = i + 1
                team_name = team_info.get('name', f'Team {current_num}')
                
                print(f"\n📍 Team {current_num}/{self.total_teams}: {team_name}")
                self.report_progress(f"Scraping {team_name}", current_num, self.total_teams)

                # Add season to team_info
                team_info_with_season = team_info.copy()
                team_info_with_season['season'] = season

                # Scrape team data - this will add to live_teams automatically
                start_team_time = time.time()
                players = self.scrape_team_complete(team_info['url'], team_info_with_season)
                team_scrape_time = time.time() - start_team_time

                # Create final team data structure
                team_data = {
                    'id': team_info['id'],
                    'name': team_info['name'],
                    'league': team_info['league'],
                    'season': season,
                    'url': team_info['url'],
                    'players': players
                }

                all_teams.append(team_data)
                self.scraped_count += 1

                print(f"✅ Team {current_num} completed: {len(players)} players in {team_scrape_time:.1f}s")
                
                # Update progress with current completion status
                self.report_progress(
                    f"Completed {team_info['name']} - {len(players)} players", 
                    current_num, self.total_teams
                )

                # Respectful delay between teams
                if current_num < self.total_teams and not self.should_stop:
                    print(f"⏳ Waiting {self.delay} seconds before next team...")
                    time.sleep(self.delay)

                    # Longer break every batch_size teams
                    if current_num % self.batch_size == 0:
                        batch_break = self.delay * 3
                        print(f"⏳ Batch break: waiting {batch_break} seconds...")
                        self.report_progress(f"Batch break - pausing {batch_break} seconds...")
                        time.sleep(batch_break)

                # Progress updates - every few teams
                if current_num % 3 == 0 or current_num == self.total_teams:
                    elapsed = time.time() - start_time
                    avg_time_per_team = elapsed / current_num
                    remaining_teams = self.total_teams - current_num
                    eta_seconds = remaining_teams * avg_time_per_team
                    eta_minutes = eta_seconds / 60

                    self.report_progress(f"Progress: {current_num}/{self.total_teams} teams (ETA: {eta_minutes:.0f}m)")

            except Exception as e:
                print(f"❌ TEAM SCRAPE FAILED for {team_info.get('name', f'Team {current_num}')}: {e}")
                self.report_progress(f"❌ Error with {team_info['name']}: {str(e)}")
                continue

        elapsed_time = time.time() - start_time
        elapsed_minutes = elapsed_time / 60

        print(f"\n{'='*60}")
        print(f"🏁 SCRAPING COMPLETED!")
        print(f"{'='*60}")
        print(f"   📊 Teams scraped: {len(all_teams)}/{self.total_teams}")
        print(f"   📊 Total players: {sum(len(team.get('players', [])) for team in all_teams)}")
        print(f"   ⏱️  Time elapsed: {elapsed_minutes:.1f} minutes")
        print(f"   ⚡ Average: {elapsed_time/len(all_teams) if all_teams else 0:.1f}s per team")
        print(f"{'='*60}\n")
        print(f"   ⏱️ Total time: {elapsed_minutes:.1f} minutes")

        self.report_progress(f"Scraping completed! {len(all_teams)} teams in {elapsed_minutes:.1f} minutes",
                           len(all_teams), self.total_teams)

        return all_teams

    def parse_age(self, age_text):
        """Extract age from text - SIMPLE STRING METHOD"""
        try:
            if not age_text:
                return 0
            numbers = ''.join(c for c in str(age_text) if c.isdigit())
            return int(numbers) if numbers else 0
        except:
            return 0

    def calculate_birth_year(self, age):
        """Calculate birth year from age"""
        current_year = 2025
        return current_year - age if age > 0 else 0

    def parse_int(self, text):
        """Parse integer from text - SIMPLE STRING METHOD"""
        try:
            if not text:
                return 0
            numbers = ''.join(c for c in str(text) if c.isdigit())
            return int(numbers) if numbers else 0
        except:
            return 0

    def names_match(self, name1, name2):
        """Check if two names match - handles names with/without position info"""
        if not name1 or not name2:
            return False
        
        clean_name1 = self.clean_name_for_matching(name1)
        clean_name2 = self.clean_name_for_matching(name2)
        
        return clean_name1.lower().strip() == clean_name2.lower().strip()
    
    def clean_name_for_matching(self, name):
        """Remove position info from name for matching purposes"""
        if not name:
            return ""
        
        clean_name = name.strip()
        
        # Remove position in parentheses
        if '(' in clean_name and ')' in clean_name:
            paren_start = clean_name.find('(')
            paren_end = clean_name.find(')', paren_start)
            if paren_end > paren_start:
                clean_name = clean_name[:paren_start].strip()
        
        return clean_name

    def close(self):
        """Close the webdriver"""
        if hasattr(self, 'driver'):
            self.driver.quit()


# Flask API
app = Flask(__name__)
CORS(app)

# Multi-league global storage
scraped_data_by_league = {}  # {'NA3HL': [teams], 'USPHL': [teams]}
scraping_progress = {
    'active': False,
    'message': 'Ready',
    'current_league_index': 0,
    'total_leagues': 0,
    'leagues': {},
    'overall_percentage': 0,
    'completed': True,
    'stopped': False
}
active_scraper = None
completed_leagues = []


def progress_callback(progress_info):
    """Multi-league progress callback"""
    global scraping_progress, scraped_data_by_league
    
    scraping_progress.update(progress_info)
    scraping_progress['active'] = not progress_info.get('completed', False)
    
    # Current team being scraped
    if 'team_data' in progress_info:
        scraping_progress['current_team'] = progress_info['team_data']
    
    # League-specific progress
    if 'current_league' in progress_info:
        league_name = progress_info['current_league']
        if 'leagues' not in scraping_progress:
            scraping_progress['leagues'] = {}
        scraping_progress['leagues'][league_name] = {
            'current': progress_info.get('current', 0),
            'total': progress_info.get('total', 0),
            'percentage': progress_info.get('percentage', 0),
            'status': progress_info.get('status', 'pending')
        }
    
    # Store league data
    if 'league_data' in progress_info and 'league_name' in progress_info:
        scraped_data_by_league[progress_info['league_name']] = progress_info['league_data']
    
    # Overall progress
    if scraping_progress.get('total_leagues', 0) > 0:
        completed = scraping_progress.get('current_league_index', 0)
        total = scraping_progress['total_leagues']
        scraping_progress['overall_percentage'] = (completed / total) * 100


@app.route('/')
def serve_dashboard():
    """Serve the enhanced HTML dashboard"""
    return send_from_directory('.', 'enhanced_dashboard.html')


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """FIXED: Get current scraping progress with proper live data"""
    return jsonify(scraping_progress)


@app.route('/api/stop', methods=['POST'])
def stop_scraping():
    """Stop active scraping"""
    global active_scraper
    if active_scraper:
        active_scraper.stop_scraping()
        return jsonify({'status': 'Stop signal sent'})
    return jsonify({'status': 'No active scraping'})


@app.route('/api/cleanup', methods=['POST'])
def cleanup_scraper():
    """Cleanup scraper after all leagues are done"""
    global active_scraper
    if active_scraper:
        try:
            active_scraper.close()
            active_scraper = None
            print("🧹 Scraper cleaned up successfully")
            return jsonify({'status': 'Cleanup successful'})
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
            return jsonify({'status': 'Cleanup failed', 'error': str(e)})
    return jsonify({'status': 'No active scraper to cleanup'})


@app.route('/api/scrape', methods=['POST'])
def scrape_teams():
    """Single-league scraping API endpoint (original working version)"""
    global scraped_data_by_league, active_scraper, scraping_progress

    if scraping_progress.get('active', False):
        return jsonify({'error': 'Scraping already in progress'}), 409

    data = request.json
    league_url = data.get('league_url')  # Single URL like original
    league_name = data.get('league_name', 'UNKNOWN')
    season = data.get('season', '2025-2026')
    delay = data.get('delay', 3)
    max_teams = data.get('max_teams')
    batch_size = data.get('batch_size', 5)
    headless = data.get('headless', True)
    is_first_league = data.get('is_first_league', False)

    if not league_url:
        return jsonify({'error': 'League URL required'}), 400

    def scrape_in_background():
        global active_scraper, scraped_data_by_league, scraping_progress
        
        try:
            scraping_progress = {
                'active': True,
                'message': f'Starting {league_name}...',
                'completed': False
            }

            print(f"\n{'='*60}")
            print(f"🏒 Scraping: {league_name}")
            print(f"🔗 URL: {league_url}/{season}")
            print(f"{'='*60}\n")

            # Reuse existing scraper if available, otherwise create new one
            if not active_scraper:
                print("🆕 Creating new scraper instance")
                active_scraper = EliteProspectsScraper(headless=headless, delay=delay, max_teams=max_teams, batch_size=batch_size)
            else:
                print("♻️ Reusing existing scraper instance")
                # Update scraper parameters for this league
                active_scraper.delay = delay
                active_scraper.max_teams = max_teams
                active_scraper.batch_size = batch_size
                
                # Clear live_teams if this is the first league of a new session
                if is_first_league:
                    print("🧹 Clearing live_teams for new scraping session")
                    active_scraper.live_teams = []
            
            active_scraper.set_progress_callback(progress_callback)

            # Get teams from league
            teams = active_scraper.get_league_teams(f"{league_url}/{season}", season)
            
            if not teams or len(teams) == 0:
                print(f"⚠️ No teams found in {league_name}")
                scraping_progress.update({'active': False, 'completed': True, 'message': f'No teams found in {league_name}'})
                # DON'T close scraper - might be reused
                return
            
            print(f"📋 Found {len(teams)} teams, starting scrape...\n")
            
            # Scrape all teams
            league_teams = active_scraper.scrape_multiple_teams(teams, season)
            
            # Store results
            scraped_data_by_league[league_name] = league_teams
            
            # DON'T close scraper here - might be reused by next league
            # active_scraper.close()
            # active_scraper = None
            
            scraping_progress.update({
                'active': False, 
                'completed': True, 
                'message': f'Complete! {league_name}: {len(league_teams)} teams'
            })
            
            print(f"\n{'='*60}")
            print(f"✅ {league_name} complete: {len(league_teams)} teams")
            print(f"{'='*60}\n")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            scraping_progress.update({'active': False, 'completed': True, 'message': f'Error: {str(e)}'})
            # Keep scraper alive even on error
            # if active_scraper:
            #     active_scraper.close()
            #     active_scraper = None

    thread = threading.Thread(target=scrape_in_background)
    thread.daemon = True
    thread.start()

    return jsonify({
        'status': 'Scraping started', 
        'message': f'Scraping {league_name}', 
        'config': {
            'league': league_name,
            'league_url': league_url,
            'season': season,
            'delay': delay,
            'max_teams': max_teams
        }
    })


@app.route('/api/teams', methods=['GET'])
def get_teams():
    """Get scraped teams data - returns league-grouped data"""
    global scraped_data_by_league
    
    print(f"🔍 API /teams called - Leagues: {list(scraped_data_by_league.keys())}")
    
    return jsonify(scraped_data_by_league)


@app.route('/api/team/<team_id>', methods=['GET'])
def get_team(team_id):
    """Get specific team data from any league"""
    global scraped_data_by_league
    
    for league_name, teams in scraped_data_by_league.items():
        for team in teams:
            if str(team.get('id', '')) == str(team_id):
                return jsonify(team)
    
    return jsonify({'error': 'Team not found'}), 404


@app.route('/api/resume', methods=['POST'])
def resume_scraping():
    """Resume stopped scraping"""
    global scraping_progress
    
    if not scraping_progress.get('stopped', False):
        return jsonify({'error': 'No stopped scraping to resume'}), 400
    
    return jsonify({'status': 'Resume ready', 'message': 'Call /api/scrape with resume=true'})


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "=" * 70)
    print("🏒 Juniors Stats Web Scraper 2025-26")
    print("=" * 70)
    print(f"\n✅ Server running on: http://localhost:{port}")
    print(f"✅ Click to open: http://localhost:{port}")
    print(f"⚡ Speed optimization: Images disabled for faster scraping\n")
    print("=" * 70 + "\n")

    # Start Flask API
    from werkzeug.serving import WSGIRequestHandler
    
    class QuietHandler(WSGIRequestHandler):
        def log_request(self, code='-', size='-'):
            pass
    
    try:
        app.run(
            debug=False, 
            host='0.0.0.0', 
            port=port,
            request_handler=QuietHandler,
            use_reloader=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
