import praw
import requests
import logging
import time
import json
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Set
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
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
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[
                        logging.FileHandler("reddit_bot.log",
                                            mode="a",
                                            encoding="utf-8"),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)


class Config:
    # Reddit OAuth credentials (use refresh token for persistent authentication)
    REDDIT_CLIENT_ID = "H_0R3y_suLY78pI-mbq-vg"
    REDDIT_CLIENT_SECRET = "gXZ2u71qSbx8P2ltK91wEZ4upgvK0w"
    REDDIT_USER_AGENT = "AfricaVoiceBot/1.0 by u/Old-Star54"
    REDDIT_REFRESH_TOKEN = "143460106421528-Ei3SO1wR3aBlnjRi2cjCmlbgc0Y-rg"
    SUBREDDIT_NAME = "AfricaVoice"
    COMMENT_DELAY = 720  # 12 minutes between comments
    SUBMISSION_DELAY = 90  # 90 seconds between submission checks (reduced from 5 minutes)
    MONITORING_PING_DELAY = 90  # 90 seconds for monitoring ping when no new posts
    MAX_POST_AGE_MINUTES = 5  # Only process posts less than 5 minutes old
    LANGUAGE = "english"
    SENTENCES_COUNT = 4
    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1379376565699219486/S4rbFt_5m4aYtNdCJgRZeleIASCK_1WV8RonVpUvjdv9gwF7k_3viqkSV5oSDJw917lC"
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
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z",
                                           time.gmtime())
            }

            if url:
                embed["url"] = url

            payload = {"embeds": [embed]}

            response = requests.post(self.webhook_url,
                                     json=payload,
                                     timeout=10)
            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
            else:
                logger.warning(
                    f"Discord notification failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")


