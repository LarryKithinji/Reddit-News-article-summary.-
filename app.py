
import praw
import requests
import logging
import time
import json
import os
from typing import Optional, Dict, Set
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from readability import Document
import newspaper
import cloudscraper

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("reddit_bot.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Config:
    REDDIT_CLIENT_ID = "f7W8IqjORfzKsNqHVVSlJg"
    REDDIT_CLIENT_SECRET = "-5Cw-MH-7r4GICQGishtgKhYuW9ssg"
    REDDIT_USER_AGENT = "CommentBot"
    REDDIT_USERNAME = "Old-Star54"
    REDDIT_PASSWORD = "KePCCgt2minU1s1"
    COMMENT_DELAY = 720  # 12 minutes between comments
    SUBMISSION_DELAY = 300  # 5 minutes between submission checks
    LANGUAGE = "english"
    SENTENCES_COUNT = 4
    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1316896298901528668/cFLNO2jF4g9kBUUz6bS_t0jB1GQKjgtFcEMuK0qoVOtKK5tOtEQ5rnQlnllq5QAyOHFW"
    COMMENT_HISTORY_FILE = "comment_history.json"
    MIN_CONTENT_LENGTH = 50

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_notification(self, title: str, message: str, url: str = None):
        """Send notification to Discord."""
        try:
            embed = {
                "title": title,
                "description": message,
                "color": 0x00ff00,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
            }
            
            if url:
                embed["url"] = url

            payload = {
                "embeds": [embed]
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
            else:
                logger.warning(f"Discord notification failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")

class ContentExtractor:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()

    def extract_content(self, url: str) -> Optional[Dict[str, any]]:
        """Extract content using multiple fallback methods."""
        methods = [
            self._try_newspaper_extraction,
            self._try_selenium_extraction,
            self._try_readability_extraction,
            self._try_basic_requests
        ]
        
        for method in methods:
            try:
                result = method(url)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"Method {method.__name__} failed: {e}")
                continue
        
        logger.warning(f"All extraction methods failed for URL: {url}")
        return None

    def _try_newspaper_extraction(self, url: str) -> Optional[Dict[str, any]]:
        """Try extraction using newspaper3k."""
        try:
            logger.info("Trying newspaper extraction...")
            article = newspaper.Article(url)
            article.download()
            article.parse()
            
            if article.text and len(article.text.split()) >= 50:
                return self._process_extracted_content(article.text)
                
        except Exception as e:
            logger.debug(f"Newspaper extraction failed: {e}")
        return None

    def _try_selenium_extraction(self, url: str) -> Optional[Dict[str, any]]:
        """Try extraction using Selenium for dynamic content."""
        driver = None
        try:
            logger.info("Trying Selenium extraction...")
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            time.sleep(3)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            content = self._extract_with_advanced_selectors(soup)
            
            if content and len(content.split()) >= 50:
                return self._process_extracted_content(content)
                
        except Exception as e:
            logger.debug(f"Selenium extraction failed: {e}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        return None

    def _try_readability_extraction(self, url: str) -> Optional[Dict[str, any]]:
        """Try extraction using readability-lxml."""
        try:
            logger.info("Trying readability extraction...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            doc = Document(response.text)
            html = doc.summary()
            soup = BeautifulSoup(html, 'html.parser')
            content = soup.get_text(separator=' ').strip()

            if content and len(content.split()) >= 50:
                return self._process_extracted_content(content)

        except Exception as e:
            logger.debug(f"Readability extraction failed: {e}")
        return None

    def _try_basic_requests(self, url: str) -> Optional[Dict[str, any]]:
        """Basic requests extraction as last resort."""
        try:
            logger.info("Trying basic requests extraction...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            
            response = self.scraper.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            content = self._extract_with_advanced_selectors(soup)
            
            if content and len(content.split()) >= 50:
                return self._process_extracted_content(content)
                
        except Exception as e:
            logger.debug(f"Basic requests extraction failed: {e}")
        return None

    def _extract_with_advanced_selectors(self, soup: BeautifulSoup) -> str:
        """Extract content using multiple CSS selectors."""
        selectors = [
            'article',
            '[role="main"]',
            '.content',
            '.article-content',
            '.post-content',
            '.entry-content',
            'main',
            '#content',
            '.story-body',
            'div[data-component="text-block"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                content = ' '.join(elem.get_text(separator=' ').strip() for elem in elements)
                if len(content.split()) >= 30:
                    return content
        
        paragraphs = soup.find_all('p')
        return ' '.join(p.get_text(separator=' ').strip() for p in paragraphs)

    def _process_extracted_content(self, content: str) -> Dict[str, any]:
        """Process and validate extracted content."""
        cleaned_content = ' '.join(content.split())
        word_count = len(cleaned_content.split())
        
        return {
            'content': cleaned_content,
            'word_count': word_count,
            'char_count': len(cleaned_content)
        }

class SumySummarizer:
    def __init__(self):
        self.language = Config.LANGUAGE
        self.sentence_count = Config.SENTENCES_COUNT

    def generate_summary(self, content: str) -> Optional[str]:
        """Generate summary using Sumy."""
        try:
            parser = PlaintextParser.from_string(content, Tokenizer(self.language))
            summarizer = LsaSummarizer(Stemmer(self.language))
            summarizer.stop_words = get_stop_words(self.language)

            sentences = summarizer(parser.document, self.sentence_count)
            summary = ' '.join(str(sentence) for sentence in sentences)

            if summary and len(summary.split()) >= 10:
                return f"**Summary:** {summary}\n\n*I am a bot. This summary was generated automatically.*"
            else:
                logger.warning("Generated summary too short or empty")
                return None
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None

class CommentHistoryManager:
    def __init__(self, filename: str):
        self.filename = filename
        self.commented_submissions: Set[str] = self._load_history()

    def _load_history(self) -> Set[str]:
        """Load comment history from file."""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    return set(data.get('commented_submissions', []))
            else:
                logger.info("No previous comment history found, starting fresh")
                return set()
        except Exception as e:
            logger.error(f"Error loading comment history: {e}")
            return set()

    def _save_history(self):
        """Save comment history to file."""
        try:
            data = {'commented_submissions': list(self.commented_submissions)}
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving comment history: {e}")

    def has_commented(self, submission_id: str) -> bool:
        """Check if we've already commented on this submission."""
        return submission_id in self.commented_submissions

    def mark_commented(self, submission_id: str):
        """Mark submission as commented."""
        self.commented_submissions.add(submission_id)
        self._save_history()

    def cleanup_old_entries(self, max_entries: int = 1000):
        """Keep only the most recent entries."""
        if len(self.commented_submissions) > max_entries:
            # Keep the last max_entries
            recent_entries = list(self.commented_submissions)[-max_entries:]
            self.commented_submissions = set(recent_entries)
            self._save_history()

class RedditBot:
    def __init__(self):
        self.extractor = ContentExtractor()
        self.summarizer = SumySummarizer()
        self.notifier = DiscordNotifier(Config.DISCORD_WEBHOOK_URL)
        self.history = CommentHistoryManager(Config.COMMENT_HISTORY_FILE)
        
        self.reddit = praw.Reddit(
            client_id=Config.REDDIT_CLIENT_ID,
            client_secret=Config.REDDIT_CLIENT_SECRET,
            user_agent=Config.REDDIT_USER_AGENT,
            username=Config.REDDIT_USERNAME,
            password=Config.REDDIT_PASSWORD,
        )

        try:
            me = self.reddit.user.me()
            logger.info(f"Successfully authenticated as: {me.name}")
            self.notifier.send_notification(
                "Bot Started", 
                f"Reddit bot authenticated as {me.name}"
            )
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise

    def run(self, subreddit_name: str = "AfricaVoice"):
        """Main bot loop."""
        logger.info("Starting bot")
        self.notifier.send_notification(
            "Bot Active", 
            f"Monitoring r/{subreddit_name} for new submissions"
        )
        
        subreddit = self.reddit.subreddit(subreddit_name)
        logger.info(f"Rate limits: {Config.COMMENT_DELAY}s between comments, {Config.SUBMISSION_DELAY}s between checks")

        while True:
            try:
                self._process_new_submissions(subreddit)
                logger.info(f"Waiting {Config.SUBMISSION_DELAY} seconds before next submission check")
                time.sleep(Config.SUBMISSION_DELAY)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)

    def _process_new_submissions(self, subreddit):
        """Process new submissions from the subreddit."""
        try:
            for submission in subreddit.new(limit=10):
                logger.info(f"Evaluating: {submission.title} ({submission.url})")
                
                if self.history.has_commented(submission.id):
                    logger.info(f"Already commented on submission {submission.id}, skipping")
                    continue

                if self._should_process_submission(submission):
                    self._process_submission(submission)
                    
        except Exception as e:
            logger.error(f"Error processing submissions: {e}")

    def _should_process_submission(self, submission) -> bool:
        """Determine if submission should be processed."""
        if submission.is_self:
            logger.info(f"Skipping text post: {submission.title}")
            return False
            
        if submission.over_18:
            logger.info(f"Skipping NSFW content: {submission.title}")
            return False
            
        excluded_domains = ['reddit.com', 'i.redd.it', 'v.redd.it']
        if any(domain in submission.url for domain in excluded_domains):
            logger.info(f"Skipping excluded domain: {submission.url}")
            return False
            
        return True

    def _process_submission(self, submission):
        """Process a single submission."""
        try:
            logger.info(f"Processing: '{submission.title}' (ID: {submission.id})")
            
            extracted = self.extractor.extract_content(submission.url)
            if not extracted:
                logger.warning(f"Content extraction failed for {submission.url}")
                return

            content = extracted['content']
            word_count = extracted['word_count']
            
            logger.info(f"Extracted {word_count} words from content")
            
            if word_count < Config.MIN_CONTENT_LENGTH:
                logger.warning(f"Content too short ({word_count} words), skipping")
                return

            summary = self.summarizer.generate_summary(content)
            if not summary:
                logger.warning("Summary generation failed")
                return

            self._post_comment(submission, summary)
            
        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}", exc_info=True)

    def _post_comment(self, submission, summary: str):
        """Post comment with summary."""
        try:
            submission.reply(summary)
            logger.info(f"Comment posted successfully on submission {submission.id}")
            
            self.history.mark_commented(submission.id)
            
            self.notifier.send_notification(
                "Comment Posted",
                f"Posted summary on: {submission.title}",
                f"https://reddit.com{submission.permalink}"
            )
            
            logger.info(f"Waiting {Config.COMMENT_DELAY} seconds before next comment")
            time.sleep(Config.COMMENT_DELAY)
            
        except Exception as e:
            logger.error(f"Failed to post comment on submission {submission.id}: {e}")

if __name__ == "__main__":
    bot = RedditBot()
    bot.run()