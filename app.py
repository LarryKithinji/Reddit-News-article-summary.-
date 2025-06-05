import praw
import requests
import logging
import time
import re
import json
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
import urllib.parse
from urllib.parse import urlparse
from readability import Document  # For readability-lxml fallback
from typing import Set
# Simple tokenizer to replace NLTK dependency
class SimpleTokenizer:
    """A simple tokenizer that splits text into sentences without NLTK dependency."""

    def __init__(self, language="english"):
        self.language = language
        # Common sentence ending patterns
        self.sentence_endings = re.compile(r'[.!?]+\s+')

    def to_sentences(self, text):
        """Split text into sentences using regex patterns."""
        # Clean up the text
        text = text.strip()
        if not text:
            return []

        # Split by sentence endings but keep the endings
        sentences = self.sentence_endings.split(text)

        # Filter out empty sentences and very short ones
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

        return sentences

    def to_words(self, sentence):
        """Split sentence into words."""
        # Simple word tokenization
        words = re.findall(r'\b\w+\b', sentence.lower())
        return words

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

# Configuration class
class Config:
    # Reddit OAuth credentials (use refresh token for persistent authentication)
    REDDIT_CLIENT_ID = "yTCQyCL5ORAtnfbarxOllA"
    REDDIT_CLIENT_SECRET = "nMJw7DFkQlyBeTIC56DUsTvtVPi59g"
    REDDIT_USER_AGENT = "AfricaVoiceBot/1.0 by u/Old-Star54"
    REDDIT_REFRESH_TOKEN = "177086754394813-K-OcOV-73ynFBmvLoJXRPy0kewplzw"
    REDDIT_SUBREDDIT = "AfricaVoice"
    
    # Rate limiting - respect Reddit's API limits
    COMMENT_DELAY = 720  # 12 minutes between comments (conservative)
    SUBMISSION_DELAY = 300  # 5 minutes between submission checks
    REQUEST_DELAY = 180  # 3 minutes between API requests

    # Language and summarization settings
    LANGUAGE = "english"
    SENTENCES_COUNT = 5

    # Percentage-based summary settings
    MIN_SUMMARY_PERCENTAGE = 20  # Minimum 20% of original content
    MAX_SUMMARY_PERCENTAGE = 40  # Maximum 40% of original content

# Comment tracking class
class CommentTracker:
    """Tracks commented posts across sessions and current runtime."""

    def __init__(self, reddit: praw.Reddit, filename="commented_posts.json"):
        self.reddit = reddit
        self.filename = filename
        self.commented_posts: Set[str] = self._load_commented_posts()
        self.session_posts: Set[str] = set()
        self._load_recent_comments_from_reddit()

    def _load_commented_posts(self) -> Set[str]:
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
                return set(data.get('posts', []))
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("No previous comment history found, starting fresh")
            return set()

    def _save_commented_posts(self):
        try:
            data = {'posts': list(self.commented_posts), 'last_updated': time.time()}
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save comment history: {e}")

    def _load_recent_comments_from_reddit(self):
        try:
            two_hours_ago = time.time() - 7200
            user = self.reddit.user.me()
            for comment in self.reddit.redditor(user.name).comments.new(limit=100):
                if comment.created_utc >= two_hours_ago:
                    self.commented_posts.add(comment.submission.id)
        except Exception as e:
            logger.warning(f"Could not fetch recent comments: {e}")

    def has_commented(self, post_id: str) -> bool:
        return post_id in self.commented_posts or post_id in self.session_posts

    def mark_as_commented(self, post_id: str):
        self.commented_posts.add(post_id)
        self.session_posts.add(post_id)
        self._save_commented_posts()
        logger.info(f"Marked post {post_id} as commented") 

