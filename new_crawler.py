import os
import time
import sqlite3
import hashlib
import logging
import requests
import feedparser
from bs4 import BeautifulSoup
import schedule
import threading
import shutil
import psutil
import re
import random
from difflib import SequenceMatcher
from datetime import datetime, timedelta
import concurrent.futures
from queue import Queue
from PIL import Image
import io
import json

# 创建必要的目录
try:
    os.makedirs("logs", exist_ok=True)  # 创建日志目录
    os.makedirs("database", exist_ok=True)  # 创建数据库目录
except Exception as e:
    print(f"Warning: Failed to create directories: {str(e)}")

# 配置区
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 创建日志目录（如果在 GitHub Actions 中运行）
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'crawler.log')

# 确保日志文件所在目录存在
try:
    if not os.path.exists(os.path.dirname(LOG_FILE)):
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
except Exception as e:
    print(f"Warning: Failed to create log directory: {str(e)}")
    # 如果无法创建日志目录，使用当前目录
    LOG_FILE = 'crawler.log'

# 配置日志
try:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )
except Exception as e:
    print(f"Warning: Failed to configure logging: {str(e)}")
    # 如果日志配置失败，使用基本配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger('NewsCrawler')

# 配置区
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 修改为您的网站实际目录
WEB_ROOT = "C:\\www\\wwwroot\\freecomic.website"  # 修改为您的网站根目录
NEWS_DIR = os.path.join(WEB_ROOT, 'news')
IMAGE_DIR = os.path.join(WEB_ROOT, 'images')
CSS_DIR = os.path.join(WEB_ROOT, 'css')
DB_PATH = os.path.join(BASE_DIR, 'database', 'news.db')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'crawler.log')
DEFAULT_IMAGE = os.path.join(IMAGE_DIR, 'default.jpg')

# 添加输出目录配置
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 输出文件路径
INDEX_FILE = os.path.join(OUTPUT_DIR, 'index.html')
MOBILE_FILE = os.path.join(OUTPUT_DIR, 'mobile_news.html') 
DATA_FILE = os.path.join(OUTPUT_DIR, 'data.json')

# 网站基本信息
SITE_NAME = "国际时报刊"
SITE_URL = "https://freecomic.website"

# 内容配置
MAX_HOME_ARTICLES = 30  # 增加首页文章数量
MIN_DISK_SPACE_GB = 1.0  # 提高最小磁盘空间要求
MAX_ARTICLES_PER_RUN = 100  # 增加每次抓取的文章数
CLEANUP_DAYS = 7  # 延长文章保留时间

# 性能配置
REQUEST_TIMEOUT = 15  # 增加超时时间
RETRY_COUNT = 5  # 增加重试次数
RETRY_DELAY = 3  # 增加重试延迟
MAX_CONCURRENT_REQUESTS = 10  # 增加并发数

# 图片处理配置
IMAGE_MAX_SIZE = 2 * 1024 * 1024  # 增加到2MB
IMAGE_QUALITY = 90  # 提高图片质量
IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'webp']

# 相似度判断配置
SIMILARITY_THRESHOLD = 0.85
TITLE_SIMILARITY_THRESHOLD = 0.9
SUMMARY_SIMILARITY_THRESHOLD = 0.8

# 更新RSS源列表
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",  # BBC国际新闻
    "https://www.theguardian.com/world/rss",        # The Guardian
    "https://www.france24.com/en/rss",              # France24
    "https://www.aljazeera.com/xml/rss/all.xml",    # Al Jazeera
    "https://www.rt.com/rss/news/",                 # RT News
    "https://www.euronews.com/rss?format=mrss&level=theme&name=news",  # Euronews
    "https://www.newsweek.com/rss",                 # Newsweek
    "https://www.themoscowtimes.com/rss/news",      # The Moscow Times
    "https://www.japantimes.co.jp/feed/",           # The Japan Times
    "https://www.straitstimes.com/news/singapore/rss.xml",  # The Straits Times
    "https://www.scmp.com/rss/91/feed",             # South China Morning Post
    "https://www.timesofindia.com/rssfeedstopstories.cms",  # Times of India
    "https://www.thehindu.com/news/international/feeder/default.rss",  # The Hindu
    "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/world/rss.xml",  # NYT World
    "https://www.washingtonpost.com/world/feed/",   # Washington Post World
    "https://www.npr.org/feeds/1001/feed.json",     # NPR World
    "https://www.abc.net.au/news/feed/4590162/rss.xml",  # ABC News World
    "https://www.cbc.ca/cmlink/rss-world",          # CBC World
    "https://www.dw.com/rss/rss-en-all",            # Deutsche Welle
    "https://www.reutersagency.com/feed/"           # Reuters
]

