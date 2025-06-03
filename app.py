import praw
import requests
import logging
import time
import re
import sys
import traceback
import asyncio
import aiohttp
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
import urllib.parse

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
    REDDIT_CLIENT_ID = "H_0R3y_suLY78pI-mbq-vg"
    REDDIT_CLIENT_SECRET = "gXZ2u71qSbx8P2ltK91wEZ4upgvK0w"
    REDDIT_USER_AGENT = "AfricaVoiceBot/1.0 by u/Old-Star54"
    REDDIT_REFRESH_TOKEN = "143460106421528-zgtWnZmgXa1zwCNFUq1E-7Seh7epoQ"
    
    
    # Rate limiting - respect Reddit's API limits
    COMMENT_DELAY = 720  # 3 minutes between comments (conservative)
    SUBMISSION_DELAY = 270  # 1.5 minutes between submission checks
    REQUEST_DELAY = 180 # 180 seconds between API requests
    
    # Language and summarization settings
    LANGUAGE = "english"
    SENTENCES_COUNT = 5
    
    # Percentage-based summary settings
    MIN_SUMMARY_PERCENTAGE = 20  # Minimum 20% of original content
    MAX_SUMMARY_PERCENTAGE = 40  # Maximum 40% of original content

# Content extractor class

class ContentExtractor:
    def __init__(self):
        self.spam_patterns = [
            # Social media promotions
            r'follow us on (twitter|facebook|instagram|linkedin|tiktok)',
            r'like and subscribe',
            r'share this (post|article|story)',
            r'@\w+',  # Twitter handles
            r'#\w+',  # Hashtags

            # Newsletter and subscription spam
            r'subscribe to our newsletter',
            r'sign up for (our|free|weekly|daily)',
            r'get our (free|weekly|daily) newsletter',
            r'join our mailing list',

            # Advertisement indicators
            r'sponsored by',
            r'advertisement',
            r'promoted content',
            r'paid partnership',
            r'affiliate link',

            # Call-to-action spam
            r'click here',
            r'read more at',
            r'visit our website',
            r'learn more about',
            r'contact us (at|for)',

            # Footer/header spam
            r'about the author',
            r'related articles',
            r'trending now',
            r'popular posts',
            r'you might also like',
            r'more from',

            # Cookie and privacy notices
            r'we use cookies',
            r'privacy policy',
            r'terms of service',
            r'cookie policy'
        ]

    def extract_content(self, url):
        try:
            if not self._is_valid_url(url):
                logger.error(f"Invalid URL: {url}")
                return None

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }

            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                for element in soup(["script", "style", "nav", "header", "footer", "aside",
                                     "noscript", "iframe", "form", "button"]):
                    element.decompose()

                content = self._extract_with_multiple_strategies(soup)

                if not content:
                    logger.warning(f"No content found using any strategy for {url}")
                    return None

                cleaned_content = self._remove_spam_content(content)

                if len(cleaned_content) > 50:
                    word_count = len(cleaned_content.split())
                    return {
                        'content': cleaned_content,
                        'word_count': word_count,
                        'char_count': len(cleaned_content),
                        'url': url
                    }
                else:
                    logger.warning(f"Content too short after cleaning: {len(cleaned_content)} characters from {url}")
                    return None
            else:
                logger.warning(f"Failed to fetch content. Status code: {response.status_code} for {url}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting content from {url}: {e}")
            return None

    def _is_valid_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def _extract_with_multiple_strategies(self, soup):
        article_selectors = [
            'article',
            '[role="main"]',
            'main',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.content',
            '.story-body',
            '.article-body'
        ]

        for selector in article_selectors:
            container = soup.select_one(selector)
            if container:
                content = self._extract_text_from_container(container)
                if len(content) > 100:
                    logger.info(f"Content extracted using selector: {selector}")
                    return content

        content_paragraphs = soup.find_all(['p', 'div'], class_=lambda x: x and any(
            keyword in str(x).lower() for keyword in ['content', 'article', 'story', 'text', 'body', 'post']
        ))

        if content_paragraphs:
            content = ' '.join(p.get_text(strip=True) for p in content_paragraphs)
            if len(content) > 100:
                logger.info("Content extracted using content-class paragraphs")
                return content

        all_paragraphs = soup.find_all('p')
        if all_paragraphs:
            substantial_paragraphs = [p for p in all_paragraphs if len(p.get_text(strip=True)) > 30]
            if substantial_paragraphs:
                content = ' '.join(p.get_text(strip=True) for p in substantial_paragraphs)
                if len(content) > 100:
                    logger.info("Content extracted using substantial paragraphs")
                    return content

        body = soup.find('body')
        if body:
            for elem in body.find_all(['nav', 'aside', 'header', 'footer', 'form', 'button']):
                elem.decompose()

            content = body.get_text(strip=True)
            if len(content) > 100:
                logger.info("Content extracted using body fallback")
                return content

        return ""

    def _extract_text_from_container(self, container):
        for elem in container.find_all(['nav', 'aside', 'header', 'footer', 'form', 'button', 'script', 'style']):
            elem.decompose()
        return container.get_text(strip=True)

    def _remove_spam_content(self, content):
        if not content:
            return ""

        cleaned = content

        for pattern in self.spam_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\,]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', cleaned)
        cleaned = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        sentences = [s.strip() for s in cleaned.split('.') if s.strip()]
        meaningful_sentences = []
        seen_sentences = set()

        for sentence in sentences:
            if len(sentence) > 15 and sentence.lower() not in seen_sentences:
                meaningful_sentences.append(sentence)
                seen_sentences.add(sentence.lower())

        result = '. '.join(meaningful_sentences)

        if result and not result.endswith(('.', '!', '?')):
            result += '.'

        return result
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
            if response.status_code == 200:
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
            else:
                logger.warning(f"Failed to fetch Google News. Status code: {response.status_code}")
                return []
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
        return similarity > 0.7  # 40% similarity threshold
    
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
            from urllib.parse import urlparse
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