class ContentExtractor:

    def extract_content(self, url: str) -> Optional[Dict[str, any]]:
        """
        Extracts main content from a webpage using:
        1. 12ft.io
        2. Original URL (custom BS4)
        3. readability-lxml fallback
        """
        try:
            # Attempt 12ft.io
            logger.info(f"Attempting to extract via 12ft.io: {url}")
            result = self._try_extraction(f"https://12ft.io/{url}")
            if result:
                return result

            # Attempt direct URL
            logger.info("12ft.io failed or content too short, trying original URL")
            result = self._try_extraction(url)
            if result:
                return result

            # Attempt readability-lxml
            logger.info("BS4 fallback failed, trying readability-lxml")
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            doc = Document(response.text)
            html = doc.summary()
            soup = BeautifulSoup(html, 'html.parser')
            content = soup.get_text(separator='\n').strip()

            return self._process_extracted_content(content)

        except Exception as e:
            logger.error(f"Unexpected error in content extraction: {e}")
            return None

    def _try_extraction(self, url: str) -> Optional[Dict[str, any]]:
        """Tries extracting with BeautifulSoup and post-processing."""
        content = self._extract_with_url(url)
        return self._process_extracted_content(content)

    def _extract_with_url(self, url: str) -> Optional[str]:
        """Extracts content from a given URL using BeautifulSoup."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Clean HTML
            for element in soup(["script", "style", "nav", "header", "footer", 
                                 "aside", "form", "button", "input"]):
                element.decompose()

            promo_selectors = [
                '[class*="ad"]', '[class*="promo"]', '[class*="sponsor"]',
                '[class*="newsletter"]', '[class*="subscribe"]', '[class*="social"]',
                '[id*="ad"]', '[id*="promo"]', '[id*="sponsor"]'
            ]
            for selector in promo_selectors:
                for element in soup.select(selector):
                    element.decompose()

            # Extract paragraphs
            paragraphs = soup.find_all('p')
            quality_paragraphs = [
                p.get_text(strip=True) for p in paragraphs
                if len(p.get_text(strip=True)) > 20 and not p.get_text(strip=True).isupper()
            ]

            content = ' '.join(quality_paragraphs)
            return content if len(content) > 100 else None

        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None

    def _process_extracted_content(self, content: Optional[str]) -> Optional[Dict[str, any]]:
        """Cleans, filters, and validates content before packaging."""
        if not content or len(content.split()) < 50:
            return None

        content = self._finalize_content(content)
        if len(content.split()) < 50:
            return None

        return self._prepare_content_data(content)

    def _finalize_content(self, content: str) -> str:
        """Applies full cleaning pipeline to raw content."""
        content = self.remove_promotional_lines(content)
        content = self.clean_content_text(content)
        return content

    def _prepare_content_data(self, content: str) -> Dict[str, any]:
        """Prepare content data with metadata."""
        word_count = len(content.split())
        return {
            'content': content,
            'word_count': word_count,
            'char_count': len(content),
            'estimated_read_time': max(1, word_count // 200)
        }

    def remove_promotional_lines(self, text: str) -> str:
        """Remove promotional and spammy content from text."""
        promo_patterns = [
            r'subscribe\s+(to|for|now)', r'newsletter', r'email\s+list',
            r'join\s+(our|the)\s+(community|list)', r'sign\s+up',
            r'sponsored\s+by', r'advertis(e|ing|ement)', r'promo\s+code',
            r'discount\s+code', r'coupon', r'special\s+offer',
            r'follow\s+us', r'like\s+us', r'share\s+this', r'tweet\s+this',
            r'facebook', r'twitter', r'instagram', r'linkedin',
            r'click\s+here', r'visit\s+our', r'buy\s+now', r'shop\s+now',
            r'learn\s+more', r'get\s+started', r'find\s+out\s+more',
            r'read\s+more', r'see\s+more', r'view\s+more',
            r'partnered\s+with', r'our\s+sponsor', r'brought\s+to\s+you\s+by',
            r'watch\s+(now|more|video)', r'listen\s+to', r'podcast',
            r'free\s+(trial|download)', r'download\s+now',
            r'home\s+page', r'contact\s+us', r'about\s+us', r'privacy\s+policy',
            r'terms\s+of\s+(service|use)', r'cookie\s+policy',
            r'leave\s+a\s+comment', r'what\s+do\s+you\s+think',
            r'tell\s+us\s+what', r'let\s+us\s+know',
            r'limited\s+time', r'act\s+now', r'don\'t\s+miss',
            r'exclusive\s+offer', r'best\s+deal', r'lowest\s+price'
        ]

        lines = text.split('\n')
        filtered_lines = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or len(line_stripped) < 10:
                continue
            if line_stripped.isupper() and len(line_stripped) > 5:
                continue
            punct_ratio = sum(1 for c in line_stripped if c in '!?*@#$%^&+=') / len(line_stripped)
            if punct_ratio > 0.2:
                continue
            is_promotional = any(
                re.search(pattern, line_stripped, re.IGNORECASE) 
                for pattern in promo_patterns
            )
            if not is_promotional:
                filtered_lines.append(line_stripped)

        return '\n'.join(filtered_lines)

    def clean_content_text(self, content: str) -> str:
        """Additional content cleaning beyond promotional removal."""
        content = re.sub(r'\s+', ' ', content)
        artifacts = [
            r'\bjavascript\b', r'\bcookies?\b', r'\bprivacy policy\b',
            r'\bterms of service\b', r'\bterms of use\b', r'\bmenu\b',
            r'\bnavigation\b', r'\bheader\b', r'\bfooter\b', r'\bsidebar\b'
        ]
        for artifact in artifacts:
            content = re.sub(artifact, '', content, flags=re.IGNORECASE)
        content = re.sub(r'@\w+', '', content)
        content = re.sub(r'#\w+', '', content)
        return re.sub(r'\s+', ' ', content).strip()

# Google News extractor class
class GoogleNewsExtractor:
    def __init__(self):
        self.base_url = "https://news.google.com/rss/search"
        
        # Africa-related keywords for filtering
        self.africa_keywords = [
            # African countries
            'nigeria', 'south africa', 'kenya', 'ghana', 'ethiopia', 'egypt', 'morocco', 'algeria', 
            'tunisia', 'libya', 'sudan', 'uganda', 'tanzania', 'zimbabwe', 'botswana', 'namibia',
            'zambia', 'malawi', 'mozambique', 'madagascar', 'cameroon', 'ivory coast', 'senegal',
            'mali', 'burkina faso', 'niger', 'chad', 'central african republic', 'democratic republic congo',
            'republic congo', 'gabon', 'equatorial guinea', 'sao tome', 'cape verde', 'gambia',
            'guinea bissau', 'guinea', 'sierra leone', 'liberia', 'togo', 'benin', 'rwanda',
            'burundi', 'djibouti', 'eritrea', 'somalia', 'comoros', 'mauritius', 'seychelles',
            'lesotho', 'swaziland', 'eswatini', 'angola',
            # General Africa terms
            'africa', 'african', 'sub-saharan', 'west africa', 'east africa', 'north africa', 
            'southern africa', 'central africa', 'african union', 'au summit', 'ecowas', 'sadc',
            # Diaspora terms
            'african diaspora', 'african immigrant', 'african community', 'nigerian diaspora',
            'ghanaian diaspora', 'kenyan diaspora', 'south african diaspora', 'ethiopian diaspora',
            # Major African cities
            'lagos', 'cairo', 'johannesburg', 'cape town', 'nairobi', 'casablanca', 'tunis',
            'algiers', 'accra', 'addis ababa', 'khartoum', 'kampala', 'dar es salaam', 'harare'
        ]

    def get_related_news(self, query: str, exclude_url: str = None, exclude_content: str = None, max_results: int = 3) -> List[Dict[str, str]]:
        """Extract Africa-related news, excluding the original URL and similar content."""
        try:
            # Clean and encode the query, add Africa context
            clean_query = re.sub(r'[^\w\s]', '', query)
            africa_enhanced_query = f"{clean_query} Africa OR African"

            # Construct Google News RSS URL
            params = {
                'q': africa_enhanced_query,
                'hl': 'en-US',
                'gl': 'US',
                'ceid': 'US:en'
            }

            url = f"{self.base_url}?{'&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in params.items()])}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')

            news_links = []
            for item in items:
                title = item.find('title')
                link = item.find('link')
                description = item.find('description')

                if title and link:
                    actual_url = self._extract_actual_url(link.text)
                    title_text = title.text.strip()
                    description_text = description.text.strip() if description else ""

                    # Skip if this is the same as the original submission URL
                    if exclude_url and self._urls_match(actual_url, exclude_url):
                        continue

                    # Skip if URL contains the original domain
                    if exclude_url and self._same_domain(actual_url, exclude_url):
                        continue

                    # Skip if content is too similar to original
                    if exclude_content and self._content_too_similar(title_text, exclude_content):
                        continue

                    # Check if the news item is Africa-related
                    if self._is_africa_related(title_text, description_text):
                        news_links.append({
                            'title': title_text,
                            'url': actual_url
                        })

                        if len(news_links) >= max_results:
                            break

            logger.info(f"Found {len(news_links)} Africa-related news articles")
            return news_links
            
        except Exception as e:
            logger.error(f"Error fetching Google News: {e}")
            return []

    def _content_too_similar(self, title: str, original_content: str) -> bool:
        """Check if news title is too similar to original content."""
        if not original_content:
            return False

        title_words = set(title.lower().split())
        content_words = set(original_content.lower().split()[:50])  # First 50 words

        # Calculate similarity
        if len(title_words) == 0:
            return False

        similarity = len(title_words.intersection(content_words)) / len(title_words)
        return similarity > 0.7  # 70% similarity threshold

    def _is_africa_related(self, title: str, description: str) -> bool:
        """Check if news item is related to Africa or African diaspora."""
        combined_text = f"{title} {description}".lower()

        for keyword in self.africa_keywords:
            if keyword.lower() in combined_text:
                return True

        return False

    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two URLs are essentially the same."""
        try:
            url1_clean = re.sub(r'^https?://(www\.)?', '', url1.lower().strip('/'))
            url2_clean = re.sub(r'^https?://(www\.)?', '', url2.lower().strip('/'))
            return url1_clean == url2_clean
        except:
            return False

    def _same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain."""
        try:
            domain1 = urlparse(url1).netloc.lower().replace('www.', '')
            domain2 = urlparse(url2).netloc.lower().replace('www.', '')
            return domain1 == domain2
        except:
            return False

    def _extract_actual_url(self, google_url: str) -> str:
        """Extract actual URL from Google redirect URL."""
        try:
            if 'url=' in google_url:
                return urllib.parse.unquote(google_url.split('url=')[1].split('&')[0])
            else:
                return google_url
        except:
            return google_url

# Percentage-based Summarizer class
class PercentageSummarizer:
    def __init__(self):
        self.language = Config.LANGUAGE
        self.tokenizer = SimpleTokenizer(self.language)

    def generate_summary(self, content_data: Dict[str, any]) -> Optional[str]:
        """Generate summary based on percentage of original content."""
        try:
            content = content_data['content']
            original_word_count = content_data['word_count']

            # Calculate target word count based on percentage
            min_target_words = int(original_word_count * (Config.MIN_SUMMARY_PERCENTAGE / 100))
            max_target_words = int(original_word_count * (Config.MAX_SUMMARY_PERCENTAGE / 100))

            logger.info(f"Original: {original_word_count} words, Target: {min_target_words}-{max_target_words} words")

            # Use Sumy for initial summarization
            parser = PlaintextParser.from_string(content, self.tokenizer)
            summarizer = LsaSummarizer(Stemmer(self.language))
            summarizer.stop_words = get_stop_words(self.language)

            # Start with estimated sentence count
            estimated_sentences = max(3, min_target_words // 25)  # Rough estimate: 25 words per sentence

            # Generate summary with iterative approach
            summary = self._generate_optimal_summary(
                parser, summarizer, estimated_sentences, min_target_words, max_target_words
            )

            if summary:
                final_word_count = len(summary.split())
                percentage = (final_word_count / original_word_count) * 100
                logger.info(f"Generated summary: {final_word_count} words ({percentage:.1f}% of original)")
                return summary
            else:
                logger.warning("Failed to generate adequate summary")
                return None

        except Exception as e:
            logger.error(f"Error generating percentage-based summary: {e}")
            return None

    def _generate_optimal_summary(self, parser, summarizer, initial_sentences, min_words, max_words):
        """Generate summary with optimal length using iterative approach."""
        best_summary = None
        best_score = float('inf')

        # Try different sentence counts
        for sentence_count in range(max(2, initial_sentences - 2), initial_sentences + 5):
            try:
                sentences = summarizer(parser.document, sentence_count)
                summary = ' '.join(str(sentence) for sentence in sentences)
                summary = self._fix_grammar(summary)

                word_count = len(summary.split())

                # Check if within acceptable range
                if min_words <= word_count <= max_words:
                    return summary

                # Calculate score (prefer closer to target range)
                if word_count < min_words:
                    score = min_words - word_count
                else:
                    score = word_count - max_words

                # Keep track of best summary
                if score < best_score and word_count >= min_words * 0.8:  # Allow 20% flexibility
                    best_score = score
                    best_summary = summary

            except Exception as e:
                logger.warning(f"Error with {sentence_count} sentences: {e}")
                continue

        return best_summary

    def _fix_grammar(self, text: str) -> str:
        """Fix common grammatical errors and punctuation issues in the summary."""
        if not text:
            return text

        # Initial cleanup - fix spacing issues
        text = re.sub(r'\s+', ' ', text).strip()

        # Fix common punctuation spacing issues first
        text = re.sub(r'\s+([.!?,:;])', r'\1', text)  # Remove space before punctuation
        text = re.sub(r'([.!?,:;])\s*([A-Za-z])', r'\1 \2', text)  # Add space after punctuation
        text = re.sub(r'([.!?])\s*([.!?])', r'\1', text)  # Remove duplicate punctuation

        # Fix multiple punctuation marks
        text = re.sub(r'[.]{2,}', '.', text)  # Multiple periods to single
        text = re.sub(r'[!]{2,}', '!', text)  # Multiple exclamations to single
        text = re.sub(r'[?]{2,}', '?', text)  # Multiple questions to single

        # Fix comma spacing
        text = re.sub(r'\s*,\s*', ', ', text)  # Standardize comma spacing
        text = re.sub(r',\s*,', ',', text)  # Remove duplicate commas

        # Fix semicolon and colon spacing
        text = re.sub(r'\s*;\s*', '; ', text)  # Standardize semicolon spacing
        text = re.sub(r'\s*:\s*', ': ', text)  # Standardize colon spacing

        # Split into sentences for proper capitalization
        sentences = re.split(r'(?<=[.!?])\s+', text)
        fixed_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                # Capitalize first letter of each sentence
                sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()

                # Fix specific punctuation issues within sentences
                sentence = self._fix_sentence_punctuation(sentence)

                fixed_sentences.append(sentence)

        # Join sentences properly
        result = ' '.join(fixed_sentences)

        # Final cleanup
        result = re.sub(r'\s+', ' ', result).strip()  # Final space cleanup

        # Ensure proper ending punctuation
        if result and not result.endswith(('.', '!', '?')):
            # Check if the last word suggests it should be a question
            if result.lower().strip().split()[-1] in ['who', 'what', 'when', 'where', 'why', 'how']:
                result += '?'
            else:
                result += '.'

        # Fix any remaining spacing issues around punctuation
        result = re.sub(r'\s+([.!?,:;])', r'\1', result)
        result = re.sub(r'([.!?,:;])([A-Za-z])', r'\1 \2', result)

        return result

    def _fix_sentence_punctuation(self, sentence: str) -> str:
        """Fix punctuation issues within a single sentence."""
        # Fix apostrophes and contractions
        sentence = re.sub(r"\s+'([sStTdDmMrReEvV])\b", r"'\1", sentence)  # Fix spaced contractions
        sentence = re.sub(r"\b([a-zA-Z]+)\s+'\s*([sStT])\b", r"\1'\2", sentence)  # Fix possessives

        # Fix quotation marks
        sentence = re.sub(r'\s+"([^"]*?)"\s*', r' "\1" ', sentence)  # Standard quote spacing
        sentence = re.sub(r"(\w)\s+'", r"\1'", sentence)  # Fix spaced single quotes

        # Fix parentheses spacing
        sentence = re.sub(r'\s*\(\s*', ' (', sentence)
        sentence = re.sub(r'\s*\)\s*', ') ', sentence)
        sentence = re.sub(r'^\s*\(\s*', '(', sentence)  # Start of sentence

        # Fix hyphen and dash spacing
        sentence = re.sub(r'\s*-\s*', '-', sentence)  # Remove spaces around hyphens in compound words
        sentence = re.sub(r'(\w)\s*--\s*(\w)', r'\1 - \2', sentence)  # Fix em dashes

        # Fix ellipsis
        sentence = re.sub(r'\.{3,}', '...', sentence)
        sentence = re.sub(r'\s*\.\.\.\s*', '... ', sentence)

        # Fix numbers and decimals
        sentence = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', sentence)  # Fix decimal points
        sentence = re.sub(r'(\d)\s*,\s*(\d{3})', r'\1,\2', sentence)  # Fix number formatting

        # Clean up any double spaces created
        sentence = re.sub(r'\s+', ' ', sentence)

        return sentence.strip()

# Reddit Bot class with proper OAuth and duplicate prevention
class RedditBot:
    def __init__(self):
        self.extractor = ContentExtractor()
        self.summarizer = PercentageSummarizer()
        self.news_extractor = GoogleNewsExtractor()
        self.comment_tracker = CommentTracker()
        self.reddit = None
        self.last_submission_time = 0
        self._initialize_reddit_connection()

    def _initialize_reddit_connection(self):
        """Initialize Reddit connection with proper OAuth authentication."""
        try:
       # Use refresh token for persistent authentication
            self.reddit = praw.Reddit(
            client_id=Config.REDDIT_CLIENT_ID,
            client_secret=Config.REDDIT_CLIENT_SECRET,
            refresh_token=Config.REDDIT_REFRESH_TOKEN,
            user_agent=Config.REDDIT_USER_AGENT
        )
       
       # Verify authentication
            me = self.reddit.user.me()
            logger.info(f"Successfully authenticated as: {me.name}")

        except Exception as e:
            logger.error(f"Reddit authentication failed: {str(e)}")
            raise

    def run(self, subreddit_name: str):
        """Main loop to monitor the subreddit and process new submissions."""
        logger.info(f"Starting AfricaVoice bot for subreddit: {subreddit_name}")
        subreddit = self.reddit.subreddit(subreddit_name)

        while True:
            try:
                processed_count = 0
                for submission in subreddit.new(limit=10):
                    if self.comment_tracker.has_commented(submission.id):
                      continue

                # Skip if too old (older than one hour)
                if time.time() - submission.created_utc > 3600:
                    continue

                # Process the submission
                if self.process_submission(submission):
                    processed_count += 1
                    # Mark as commented even if we didn't comment to avoid reprocessing
                    self.comment_tracker.mark_as_commented(submission.id)

                    # Rate limiting between submissions
                    time.sleep(Config.SUBMISSION_DELAY)

                    # Limit processing to avoid overwhelming
                    if processed_count >= 3:
                        break

            # Sleep before next check
               logger.info(f"Processed {processed_count} submissions. Sleeping for {Config.REQUEST_DELAY} seconds...")
            time.sleep(Config.REQUEST_DELAY)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
            time.sleep(300)  # 5 minute cooldown on error

    def process_submission(self, submission) -> bool:
        """Process a single submission with improved content extraction and summarization."""
        try:
            logger.info(f"Processing: '{submission.title}' (ID: {submission.id})")

            # Check if already commented on this submission
            if self.comment_tracker.has_commented(submission.id):
                logger.info(f"Already commented on submission {submission.id}, skipping")
                return False

            # Skip if no valid URLwhile True:
            if not hasattr(submission, 'url') or not submission.url:
                logger.info(f"Skipping non-link submission {submission.id}")
                return False

            # Skip self-referential Reddit URLs
            if 'reddit.com' in submission.url:
                logger.info(f"Skipping reddit URL {submission.id}")
                return False

            # Extract article content
            content_data = self.extractor.extract_content(submission.url)
            summary = None

            if content_data:
                logger.info(f"Extracted {content_data['word_count']} words from article")
                if content_data['word_count'] >= 100:
                    summary = self.summarizer.generate_summary(content_data)
                else:
                    logger.info("Content too short to summarize")
            else:
                logger.info("No content could be extracted from the article")

            # Fetch related news regardless of summary
            related_news = self.news_extractor.get_related_news(
                submission.title,
                submission.url,
                content_data['content'] if content_data else None
            )

            # Only post if there's meaningful content
               # ✅ PROPER INDENT HERE
            if summary or related_news:
                if not self.comment_tracker.has_commented(submission.id):
                    self._post_comment(submission, summary, related_news)
                    self.comment_tracker.mark_as_commented(submission.id)
                    logger.info(f"Commented on submission {submission.id}")
                    return True
                else:
                    logger.info(f"Already commented on {submission.id} at posting stage, skipping")
                    return False
            else:
                logger.info(f"Skipping submission {submission.id} - no suitable content found")
                return False

        except Exception as e:
            logger.error(f"Failed to process submission {submission.id}: {e}")
            return False

 
    def _post_comment(self, submission, summary: Optional[str], related_news: List[Dict[str, str]]):
        """Post a comment with improved formatting and rate limiting."""
        try:
            formatted_comment = self._format_comment(submission.title, summary, related_news)

            # Respect rate limits
            time.sleep(Config.REQUEST_DELAY)

            submission.reply(formatted_comment)
            logger.info(f"Successfully posted comment on submission {submission.id}")

            # Wait before next comment
            time.sleep(Config.COMMENT_DELAY)

        except Exception as e:
            logger.error(f"Failed to post comment on submission {submission.id}: {e}")
            raise  # Re-raise to handle in calling function

    def _format_comment(self, title: str, summary: Optional[str], related_news: List[Dict[str, str]]) -> str:
        """Format the comment with improved structure."""
        comment_parts = []

        # Header
        comment_parts.append(f'📰 **TLDR for:** "{title}"')
        comment_parts.append("")
        comment_parts.append("---")
        comment_parts.append("")

        # Summary section
        if summary:
            comment_parts.append("💡 **Article Summary:**")
            comment_parts.append("")
            comment_parts.append(f"> {summary}")
            comment_parts.append("")
        else:
            comment_parts.append("💡 **Article Summary:**")
            comment_parts.append("")
            comment_parts.append("> Unable to extract and summarize content from the original article.")
            comment_parts.append("")

        comment_parts.append("---")
        comment_parts.append("")

        # Related news section
        comment_parts.append("📰 **Related Africa News:**")
        comment_parts.append("")

        if related_news:
            for news_item in related_news:
                comment_parts.append(f"🔗 [{news_item['title']}]({news_item['url']})")
                comment_parts.append("")
        else:
            comment_parts.append("🔗 No additional Africa-related news found at this time.")
            comment_parts.append("")

        comment_parts.append("---")
        comment_parts.append("")
        comment_parts.append("🤖 **^Powered ^by ^caffeine, ^code, ^and ^the ^spirit ^of ^Africa. ^This ^was ^your ^TL;DR ^from ^r/AfricaVoice.**")

        return '\n'.join(comment_parts)

# Run the bot
if __name__ == "__main__":
    try:
        bot = RedditBot()
        bot.run("AfricaVoice")
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)