class ContentExtractor:

    def __init__(self):
        self.scraper = cloudscraper.create_scraper()

    def extract_content(self, url: str) -> Optional[Dict[str, any]]:
        """Extract content using multiple fallback methods."""
        methods = [
            self._try_newspaper_extraction, self._try_selenium_extraction,
            self._try_readability_extraction, self._try_basic_requests
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
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body")))

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
                except Exception as e:
                    logger.debug(f"Error closing driver: {e}")
        return None

    def _try_readability_extraction(self,
                                    url: str) -> Optional[Dict[str, any]]:
        """Try extraction using readability-lxml."""
        try:
            logger.info("Trying readability extraction...")
            headers = {
                "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
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
                "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept":
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
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
            'article', '[role="main"]', '.content', '.article-content',
            '.post-content', '.entry-content', 'main', '#content',
            '.story-body', 'div[data-component="text-block"]'
        ]

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                content = ' '.join(
                    elem.get_text(separator=' ').strip() for elem in elements)
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

        # Patterns to filter out promotional/irrelevant content
        self.filter_patterns = [
            r'subscribe\s+to\s+our\s+newsletter',
            r'click\s+here\s+to\s+learn\s+more', r'advertisement',
            r'sponsored\s+content', r'follow\s+us\s+on\s+social\s+media',
            r'share\s+this\s+article', r'related\s+articles?',
            r'more\s+from\s+this\s+author', r'get\s+our\s+free\s+newsletter',
            r'sign\s+up\s+for\s+updates', r'download\s+our\s+app',
            r'join\s+our\s+community', r'cookie\s+policy', r'privacy\s+policy',
            r'terms\s+of\s+service'
        ]

        # Enhanced promotional/navigation words to avoid in summaries
        self.promotional_words = {
            'subscribe', 'newsletter', 'advertisement', 'sponsored',
            'promotion', 'follow', 'like', 'share', 'tweet', 'facebook',
            'twitter', 'instagram', 'download', 'app', 'mobile', 'website',
            'homepage', 'sitemap', 'cookies', 'privacy', 'terms', 'disclaimer',
            'copyright', 'subscription', 'premium', 'trial', 'billing',
            'payment', 'discount', 'offer', 'deal', 'save', 'upfront',
            'monthly', 'yearly', 'cancel', 'journalism', 'access', 'digital',
            'unlimited', 'expert', 'analysis', 'industry', 'leaders',
            'quality', 'ft', 'financial', 'times'
        }

    def generate_summary(self, content: str) -> Optional[str]:
        """Generate enhanced summary with content filtering and formatting."""
        try:
            # Clean and filter content first
            cleaned_content = self._clean_content(content)

            if not cleaned_content or len(cleaned_content.split()) < 30:
                logger.warning("Content too short after cleaning")
                return "No summary could be extracted from the news article."

            # Use simple sentence splitting instead of NLTK
            import re
            sentences = re.split(r'[.!?]+', cleaned_content)
            sentences = [
                s.strip() for s in sentences
                if s.strip() and len(s.split()) > 5
            ]

            if len(sentences) < 2:
                logger.warning("Not enough quality sentences found")
                return "No summary could be extracted from the news article."

            # Intelligent sentence selection for better summary quality
            selected_sentences = self._select_best_sentences(sentences)

            # Filter and format sentences
            filtered_sentences = self._filter_sentences(selected_sentences)

            if not filtered_sentences:
                logger.warning("No relevant sentences found after filtering")
                return "No summary could be extracted from the news article."

            summary = self._format_summary(filtered_sentences)

            # Enhanced validation
            if not self._is_valid_summary(summary):
                logger.warning("Generated summary failed validation")
                return "No summary could be extracted from the news article."

            return summary
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "No summary could be extracted from the news article."

    def _clean_content(self, content: str) -> str:
        """Remove promotional and irrelevant content with enhanced filtering."""
        import re

        # Enhanced promotional patterns
        enhanced_patterns = [
            r'subscribe\s+to\s+our\s+newsletter',
            r'click\s+here\s+to\s+learn\s+more',
            r'advertisement',
            r'sponsored\s+content',
            r'follow\s+us\s+on\s+social\s+media',
            r'share\s+this\s+article',
            r'related\s+articles?',
            r'more\s+from\s+this\s+author',
            r'get\s+our\s+free\s+newsletter',
            r'sign\s+up\s+for\s+updates',
            r'download\s+our\s+app',
            r'join\s+our\s+community',
            r'cookie\s+policy',
            r'privacy\s+policy',
            r'terms\s+of\s+service',
            r'complete\s+digital\s+access',
            r'quality\s+.*\s+journalism',
            r'pay\s+.*\s+upfront\s+and\s+save',
            r'expert\s+analysis\s+from\s+industry\s+leaders',
            r'subscribe\s+for\s+.*\s+per\s+month',
            r'unlimited\s+access\s+to',
            r'premium\s+subscription',
            r'free\s+trial',
            r'cancel\s+anytime',
            r'billed\s+monthly',
            r'special\s+offer',
            r'limited\s+time\s+offer',
        ]

        # Split into sentences
        sentences = re.split(r'[.!?]+', content)
        clean_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Skip very short sentences (likely fragments)
            if len(sentence.split()) < 5:
                continue

            # Enhanced promotional content detection
            sentence_lower = sentence.lower()

            # Check against enhanced patterns
            if any(
                    re.search(pattern, sentence_lower)
                    for pattern in enhanced_patterns):
                continue

            # Skip sentences with repetitive phrases (3+ word sequences)
            words = sentence_lower.split()
            if self._has_repetitive_phrases(words):
                continue

            # Skip sentences that are mostly promotional/subscription words
            promo_word_count = sum(1 for word in words if any(
                promo in word for promo in self.promotional_words))
            if len(words) > 0 and (promo_word_count /
                                   len(words)) > 0.25:  # Lowered threshold
                continue

            # Skip sentences with excessive capitalization (likely promotional)
            if sum(1 for c in sentence if c.isupper()) > len(sentence) * 0.3:
                continue

            clean_sentences.append(sentence)

        return '. '.join(clean_sentences)

    def _contains_promotional_content(self, text: str) -> bool:
        """Check if text contains promotional patterns."""
        import re

        for pattern in self.filter_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _has_repetitive_phrases(self, words: list) -> bool:
        """Check if sentence contains repetitive phrases (3+ word sequences)."""
        if len(
                words
        ) < 6:  # Need at least 6 words to have repetitive 3-word phrases
            return False

        # Create 3-word phrases
        phrases = []
        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i + 3])
            phrases.append(phrase)

        # Check for duplicates
        unique_phrases = set(phrases)
        return len(phrases) > len(unique_phrases)

    def _filter_sentences(self, sentences) -> list:
        """Filter out low-quality sentences."""
        filtered = []

        for sentence in sentences:
            sentence_str = str(sentence).strip()

            # Skip very short sentences
            if len(sentence_str.split()) < 6:
                continue

            # Skip sentences with promotional content
            if self._contains_promotional_content(sentence_str.lower()):
                continue

            # Skip sentences that are mostly numbers or special characters
            words = sentence_str.split()
            alpha_words = [word for word in words if word.isalpha()]
            if len(alpha_words) < len(
                    words) * 0.6:  # At least 60% should be alphabetic words
                continue

            filtered.append(sentence_str)

        return filtered

    def _select_best_sentences(self, sentences: list) -> list:
        """Intelligently select the best sentences for summary."""
        if len(sentences) <= self.sentence_count:
            return sentences

        # Score sentences based on content quality indicators
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = self._score_sentence(sentence, i, len(sentences))
            scored_sentences.append((sentence, score))

        # Sort by score (highest first)
        scored_sentences.sort(key=lambda x: x[1], reverse=True)

        # Select top sentences
        selected = [
            sentence
            for sentence, score in scored_sentences[:self.sentence_count]
        ]
        return selected

    def _score_sentence(self, sentence: str, position: int,
                        total_sentences: int) -> float:
        """Score a sentence based on content quality indicators."""
        score = 0.0
        words = sentence.lower().split()

        # Position bonus (first few sentences are often important)
        if position < 3:
            score += 0.3
        elif position < total_sentences // 3:
            score += 0.2

        # Length penalty for very long or short sentences
        if 8 <= len(words) <= 25:
            score += 0.2
        elif len(words) < 5 or len(words) > 35:
            score -= 0.3

        # Bonus for sentences with numbers (often factual)
        if any(word.isdigit() or any(char.isdigit() for char in word)
               for word in words):
            score += 0.1

        # Penalty for sentences with too many promotional words
        promo_count = sum(1 for word in words
                          if word in self.promotional_words)
        if promo_count > 0:
            score -= promo_count * 0.2

        # Bonus for sentences with important keywords
        important_keywords = {
            'said', 'reported', 'according', 'announced', 'confirmed',
            'revealed'
        }
        if any(keyword in words for keyword in important_keywords):
            score += 0.15

        return score

    def _is_valid_summary(self, summary: str) -> bool:
        """Validate if the summary meets quality standards."""
        if not summary or len(summary.strip()) < 20:
            return False

        words = summary.lower().split()

        # Check minimum word count
        if len(words) < 15:
            return False

        # Check for excessive promotional content
        promo_count = sum(1 for word in words
                          if word in self.promotional_words)
        if promo_count > len(words) * 0.2:  # More than 20% promotional words
            return False

        # Check for repetitive content
        if self._has_repetitive_phrases(words):
            return False

        # Check for meaningful content (not just filler words)
        meaningful_words = [
            w for w in words if len(w) > 3 and w not in {
                'this', 'that', 'with', 'from', 'they', 'them', 'were', 'been',
                'have', 'will'
            }
        ]
        if len(meaningful_words) < len(words) * 0.5:
            return False

        return True

    def _format_summary(self, sentences: list) -> str:
        """Format sentences into a well-structured summary."""
        if not sentences:
            return ""

        # Ensure proper punctuation and capitalization
        formatted_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()

            # Ensure sentence starts with capital letter
            if sentence and sentence[0].islower():
                sentence = sentence[0].upper() + sentence[1:]

            # Ensure sentence ends with proper punctuation
            if sentence and sentence[-1] not in '.!?':
                sentence += '.'

            formatted_sentences.append(sentence)

        # Join sentences with proper spacing
        summary = ' '.join(formatted_sentences)

        # Clean up any double spaces or punctuation issues
        import re
        summary = re.sub(r'\s+', ' ', summary)  # Multiple spaces to single
        summary = re.sub(r'\.+', '.', summary)  # Multiple periods to single
        summary = re.sub(r'\s+([.!?])', r'\1',
                         summary)  # Remove space before punctuation

        return summary.strip()


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
                logger.info(
                    "No previous comment history found, starting fresh")
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
            refresh_token=Config.REDDIT_REFRESH_TOKEN,
        )

        try:
            me = self.reddit.user.me()
            logger.info(f"Successfully authenticated as: {me.name}")
            self.notifier.send_notification(
                "Bot Started", f"Reddit bot authenticated as {me.name}")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise

    def run(self, subreddit_name: str = None):
        """Main bot loop."""
        if subreddit_name is None:
            subreddit_name = Config.SUBREDDIT_NAME

        logger.info("Starting bot")
        self.notifier.send_notification(
            "Bot Active",
            f"Monitoring r/{subreddit_name} for new submissions (max age: {Config.MAX_POST_AGE_MINUTES} minutes)"
        )

        subreddit = self.reddit.subreddit(subreddit_name)
        logger.info(
            f"Rate limits: {Config.COMMENT_DELAY}s between comments, {Config.SUBMISSION_DELAY}s between checks"
        )
        logger.info(
            f"Only processing posts less than {Config.MAX_POST_AGE_MINUTES} minutes old"
        )

        last_monitoring_ping = time.time()

        while True:
            try:
                processed_any = self._process_new_submissions(subreddit)

                # Send monitoring ping if no new posts were processed and it's been a while
                if not processed_any:
                    current_time = time.time()
                    if current_time - last_monitoring_ping >= Config.MONITORING_PING_DELAY:
                        self._send_monitoring_ping(subreddit_name)
                        last_monitoring_ping = current_time

                logger.info(
                    f"Waiting {Config.SUBMISSION_DELAY} seconds before next submission check"
                )
                time.sleep(Config.SUBMISSION_DELAY)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)

    def _process_new_submissions(self, subreddit):
        """Process new submissions from the subreddit."""
        processed_any = False
        try:
            # Only check the 5 newest posts to reduce load
            for submission in subreddit.new(limit=5):
                # Check if post is too old (older than MAX_POST_AGE_MINUTES)
                if not self._is_post_recent(submission):
                    logger.info(
                        f"Skipping old post (>{Config.MAX_POST_AGE_MINUTES}min): {submission.title}"
                    )
                    continue

                logger.info(
                    f"Evaluating recent post: {submission.title} ({submission.url}) [Age: {self._get_post_age_minutes(submission):.1f}min]"
                )

                # Check if the bot has already commented on this submission
                if self._has_bot_commented(submission):
                    logger.info(
                        f"Bot already commented on submission {submission.id}, skipping"
                    )
                    continue

                if self.history.has_commented(submission.id):
                    logger.info(
                        f"Already commented on submission {submission.id}, skipping"
                    )
                    continue

                if self._should_process_submission(submission):
                    self._process_submission(submission)
                    processed_any = True

        except Exception as e:
            logger.error(f"Error processing submissions: {e}")

        return processed_any

    def _has_bot_commented(self, submission) -> bool:
        """Check if the bot has already commented on the submission."""
        try:
            # Only check top-level comments and limit to first 20 to avoid hanging
            submission.comments.replace_more(
                limit=0)  # Don't expand "more comments"

            bot_username = self.reddit.user.me().name

            # Check only the first 20 top-level comments
            for i, comment in enumerate(submission.comments):
                if i >= 20:  # Limit to prevent hanging
                    break

                if hasattr(
                        comment, 'author'
                ) and comment.author and comment.author.name == bot_username:
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking comments: {e}")
            return False

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
            logger.info(
                f"Processing: '{submission.title}' (ID: {submission.id})")

            extracted = self.extractor.extract_content(submission.url)
            if not extracted:
                logger.warning(
                    f"Content extraction failed for {submission.url}")
                return

            content = extracted['content']
            word_count = extracted['word_count']

            logger.info(f"Extracted {word_count} words from content")

            if word_count < Config.MIN_CONTENT_LENGTH:
                logger.warning(
                    f"Content too short ({word_count} words), skipping")
                return

            summary = self.summarizer.generate_summary(content)
            if not summary:
                logger.warning("Summary generation failed")
                return

            self._post_comment(submission, summary)

        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}",
                         exc_info=True)

    def _post_comment(self, submission, summary: str):
        """Post comment with summary."""
        try:
            # Fetch related Africa news links
            related_news = self._fetch_related_africa_news(
                submission.title, submission.url)

            # Construct the comment with the new format
            comment_text = f"""---

💡 Summary:

> {summary}

---

💡 Related News:

"""
            for news in related_news:
                comment_text += f"🔗”— [{news['title']}]({news['link']})\n\n"

            comment_text += """---

🛠️ This response was automated!"""

            submission.reply(comment_text)
            logger.info(
                f"Comment posted successfully on submission {submission.id}")

            self.history.mark_commented(submission.id)

            self.notifier.send_notification(
                "Comment Posted", f"Posted summary on: {submission.title}",
                f"https://reddit.com{submission.permalink}")

            logger.info(
                f"Waiting {Config.COMMENT_DELAY} seconds before next comment")
            time.sleep(Config.COMMENT_DELAY)

        except Exception as e:
            logger.error(
                f"Failed to post comment on submission {submission.id}: {e}")

    def _fetch_related_africa_news(self, query: str, original_url: str = None):
        """
        Fetch genuinely related African news with relevance filtering and duplicate prevention.
        """
        try:
            # Extract key terms from the query for better search relevance
            key_terms = self._extract_key_terms(query)

            # Create multiple search queries to increase relevance
            search_queries = [
                f"{key_terms} Africa news", f"{key_terms} African",
                f"Africa {key_terms}"
            ]

            all_news_items = []

            for search_query in search_queries:
                base_url = f"https://news.google.com/rss/search?q={requests.utils.quote(search_query)}&hl=en-ZA&gl=ZA&ceid=ZA:en"

                try:
                    response = requests.get(base_url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'xml')

                    for item in soup.find_all(
                            'item')[:10]:  # Get more items for filtering
                        title = item.title.text if item.title else ""
                        link = item.link.text if item.link else ""
                        pub_date = item.pubDate.text if item.pubDate else ""

                        if title and link:
                            all_news_items.append({
                                "title": title,
                                "link": link,
                                "pub_date": pub_date,
                                "search_query": search_query
                            })

                except Exception as e:
                    logger.debug(
                        f"Error with search query '{search_query}': {e}")
                    continue

            # Filter for relevance and remove duplicates
            filtered_news = self._filter_relevant_news(all_news_items, query,
                                                       original_url)

            # Return top 3 most relevant items
            return filtered_news[:3]

        except Exception as e:
            logger.error(f"Error fetching related news: {e}")
            return []

    def _extract_key_terms(self, query: str) -> str:
        """Extract key terms from the query for better search relevance."""
        import re

        # Remove common stop words and non-essential terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'among', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'me', 'him', 'her', 'us', 'them'
        }

        # Extract words and filter
        words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
        key_words = [word for word in words if word not in stop_words]

        # Prioritize important terms (capitals in original, longer words)
        original_words = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', query)
        if original_words:
            key_words = list(
                set(key_words + [word.lower() for word in original_words]))

        return ' '.join(key_words[:5])  # Limit to 5 key terms

    def _filter_relevant_news(self,
                              news_items: list,
                              original_query: str,
                              original_url: str = None) -> list:
        """Filter news items for relevance and remove duplicates."""
        if not news_items:
            return []

        # Extract key terms from original query
        query_terms = set(
            self._extract_key_terms(original_query).lower().split())

        # Normalize the original query title for comparison
        original_title_normalized = self._normalize_title(original_query)

        filtered_items = []
        seen_titles = set()
        seen_domains = set()

        for item in news_items:
            title = item['title']
            link = item['link']

            # Skip duplicate titles (with some fuzzy matching)
            title_normalized = self._normalize_title(title)
            if title_normalized in seen_titles:
                continue

            # Skip if this is the same article being summarized (compare titles)
            if self._is_same_title(title_normalized, original_title_normalized):
                continue

            # Limit articles from the same domain
            domain = self._extract_domain(link)
            if domain in seen_domains and len([
                    x for x in filtered_items
                    if self._extract_domain(x['link']) == domain
            ]) >= 1:
                continue

            # Calculate relevance score
            relevance_score = self._calculate_relevance_score(
                title, query_terms, original_query)

            # Only include if relevance score is above threshold
            if relevance_score >= 0.3:  # 30% relevance threshold
                item['relevance_score'] = relevance_score
                filtered_items.append(item)
                seen_titles.add(title_normalized)
                seen_domains.add(domain)

        # Sort by relevance score (highest first)
        filtered_items.sort(key=lambda x: x['relevance_score'], reverse=True)

        return filtered_items

    def _is_same_article(self, url1: str, url2: str) -> bool:
        """Check if two URLs point to the same article."""
        import re
        from urllib.parse import urlparse, parse_qs

        try:
            # Parse URLs
            parsed1 = urlparse(url1)
            parsed2 = urlparse(url2)

            # Same domain and path
            if parsed1.netloc == parsed2.netloc and parsed1.path == parsed2.path:
                return True

            # Check for Google News redirect URLs
            if 'news.google.com' in parsed1.netloc and 'url' in parse_qs(
                    parsed1.query):
                actual_url1 = parse_qs(parsed1.query)['url'][0]
                return self._is_same_article(actual_url1, url2)

            if 'news.google.com' in parsed2.netloc and 'url' in parse_qs(
                    parsed2.query):
                actual_url2 = parse_qs(parsed2.query)['url'][0]
                return self._is_same_article(url1, actual_url2)

            # Extract article identifiers (common patterns)
            def extract_article_id(url):
                # Common patterns for article IDs
                patterns = [
                    r'/(\d{4}/\d{2}/\d{2})/([^/]+)',  # Date-based URLs
                    r'/article/([^/]+)',  # Article slug
                    r'/news/([^/]+)',  # News slug
                    r'/(\d+)/?$',  # Numeric ID at end
                ]
                for pattern in patterns:
                    match = re.search(pattern, url)
                    if match:
                        return match.groups()
                return None

            id1 = extract_article_id(url1)
            id2 = extract_article_id(url2)

            if id1 and id2 and id1 == id2:
                return True

            return False

        except Exception:
            return False

    def _normalize_title(self, title: str) -> str:
        """Normalize title for duplicate detection."""
        import re

        # Remove common prefixes/suffixes
        title = re.sub(r'^(Breaking:|BREAKING:|Update:|UPDATE:)\s*',
                       '',
                       title,
                       flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*(Reuters|AP|BBC|CNN|News24).*$',
                       '',
                       title,
                       flags=re.IGNORECASE)

        # Convert to lowercase and remove extra whitespace
        title = ' '.join(title.lower().split())

        # Remove punctuation
        title = re.sub(r'[^\w\s]', '', title)

        return title

    def _is_same_title(self, title1: str, title2: str) -> bool:
        """Check if two titles refer to the same article."""
        if not title1 or not title2:
            return False
        
        # Calculate similarity using word overlap
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return False
        
        # Calculate Jaccard similarity (intersection over union)
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0
        
        # Consider titles the same if they have 70% or more word overlap
        return similarity >= 0.7

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc.lower()
        except:
            return ""

    def _calculate_relevance_score(self, title: str, query_terms: set,
                                   original_query: str) -> float:
        """Calculate relevance score between title and query terms."""
        if not title or not query_terms:
            return 0.0

        title_words = set(title.lower().split())

        # Count matching terms
        matching_terms = query_terms.intersection(title_words)
        term_match_score = len(matching_terms) / len(
            query_terms) if query_terms else 0

        # Bonus for Africa-related content
        africa_terms = {
            'africa', 'african', 'continent', 'sahara', 'subsaharan',
            'sub-saharan'
        }
        africa_bonus = 0.2 if africa_terms.intersection(title_words) else 0

        # Penalty for generic news terms that might not be relevant
        generic_terms = {
            'breaking', 'update', 'report', 'news', 'latest', 'today',
            'yesterday'
        }
        generic_penalty = -0.1 if len(
            generic_terms.intersection(title_words)) > 2 else 0

        # Bonus for exact phrase matches
        phrase_bonus = 0.3 if any(term in title.lower()
                                  for term in original_query.lower().split()
                                  if len(term) > 3) else 0

        total_score = term_match_score + africa_bonus + generic_penalty + phrase_bonus

        return max(0.0, min(1.0, total_score))  # Clamp between 0 and 1

    def _is_post_recent(self, submission) -> bool:
        """Check if post is recent enough to process."""
        post_age_minutes = self._get_post_age_minutes(submission)
        return post_age_minutes <= Config.MAX_POST_AGE_MINUTES

    def _get_post_age_minutes(self, submission) -> float:
        """Get the age of a post in minutes."""
        try:
            post_time = datetime.fromtimestamp(submission.created_utc,
                                               tz=timezone.utc)
            current_time = datetime.now(timezone.utc)
            age_seconds = (current_time - post_time).total_seconds()
            return age_seconds / 60.0
        except Exception as e:
            logger.error(f"Error calculating post age: {e}")
            return float('inf')  # Return large number to skip if error

    def _send_monitoring_ping(self, subreddit_name: str):
        """Send a lightweight monitoring ping to keep the bot active."""
        try:
            current_time = datetime.now(timezone.utc).strftime("%H:%M UTC")
            logger.info(
                f"ðŸ“¡ Monitoring ping sent at {current_time} - No new posts to process"
            )

            # Send lightweight Discord notification every few pings to avoid spam
            if hasattr(self, '_ping_count'):
                self._ping_count += 1
            else:
                self._ping_count = 1

            # Only send Discord notification every 10 pings (15 minutes)
            if self._ping_count % 10 == 0:
                self.notifier.send_notification(
                    "Bot Monitoring",
                    f"Bot active and monitoring r/{subreddit_name} - No new posts in last 15 minutes"
                )
        except Exception as e:
            logger.error(f"Error sending monitoring ping: {e}")


if __name__ == "__main__":
    bot = RedditBot()
    bot.run()