# User-Agent池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
]

# 内容提取选择器
CONTENT_SELECTORS = [
    'article',
    '.article-content',
    '.story-body',
    '.article-body',
    '#article-body',
    '.content',
    'main',
    '.post-content',
    '.entry-content',
    '.article__body',
    '.article-text',
    '.article__content',
    '.story__content',
    '.article__story',
    '.article__main'
]

# 图片提取选择器
IMAGE_SELECTORS = [
    'meta[property="og:image"]',
    'meta[name="twitter:image"]',
    '.article-image img',
    '.story-image img',
    '.main-image img',
    '.article__image img',
    '.article__media img',
    '.article__header img',
    '.story__media img',
    '.article__hero img',
    '.article__lead-image img'
]

# 日志配置
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('NewsCrawler')

# 数据库初始化
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        summary TEXT,
        url TEXT NOT NULL UNIQUE,
        img_url TEXT,
        hash TEXT NOT NULL UNIQUE,
        full_generated INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_full_generated ON articles(full_generated)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)")
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def calculate_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def calculate_similarity(str1, str2):
    """计算两个字符串的相似度，使用更精确的算法"""
    if not str1 or not str2:
        return 0.0
        
    # 预处理文本
    str1 = re.sub(r'\s+', ' ', str1.lower().strip())
    str2 = re.sub(r'\s+', ' ', str2.lower().strip())
    
    # 使用SequenceMatcher计算相似度
    return SequenceMatcher(None, str1, str2).ratio()