# Reddit Bot class with proper OAuth
class RedditBot:
    def __init__(self):
        self.extractor = ContentExtractor()
        self.summarizer = PercentageSummarizer()
        self.news_extractor = GoogleNewsExtractor()
        self.reddit = None
        self.last_submission_time = time.time()
        self._initialize_reddit_connection()

    def _initialize_reddit_connection(self):
        """Initialize Reddit connection with proper OAuth authentication."""
        try:
            if Config.REDDIT_REFRESH_TOKEN:
                # Use refresh token for persistent authentication (preferred)
                self.reddit = praw.Reddit(
                    client_id=Config.REDDIT_CLIENT_ID,
                    client_secret=Config.REDDIT_CLIENT_SECRET,
                    refresh_token=Config.REDDIT_REFRESH_TOKEN,
                    user_agent=Config.REDDIT_USER_AGENT
                )
                logger.info("Authenticated using refresh token")
            else:
                # Fallback to username/password (will generate refresh token)
                self.reddit = praw.Reddit(
                    client_id=Config.REDDIT_CLIENT_ID,
                    client_secret=Config.REDDIT_CLIENT_SECRET,
                    username=Config.REDDIT_USERNAME,
                    password=Config.REDDIT_PASSWORD,
                    user_agent=Config.REDDIT_USER_AGENT
                )
                logger.info("Authenticated using username/password")
                
                # Get and save refresh token for future use
                try:
                    refresh_token = self.reddit.auth.refresh_token
                    logger.info(f"Save this refresh token for future use: {refresh_token}")
                except:
                    logger.warning("Could not retrieve refresh token")

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
                # Process new submissions
                for submission in subreddit.new(limit=5):  # Reduced limit for rate limiting
                    if submission.created_utc > self.last_submission_time:
                        self._process_submission(submission)
                        self.last_submission_time = submission.created_utc
                        time.sleep(Config.SUBMISSION_DELAY)
                
                # Sleep before next check
                time.sleep(Config.REQUEST_DELAY)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(300)  # 5 minute cooldown on error

    def _process_submission(self, submission):
        """Process a single submission with improved content extraction and summarization."""
        try:
            logger.info(f"Processing: '{submission.title}' (ID: {submission.id})")
            
            # Extract content with metadata
            content_data = self.extractor.extract_content(submission.url)
            summary = None
            
            if content_data:
                logger.info(f"Extracted {content_data['word_count']} words from article")
                summary = self.summarizer.generate_summary(content_data)
            else:
                logger.info("No content could be extracted from the article")
            
            # Get related Africa-focused news
            related_news = self.news_extractor.get_related_news(
                submission.title, 
                submission.url, 
                content_data['content'] if content_data else None
            )
            
            # Only post if we have meaningful content
            if summary or related_news:
                self._post_comment(submission, summary, related_news)
            else:
                logger.info(f"Skipping submission {submission.id} - no suitable content found")
                
        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}", exc_info=True)

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

    def _format_comment(self, title: str, summary: Optional[str], related_news: List[Dict[str, str]]) -> str:
        """Format the comment with improved structure."""
        comment_parts = []
        
        # Header
        comment_parts.append(f'📰 **Summary for:** "{title}"')
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
        comment_parts.append("🤖 **AfricaVoice Bot** | Powered by AI summarization")
        
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