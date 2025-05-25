import sys
import os
import random
import string
import time
import configparser
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import traceback
import json # Added for potential future JSON proxy file parsing

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar, QSpinBox,
    QFormLayout, QFileDialog, QMessageBox, QRadioButton, QGroupBox,
    QCheckBox, QSpacerItem, QSizePolicy, QFontComboBox
)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QMutex
import requests

# --- Constants ---
CONFIG_DIR = 'config'
CONFIG_FNAME = 'config.ini'
ICON_FNAME = 'icon.png'

CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, CONFIG_FNAME)
ICON_FILE_PATH = os.path.join(CONFIG_DIR, ICON_FNAME)

DATA_ROOT_DIR = 'data'
ATTEMPTED_LOG_FNAME = 'attempted_links.log'
GOOD_LINKS_FNAME = 'good_links.txt'
BAD_LINKS_FNAME = 'bad_links.txt'
UNCLASSIFIED_LINKS_FNAME = 'unclassified_links.txt'
APP_LOG_FILE = 'app_activity.log'


# --- Comprehensive User Agent Generation ---
# (Giữ nguyên User Agent Generation)
PLATFORMS = {
    "Windows": [
        "Windows NT 10.0; Win64; x64", "Windows NT 10.0; WOW64", "Windows NT 6.3; Win64; x64",
        "Windows NT 6.2; Win64; x64", "Windows NT 6.1; Win64; x64", "Windows NT 6.1; WOW64"
    ],
    "Macintosh": [
        "Macintosh; Intel Mac OS X 10_15_7", "Macintosh; Intel Mac OS X 10_14_6",
        "Macintosh; Intel Mac OS X 10_13_6", "Macintosh; Intel Mac OS X 11_5_2",
        "Macintosh; Intel Mac OS X 12_3_1"
    ],
    "Linux": [
        "X11; Linux x86_64", "X11; Ubuntu; Linux x86_64", "X11; Fedora; Linux x86_64"
    ],
    "Mobile_iOS": [
        "iPhone; CPU iPhone OS 15_4 like Mac OS X", "iPhone; CPU iPhone OS 14_7 like Mac OS X",
        "iPad; CPU OS 15_4 like Mac OS X", "iPad; CPU OS 14_6 like Mac OS X"
    ],
    "Mobile_Android": [
        "Linux; Android 11; SM-G991U Build/RP1A.200720.012",
        "Linux; Android 10; Pixel 4 Build/QD1A.190821.014"
    ]
}
WEBKIT_VERSIONS = ["AppleWebKit/537.36 (KHTML, like Gecko)", "AppleWebKit/605.1.15 (KHTML, like Gecko)"]
CHROME_VERSIONS = [f"Chrome/{random.randint(80, 105)}.0.{random.randint(4000, 5000)}.{random.randint(100, 200)}" for _ in range(30)]
FIREFOX_VERSIONS = [f"Gecko/20100101 Firefox/{random.randint(70, 100)}.0" for _ in range(20)]
SAFARI_VERSIONS = [f"Version/{random.randint(12, 15)}.{random.randint(0,1)}.{random.randint(0,2)} Safari/{WEBKIT_VERSIONS[1].split(' ')[-1]}" for _ in range(20)]
EDGE_VERSIONS = [f"Edg/{random.randint(90,105)}.0.{random.randint(1000,1500)}.{random.randint(40,70)}" for _ in range(15)]

def generate_random_user_agent():
    browser_type = random.choice(["chrome", "firefox", "safari", "edge"])
    platform_type = random.choice(list(PLATFORMS.keys()))
    platform = random.choice(PLATFORMS[platform_type])
    webkit = random.choice(WEBKIT_VERSIONS)
    ua = f"Mozilla/5.0 ({platform}) {webkit}"
    if browser_type == "chrome":
        ua += f" {random.choice(CHROME_VERSIONS)} {random.choice(SAFARI_VERSIONS).split(' ')[-1]}"
    elif browser_type == "firefox":
        if "Windows" in platform or "Linux" in platform:
             ua = f"Mozilla/5.0 ({platform}; rv:{FIREFOX_VERSIONS[0].split('/')[-1].split('.')[0]}.0) {random.choice(FIREFOX_VERSIONS)}"
        elif "Macintosh" in platform:
             ua = f"Mozilla/5.0 ({platform}; rv:{FIREFOX_VERSIONS[0].split('/')[-1].split('.')[0]}.0) {random.choice(FIREFOX_VERSIONS)}"
    elif browser_type == "safari" and ("Macintosh" in platform or "Mobile_iOS" in platform):
        ua += f" {random.choice(SAFARI_VERSIONS)}"
    elif browser_type == "edge" and "Windows" in platform:
        ua += f" {random.choice(CHROME_VERSIONS)} {random.choice(SAFARI_VERSIONS).split(' ')[-1]} {random.choice(EDGE_VERSIONS)}"
    else:
        ua = f"Mozilla/5.0 ({platform}) {webkit} {random.choice(CHROME_VERSIONS)} {random.choice(SAFARI_VERSIONS).split(' ')[-1]}"
    return ua

USER_AGENTS = [generate_random_user_agent() for _ in range(300)]
USER_AGENTS.extend([
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
])
random.shuffle(USER_AGENTS)

# --- Logging Setup ---

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# --- Shared Resources Manager ---
# (Giữ nguyên SharedScanResources)
class SharedScanResources:
    def __init__(self, website_data_path):
        self.website_data_path = website_data_path
        os.makedirs(self.website_data_path, exist_ok=True)

        self.attempted_log_file_path = os.path.join(self.website_data_path, ATTEMPTED_LOG_FNAME)
        self.good_links_file_path = os.path.join(self.website_data_path, GOOD_LINKS_FNAME)
        self.bad_links_file_path = os.path.join(self.website_data_path, BAD_LINKS_FNAME)
        self.unclassified_links_file_path = os.path.join(self.website_data_path, UNCLASSIFIED_LINKS_FNAME)

        self.attempted_links_set = set()
        self.attempted_links_mutex = QMutex()

        self.attempted_log_file_mutex = QMutex()
        self.good_links_file_mutex = QMutex()
        self.bad_links_file_mutex = QMutex()
        self.unclassified_links_file_mutex = QMutex()

        self.total_scanned_count = 0
        self.good_links_count = 0
        self.bad_links_count = 0
        self.unclassified_links_count = 0
        self.stats_mutex = QMutex()

        self.load_attempted_links_from_file()

    def load_attempted_links_from_file(self):
        self.attempted_links_mutex.lock()
        try:
            if os.path.exists(self.attempted_log_file_path):
                with open(self.attempted_log_file_path, 'r', encoding='utf-8') as f:
                    self.attempted_links_set = set(line.strip() for line in f)
                logging.info(f"Đã tải {len(self.attempted_links_set)} link đã thử từ '{self.attempted_log_file_path}' vào SharedResources.")
        except Exception as e:
            logging.error(f"Lỗi khi tải log link đã thử từ '{self.attempted_log_file_path}': {e}\n{traceback.format_exc()}")
        finally:
            self.attempted_links_mutex.unlock()

    def is_link_attempted(self, link):
        self.attempted_links_mutex.lock()
        try:
            return link in self.attempted_links_set
        finally:
            self.attempted_links_mutex.unlock()

    def add_processed_link_to_attempted(self, link):
        self.attempted_log_file_mutex.lock()
        try:
            with open(self.attempted_log_file_path, 'a', encoding='utf-8') as f_log:
                f_log.write(link + '\n')
        except Exception as e:
            logging.error(f"Lỗi khi ghi vào {self.attempted_log_file_path}: {e}\n{traceback.format_exc()}")
        finally:
            self.attempted_log_file_mutex.unlock()

        self.attempted_links_mutex.lock()
        try:
            self.attempted_links_set.add(link)
        finally:
            self.attempted_links_mutex.unlock()

    def log_good_link(self, link):
        self.good_links_file_mutex.lock()
        try:
            with open(self.good_links_file_path, 'a', encoding='utf-8') as f_good:
                f_good.write(f"{link}\n")
        except Exception as e:
            logging.error(f"Lỗi khi ghi vào {self.good_links_file_path}: {e}\n{traceback.format_exc()}")
        finally:
            self.good_links_file_mutex.unlock()

    def log_bad_link(self, link):
        self.bad_links_file_mutex.lock()
        try:
            with open(self.bad_links_file_path, 'a', encoding='utf-8') as f_bad:
                f_bad.write(f"{link}\n")
        except Exception as e:
            logging.error(f"Lỗi khi ghi vào {self.bad_links_file_path}: {e}\n{traceback.format_exc()}")
        finally:
            self.bad_links_file_mutex.unlock()

    def log_unclassified_link(self, link):
        self.unclassified_links_file_mutex.lock()
        try:
            with open(self.unclassified_links_file_path, 'a', encoding='utf-8') as f_unclassified:
                f_unclassified.write(f"{link}\n")
        except Exception as e:
            logging.error(f"Lỗi khi ghi vào {self.unclassified_links_file_path}: {e}\n{traceback.format_exc()}")
        finally:
            self.unclassified_links_file_mutex.unlock()

    def increment_total_scanned_and_get_stats(self):
        self.stats_mutex.lock()
        self.total_scanned_count += 1
        current_total = self.total_scanned_count
        current_good = self.good_links_count
        current_bad = self.bad_links_count
        current_unclassified = self.unclassified_links_count
        self.stats_mutex.unlock()
        return current_total, current_good, current_bad, current_unclassified

    def increment_good_links(self):
        self.stats_mutex.lock()
        self.good_links_count += 1
        self.stats_mutex.unlock()

    def increment_bad_links(self):
        self.stats_mutex.lock()
        self.bad_links_count += 1
        self.stats_mutex.unlock()

    def increment_unclassified_links(self):
        self.stats_mutex.lock()
        self.unclassified_links_count += 1
        self.stats_mutex.unlock()

    def get_current_stats(self):
        self.stats_mutex.lock()
        stats = (self.total_scanned_count, self.good_links_count, self.bad_links_count, self.unclassified_links_count)
        self.stats_mutex.unlock()
        return stats

    def reset_stats(self):
        self.stats_mutex.lock()
        self.total_scanned_count = 0
        self.good_links_count = 0
        self.bad_links_count = 0
        self.unclassified_links_count = 0
        self.stats_mutex.unlock()