def is_similar_article(title, summary, conn):
    """检查是否存在相似文章，使用更严格的判断标准"""
    cur = conn.cursor()
    
    # 获取最近24小时内的文章
    one_day_ago = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""
        SELECT title, summary 
        FROM articles 
        WHERE created_at > ?
    """, (one_day_ago,))
    
    existing_articles = cur.fetchall()
    
    for existing_title, existing_summary in existing_articles:
        # 检查标题相似度
        title_similarity = calculate_similarity(title, existing_title)
        if title_similarity > TITLE_SIMILARITY_THRESHOLD:
            return True
            
        # 检查摘要相似度
        if summary and existing_summary:
            summary_similarity = calculate_similarity(summary, existing_summary)
            if summary_similarity > SUMMARY_SIMILARITY_THRESHOLD:
                return True
    
    return False

def fetch_url_content(url):
    """获取URL内容，带重试机制和智能解析"""
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    for attempt in range(RETRY_COUNT):
        try:
            print(f"正在获取内容: {url} (尝试 {attempt + 1}/{RETRY_COUNT})")
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # 检测并设置正确的编码
            if response.encoding == 'ISO-8859-1':
                response.encoding = response.apparent_encoding
            
            # 智能解析内容
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除不需要的元素
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'aside', 'form']):
                element.decompose()
            
            # 尝试不同的内容选择器
            content = None
            for selector in CONTENT_SELECTORS:
                element = soup.select_one(selector)
                if element:
                    # 移除广告、分享按钮等干扰元素
                    for ad in element.find_all(class_=lambda x: x and ('ad' in x.lower() or 'share' in x.lower() or 'social' in x.lower())):
                        ad.decompose()
                    content = element.get_text(strip=True)
                    break
            
            if not content:
                # 如果找不到特定选择器，尝试获取body内容
                content = soup.body.get_text(strip=True) if soup.body else ''
            
            # 清理文本
            content = ' '.join(content.split())  # 移除多余空白
            content = re.sub(r'\s+', ' ', content)  # 规范化空白字符
            content = re.sub(r'[^\S\n]+', ' ', content)  # 保留段落换行
            
            if len(content) > 100:  # 确保内容有效
                print(f"成功获取内容，长度: {len(content)} 字符")
                return content
            else:
                print(f"警告: 内容太短 ({len(content)} 字符)")
                continue
            
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {str(e)}")
            if attempt < RETRY_COUNT - 1:
                time.sleep(RETRY_DELAY)
                continue
            logger.error(f"请求URL失败: {url}: {str(e)}")
            return None
        except Exception as e:
            print(f"处理内容失败: {str(e)}")
            logger.error(f"处理URL内容失败: {url}: {str(e)}")
            return None
    
    return None

def download_image(img_url, article_id):
    """下载并处理图片，添加图片优化"""
    try:
        if not img_url:
            return '/images/default.jpg'
            
        print(f"正在下载图片: {img_url}")
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': SITE_URL
        }
        
        response = requests.get(img_url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        # 检查内容类型和大小
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            print(f"警告: 非图片内容类型: {content_type}")
            return '/images/default.jpg'
            
        if len(response.content) > IMAGE_MAX_SIZE:
            print(f"警告: 图片太大 ({len(response.content)} bytes)")
            return '/images/default.jpg'
        
        # 确定文件扩展名
        ext = 'jpg'
        if 'image/jpeg' in content_type:
            ext = 'jpg'
        elif 'image/png' in content_type:
            ext = 'png'
        elif 'image/gif' in content_type:
            ext = 'gif'
        elif 'image/webp' in content_type:
            ext = 'webp'
        
        # 生成文件名并保存
        filename = f"{article_id}.{ext}"
        filepath = os.path.join(IMAGE_DIR, filename)
        
        # 优化图片
        try:
            img = Image.open(io.BytesIO(response.content))
            
            # 调整大小
            max_size = (800, 800)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 保存优化后的图片
            img.save(filepath, quality=IMAGE_QUALITY, optimize=True)
            
        except Exception as e:
            print(f"图片优化失败: {str(e)}")
            # 如果优化失败，保存原始图片
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
        print(f"图片下载成功: {filename}")
        return f"/images/{filename}"
        
    except Exception as e:
        print(f"下载图片失败: {str(e)}")
        logger.error(f"下载图片失败: {img_url}: {str(e)}")
        return '/images/default.jpg'

def extract_image_from_content(url, soup):
    """从页面内容中提取图片URL"""
    try:
        # 首先检查meta标签
        for selector in IMAGE_SELECTORS:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    img_url = element.get('content')
                else:
                    img_url = element.get('src')
                if img_url:
                    # 处理相对URL
                    if not img_url.startswith(('http://', 'https://')):
                        from urllib.parse import urljoin
                        img_url = urljoin(url, img_url)
                    return img_url
        
        # 如果meta标签中没有找到，尝试查找文章中的第一张图片
        article_img = soup.select_one('article img, .article img, .content img')
        if article_img:
            img_url = article_img.get('src')
            if img_url:
                if not img_url.startswith(('http://', 'https://')):
                    from urllib.parse import urljoin
                    img_url = urljoin(url, img_url)
                return img_url
                
        return None
    except Exception as e:
        logger.error(f"提取图片URL失败: {url}: {str(e)}")
        return None

def save_data_file(articles):
    """保存抓取的原始数据为JSON"""
    try:
        data = {
            'site_name': SITE_NAME,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'articles': articles
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"数据文件已保存: {DATA_FILE}")
    except Exception as e:
        logger.error(f"保存数据文件失败: {str(e)}")

def generate_mobile_page(articles):
    """生成移动端页面"""
    try:
        mobile_blocks = []
        for article in articles:
            article_id, title, summary, img_url = article
            # 移动端样式的文章块
            block = f"""
            <div class="mobile-news-item">
                <h3><a href="{SITE_URL}/news/{article_id}.html">{title}</a></h3>
                <div class="mobile-news-summary">{summary}</div>
            </div>
            """
            mobile_blocks.append(block)
            
        mobile_html = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{SITE_NAME} - 移动版</title>
            <style>
                body {{ padding: 10px; margin: 0; font-family: system-ui; }}
                .mobile-news-item {{ padding: 15px; border-bottom: 1px solid #eee; }}
                .mobile-news-item h3 {{ margin: 0 0 10px 0; }}
                .mobile-news-item a {{ color: #333; text-decoration: none; }}
                .mobile-news-summary {{ color: #666; font-size: 14px; }}
            </style>
        </head>
        <body>
            <h1 style="text-align:center;font-size:1.5em;">{SITE_NAME}</h1>
            {''.join(mobile_blocks)}
            <footer style="text-align:center;padding:20px;color:#999;">
                <p>更新时间: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            </footer>
        </body>
        </html>
        """
        
        with open(MOBILE_FILE, 'w', encoding='utf-8') as f:
            f.write(mobile_html)
        logger.info(f"移动端页面已生成: {MOBILE_FILE}")
        
    except Exception as e:
        logger.error(f"生成移动端页面失败: {str(e)}")