# --- Worker Thread for Scanning ---
class ScanWorker(QThread):
    progress_update = pyqtSignal(int)
    log_message = pyqtSignal(str, str) # MODIFIED: message, type
    individual_stats_update = pyqtSignal()
    finished = pyqtSignal(object)

    def __init__(self, worker_id, base_url, additional_paths,
                 suffix_char_options, suffix_length,
                 suffix_pattern, suffix_ratios, suffix_generation_mode,
                 proxy_sources,
                 scan_limit_count_per_worker,
                 scan_limit_minutes,
                 requests_per_active_proxy,
                 shared_resources: SharedScanResources,
                 good_link_keywords,
                 bad_link_keywords,
                 bad_link_is_everything_else,
                 good_link_is_everything_else, # NEW PARAM
                 suffix_separator_mode,       # NEW
                 custom_suffix_separator      # NEW
                ):
        super().__init__()
        self.worker_id = worker_id
        self.base_url = base_url.rstrip('/')
        self.additional_paths = additional_paths if additional_paths else [""]
        
        self.suffix_char_options = suffix_char_options
        self.suffix_length = suffix_length
        self.suffix_pattern = suffix_pattern
        self.suffix_ratios = suffix_ratios
        self.suffix_generation_mode = suffix_generation_mode

        self.proxy_sources = proxy_sources
        self.requests_per_active_proxy = requests_per_active_proxy

        self.scan_limit_count_per_worker = scan_limit_count_per_worker if scan_limit_count_per_worker > 0 else float('inf')
        self.scan_limit_minutes_global = scan_limit_minutes
        self.shared_resources = shared_resources
        self.running = True
        self.start_time_global = None

        self.raw_proxies_list_local = []
        self.current_raw_proxy_idx_local = 0
        self.links_successfully_processed_by_worker = 0
        
        self.character_set = self._build_character_set()
        self.character_set_parts = self._build_character_set_parts()

        self.good_link_keywords = [kw.strip().lower() for kw in good_link_keywords if kw.strip()]
        self.bad_link_keywords = [kw.strip().lower() for kw in bad_link_keywords if kw.strip()]
        self.bad_link_is_everything_else = bad_link_is_everything_else
        self.good_link_is_everything_else = good_link_is_everything_else 
        self.suffix_separator_mode = suffix_separator_mode                 
        self.custom_suffix_separator = custom_suffix_separator             

    def _build_character_set(self): # Original method for combined char set
        chars = []
        if self.suffix_char_options.get('lowercase'):
            chars.extend(string.ascii_lowercase)
        if self.suffix_char_options.get('uppercase'):
            chars.extend(string.ascii_uppercase)
        if self.suffix_char_options.get('digits'):
            chars.extend(string.digits)
        
        custom_special = self.suffix_char_options.get('custom_special_chars', "")
        if self.suffix_char_options.get('all_special'):
            common_punctuation = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            chars.extend(list(common_punctuation))
            if custom_special:
                 for char in custom_special:
                    if char not in chars:
                        chars.append(char)
        elif custom_special:
            chars.extend(list(custom_special))
        
        if not chars:
            logging.warning(f"[Worker {self.worker_id}] Bộ ký tự (kết hợp) rỗng. Mặc định dùng chữ thường + số.")
            chars.extend(string.ascii_lowercase + string.digits)
        return list(set(chars))

    def _build_character_set_parts(self): # NEW: For ratio and pattern char sources
        parts = {
            'lowercase': [], 'uppercase': [], 'digits': [], 'special': []
        }
        if self.suffix_char_options.get('lowercase'):
            parts['lowercase'].extend(list(string.ascii_lowercase))
        if self.suffix_char_options.get('uppercase'):
            parts['uppercase'].extend(list(string.ascii_uppercase))
        if self.suffix_char_options.get('digits'):
            parts['digits'].extend(list(string.digits))
        
        temp_special_chars = []
        custom_special = self.suffix_char_options.get('custom_special_chars', "")
        if self.suffix_char_options.get('all_special'):
            common_punctuation = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            temp_special_chars.extend(list(common_punctuation))
        if custom_special:
             for char_val in custom_special: 
                if char_val not in temp_special_chars:
                    temp_special_chars.append(char_val)
        parts['special'].extend(list(set(temp_special_chars)))
        return parts

    def _get_random_char_from_type(self, char_type_key): 
        char_list_for_type = self.character_set_parts.get(char_type_key, [])
        if char_list_for_type:
            return random.choice(char_list_for_type)
        logging.warning(f"[Worker {self.worker_id}] Loại ký tự '{char_type_key}' được yêu cầu cho ratio/pattern nhưng không có ký tự nào được định nghĩa trong tùy chọn. Dùng ký tự từ bộ kết hợp.")
        if self.character_set: 
            return random.choice(self.character_set)
        return random.choice(string.ascii_lowercase + string.digits)

    def _get_random_suffix(self):
        if self.suffix_pattern:
            generated_suffix_list = []
            wildcard_chars = []
            if self.suffix_char_options.get('lowercase') and self.character_set_parts['lowercase']:
                wildcard_chars.extend(self.character_set_parts['lowercase'])
            if self.suffix_char_options.get('uppercase') and self.character_set_parts['uppercase']:
                wildcard_chars.extend(self.character_set_parts['uppercase'])
            if self.suffix_char_options.get('digits') and self.character_set_parts['digits']:
                wildcard_chars.extend(self.character_set_parts['digits'])
            if (self.suffix_char_options.get('all_special') or self.suffix_char_options.get('custom_special_chars')) and self.character_set_parts['special']:
                 wildcard_chars.extend(self.character_set_parts['special'])
            if not wildcard_chars:
                msg = f"[Worker {self.worker_id}] Pattern '{self.suffix_pattern}' được dùng, nhưng không có loại ký tự nào được chọn cho dấu '*'. Sẽ dùng a-z, 0-9."
                logging.warning(msg)
                self.log_message.emit(msg, "warning")
                wildcard_chars.extend(list(string.ascii_lowercase + string.digits))
            for char_in_pattern in self.suffix_pattern:
                if char_in_pattern == '*':
                    generated_suffix_list.append(random.choice(wildcard_chars))
                else:
                    generated_suffix_list.append(char_in_pattern)
            return "".join(generated_suffix_list)

        total_ratio_chars = sum(self.suffix_ratios.values())
        if total_ratio_chars > 0:
            for char_type, count in self.suffix_ratios.items():
                if count > 0 and not self.character_set_parts[char_type]:
                    msg = f"[Worker {self.worker_id}] Tỷ lệ yêu cầu {count} ký tự '{char_type}', nhưng không có ký tự nào được định nghĩa cho loại này. Sẽ dùng chế độ random cổ điển."
                    logging.warning(msg)
                    self.log_message.emit(msg, "error") 
                    total_ratio_chars = 0 
                    break
            if total_ratio_chars > 0: 
                current_suffix_parts = []
                for _ in range(self.suffix_ratios.get('lowercase', 0)):
                    current_suffix_parts.append(self._get_random_char_from_type('lowercase'))
                for _ in range(self.suffix_ratios.get('uppercase', 0)):
                    current_suffix_parts.append(self._get_random_char_from_type('uppercase'))
                for _ in range(self.suffix_ratios.get('digits', 0)):
                    current_suffix_parts.append(self._get_random_char_from_type('digits'))
                for _ in range(self.suffix_ratios.get('special', 0)):
                    current_suffix_parts.append(self._get_random_char_from_type('special'))
                random.shuffle(current_suffix_parts)
                return "".join(current_suffix_parts)

        if not self.character_set:
            msg = f"[Worker {self.worker_id}] Bộ ký tự (kết hợp) rỗng và không dùng pattern/ratio! Dùng tạm a-z0-9."
            logging.error(msg)
            self.log_message.emit(msg, "error")
            return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(self.suffix_length if self.suffix_length > 0 else 8))
        return ''.join(random.choice(self.character_set) for _ in range(self.suffix_length))


    def _fetch_new_proxies_from_sources_local(self):
        logging.debug(f"[Worker {self.worker_id}] Starting _fetch_new_proxies_from_sources_local.")
        new_raw_proxies = []
        for source_item in self.proxy_sources: 
            if not self.running:
                logging.debug(f"[Worker {self.worker_id}] Fetch proxies aborted, worker not running.")
                return []
            source_item_stripped = source_item.strip()
            if not source_item_stripped:
                continue
            parsed_item = urlparse(source_item_stripped)
            if not parsed_item.scheme and ":" in source_item_stripped and "." in source_item_stripped:
                new_raw_proxies.append(source_item_stripped)
                logging.info(f"[Worker {self.worker_id}] Đã thêm proxy trực tiếp: {source_item_stripped}")
                continue
            logging.debug(f"[Worker {self.worker_id}] Fetching from URL: {source_item_stripped}")
            try:
                response = requests.get(source_item_stripped, timeout=10)
                response.raise_for_status()
                proxies_from_source_text = response.text.splitlines()
                fetched_count = 0
                for p_line in proxies_from_source_text:
                    p_strip = p_line.strip()
                    if not p_strip: continue
                    parsed_p = urlparse(p_strip)
                    if (parsed_p.scheme and parsed_p.netloc and ":" in parsed_p.netloc) or \
                       (not parsed_p.scheme and "." in p_strip and ":" in p_strip and p_strip.count(':') >= 1):
                        new_raw_proxies.append(p_strip)
                        fetched_count +=1
                if fetched_count > 0:
                    logging.info(f"[Worker {self.worker_id}] Đã lấy {fetched_count} proxy từ {source_item_stripped}")
            except requests.RequestException as e:
                logging.warning(f"[Worker {self.worker_id}] Lỗi khi lấy proxy từ {source_item_stripped}: {e}")
                self.log_message.emit(f"Lỗi lấy proxy từ {source_item_stripped}: {e}", "error")
            except Exception as e_gen:
                 logging.error(f"[Worker {self.worker_id}] Lỗi không xác định khi fetch proxy từ {source_item_stripped}: {e_gen}\n{traceback.format_exc()}")
                 self.log_message.emit(f"Lỗi lạ fetch proxy từ {source_item_stripped}: {e_gen}", "error")
        if not new_raw_proxies:
            logging.info(f"[Worker {self.worker_id}] Không lấy được proxy thô nào trong lần fetch này.")
        logging.debug(f"[Worker {self.worker_id}] Finished _fetch_new_proxies_from_sources_local. Found {len(new_raw_proxies)} proxies.")
        return new_raw_proxies
        
    def _check_proxy_local(self, proxy_candidate_str):
        parsed_candidate = urlparse(proxy_candidate_str)
        schemes_to_try_formatted = []
        if parsed_candidate.scheme and parsed_candidate.netloc: 
            if parsed_candidate.scheme in ["http", "https", "socks5", "socks4", "socks5h", "socks4a"]:
                 schemes_to_try_formatted.append(proxy_candidate_str)
            else: 
                logging.debug(f"[Worker {self.worker_id}] Proxy candidate '{proxy_candidate_str}' has unsupported scheme '{parsed_candidate.scheme}'.")
                return None
        elif not parsed_candidate.scheme and ":" in proxy_candidate_str and "." in proxy_candidate_str : 
            if "@" in proxy_candidate_str: 
                 schemes_to_try_formatted = [
                    f"http://{proxy_candidate_str}", 
                    f"https://{proxy_candidate_str}",
                    f"socks5://{proxy_candidate_str}", 
                    f"socks4://{proxy_candidate_str.split('@')[1]}"
                ]
            else: 
                schemes_to_try_formatted = [
                    f"http://{proxy_candidate_str}", 
                    f"https://{proxy_candidate_str}",
                    f"socks5://{proxy_candidate_str}", 
                    f"socks4://{proxy_candidate_str}"
                ]
        else: 
            logging.debug(f"[Worker {self.worker_id}] Proxy candidate '{proxy_candidate_str}' is not a valid format.")
            return None
        for scheme_url in schemes_to_try_formatted:
            if not self.running: return None
            proxies_dict = {"http": scheme_url, "https": scheme_url}
            try:
                response = requests.get("https://api.ipify.org", proxies=proxies_dict, timeout=7) 
                if response.status_code == 200 and response.text.strip():
                    return proxies_dict
            except Exception: 
                pass
        logging.debug(f"[Worker {self.worker_id}] Proxy candidate '{proxy_candidate_str}' (tried as {schemes_to_try_formatted}) failed all scheme checks.")
        return None

    def run(self):
        try:
            if self.start_time_global is None:
                self.start_time_global = datetime.now()
            
            initial_log_msg = f"[Worker {self.worker_id}] Bắt đầu."
            if self.suffix_pattern: initial_log_msg += f" Pattern: '{self.suffix_pattern}'."
            elif sum(self.suffix_ratios.values()) > 0: initial_log_msg += f" Ratios: {self.suffix_ratios}."
            else: initial_log_msg += f" Suffix: {self.suffix_length} ký tự, Bộ ký tự: {''.join(self.character_set)}."
            self.log_message.emit(initial_log_msg, "info")
            logging.info(initial_log_msg)

            while self.running:
                if self.links_successfully_processed_by_worker >= self.scan_limit_count_per_worker:
                    msg = f"[Worker {self.worker_id}] Đạt giới hạn link/worker ({self.scan_limit_count_per_worker})."
                    self.log_message.emit(msg, "info")
                    logging.info(msg)
                    break
                if (datetime.now() - self.start_time_global).total_seconds() / 60 >= self.scan_limit_minutes_global:
                    msg = f"[Worker {self.worker_id}] Đạt giới hạn thời gian chạy chung."
                    self.log_message.emit(msg, "info")
                    logging.info(msg)
                    break
                
                if not self.raw_proxies_list_local or self.current_raw_proxy_idx_local >= len(self.raw_proxies_list_local):
                    logging.debug(f"[Worker {self.worker_id}] Làm mới danh sách proxy...")
                    fetched_list = self._fetch_new_proxies_from_sources_local() 
                    if not fetched_list and not self.proxy_sources:
                        msg = f"[Worker {self.worker_id}] Không có nguồn proxy. Chạy không proxy."
                        self.log_message.emit(msg, "info")
                        logging.info(msg)
                    elif not fetched_list:
                        msg = f"[Worker {self.worker_id}] Không lấy được proxy mới. Chờ 10 giây..."
                        self.log_message.emit(msg, "warning")
                        logging.info(msg)
                        for _ in range(100): 
                            if not self.running: break
                            time.sleep(0.1)
                        if not self.running: break
                        continue
                    self.raw_proxies_list_local = fetched_list
                    random.shuffle(self.raw_proxies_list_local)
                    self.current_raw_proxy_idx_local = 0
                    if self.raw_proxies_list_local:
                        msg = f"[Worker {self.worker_id}] Đã fetch/load và xáo trộn {len(self.raw_proxies_list_local)} proxy."
                        self.log_message.emit(msg, "info")
                        logging.info(msg)

                active_proxy_dict_to_use = None
                if self.raw_proxies_list_local and self.current_raw_proxy_idx_local < len(self.raw_proxies_list_local):
                    proxy_candidate_str = self.raw_proxies_list_local[self.current_raw_proxy_idx_local]
                    self.current_raw_proxy_idx_local += 1
                    active_proxy_dict_to_use = self._check_proxy_local(proxy_candidate_str) 
                    if active_proxy_dict_to_use:
                        msg = f"[Worker {self.worker_id}] Proxy {active_proxy_dict_to_use['http']} hoạt động. Dùng cho {self.requests_per_active_proxy} link."
                        self.log_message.emit(msg, "info")
                        logging.info(msg)
                    else: 
                        self.log_message.emit(f"[Worker {self.worker_id}] Proxy '{proxy_candidate_str}' không hoạt động.", "warning")
                elif not self.proxy_sources: 
                    active_proxy_dict_to_use = None 
                else: 
                    for _ in range(5): 
                        if not self.running: break
                        time.sleep(0.1)
                    if not self.running: break
                    continue 
                
                num_requests_for_current_proxy_or_no_proxy = self.requests_per_active_proxy if active_proxy_dict_to_use else 1
                requests_done_with_current_setup = 0

                while requests_done_with_current_setup < num_requests_for_current_proxy_or_no_proxy and self.running:
                    if self.links_successfully_processed_by_worker >= self.scan_limit_count_per_worker: break
                    if (datetime.now() - self.start_time_global).total_seconds() / 60 >= self.scan_limit_minutes_global:
                        self.running = False; break

                    random_suffix = self._get_random_suffix()
                    
                    for add_path in self.additional_paths:
                        if not self.running: break
                        
                        # --- MODIFIED URL CONSTRUCTION for SUFFIX ---
                        current_url = self.base_url # self.base_url is already rstrip('/')'ed
                        if random_suffix:
                            separator_for_suffix = ""
                            if self.suffix_separator_mode == "custom":
                                separator_for_suffix = self.custom_suffix_separator
                            # If mode is "none", separator_for_suffix remains ""
                            current_url = f"{current_url}{separator_for_suffix}{random_suffix}"
                        # --- END MODIFIED URL CONSTRUCTION for SUFFIX ---
                        
                        if add_path: 
                            current_url = f"{current_url}/{add_path.lstrip('/')}"
                        
                        parsed_for_normalize = urlparse(current_url)
                        if parsed_for_normalize.path and parsed_for_normalize.path != '/' and current_url.endswith('/'):
                            current_url = current_url.rstrip('/')
                        elif add_path == "/" and not current_url.endswith('/'):
                             current_url += "/"

                        if self.shared_resources.is_link_attempted(current_url):
                            if not active_proxy_dict_to_use: 
                                requests_done_with_current_setup += 1 
                                if requests_done_with_current_setup >= num_requests_for_current_proxy_or_no_proxy:
                                    break 
                            continue 

                        headers = {'User-Agent': random.choice(USER_AGENTS)}
                        log_proxy_msg_part = f" (Proxy: {active_proxy_dict_to_use['http']})" if active_proxy_dict_to_use else " (Không Proxy)"

                        try:
                            response = requests.get(current_url, headers=headers, proxies=active_proxy_dict_to_use, timeout=15, allow_redirects=True)
                            
                            self.links_successfully_processed_by_worker += 1
                            self.shared_resources.add_processed_link_to_attempted(current_url) 
                            self.shared_resources.increment_total_scanned_and_get_stats() 
                            
                            content_lower = response.text.lower()
                            link_category = "unclassified" 
                            is_good = False
                            is_bad = False

                            if self.good_link_is_everything_else:
                                if self.bad_link_keywords:
                                    for keyword in self.bad_link_keywords:
                                        if keyword in content_lower:
                                            is_bad = True
                                            break
                                if is_bad:
                                    link_category = "bad"
                                else: # Not bad (or no bad keywords) -> good
                                    link_category = "good"
                            elif self.bad_link_is_everything_else:
                                if self.good_link_keywords:
                                    for keyword in self.good_link_keywords:
                                        if keyword in content_lower:
                                            is_good = True
                                            break
                                if is_good:
                                    link_category = "good"
                                else: # Not good (or no good keywords) -> bad
                                    link_category = "bad"
                            else: # Standard classification
                                if self.good_link_keywords:
                                    for keyword in self.good_link_keywords:
                                        if keyword in content_lower:
                                            is_good = True
                                            link_category = "good"
                                            break
                                if not is_good and self.bad_link_keywords:
                                    for keyword in self.bad_link_keywords:
                                        if keyword in content_lower:
                                            is_bad = True
                                            link_category = "bad"
                                            break
                            
                            if link_category == "good":
                                self.shared_resources.increment_good_links()
                                self.shared_resources.log_good_link(current_url)
                                msg = f"[Worker {self.worker_id}] HỢP LỆ: {current_url} (Code: {response.status_code})"
                                self.log_message.emit(msg, "good_link")
                                logging.info(msg)
                            elif link_category == "bad":
                                self.shared_resources.increment_bad_links()
                                self.shared_resources.log_bad_link(current_url)
                                msg = f"[Worker {self.worker_id}] LOẠI: {current_url} (Code: {response.status_code})"
                                self.log_message.emit(msg, "bad_link")
                                logging.info(msg)
                            else: # Unclassified
                                self.shared_resources.increment_unclassified_links()
                                self.shared_resources.log_unclassified_link(current_url)
                                msg = f"[Worker {self.worker_id}] KHÔNG PHÂN LOẠI: {current_url} (Code: {response.status_code})"
                                self.log_message.emit(msg, "unclassified_link")
                                logging.info(msg)
                            
                            self.individual_stats_update.emit()

                        except requests.Timeout:
                            err_msg = f"[Worker {self.worker_id}] TIMEOUT: {current_url}{log_proxy_msg_part}. Link sẽ thử lại sau."
                            self.log_message.emit(err_msg, "error")
                            logging.warning(err_msg)
                            if active_proxy_dict_to_use: 
                                requests_done_with_current_setup = num_requests_for_current_proxy_or_no_proxy
                                break 
                        except requests.RequestException as e:
                            err_msg = f"[Worker {self.worker_id}] LỖI REQUEST: {current_url}{log_proxy_msg_part} - {type(e).__name__}. Link sẽ thử lại sau."
                            self.log_message.emit(err_msg, "error")
                            logging.warning(err_msg)
                            if active_proxy_dict_to_use:
                                requests_done_with_current_setup = num_requests_for_current_proxy_or_no_proxy
                                break 
                        except Exception as e_inner_loop:
                            err_msg = f"[Worker {self.worker_id}] LỖI KHÁC (inner loop): {current_url}{log_proxy_msg_part}: {e_inner_loop}"
                            self.log_message.emit(err_msg, "error")
                            logging.error(f"{err_msg}\n{traceback.format_exc()}")
                        finally:
                            if not self.running: break
                            time.sleep(random.uniform(0.05, 0.15))
                    
                    if not self.running: break 
                    requests_done_with_current_setup += 1

        except Exception as e_outer:
            err_msg = f"[Worker {self.worker_id}] LỖI NGHIÊM TRỌNG WORKER: {e_outer}"
            self.log_message.emit(err_msg, "error")
            logging.critical(f"{err_msg}\n{traceback.format_exc()}")
        finally:
            final_msg = f"[Worker {self.worker_id}] Đã dừng."
            self.log_message.emit(final_msg, "info")
            logging.info(final_msg)
            self.finished.emit(self)

    def stop(self):
        msg = f"[Worker {self.worker_id}] Đang yêu cầu dừng..."
        self.log_message.emit(msg, "info")
        logging.info(msg)
        self.running = False