def generate_homepage():
    """生成首页"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        print("\n开始生成首页...")
        cur.execute("""
            SELECT id, title, summary, img_url 
            FROM articles 
            WHERE full_generated = 1 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (MAX_HOME_ARTICLES,))
        articles = cur.fetchall()
        if not articles:
            print("警告: 没有可展示的文章")
            logger.warning("没有可展示的文章")
            return False
            
        # 保存原始数据
        save_data_file(articles)
        
        # 生成移动端页面
        generate_mobile_page(articles)
        
        # 生成PC端首页
        print(f"找到 {len(articles)} 篇文章用于首页展示")
        article_blocks = []
        for article in articles:
            article_id, title, summary, img_url = article
            full_url = f"{SITE_URL}/news/{article_id}.html"
            img_path = f"{SITE_URL}/images/default.jpg" if not img_url else f"{SITE_URL}{img_url}"
            
            # 清理摘要中的HTML标签
            if summary:
                summary = re.sub(r'<[^>]+>', '', summary)
                summary = summary[:200] + '...' if len(summary) > 200 else summary
            else:
                summary = '暂无摘要'
                
            block = f"""
            <div class="news-block">
                <div class="news-image">
                    <a href="{full_url}">
                        <img src="{img_path}" alt="{title}">
                    </a>
                </div>
                <div class="news-content">
                    <h3><a href="{full_url}">{title}</a></h3>
                    <p>{summary}</p>
                    <a href="{full_url}" class="read-more">阅读全文</a>
                </div>
            </div>
            """
            article_blocks.append(block)
            
        html_content = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{SITE_NAME} - 最新国际新闻</title>
            <meta name="description" content="{SITE_NAME}为您提供最新的国际新闻资讯">
            <meta name="keywords" content="国际新闻,国际时报刊,最新新闻">
            <link rel="stylesheet" href="{SITE_URL}/css/style.css">
            <link rel="canonical" href="{SITE_URL}">
            <!-- Open Graph / Facebook -->
            <meta property="og:type" content="website">
            <meta property="og:url" content="{SITE_URL}">
            <meta property="og:title" content="{SITE_NAME} - 最新国际新闻">
            <meta property="og:description" content="{SITE_NAME}为您提供最新的国际新闻资讯">
            <meta property="og:image" content="{SITE_URL}/images/default.jpg">
            <!-- Twitter -->
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:url" content="{SITE_URL}">
            <meta name="twitter:title" content="{SITE_NAME} - 最新国际新闻">
            <meta name="twitter:description" content="{SITE_NAME}为您提供最新的国际新闻资讯">
            <meta name="twitter:image" content="{SITE_URL}/images/default.jpg">
        </head>
        <body>
            <div class="container">
                <header>
                    <h1>{SITE_NAME}</h1>
                    <p>每日精选国际新闻</p>
                </header>
                <div class="news-grid">
                    {''.join(article_blocks)}
                </div>
                <footer>
                    <p>内容由AI自动收集整理 &copy; {time.strftime('%Y')} {SITE_NAME}</p>
                    <p>数据更新时间: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </footer>
            </div>
        </body>
        </html>
        """
        
        # 直接更新网站首页
        index_path = os.path.join(WEB_ROOT, 'index.html')
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"首页更新成功: {index_path}")
            logger.info(f"首页更新成功: {index_path}")
        except Exception as e:
            print(f"错误: 写入首页文件失败 - {str(e)}")
            logger.error(f"写入首页文件失败: {str(e)}")
            return False
        
        # 同时保存到output目录
        try:
            shutil.copy2(index_path, INDEX_FILE)
            logger.info(f"首页已复制到输出目录: {INDEX_FILE}")
        except Exception as e:
            logger.error(f"复制首页到输出目录失败: {str(e)}")
            
        return True
            
    except Exception as e:
        print(f"错误: 更新首页失败")
        logger.error(f"更新首页失败: {str(e)}")
        return False
    finally:
        conn.close()

def check_disk_space():
    """检查磁盘空间，优化检查逻辑"""
    try:
        disk = psutil.disk_usage(BASE_DIR)
        free_gb = disk.free / (1024 * 1024 * 1024)
        print(f"\n当前磁盘空间状态:")
        print(f"总空间: {disk.total / (1024**3):.2f} GB")
        print(f"已用: {disk.used / (1024**3):.2f} GB")
        print(f"可用: {free_gb:.2f} GB")
        
        if free_gb < MIN_DISK_SPACE_GB:
            print(f"\n警告: 磁盘空间不足 ({free_gb:.2f}GB < {MIN_DISK_SPACE_GB}GB)")
            print("尝试清理旧文件...")
            cleanup_old_files()
            
            # 再次检查
            disk = psutil.disk_usage(BASE_DIR)
            free_gb = disk.free / (1024 * 1024 * 1024)
            print(f"清理后可用空间: {free_gb:.2f} GB")
            
            if free_gb < MIN_DISK_SPACE_GB:
                print("错误: 清理后仍空间不足")
                return False
            print("清理成功，空间充足")
        return True
    except Exception as e:
        print(f"检查磁盘空间时出错: {str(e)}")
        return True  # 出错时默认允许继续运行

def cleanup_old_files():
    """清理旧文件"""
    try:
        print("\n开始清理旧文件...")
        # 清理旧文章
        current_time = time.time()
        cleaned_count = 0
        
        # 清理旧文章
        for filename in os.listdir(NEWS_DIR):
            if filename.endswith('.html'):
                file_path = os.path.join(NEWS_DIR, filename)
                if current_time - os.path.getmtime(file_path) > CLEANUP_DAYS * 86400:
                    os.remove(file_path)
                    cleaned_count += 1
                    print(f"删除旧文章: {filename}")
        
        # 清理旧图片
        for filename in os.listdir(IMAGE_DIR):
            if filename != 'default.jpg':
                file_path = os.path.join(IMAGE_DIR, filename)
                if current_time - os.path.getmtime(file_path) > CLEANUP_DAYS * 86400:
                    os.remove(file_path)
                    cleaned_count += 1
                    print(f"删除旧图片: {filename}")
                    
        # 清理数据库中的旧记录
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM articles WHERE created_at < datetime('now', '-3 days')")
        deleted_count = cur.rowcount
        conn.commit()
        conn.close()
        
        print(f"清理完成: 删除了 {cleaned_count} 个文件, {deleted_count} 条数据库记录")
        
    except Exception as e:
        print(f"清理旧文件失败: {str(e)}")

def init_directories():
    """初始化目录结构"""
    try:
        # 确保网站目录存在
        for d in [WEB_ROOT, NEWS_DIR, IMAGE_DIR, CSS_DIR]:
            if not os.path.exists(d):
                os.makedirs(d)
                print(f"创建目录: {d}")
                
        # 测试写入权限
        test_file = os.path.join(WEB_ROOT, 'test.txt')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print("目录写入权限正常")
        except Exception as e:
            print(f"错误: 目录没有写入权限 - {str(e)}")
            return False
            
        # 确保默认图片存在
        if not os.path.exists(DEFAULT_IMAGE):
            # 创建一个简单的默认图片
            img = Image.new('RGB', (800, 400), color='gray')
            img.save(DEFAULT_IMAGE)
            print(f"创建默认图片: {DEFAULT_IMAGE}")
            
        # 确保CSS文件存在
        css_file = os.path.join(CSS_DIR, 'style.css')
        if not os.path.exists(css_file):
            with open(css_file, 'w', encoding='utf-8') as f:
                f.write("""
                body { 
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background: #f5f5f5;
                    line-height: 1.6;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                header {
                    background: #fff;
                    padding: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    text-align: center;
                }
                header h1 {
                    margin: 0;
                    color: #333;
                }
                .news-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }
                .news-block {
                    background: #fff;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    transition: transform 0.2s;
                }
                .news-block:hover {
                    transform: translateY(-5px);
                }
                .news-image img {
                    width: 100%;
                    height: 200px;
                    object-fit: cover;
                }
                .news-content {
                    padding: 15px;
                }
                .news-content h3 {
                    margin: 0 0 10px 0;
                    font-size: 1.2em;
                }
                .news-content h3 a {
                    color: #333;
                    text-decoration: none;
                }
                .news-content h3 a:hover {
                    color: #007bff;
                }
                .news-content p {
                    color: #666;
                    margin: 0 0 15px 0;
                }
                .read-more {
                    display: inline-block;
                    padding: 5px 15px;
                    background: #007bff;
                    color: #fff;
                    text-decoration: none;
                    border-radius: 4px;
                    transition: background 0.2s;
                }
                .read-more:hover {
                    background: #0056b3;
                }
                .article-container {
                    background: #fff;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    margin: 20px 0;
                }
                .article-image {
                    max-width: 100%;
                    height: auto;
                    margin: 20px 0;
                    border-radius: 4px;
                }
                .article-content {
                    line-height: 1.8;
                    color: #333;
                }
                footer {
                    text-align: center;
                    padding: 20px;
                    background: #fff;
                    margin-top: 20px;
                    box-shadow: 0 -2px 4px rgba(0,0,0,0.1);
                    color: #666;
                }
                footer a {
                    color: #007bff;
                    text-decoration: none;
                }
                footer a:hover {
                    text-decoration: underline;
                }
                @media (max-width: 768px) {
                    .news-grid {
                        grid-template-columns: 1fr;
                    }
                    .container {
                        padding: 10px;
                    }
                }
                """)
            print(f"创建CSS文件: {css_file}")
        return True
    except Exception as e:
        print(f"初始化目录结构失败: {str(e)}")
        return False

def fetch_and_store():
    """抓取并存储新闻文章
    
    Returns:
        int: 新增的文章数量
    """
    conn = get_db_connection()
    cur = conn.cursor()
    new_articles = 0
    
    try:
        # 遍历所有RSS源
        for rss_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(rss_url)
                if not feed.entries:
                    logger.warning(f"No entries found in feed: {rss_url}")
                    continue
                    
                # 处理每篇文章
                for entry in feed.entries:
                    title = entry.get('title', '').strip()
                    summary = entry.get('summary', '').strip()
                    url = entry.get('link', '').strip()
                    
                    # 提取图片URL
                    img_url = None
                    if 'media_content' in entry:
                        for media in entry.media_content:
                            if media.get('type', '').startswith('image/'):
                                img_url = media.get('url')
                                break
                                
                    # 计算文章哈希值
                    hash_val = calculate_hash(f"{title}{url}")
                    
                    # 检查文章是否已存在
                    cur.execute("SELECT id FROM articles WHERE hash = ?", (hash_val,))
                    if cur.fetchone():
                        continue
                        
                    # 检查相似文章
                    if is_similar_article(title, summary, conn):
                        continue
                    
                    # 插入新文章
                    try:
                        cur.execute("""
                            INSERT INTO articles (title, summary, url, img_url, hash)
                            VALUES (?, ?, ?, ?, ?)
                        """, (title, summary, url, img_url, hash_val))
                        new_articles += 1
                        logger.info(f"Added new article: {title}")
                    except sqlite3.IntegrityError:
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing feed {rss_url}: {str(e)}")
                continue
                
        conn.commit()
        return new_articles
        
    except Exception as e:
        logger.error(f"Error in fetch_and_store: {str(e)}")
        return 0
    finally:
        conn.close()

def process_unprocessed_articles():
    """处理未处理的文章
    
    使用多线程并发处理未生成完整页面的文章
    
    Returns:
        int: 处理成功的文章数量
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 获取未处理文章
        cur.execute("""
            SELECT id, title, url, img_url 
            FROM articles 
            WHERE full_generated = 0
            ORDER BY created_at DESC
        """)
        articles = cur.fetchall()
        
        if not articles:
            return 0
            
        # 创建线程池处理文章
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            future_to_article = {
                executor.submit(process_article, article): article 
                for article in articles
            }
            
            processed_count = 0
            for future in concurrent.futures.as_completed(future_to_article):
                article = future_to_article[future]
                try:
                    if future.result():
                        processed_count += 1
                        # 更新文章状态
                        cur.execute("""
                            UPDATE articles 
                            SET full_generated = 1 
                            WHERE id = ?
                        """, (article[0],))
                except Exception as e:
                    logger.error(f"Error processing article {article[1]}: {str(e)}")
                    
        conn.commit()
        return processed_count
        
    except Exception as e:
        logger.error(f"Error in process_unprocessed_articles: {str(e)}")
        return 0
    finally:
        conn.close()

def process_article(article_data):
    """处理单篇文章
    
    Args:
        article_data: 元组(id, title, url, img_url)
    
    Returns:
        bool: 处理是否成功
    """
    article_id, title, url, img_url = article_data
    
    try:
        # 获取文章内容
        content = fetch_url_content(url)
        if not content:
            return False
            
        # 处理图片
        if not img_url:
            response = requests.get(url, headers={'User-Agent': random.choice(USER_AGENTS)})
            soup = BeautifulSoup(response.text, 'html.parser')
            img_url = extract_image_from_content(url, soup)
            
        local_img = download_image(img_url, article_id) if img_url else '/images/default.jpg'
        
        # 生成文章HTML
        html_content = generate_article_html(title, content, local_img, article_id)
        
        # 保存文章
        file_path = os.path.join(NEWS_DIR, f"{article_id}.html")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return True
        
    except Exception as e:
        logger.error(f"Error processing article {title}: {str(e)}")
        return False

def generate_article_html(title, content, img_url, article_id):
    """生成文章HTML页面
    
    Args:
        title: 文章标题
        content: 文章内容
        img_url: 图片URL
        article_id: 文章ID
    
    Returns:
        str: 生成的HTML内容
    """
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - {SITE_NAME}</title>
        <link rel="stylesheet" href="{SITE_URL}/css/style.css">
    </head>
    <body>
        <div class="container">
            <article class="article-container">
                <h1>{title}</h1>
                <img class="article-image" src="{img_url}" alt="{title}">
                <div class="article-content">{content}</div>
            </article>
        </div>
    </body>
    </html>
    """

def run_crawler():
    """运行爬虫任务，添加错误恢复机制"""
    try:
        print(f"\n{'='*50}")
        print(f"开始执行爬虫任务 - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        start_time = time.time()
        logger.info("=" * 50)
        logger.info(f"开始执行新闻抓取流程 - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 初始化目录结构
        print("\n初始化目录结构...")
        if not init_directories():
            print("错误: 初始化目录结构失败")
            return
        
        print("目录结构初始化完成")
        
        # 检查磁盘空间
        print("\n检查磁盘空间...")
        if not check_disk_space():
            print("错误: 磁盘空间不足，尝试清理后继续")
            cleanup_old_files()
            if not check_disk_space():
                print("错误: 清理后仍空间不足，跳过本次执行")
                logger.error("磁盘空间不足，跳过本次执行")
                return
        
        print("磁盘空间充足")
        
        # 清理旧文件
        print("\n清理旧文件...")
        cleanup_old_files()
        print("清理完成")
        
        # 初始化数据库
        print("\n初始化数据库...")
        init_db()
        print("数据库初始化完成")
        
        # 抓取新文章
        print("\n开始抓取新文章...")
        new_count = fetch_and_store()
        print(f"新增文章数量: {new_count}")
        
        # 处理文章
        print("\n开始处理文章...")
        processed_count = process_unprocessed_articles()
        print(f"处理文章数量: {processed_count}")
        
        # 更新首页
        print("\n开始更新首页...")
        update_success = generate_homepage()
        print(f"首页更新{'成功' if update_success else '失败'}")
        
        elapsed = time.time() - start_time
        print(f"\n爬虫执行完成, 耗时: {elapsed:.2f}秒")
        logger.info(f"爬虫执行完成, 耗时: {elapsed:.2f}秒")
        logger.info("=" * 50)
        
    except Exception as e:
        print(f"错误: 爬虫执行出错")
        logger.error(f"爬虫执行出错: {str(e)}")
        print(f"错误详情: {str(e)}")
        # 尝试恢复
        try:
            cleanup_old_files()
            init_db()
        except:
            pass

def run_scheduler():
    """运行调度器，优化调度逻辑"""
    # 立即执行一次
    run_crawler()
    
    # 设置每5分钟执行一次
    schedule.every(5).minutes.do(run_crawler)
    
    # 每天凌晨3点执行一次完整清理
    schedule.every().day.at("03:00").do(cleanup_old_files)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"调度器出错: {str(e)}")
            print(f"调度器错误: {str(e)}")
            time.sleep(30)  # 出错后等待30秒再继续

def main():
    # 只执行一次抓取和保存
    crawl_website()
    save_to_database_or_html()

if __name__ == "__main__":
    main()