# --- Main Application Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Website Link Scanner - V1.3.2") # Version update for separator feature
        self.initial_width = 1350 
        self.initial_height = 1000 
        self.setGeometry(100, 100, self.initial_width, self.initial_height)

        if os.path.exists(ICON_FILE_PATH):
            self.setWindowIcon(QIcon(ICON_FILE_PATH))
        else:
            logging.warning(f"Không tìm thấy file icon: {ICON_FILE_PATH}")
            print(f"WARNING: Không tìm thấy file icon: {ICON_FILE_PATH}")

        self.config = configparser.ConfigParser()
        self.scan_workers = []
        self.shared_resources = None
        self.active_workers_count = 0
        self.main_scan_start_time = None
        self.current_website_data_path = None 

        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.update_time_progress_and_check_global_limits)
        self.elapsed_time_seconds = 0

        self.init_ui() 
        self.load_config() 
        self.update_classification_mode() 
        self.update_separator_input_state() # Initialize separator input state

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_horizontal_layout = QHBoxLayout(main_widget)

        left_panel_widget = QWidget()
        left_v_layout = QVBoxLayout(left_panel_widget)

        # 1. General Settings Group
        general_input_group = QGroupBox("⚙️Cài đặt chung")
        general_form_layout = QFormLayout()
        
        self.website_entry = QLineEdit()
        self.website_entry.setPlaceholderText("Bắt buộc, ví dụ: https://abc.com")
        general_form_layout.addRow("🔗URL Trang Web (Base):", self.website_entry)
        
        self.additional_paths_entry = QLineEdit()
        self.additional_paths_entry.setPlaceholderText("Tùy chọn, cách nhau bởi dấu phẩy, ví dụ: path1,path2/sub,/")
        general_form_layout.addRow("🔗Đường dẫn phụ:", self.additional_paths_entry)

        # --- NEW: Suffix Separator Options ---
        self.suffix_separator_group = QGroupBox("↔️Phân tách URL & Suffix")
        suffix_separator_layout_h = QHBoxLayout() # Use QHBoxLayout for horizontal arrangement
        self.separator_none_rb = QRadioButton("Không phân tách")
        self.separator_custom_rb = QRadioButton("Phân tách bằng:")
        self.separator_custom_rb.setChecked(True) 
        self.custom_separator_entry = QLineEdit("/")
        self.custom_separator_entry.setFixedWidth(60) 
        self.custom_separator_entry.setToolTip("Ký tự (hoặc chuỗi) để nối giữa URL Base và Suffix.\nĐể trống nếu 'Phân tách bằng' được chọn có nghĩa là nối trực tiếp (giống 'Không phân tách').")
        
        suffix_separator_layout_h.addWidget(self.separator_none_rb)
        suffix_separator_layout_h.addWidget(self.separator_custom_rb)
        suffix_separator_layout_h.addWidget(self.custom_separator_entry)
        suffix_separator_layout_h.addStretch() 
        self.suffix_separator_group.setLayout(suffix_separator_layout_h)
        general_form_layout.addRow(self.suffix_separator_group)

        self.separator_none_rb.toggled.connect(self.update_separator_input_state)
        # --- END NEW: Suffix Separator Options ---
        
        self.suffix_len_spin = QSpinBox()
        self.suffix_len_spin.setRange(1, 30)
        self.suffix_len_spin.setValue(8)
        self.suffix_len_spin.setToolTip("Độ dài suffix cho chế độ random cổ điển (nếu không dùng Pattern hoặc Tỷ lệ).")
        general_form_layout.addRow("⚠️Số ký tự suffix (cổ điển):", self.suffix_len_spin)
        
        suffix_chars_group = QGroupBox("🔠Bộ ký tự cho Suffix (áp dụng cho '*', tỷ lệ, và random cổ điển)")
        suffix_chars_layout = QVBoxLayout()
        self.suffix_lowercase_cb = QCheckBox("🔡Chữ thường (a-z)")
        self.suffix_lowercase_cb.setChecked(True)
        suffix_chars_layout.addWidget(self.suffix_lowercase_cb)
        self.suffix_uppercase_cb = QCheckBox("🔠Chữ hoa (A-Z)")
        self.suffix_uppercase_cb.setChecked(True)
        suffix_chars_layout.addWidget(self.suffix_uppercase_cb)
        self.suffix_digits_cb = QCheckBox("Số (0-9)")
        self.suffix_digits_cb.setChecked(True)
        suffix_chars_layout.addWidget(self.suffix_digits_cb)
        special_chars_group_layout = QHBoxLayout()
        self.suffix_all_special_cb = QCheckBox("🧩Toàn bộ ký tự đặc biệt phổ biến")
        special_chars_group_layout.addWidget(self.suffix_all_special_cb)
        self.suffix_custom_special_entry = QLineEdit()
        self.suffix_custom_special_entry.setPlaceholderText("✍️Hoặc nhập tùy chỉnh (vd: -_.)")
        special_chars_group_layout.addWidget(self.suffix_custom_special_entry)
        suffix_chars_layout.addLayout(special_chars_group_layout)
        suffix_chars_group.setLayout(suffix_chars_layout)
        general_form_layout.addRow(suffix_chars_group)

        advanced_suffix_group = QGroupBox("🛠️Tùy chỉnh tạo Suffix nâng cao")
        adv_suffix_main_h_layout = QHBoxLayout()
        adv_suffix_left_v_layout = QVBoxLayout()
        mode_group = QGroupBox("Kiểu tạo Suffix")
        mode_v_layout = QVBoxLayout()
        self.suffix_mode_classic_random_rb = QRadioButton("Random cổ điển (dùng độ dài ở trên)")
        self.suffix_mode_pattern_rb = QRadioButton("Theo Pattern (Định dạng)")
        self.suffix_mode_ratio_rb = QRadioButton("Theo Tỷ lệ ký tự")
        self.suffix_mode_sequential_rb = QRadioButton("Lần lượt (Tuần tự - Chưa hỗ trợ)")
        self.suffix_mode_classic_random_rb.setChecked(True) 
        self.suffix_mode_sequential_rb.setEnabled(False)
        mode_v_layout.addWidget(self.suffix_mode_classic_random_rb)
        mode_v_layout.addWidget(self.suffix_mode_pattern_rb)
        mode_v_layout.addWidget(self.suffix_mode_ratio_rb)
        mode_v_layout.addWidget(self.suffix_mode_sequential_rb)
        mode_group.setLayout(mode_v_layout)
        adv_suffix_left_v_layout.addWidget(mode_group)
        self.suffix_pattern_entry = QLineEdit()
        self.suffix_pattern_entry.setPlaceholderText("VD: AA***BB (* là ký tự ngẫu nhiên)")
        self.suffix_pattern_entry.setToolTip("Nếu nhập, Suffix sẽ được tạo theo định dạng này.\nCác cài đặt tỷ lệ và độ dài cổ điển sẽ bị bỏ qua.")
        adv_suffix_left_v_layout.addWidget(QLabel("Định dạng Suffix (Pattern):"))
        adv_suffix_left_v_layout.addWidget(self.suffix_pattern_entry)
        adv_suffix_left_v_layout.addStretch()
        adv_suffix_main_h_layout.addLayout(adv_suffix_left_v_layout)
        ratios_group = QGroupBox("Tỷ lệ ký tự (nếu chọn kiểu 'Theo Tỷ lệ')")
        ratios_form_layout = QFormLayout()
        self.suffix_ratio_lowercase_spin = QSpinBox(); self.suffix_ratio_lowercase_spin.setRange(0, 30)
        ratios_form_layout.addRow("🔡Chữ thường:", self.suffix_ratio_lowercase_spin)
        self.suffix_ratio_uppercase_spin = QSpinBox(); self.suffix_ratio_uppercase_spin.setRange(0, 30)
        ratios_form_layout.addRow("🔠Chữ hoa:", self.suffix_ratio_uppercase_spin)
        self.suffix_ratio_digits_spin = QSpinBox(); self.suffix_ratio_digits_spin.setRange(0, 30)
        ratios_form_layout.addRow("0-9 Số:", self.suffix_ratio_digits_spin)
        self.suffix_ratio_special_spin = QSpinBox(); self.suffix_ratio_special_spin.setRange(0, 30)
        ratios_form_layout.addRow("🧩Ký tự đặc biệt:", self.suffix_ratio_special_spin)
        self.total_ratio_label = QLabel("Tổng độ dài từ tỷ lệ: 0")
        ratios_form_layout.addRow(self.total_ratio_label)
        self.suffix_ratio_lowercase_spin.valueChanged.connect(self.update_total_ratio_label)
        self.suffix_ratio_uppercase_spin.valueChanged.connect(self.update_total_ratio_label)
        self.suffix_ratio_digits_spin.valueChanged.connect(self.update_total_ratio_label)
        self.suffix_ratio_special_spin.valueChanged.connect(self.update_total_ratio_label)
        ratios_group.setLayout(ratios_form_layout)
        adv_suffix_main_h_layout.addWidget(ratios_group)
        advanced_suffix_group.setLayout(adv_suffix_main_h_layout)
        general_form_layout.addRow(advanced_suffix_group)
        general_input_group.setLayout(general_form_layout)
        left_v_layout.addWidget(general_input_group)

        # 2. Advanced Scan Settings Group (Threads, Proxy)
        scan_config_group = QGroupBox("🛠️Cài đặt quét nâng cao")
        scan_config_v_layout = QVBoxLayout() 
        scan_config_form_part_layout = QFormLayout()
        self.num_threads_spin = QSpinBox()
        cpu_cores = os.cpu_count()
        default_threads = max(1, cpu_cores if cpu_cores else 2)
        max_threads = max(1, cpu_cores * 2 if cpu_cores else 16) 
        self.num_threads_spin.setRange(1, max_threads)
        self.num_threads_spin.setValue(default_threads)
        scan_config_form_part_layout.addRow("💻Số luồng quét:", self.num_threads_spin)
        self.requests_per_active_proxy_spin = QSpinBox()
        self.requests_per_active_proxy_spin.setRange(1, 1000)
        self.requests_per_active_proxy_spin.setValue(10)
        scan_config_form_part_layout.addRow("🔗Số link / 1 proxy:", self.requests_per_active_proxy_spin)
        scan_config_v_layout.addLayout(scan_config_form_part_layout)
        
        proxy_title_button_layout = QHBoxLayout()
        proxy_sources_label = QLabel("🔗Nguồn Proxy (URLs hoặc IP:PORT) -  Mỗi mục 1 dòng:")
        proxy_title_button_layout.addWidget(proxy_sources_label)
        proxy_title_button_layout.addStretch(1) 
        self.load_proxy_file_button = QPushButton("📂 Tải File")
        self.load_proxy_file_button.setToolTip("Tải danh sách proxy/nguồn proxy từ file (.txt, .list)")
        self.load_proxy_file_button.clicked.connect(self.load_proxy_file_dialog)
        proxy_title_button_layout.addWidget(self.load_proxy_file_button)
        scan_config_v_layout.addLayout(proxy_title_button_layout)
        
        self.proxy_sources_text = QTextEdit()
        self.proxy_sources_text.setPlaceholderText("Mỗi URL nguồn proxy hoặc proxy IP:PORT trên một dòng. Để trống nếu muốn chạy không proxy.")
        self.proxy_sources_text.setMinimumHeight(100) 
        scan_config_v_layout.addWidget(self.proxy_sources_text)

        scan_config_group.setLayout(scan_config_v_layout)
        left_v_layout.addWidget(scan_config_group, 1) 
        left_panel_widget.setLayout(left_v_layout)
        main_horizontal_layout.addWidget(left_panel_widget, 1)

        # --- Right Panel: Display, Limits, Controls, Stats, Log ---
        right_panel_widget = QWidget()
        right_v_layout = QVBoxLayout(right_panel_widget)

        # 1. Display Settings
        display_settings_group = QGroupBox("🖼️Cài đặt hiển thị")
        display_settings_form = QFormLayout()
        size_layout = QHBoxLayout()
        self.window_width_spin = QSpinBox(); self.window_width_spin.setRange(800, 5000); self.window_width_spin.setValue(self.initial_width)
        size_layout.addWidget(QLabel("Rộng:")); size_layout.addWidget(self.window_width_spin)
        self.window_height_spin = QSpinBox(); self.window_height_spin.setRange(600, 5000); self.window_height_spin.setValue(self.initial_height)
        size_layout.addWidget(QLabel("Cao:")); size_layout.addWidget(self.window_height_spin)
        self.apply_window_size_button = QPushButton("Áp dụng Kích thước"); self.apply_window_size_button.clicked.connect(self.apply_window_size_settings)
        size_layout.addWidget(self.apply_window_size_button)
        display_settings_form.addRow("Kích thước cửa sổ:", size_layout)
        font_layout = QHBoxLayout()
        self.font_combo_box = QFontComboBox() 
        font_layout.addWidget(QLabel("Font:"))
        font_layout.addWidget(self.font_combo_box)
        self.font_size_spin = QSpinBox(); self.font_size_spin.setRange(6, 30); self.font_size_spin.setValue(QApplication.font().pointSize())
        font_layout.addWidget(QLabel("Cỡ chữ (pt):"))
        font_layout.addWidget(self.font_size_spin)
        self.apply_font_button = QPushButton("Áp dụng Font") 
        self.apply_font_button.clicked.connect(self.apply_font_settings) 
        font_layout.addWidget(self.apply_font_button)
        display_settings_form.addRow("Font chữ:", font_layout)
        display_settings_group.setLayout(display_settings_form)
        right_v_layout.addWidget(display_settings_group)

        # --- NEW: Classification Group on Right Panel ---
        classification_group = QGroupBox("🔍Tùy chỉnh phân loại Link")
        classification_layout = QFormLayout()
        self.good_link_keywords_text = QTextEdit()
        self.good_link_keywords_text.setPlaceholderText("Mỗi từ khóa Good Link một dòng.")
        self.good_link_keywords_text.setFixedHeight(60)
        classification_layout.addRow("Từ khóa Good Link:", self.good_link_keywords_text)
        
        self.bad_link_keywords_text = QTextEdit()
        self.bad_link_keywords_text.setPlaceholderText("Mỗi từ khóa Bad Link một dòng.")
        self.bad_link_keywords_text.setFixedHeight(60)
        classification_layout.addRow("Từ khóa Bad Link:", self.bad_link_keywords_text)
        
        self.good_link_is_everything_else_cb = QCheckBox("✅Good Link là tất cả link KHÔNG phải Bad Link") 
        self.good_link_is_everything_else_cb.setToolTip(
            "Nếu chọn: chỉ cần nhập Từ khóa Bad Link.\nLink không khớp Bad Link sẽ là Good Link.\nÔ 'Từ khóa Good Link' ở trên sẽ bị bỏ qua."
        )
        classification_layout.addRow("", self.good_link_is_everything_else_cb)

        self.bad_link_is_everything_else_cb = QCheckBox("⛔Bad Link là tất cả link KHÔNG phải Good Link")
        self.bad_link_is_everything_else_cb.setToolTip(
            "Nếu chọn: chỉ cần nhập Từ khóa Good Link.\nLink không khớp Good Link sẽ là Bad Link.\nÔ 'Từ khóa Bad Link' ở trên sẽ bị bỏ qua."
        )
        classification_layout.addRow("", self.bad_link_is_everything_else_cb)
        classification_group.setLayout(classification_layout)
        right_v_layout.addWidget(classification_group) 

        self.good_link_is_everything_else_cb.toggled.connect(self.update_classification_mode)
        self.bad_link_is_everything_else_cb.toggled.connect(self.update_classification_mode)
        # --- END NEW Classification Group ---

        # 2. Scan Limits (Now after classification group on right panel)
        self.limit_group = QGroupBox("🪟Giới hạn quét (Tổng cộng)")
        limit_layout = QHBoxLayout()
        self.limit_type_count_radio = QRadioButton("🔗Số lượng link:")
        self.limit_type_count_radio.setChecked(True)
        self.scan_limit_count_spin = QSpinBox(); self.scan_limit_count_spin.setRange(0, 10000000); self.scan_limit_count_spin.setValue(1000)
        limit_layout.addWidget(self.limit_type_count_radio); limit_layout.addWidget(self.scan_limit_count_spin)
        self.limit_type_time_radio = QRadioButton("🕒Thời gian (phút):")
        self.scan_limit_time_spin = QSpinBox(); self.scan_limit_time_spin.setRange(0, 1440 * 7); self.scan_limit_time_spin.setValue(0)
        limit_layout.addWidget(self.limit_type_time_radio); limit_layout.addWidget(self.scan_limit_time_spin)
        self.limit_type_count_radio.toggled.connect(self.toggle_limit_inputs)
        self.limit_group.setLayout(limit_layout)
        right_v_layout.addWidget(self.limit_group)
        self.toggle_limit_inputs() 

        # 3. Scan Controls
        control_layout = QHBoxLayout()
        self.start_button = QPushButton("⏯Bắt đầu Scan"); self.start_button.clicked.connect(self.start_scan)
        control_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("⏹Dừng Scan"); self.stop_button.clicked.connect(self.stop_scan); self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        right_v_layout.addLayout(control_layout)

        # 4. Progress Bar
        self.progress_bar = QProgressBar()
        right_v_layout.addWidget(self.progress_bar)

        # 5. Stats
        stats_group = QGroupBox("📊Trạng thái")
        self.stats_layout_form = QFormLayout() 
        self.total_scanned_label = QLabel("0")
        self.stats_layout_form.addRow("🔗Tổng link đã quét (có response):", self.total_scanned_label)
        self.good_links_label = QLabel("0")
        self.stats_layout_form.addRow("❇️Link hợp lệ (Good):", self.good_links_label)
        self.bad_links_label = QLabel("0")
        self.stats_layout_form.addRow("⛔Link bị loại (Bad):", self.bad_links_label)
        self.unclassified_links_label = QLabel("0")
        self.stats_layout_form.addRow("❓Link không phân loại:", self.unclassified_links_label)
        self.time_elapsed_label = QLabel("00:00:00")
        self.stats_layout_form.addRow("🕒Thời gian chạy:", self.time_elapsed_label)
        stats_group.setLayout(self.stats_layout_form)
        right_v_layout.addWidget(stats_group)

        # 6. Log output
        self.log_output_text = QTextEdit()
        self.log_output_text.setReadOnly(True)
        self.log_output_text.setMinimumHeight(150) 
        right_v_layout.addWidget(self.log_output_text, 1)
        
        right_panel_widget.setLayout(right_v_layout)
        main_horizontal_layout.addWidget(right_panel_widget, 1) 
        main_widget.setLayout(main_horizontal_layout)

    def update_total_ratio_label(self): 
        total = (self.suffix_ratio_lowercase_spin.value() +
                 self.suffix_ratio_uppercase_spin.value() +
                 self.suffix_ratio_digits_spin.value() +
                 self.suffix_ratio_special_spin.value())
        self.total_ratio_label.setText(f"Tổng độ dài từ tỷ lệ: {total}")

    def update_separator_input_state(self): # NEW method for separator UI
        self.custom_separator_entry.setEnabled(self.separator_custom_rb.isChecked())

    def update_classification_mode(self): 
        good_is_else = self.good_link_is_everything_else_cb.isChecked()
        bad_is_else = self.bad_link_is_everything_else_cb.isChecked()
        
        sender = self.sender()

        if sender == self.good_link_is_everything_else_cb and good_is_else:
            if bad_is_else:
                self.bad_link_is_everything_else_cb.blockSignals(True)
                self.bad_link_is_everything_else_cb.setChecked(False)
                self.bad_link_is_everything_else_cb.blockSignals(False)
        elif sender == self.bad_link_is_everything_else_cb and bad_is_else:
            if good_is_else:
                self.good_link_is_everything_else_cb.blockSignals(True)
                self.good_link_is_everything_else_cb.setChecked(False)
                self.good_link_is_everything_else_cb.blockSignals(False)
        
        current_good_is_else = self.good_link_is_everything_else_cb.isChecked()
        current_bad_is_else = self.bad_link_is_everything_else_cb.isChecked()

        if current_good_is_else:
            self.good_link_keywords_text.setEnabled(False)
            self.bad_link_keywords_text.setEnabled(True)
        elif current_bad_is_else:
            self.bad_link_keywords_text.setEnabled(False)
            self.good_link_keywords_text.setEnabled(True)
        else: 
            self.good_link_keywords_text.setEnabled(True)
            self.bad_link_keywords_text.setEnabled(True)

    def apply_window_size_settings(self):
        width = self.window_width_spin.value()
        height = self.window_height_spin.value()
        self.resize(width, height)
        self.log_message(f"Đã áp dụng kích thước cửa sổ: {width}x{height}", "info")
        logging.info(f"Đã áp dụng kích thước cửa sổ: {width}x{height}")

    def apply_font_settings(self, font_to_set=None, size_pt_to_set=None): 
        current_font = QFont() 
        if font_to_set is None: 
            current_font = self.font_combo_box.currentFont()
        else: 
            current_font = QFont(font_to_set) 
            self.font_combo_box.setCurrentFont(current_font)
        if size_pt_to_set is None: 
            size_pt = self.font_size_spin.value()
        else: 
            size_pt = size_pt_to_set
            self.font_size_spin.setValue(size_pt)
        current_font.setPointSize(size_pt)
        QApplication.setFont(current_font)
        widgets_to_update = self.findChildren(QWidget)
        for widget in widgets_to_update:
            try:
                widget.setFont(current_font)
                widget.update() 
            except AttributeError:
                pass 
        font_family_qss = f'"{current_font.family()}"' if ' ' in current_font.family() else current_font.family()
        stylesheet = f"""
        * {{ 
            font-family: {font_family_qss}; 
            font-size: {size_pt}pt; 
        }}
        QTextEdit, QLineEdit {{
            font-family: {font_family_qss}; 
            font-size: {size_pt}pt; 
        }}
        """
        QApplication.instance().setStyleSheet(stylesheet)
        self.log_message(f"Đã áp dụng font: {current_font.family()} {size_pt}pt", "info")
        logging.info(f"Đã áp dụng font: {current_font.family()} {size_pt}pt")

    def toggle_limit_inputs(self):
        is_count_limit = self.limit_type_count_radio.isChecked()
        self.scan_limit_count_spin.setEnabled(is_count_limit)
        self.scan_limit_time_spin.setEnabled(not is_count_limit)
        if is_count_limit:
            if self.scan_limit_time_spin.value() != 0: self.scan_limit_time_spin.setValue(0) 
        else:
            if self.scan_limit_count_spin.value() != 0: self.scan_limit_count_spin.setValue(0)

    def log_message(self, message, msg_type="default"): 
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "black" 
        if msg_type == "info": color = "blue"
        elif msg_type == "error": color = "red"
        elif msg_type == "good_link": color = "purple"
        elif msg_type == "bad_link": color = "#333333" 
        elif msg_type == "unclassified_link": color = "darkorange" 
        elif msg_type == "warning": color = "orangered" 
        formatted_message = f'<span style="color:{color};">[{timestamp}] {message}</span>'
        self.log_output_text.append(formatted_message)

    def update_main_stats_ui(self):
        if self.shared_resources:
            total, good, bad, unclassified = self.shared_resources.get_current_stats()
            self.total_scanned_label.setText(str(total))
            self.good_links_label.setText(str(good))
            self.bad_links_label.setText(str(bad))
            self.unclassified_links_label.setText(str(unclassified))
            if self.limit_type_count_radio.isChecked() and self.scan_limit_count_spin.value() > 0:
                limit_val = self.scan_limit_count_spin.value()
                progress = int((total / limit_val) * 100) if limit_val > 0 else 0
                self.progress_bar.setValue(min(progress, 100))
                
    def update_time_progress_and_check_global_limits(self):
        if not self.main_scan_start_time or self.active_workers_count == 0:
            self.scan_timer.stop() 
            return
        self.elapsed_time_seconds = (datetime.now() - self.main_scan_start_time).total_seconds()
        elapsed_td = timedelta(seconds=int(self.elapsed_time_seconds))
        self.time_elapsed_label.setText(str(elapsed_td).split('.')[0]) 
        global_time_limit_minutes = self.scan_limit_time_spin.value()
        if self.limit_type_time_radio.isChecked() and global_time_limit_minutes > 0:
            total_time_seconds = global_time_limit_minutes * 60
            progress_val = int((self.elapsed_time_seconds / total_time_seconds) * 100) if total_time_seconds > 0 else 0
            self.progress_bar.setValue(min(progress_val, 100))
            if self.elapsed_time_seconds >= total_time_seconds:
                msg = "Đã đạt giới hạn thời gian quét tổng. Dừng tất cả các luồng..."
                logging.info(msg)
                self.log_message(msg, "info")
                self.stop_scan_internal() 
        global_count_limit = self.scan_limit_count_spin.value()
        if self.limit_type_count_radio.isChecked() and global_count_limit > 0:
            if self.shared_resources and self.shared_resources.total_scanned_count >= global_count_limit:
                msg = "Đã đạt giới hạn số lượng link quét tổng. Dừng tất cả các luồng..."
                logging.info(msg)
                self.log_message(msg, "info")
                self.stop_scan_internal()

    def load_proxy_file_dialog(self): 
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Tải File Proxy/Nguồn Proxy", "",
                                                  "Text Files (*.txt);;List Files (*.list);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, 'r', encoding='utf-8') as f:
                    content = f.read()
                lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith('#')]
                if not lines:
                    self.log_message(f"File '{os.path.basename(fileName)}' rỗng hoặc chỉ chứa comment.", "warning")
                    return
                current_proxies_in_textarea = [p.strip() for p in self.proxy_sources_text.toPlainText().splitlines() if p.strip()]
                newly_added_count = 0
                for line_from_file in lines:
                    if line_from_file not in current_proxies_in_textarea:
                        current_proxies_in_textarea.append(line_from_file)
                        newly_added_count += 1
                self.proxy_sources_text.setText("\n".join(current_proxies_in_textarea))
                if newly_added_count > 0:
                    msg = f"Đã tải và thêm {newly_added_count} mục từ file '{os.path.basename(fileName)}' vào danh sách nguồn proxy."
                    self.log_message(msg, "info")
                    logging.info(msg)
                else:
                    msg = f"Tất cả các mục từ file '{os.path.basename(fileName)}' đã có trong danh sách hoặc file rỗng."
                    self.log_message(msg, "warning")
                    logging.info(msg)
            except Exception as e:
                err_msg = f"Lỗi khi tải file proxy '{os.path.basename(fileName)}': {e}"
                self.log_message(err_msg, "error")
                logging.error(f"{err_msg}\n{traceback.format_exc()}")
                QMessageBox.critical(self, "Lỗi Tải File", err_msg)

    def start_scan(self):
        try:
            base_url = self.website_entry.text().strip()
            if not base_url:
                QMessageBox.warning(self, "Lỗi", "Vui lòng nhập URL Trang Web (Base).")
                return
            parsed_url = urlparse(base_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                QMessageBox.warning(self, "Lỗi", "URL Trang Web (Base) không hợp lệ.")
                return
            
            website_name = parsed_url.netloc 
            self.current_website_data_path = os.path.join(DATA_ROOT_DIR, website_name.replace(":", "_")) 

            if not os.path.exists(DATA_ROOT_DIR):
                try:
                    os.makedirs(DATA_ROOT_DIR)
                    logging.info(f"Đã tạo thư mục gốc '{DATA_ROOT_DIR}'.")
                except OSError as e:
                    QMessageBox.critical(self, "Lỗi", f"Không thể tạo thư mục gốc '{DATA_ROOT_DIR}': {e}")
                    logging.error(f"Không thể tạo thư mục gốc '{DATA_ROOT_DIR}': {e}")
                    return
            
            if not os.path.exists(self.current_website_data_path):
                self.log_message(f"Sẽ tạo thư mục dữ liệu mới cho {website_name} tại: {self.current_website_data_path}", "info")
                logging.info(f"Sẽ tạo thư mục dữ liệu mới cho {website_name} tại: {self.current_website_data_path}")
            else:
                self.log_message(f"Tìm thấy thư mục dữ liệu cho {website_name}. Sẽ tiếp tục/tải lại dữ liệu đã thử.", "info")
                logging.info(f"Tìm thấy thư mục dữ liệu cho {website_name}. Sẽ tiếp tục/tải lại dữ liệu đã thử.")

            additional_paths_str = self.additional_paths_entry.text().strip()
            additional_paths = [p.strip() for p in additional_paths_str.split(',') if p.strip()]
            if not additional_paths_str: 
                additional_paths = [""] 
            
            # --- Get Suffix Separator Settings ---
            suffix_separator_mode = "custom" # Default if custom is checked
            if self.separator_none_rb.isChecked():
                suffix_separator_mode = "none"
            custom_suffix_separator = self.custom_separator_entry.text()
            # Note: if mode is "custom" and custom_suffix_separator is empty, it means direct concatenation for suffix.
            # ---

            suffix_char_options = {
                'lowercase': self.suffix_lowercase_cb.isChecked(),
                'uppercase': self.suffix_uppercase_cb.isChecked(),
                'digits': self.suffix_digits_cb.isChecked(),
                'all_special': self.suffix_all_special_cb.isChecked(),
                'custom_special_chars': self.suffix_custom_special_entry.text().strip()
            }
            if not any(suffix_char_options.values()): 
                 if not suffix_char_options['custom_special_chars']: 
                    QMessageBox.warning(self, "Cảnh báo", "Không có loại ký tự nào cho Suffix được chọn. Worker sẽ dùng mặc định (chữ thường + số).")
                    suffix_char_options['lowercase'] = True
                    suffix_char_options['digits'] = True

            suffix_length_classic = self.suffix_len_spin.value()
            suffix_pattern = ""
            suffix_ratios = {} 
            actual_suffix_generation_mode_for_worker = "classic_random" 

            if self.suffix_mode_pattern_rb.isChecked():
                suffix_pattern = self.suffix_pattern_entry.text().strip()
                if not suffix_pattern:
                    QMessageBox.warning(self, "Lỗi Cài Đặt Suffix", "Đã chọn chế độ 'Theo Pattern' nhưng không nhập Pattern. Sử dụng Random cổ điển.")
                    self.suffix_mode_classic_random_rb.setChecked(True) 
                else:
                    actual_suffix_generation_mode_for_worker = "pattern"
            elif self.suffix_mode_ratio_rb.isChecked():
                suffix_ratios = {
                    'lowercase': self.suffix_ratio_lowercase_spin.value(),
                    'uppercase': self.suffix_ratio_uppercase_spin.value(),
                    'digits': self.suffix_ratio_digits_spin.value(),
                    'special': self.suffix_ratio_special_spin.value()
                }
                if sum(suffix_ratios.values()) == 0:
                    QMessageBox.warning(self, "Lỗi Cài Đặt Suffix", "Đã chọn chế độ 'Theo Tỷ lệ' nhưng tổng tỷ lệ là 0. Sử dụng Random cổ điển.")
                    suffix_ratios = {} 
                    self.suffix_mode_classic_random_rb.setChecked(True)
                else:
                     actual_suffix_generation_mode_for_worker = "ratio"

            good_link_keywords_raw = self.good_link_keywords_text.toPlainText().strip().splitlines()
            good_link_keywords = [kw.strip() for kw in good_link_keywords_raw if kw.strip()]
            bad_link_keywords_raw = self.bad_link_keywords_text.toPlainText().strip().splitlines()
            bad_link_keywords = [kw.strip() for kw in bad_link_keywords_raw if kw.strip()]
            
            good_link_is_everything_else = self.good_link_is_everything_else_cb.isChecked() 
            bad_link_is_everything_else = self.bad_link_is_everything_else_cb.isChecked()
            
            num_threads = self.num_threads_spin.value()
            requests_per_proxy = self.requests_per_active_proxy_spin.value()
            proxy_sources_raw = self.proxy_sources_text.toPlainText().strip().splitlines()
            proxy_sources = [line for line in proxy_sources_raw if line.strip()] 
            
            global_limit_count = 0
            global_limit_minutes = 0
            is_count_limit_selected = self.limit_type_count_radio.isChecked()
            
            if is_count_limit_selected:
                global_limit_count = self.scan_limit_count_spin.value()
                if global_limit_count == 0:
                     QMessageBox.warning(self, "Cảnh báo", "Giới hạn tổng số link quét phải > 0 nếu được chọn.")
                     return
            else: 
                global_limit_minutes = self.scan_limit_time_spin.value()
                if global_limit_minutes == 0:
                     QMessageBox.warning(self, "Cảnh báo", "Giới hạn tổng thời gian quét phải > 0 nếu được chọn.")
                     return
            
            self.save_config() 

            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.progress_bar.setValue(0)
            self.total_scanned_label.setText("0")
            self.good_links_label.setText("0")
            self.bad_links_label.setText("0")
            self.unclassified_links_label.setText("0")
            self.elapsed_time_seconds = 0
            self.time_elapsed_label.setText("00:00:00")

            log_start_msg = f"Bắt đầu scan: {base_url}."
            if suffix_separator_mode == "none":
                log_start_msg += " Nối suffix trực tiếp."
            else: # custom
                log_start_msg += f" Phân tách URL-Suffix bằng: '{custom_suffix_separator}'."

            if actual_suffix_generation_mode_for_worker == "pattern":
                log_start_msg += f" Dùng Pattern Suffix: '{suffix_pattern}'."
            elif actual_suffix_generation_mode_for_worker == "ratio":
                 log_start_msg += f" Dùng Tỷ lệ Suffix: {suffix_ratios} (Tổng: {sum(suffix_ratios.values())})."
            else: 
                 log_start_msg += f" Dùng Random Suffix cổ điển, độ dài: {suffix_length_classic} ký tự."
            self.log_message(log_start_msg, "info")
            logging.info(log_start_msg)

            if additional_paths != [""]:
                 self.log_message(f"Đường dẫn phụ: {', '.join(additional_paths)}", "info")
                 logging.info(f"Đường dẫn phụ: {', '.join(additional_paths)}")

            if good_link_is_everything_else:
                self.log_message("Chế độ: Good Link là tất cả những gì KHÔNG khớp Từ khóa Bad Link.", "info")
                if bad_link_keywords:
                    self.log_message(f"Từ khóa Bad Link (để xác định cái gì KHÔNG phải Good): {', '.join(bad_link_keywords)}", "info")
                else:
                    self.log_message("CẢNH BÁO: Chế độ 'Good là phần còn lại' đang hoạt động mà KHÔNG có Từ khóa Bad Link. TẤT CẢ link sẽ là Good.", "warning")
            elif bad_link_is_everything_else:
                self.log_message("Chế độ: Bad Link là tất cả những gì KHÔNG khớp Từ khóa Good Link.", "info")
                if good_link_keywords:
                    self.log_message(f"Từ khóa Good Link (để xác định cái gì KHÔNG phải Bad): {', '.join(good_link_keywords)}", "info")
                else:
                    self.log_message("CẢNH BÁO: Chế độ 'Bad là phần còn lại' đang hoạt động mà KHÔNG có Từ khóa Good Link. TẤT CẢ link sẽ là Bad.", "warning")
            else: 
                self.log_message("Chế độ: Phân loại dựa trên Từ khóa Good và Từ khóa Bad (nếu có).", "info")
                if good_link_keywords:
                    self.log_message(f"Từ khóa Good Link: {', '.join(good_link_keywords)}", "info")
                if bad_link_keywords:
                    self.log_message(f"Từ khóa Bad Link: {', '.join(bad_link_keywords)}", "info")
                if not good_link_keywords and not bad_link_keywords:
                    self.log_message("CẢNH BÁO: Không có Từ khóa Good Link hay Bad Link nào được cung cấp. Tất cả link sẽ là Unclassified.", "warning")


            self.shared_resources = SharedScanResources(self.current_website_data_path)
            self.shared_resources.reset_stats() 

            self.scan_workers.clear()
            self.active_workers_count = num_threads
            self.main_scan_start_time = datetime.now()

            limit_per_worker = float('inf')
            if is_count_limit_selected and global_limit_count > 0:
                limit_per_worker = (global_limit_count + num_threads -1) // num_threads 
                self.log_message(f"Mỗi luồng sẽ cố gắng xử lý ~{limit_per_worker} link (giới hạn tổng sẽ được áp dụng).", "info")
                logging.info(f"Mỗi luồng sẽ cố gắng xử lý ~{limit_per_worker} link (giới hạn tổng sẽ được áp dụng).")

            for i in range(num_threads):
                worker = ScanWorker(
                    worker_id=i + 1,
                    base_url=base_url,
                    additional_paths=list(additional_paths),
                    suffix_char_options=dict(suffix_char_options),
                    suffix_length=suffix_length_classic,
                    suffix_pattern=suffix_pattern if actual_suffix_generation_mode_for_worker == "pattern" else "",
                    suffix_ratios=dict(suffix_ratios) if actual_suffix_generation_mode_for_worker == "ratio" else {},
                    suffix_generation_mode=actual_suffix_generation_mode_for_worker,
                    proxy_sources=list(proxy_sources),
                    scan_limit_count_per_worker=limit_per_worker if is_count_limit_selected else float('inf'),
                    scan_limit_minutes=global_limit_minutes if not is_count_limit_selected else float('inf'),
                    requests_per_active_proxy=requests_per_proxy,
                    shared_resources=self.shared_resources,
                    good_link_keywords=list(good_link_keywords),
                    bad_link_keywords=list(bad_link_keywords),
                    bad_link_is_everything_else=bad_link_is_everything_else,
                    good_link_is_everything_else=good_link_is_everything_else,
                    suffix_separator_mode=suffix_separator_mode,            
                    custom_suffix_separator=custom_suffix_separator         
                )
                worker.setObjectName(f"ScanWorker-{i+1}") 
                worker.start_time_global = self.main_scan_start_time
                worker.log_message.connect(self.log_message) 
                worker.individual_stats_update.connect(self.update_main_stats_ui)
                worker.finished.connect(self.on_worker_finished)
                self.scan_workers.append(worker)
                logging.debug(f"Khởi tạo worker {i+1}")
                worker.start()
                logging.debug(f"Worker {i+1} đã start.")
            self.scan_timer.start(1000) 
        except Exception as e_start:
            err_msg = f"Lỗi nghiêm trọng khi bắt đầu scan: {e_start}"
            self.log_message(err_msg, "error")
            logging.critical(f"{err_msg}\n{traceback.format_exc()}")
            self.start_button.setEnabled(True) 
            self.stop_button.setEnabled(False)

    def stop_scan(self):
        logging.info("Yêu cầu dừng thủ công từ người dùng...")
        self.log_message("Yêu cầu dừng thủ công từ người dùng...", "info")
        self.stop_scan_internal()

    def stop_scan_internal(self):
        if not self.scan_workers and self.active_workers_count == 0 : 
            if not self.start_button.isEnabled():
                 self.start_button.setEnabled(True)
                 self.stop_button.setEnabled(False)
            logging.debug("stop_scan_internal: Không có worker nào để dừng hoặc đã dừng.")
            return
        logging.info(f"Đang yêu cầu dừng {self.active_workers_count} luồng đang chạy...")
        self.log_message(f"Đang yêu cầu dừng {self.active_workers_count} luồng đang chạy...", "info")
        for worker in self.scan_workers:
            if worker.isRunning():
                logging.debug(f"Yêu cầu dừng worker {worker.worker_id}")
                worker.stop()
                
    def on_worker_finished(self, finished_worker_object):
        if self.active_workers_count > 0: 
            self.active_workers_count -= 1
        logging.info(f"Worker {finished_worker_object.worker_id} đã hoàn thành. Còn lại {self.active_workers_count} luồng.")
        self.update_main_stats_ui() 
        if self.active_workers_count == 0:
            self.log_message("Tất cả các luồng quét đã hoàn thành hoặc bị dừng.", "info")
            logging.info("Tất cả các luồng quét đã hoàn thành hoặc bị dừng.")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.scan_timer.stop()
            logging.debug("Chờ các worker kết thúc hẳn...")
            all_stopped_gracefully = True
            for worker_obj in self.scan_workers: 
                if worker_obj.isRunning(): 
                    if not worker_obj.wait(3000): 
                        logging.warning(f"Worker {worker_obj.worker_id} không dừng hẳn sau 3 giây.")
                        all_stopped_gracefully = False
            if all_stopped_gracefully: logging.info("Tất cả worker đã dừng hẳn.")
            self.scan_workers.clear() 
            if self.limit_type_time_radio.isChecked() and self.scan_limit_time_spin.value() > 0:
                if self.elapsed_time_seconds >= self.scan_limit_time_spin.value() * 60:
                     self.progress_bar.setValue(100) 
            elif self.limit_type_count_radio.isChecked() and self.scan_limit_count_spin.value() > 0:
                 current_total_scanned = 0
                 try: current_total_scanned = int(self.total_scanned_label.text())
                 except ValueError: pass
                 if current_total_scanned >= self.scan_limit_count_spin.value():
                     self.progress_bar.setValue(100)
            self.log_message("--- QUÁ TRÌNH SCAN KẾT THÚC ---", "info")
            logging.info("--- QUÁ TRÌNH SCAN KẾT THÚC ---")

    def load_config(self):
        default_req_per_proxy = 10
        cpu_cores = os.cpu_count()
        default_num_threads = max(1, cpu_cores if cpu_cores else 2)
        default_q_font = QApplication.font()
        default_font_family = default_q_font.family()
        default_font_size = default_q_font.pointSize()
        default_separator_mode = "custom" # Default to custom with "/"
        default_custom_separator = "/"

        self.window_width_spin.setValue(self.width())
        self.window_height_spin.setValue(self.height())
        self.font_combo_box.setCurrentFont(default_q_font) 
        self.font_size_spin.setValue(default_font_size)

        if not os.path.exists(CONFIG_FILE_PATH):
            self.log_message(f"File {CONFIG_FILE_PATH} không tìm thấy. Sử dụng giá trị mặc định.", "warning")
            logging.info(f"File {CONFIG_FILE_PATH} không tìm thấy. Sử dụng giá trị mặc định.")
            self.website_entry.setText("")
            self.additional_paths_entry.setText("")
            self.separator_custom_rb.setChecked(True) # Default separator
            self.custom_separator_entry.setText(default_custom_separator)
            self.suffix_len_spin.setValue(8)
            self.suffix_lowercase_cb.setChecked(True)
            self.suffix_uppercase_cb.setChecked(True)
            self.suffix_digits_cb.setChecked(True)
            self.suffix_all_special_cb.setChecked(False)
            self.suffix_custom_special_entry.setText("")
            self.suffix_mode_classic_random_rb.setChecked(True)
            self.suffix_pattern_entry.setText("")
            self.suffix_ratio_lowercase_spin.setValue(0)
            self.suffix_ratio_uppercase_spin.setValue(0)
            self.suffix_ratio_digits_spin.setValue(0)
            self.suffix_ratio_special_spin.setValue(0)
            self.update_total_ratio_label()
            self.good_link_keywords_text.setText("")
            self.bad_link_keywords_text.setText("")
            self.bad_link_is_everything_else_cb.setChecked(False)
            self.good_link_is_everything_else_cb.setChecked(False) 
            default_proxy_sources = [
                "https://raw.githubusercontent.com/theriturajps/proxy-list/refs/heads/main/proxies.txt",
                "https://raw.githubusercontent.com/hookzof/socks5_list/refs/heads/master/proxy.txt",
                "https://raw.githubusercontent.com/ALIILAPRO/Proxy/refs/heads/main/http.txt",
                "https://raw.githubusercontent.com/databay-labs/free-proxy-list/refs/heads/master/http.txt",
                "https://raw.githubusercontent.com/databay-labs/free-proxy-list/refs/heads/master/socks5.txt",
                "https://raw.githubusercontent.com/r00tee/Proxy-List/refs/heads/main/Socks4.txt",
                "https://raw.githubusercontent.com/r00tee/Proxy-List/refs/heads/main/Socks5.txt"
            ]
            self.proxy_sources_text.setText("\n".join(default_proxy_sources))
            self.limit_type_count_radio.setChecked(True)
            self.scan_limit_count_spin.setValue(1000)
            self.scan_limit_time_spin.setValue(0)
            self.requests_per_active_proxy_spin.setValue(default_req_per_proxy)
            self.num_threads_spin.setValue(default_num_threads)
            self.apply_font_settings(font_to_set=default_font_family, size_pt_to_set=default_font_size)
        else: 
            self.config.read(CONFIG_FILE_PATH, encoding='utf-8')
            if 'Settings' in self.config:
                settings = self.config['Settings']
                self.website_entry.setText(settings.get('website', ''))
                self.additional_paths_entry.setText(settings.get('additional_paths', ''))
                
                separator_mode_loaded = settings.get('suffix_separator_mode', default_separator_mode)
                custom_separator_loaded = settings.get('custom_suffix_separator', default_custom_separator)
                if separator_mode_loaded == "none":
                    self.separator_none_rb.setChecked(True)
                else: # custom or default
                    self.separator_custom_rb.setChecked(True)
                self.custom_separator_entry.setText(custom_separator_loaded)

                self.suffix_len_spin.setValue(settings.getint('suffix_length', 8))
                self.suffix_lowercase_cb.setChecked(settings.getboolean('suffix_lowercase', True))
                self.suffix_uppercase_cb.setChecked(settings.getboolean('suffix_uppercase', True))
                self.suffix_digits_cb.setChecked(settings.getboolean('suffix_digits', True))
                self.suffix_all_special_cb.setChecked(settings.getboolean('suffix_all_special', False))
                self.suffix_custom_special_entry.setText(settings.get('suffix_custom_special', ''))
                suffix_mode_loaded = settings.get('suffix_generation_mode', 'classic_random')
                if suffix_mode_loaded == 'pattern': self.suffix_mode_pattern_rb.setChecked(True)
                elif suffix_mode_loaded == 'ratio': self.suffix_mode_ratio_rb.setChecked(True)
                else: self.suffix_mode_classic_random_rb.setChecked(True)
                self.suffix_pattern_entry.setText(settings.get('suffix_pattern', ''))
                self.suffix_ratio_lowercase_spin.setValue(settings.getint('suffix_ratio_lowercase', 0))
                self.suffix_ratio_uppercase_spin.setValue(settings.getint('suffix_ratio_uppercase', 0))
                self.suffix_ratio_digits_spin.setValue(settings.getint('suffix_ratio_digits', 0))
                self.suffix_ratio_special_spin.setValue(settings.getint('suffix_ratio_special', 0))
                self.update_total_ratio_label()
                self.good_link_keywords_text.setText(settings.get('good_link_keywords', ''))
                self.bad_link_keywords_text.setText(settings.get('bad_link_keywords', ''))
                self.bad_link_is_everything_else_cb.setChecked(settings.getboolean('bad_link_is_everything_else', False))
                self.good_link_is_everything_else_cb.setChecked(settings.getboolean('good_link_is_everything_else', False)) 
                self.num_threads_spin.setValue(settings.getint('num_threads', default_num_threads))
                self.requests_per_active_proxy_spin.setValue(settings.getint('requests_per_active_proxy', default_req_per_proxy))
                self.proxy_sources_text.setText(settings.get('proxy_sources', ''))
                limit_type = settings.get('limit_type', 'count')
                if limit_type == 'time': self.limit_type_time_radio.setChecked(True)
                else: self.limit_type_count_radio.setChecked(True)
                self.scan_limit_count_spin.setValue(settings.getint('limit_count', 1000))
                self.scan_limit_time_spin.setValue(settings.getint('limit_time_minutes', 0))
                loaded_width = settings.getint('window_width', self.initial_width)
                loaded_height = settings.getint('window_height', self.initial_height)
                self.window_width_spin.setValue(loaded_width) 
                self.window_height_spin.setValue(loaded_height)
                self.resize(loaded_width, loaded_height) 
                loaded_font_family = settings.get('font_family', default_font_family)
                loaded_font_size = settings.getint('font_size', default_font_size)
                self.apply_font_settings(font_to_set=loaded_font_family, size_pt_to_set=loaded_font_size)
                self.log_message(f"Đã tải cài đặt từ {CONFIG_FILE_PATH}", "info")
                logging.info(f"Đã tải cài đặt từ {CONFIG_FILE_PATH}")
            else: 
                self.log_message(f"Mục 'Settings' không tìm thấy trong {CONFIG_FILE_PATH}. Dùng giá trị mặc định.", "warning")
                logging.warning(f"Mục 'Settings' không tìm thấy trong {CONFIG_FILE_PATH}. Dùng giá trị mặc định.")
                self.apply_font_settings(font_to_set=default_font_family, size_pt_to_set=default_font_size)
        self.toggle_limit_inputs()
        self.update_classification_mode() 
        self.update_separator_input_state() # Ensure UI state for separator is correct


    def save_config(self):
        if not os.path.exists(CONFIG_DIR):
            try:
                os.makedirs(CONFIG_DIR)
                logging.info(f"Đã tạo thư mục config: {CONFIG_DIR}")
            except OSError as e:
                logging.error(f"Lỗi khi tạo thư mục config '{CONFIG_DIR}': {e}")
                QMessageBox.critical(self, "Lỗi", f"Không thể tạo thư mục '{CONFIG_DIR}' để lưu cấu hình: {e}")
                return
        if 'Settings' not in self.config: self.config.add_section('Settings')
        settings = self.config['Settings'] 
        settings['website'] = self.website_entry.text()
        settings['additional_paths'] = self.additional_paths_entry.text()
        
        if self.separator_none_rb.isChecked():
            settings['suffix_separator_mode'] = 'none'
        else:
            settings['suffix_separator_mode'] = 'custom'
        settings['custom_suffix_separator'] = self.custom_separator_entry.text()

        settings['suffix_length'] = str(self.suffix_len_spin.value())
        settings['suffix_lowercase'] = str(self.suffix_lowercase_cb.isChecked())
        settings['suffix_uppercase'] = str(self.suffix_uppercase_cb.isChecked())
        settings['suffix_digits'] = str(self.suffix_digits_cb.isChecked())
        settings['suffix_all_special'] = str(self.suffix_all_special_cb.isChecked())
        settings['suffix_custom_special'] = self.suffix_custom_special_entry.text()
        if self.suffix_mode_pattern_rb.isChecked(): settings['suffix_generation_mode'] = 'pattern'
        elif self.suffix_mode_ratio_rb.isChecked(): settings['suffix_generation_mode'] = 'ratio'
        else: settings['suffix_generation_mode'] = 'classic_random'
        settings['suffix_pattern'] = self.suffix_pattern_entry.text()
        settings['suffix_ratio_lowercase'] = str(self.suffix_ratio_lowercase_spin.value())
        settings['suffix_ratio_uppercase'] = str(self.suffix_ratio_uppercase_spin.value())
        settings['suffix_ratio_digits'] = str(self.suffix_ratio_digits_spin.value())
        settings['suffix_ratio_special'] = str(self.suffix_ratio_special_spin.value())
        settings['good_link_keywords'] = self.good_link_keywords_text.toPlainText()
        settings['bad_link_keywords'] = self.bad_link_keywords_text.toPlainText()
        settings['bad_link_is_everything_else'] = str(self.bad_link_is_everything_else_cb.isChecked())
        settings['good_link_is_everything_else'] = str(self.good_link_is_everything_else_cb.isChecked()) 
        settings['num_threads'] = str(self.num_threads_spin.value())
        settings['requests_per_active_proxy'] = str(self.requests_per_active_proxy_spin.value())
        settings['proxy_sources'] = self.proxy_sources_text.toPlainText()
        if self.limit_type_count_radio.isChecked(): settings['limit_type'] = 'count'
        else: settings['limit_type'] = 'time'
        settings['limit_count'] = str(self.scan_limit_count_spin.value())
        settings['limit_time_minutes'] = str(self.scan_limit_time_spin.value())
        settings['window_width'] = str(self.width()) 
        settings['window_height'] = str(self.height())
        settings['font_family'] = self.font_combo_box.currentFont().family() 
        settings['font_size'] = str(self.font_size_spin.value())
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            logging.info(f"Đã lưu cài đặt vào {CONFIG_FILE_PATH}")
        except Exception as e:
            logging.error(f"Lỗi khi lưu cài đặt: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu file cấu hình vào '{CONFIG_FILE_PATH}': {e}")

    def closeEvent(self, event):
        logging.info("Ứng dụng đang đóng...")
        self.save_config()
        if self.active_workers_count > 0:
            reply = QMessageBox.question(self, 'Thoát Ứng Dụng',
                                       "Quá trình scan đang chạy. Bạn có chắc muốn thoát?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                logging.info("Người dùng chọn thoát khi scan đang chạy.")
                self.stop_scan_internal() 
                QApplication.processEvents() 
                all_stopped_gracefully = True
                logging.debug("Chờ các worker dừng trong closeEvent...")
                for _i in range(10): 
                    if self.active_workers_count == 0: break
                    time.sleep(0.5)
                    QApplication.processEvents()
                if self.active_workers_count > 0:
                    logging.warning(f"{self.active_workers_count} workers không dừng hẳn trong closeEvent.")
                    all_stopped_gracefully = False
                if all_stopped_gracefully: logging.info("Tất cả worker đã dừng nhẹ nhàng trong closeEvent.")
                event.accept()
            else:
                logging.info("Người dùng hủy thoát.")
                event.ignore()
        else:
            logging.info("Thoát ứng dụng (không có worker nào chạy).")
            event.accept()

if __name__ == '__main__':
    from pathlib import Path 
    log_file_path_obj = Path(APP_LOG_FILE)
    dirs_to_create_str = [CONFIG_DIR, DATA_ROOT_DIR]
    if log_file_path_obj.parent != Path('.'): 
        dirs_to_create_str.append(str(log_file_path_obj.parent))
    for dir_path_str in dirs_to_create_str:
        dir_path = Path(dir_path_str)
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"INFO: Đã tạo thư mục: {dir_path}")
            except OSError as e:
                print(f"ERROR: Không thể tạo thư mục '{dir_path}': {e}", file=sys.stderr)
                if str(dir_path) == CONFIG_DIR:
                     print(f"ERROR: Không thể tạo thư mục cấu hình '{CONFIG_DIR}'. Thoát.", file=sys.stderr)
                     sys.exit(1) 
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
