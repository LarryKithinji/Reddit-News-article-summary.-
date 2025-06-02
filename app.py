import praw
import requests
import logging
import time
import re
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
    REDDIT_CLIENT_ID = "p4SHQ57gs2X_bMtaARiJvw"
    REDDIT_CLIENT_SECRET = "PVwX9RTdLj99l1lU9LkvPTEUNmotyQ"
    REDDIT_REFRESH_TOKEN = "G9kwcz2DS6pV2a76uNobRV9EQZjYKA"  # Replace with your actual refresh token
    REDDIT_USER_AGENT = "AfricaVoiceBot by u/Beginning_Item_9587"
    COMMENT_DELAY = 300  # 5 minutes between comments (increased for rate limits)
    SUBMISSION_DELAY = 120  # 2 minutes between submission checks (increased for rate limits)
    LANGUAGE = "english"  # Language for Sumy summarizer
    SENTENCES_COUNT = 4  # Number of sentences for summary
    # Liberal summary length thresholds for complete summaries
    MIN_SUMMARY_WORDS = 80  # Minimum words (reduced from 100)
    MAX_SUMMARY_WORDS = 150  # Maximum words (increased from 110)

# Content extractor class
class ContentExtractor:
    def extract_content(self, url: str) -> Optional[str]:
        """Extracts main content from a webpage using BeautifulSoup."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract main content by focusing on paragraphs
                paragraphs = soup.find_all('p')
                content = ' '.join(p.get_text(strip=True) for p in paragraphs)

                # Validate extracted content length
                if len(content) > 100:
                    return content
                else:
                    logger.warning(f"Content too short after parsing: {len(content)} characters")
                    return None
            else:
                logger.warning(f"Failed to fetch content. Status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching or parsing content: {e}")
            return None

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
            'algiers', 'accra', 'addis ababa', 'khartoum', 'kampala', 'dar es salaam', 'harare',
            'gaborone', 'windhoek', 'lusaka', 'maputo', 'antananarivo', 'yaounde', 'abidjan',
            'dakar', 'bamako', 'ouagadougou', 'niamey', 'ndjamena', 'bangui', 'kinshasa',
            'brazzaville', 'libreville', 'malabo', 'praia', 'banjul', 'bissau', 'conakry',
            'freetown', 'monrovia', 'lome', 'porto novo', 'kigali', 'bujumbura', 'djibouti city',
            'asmara', 'mogadishu', 'moroni', 'port louis', 'victoria', 'maseru', 'mbabane',
            'luanda'
        ]
    
    def get_related_news(self, query: str, exclude_url: str = None, max_results: int = 2) -> List[Dict[str, str]]:
        """Extract Africa-related news from Google News RSS, excluding the original URL."""
        try:
            # Clean and encode the query, add Africa context
            clean_query = re.sub(r'[^\w\s]', '', query)
            # Enhance query with Africa-related terms for better filtering
            africa_enhanced_query = f"{clean_query} Africa OR African"
            encoded_query = urllib.parse.quote(africa_enhanced_query)
            
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
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')
                
                news_links = []
                for item in items:
                    title = item.find('title')
                    link = item.find('link')
                    description = item.find('description')
                    
                    if title and link:
                        # Extract actual URL from Google redirect
                        actual_url = self._extract_actual_url(link.text)
                        
                        # Skip if this is the same as the original submission URL
                        if exclude_url and self._urls_match(actual_url, exclude_url):
                            continue
                            
                        # Skip if URL contains the original domain to avoid duplicates
                        if exclude_url and self._same_domain(actual_url, exclude_url):
                            continue
                        
                        # Check if the news item is Africa-related
                        title_text = title.text.strip()
                        description_text = description.text.strip() if description else ""
                        
                        if self._is_africa_related(title_text, description_text):
                            news_links.append({
                                'title': title_text,
                                'url': actual_url
                            })
                            
                            # Stop when we have enough results
                            if len(news_links) >= max_results:
                                break
                
                return news_links
            else:
                logger.warning(f"Failed to fetch Google News. Status code: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching Google News: {e}")
            return []
    
    def _is_africa_related(self, title: str, description: str) -> bool:
        """Check if news item is related to Africa or African diaspora."""
        # Combine title and description for checking
        combined_text = f"{title} {description}".lower()
        
        # Check against Africa keywords
        for keyword in self.africa_keywords:
            if keyword.lower() in combined_text:
                return True
        
        return False
    
    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two URLs are essentially the same."""
        try:
            # Normalize URLs for comparison
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
            # Google News URLs often contain the actual URL as a parameter
            if 'url=' in google_url:
                return urllib.parse.unquote(google_url.split('url=')[1].split('&')[0])
            else:
                return google_url
        except:
            return google_url

# Sumy Summarizer class
class SumySummarizer:
    def __init__(self):
        self.language = Config.LANGUAGE
        self.sentence_count = Config.SENTENCES_COUNT
        self.tokenizer = SimpleTokenizer(self.language)

    def generate_summary(self, content: str) -> Optional[str]:
        """Generates a concise summary using Sumy with custom tokenizer and liberal length requirements."""
        try:
            # Clean content to remove promotional text and ads
            cleaned_content = self._clean_content(content)
            
            # Use our custom tokenizer instead of NLTK
            parser = PlaintextParser.from_string(cleaned_content, self.tokenizer)
            summarizer = LsaSummarizer(Stemmer(self.language))
            summarizer.stop_words = get_stop_words(self.language)

            # Start with more sentences to reach target word count
            initial_sentence_count = 5
            sentences = summarizer(parser.document, initial_sentence_count)
            summary = ' '.join(str(sentence) for sentence in sentences)

            # Adjust summary length with liberal thresholds for complete summaries
            summary = self._adjust_summary_length(summary, cleaned_content)

            if summary and len(summary.split()) >= Config.MIN_SUMMARY_WORDS:
                return summary
            else:
                logger.warning("Summary generation failed or too short.")
                return None
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None

    def _clean_content(self, content: str) -> str:
        """Remove promotional content, spam, and ads from the text."""
        # Comprehensive list of promotional and spam phrases to remove
        promotional_phrases = [
            # Newsletter and subscription prompts
            r'subscribe to our newsletter',
            r'sign up for our newsletter',
            r'join our mailing list',
            r'get our newsletter',
            r'subscribe now',
            r'sign up today',
            
            # Social media promotions
            r'follow us on',
            r'like us on facebook',
            r'follow on twitter',
            r'follow on instagram',
            r'connect with us',
            r'find us on',
            r'@\w+',  # Remove @mentions
            r'#\w+',  # Remove hashtags
            
            # Sharing and engagement prompts
            r'share this article',
            r'share on social media',
            r'share with friends',
            r'tell your friends',
            r'spread the word',
            r'like and share',
            r'retweet',
            r'share on facebook',
            r'share on twitter',
            
            # Website and traffic driving
            r'read more at',
            r'visit our website',
            r'check out our website',
            r'go to our website',
            r'visit us at',
            r'more information at',
            r'full story at',
            r'continue reading at',
            r'click here',
            r'learn more',
            r'find out more',
            
            # Advertisement and sponsored content
            r'advertisement',
            r'sponsored content',
            r'sponsored by',
            r'brought to you by',
            r'in partnership with',
            r'paid promotion',
            r'affiliate link',
            r'promo code',
            r'discount code',
            
            # Author and publication info
            r'about the author',
            r'author bio',
            r'writer bio',
            r'contact the author',
            r'email the author',
            
            # Related content and navigation
            r'related articles',
            r'you might also like',
            r'recommended reading',
            r'similar posts',
            r'trending now',
            r'popular posts',
            r'most read',
            r'editor\'s pick',
            
            # Comments and engagement
            r'leave a comment',
            r'comment below',
            r'what do you think',
            r'tell us your thoughts',
            r'join the discussion',
            r'start a conversation',
            
            # App and download prompts
            r'download our app',
            r'get the app',
            r'mobile app',
            r'available on app store',
            r'google play',
            
            # Email and contact
            r'contact us',
            r'email us',
            r'send us an email',
            r'get in touch',
            
            # Copyright and legal
            r'all rights reserved',
            r'copyright',
            r'terms of service',
            r'privacy policy',
            r'disclaimer',
            
            # Donation and support
            r'donate',
            r'support us',
            r'become a patron',
            r'contribute',
            r'help us',
            
            # Event and webinar promotions
            r'register now',
            r'sign up for',
            r'join our webinar',
            r'attend our event',
            r'rsvp',
            
            # Product and service promotions
            r'buy now',
            r'purchase',
            r'order now',
            r'get yours today',
            r'limited time offer',
            r'sale ends',
            r'discount',
            r'free trial',
            r'money back guarantee'
        ]
        
        cleaned = content
        for phrase in promotional_phrases:
            cleaned = re.sub(phrase, '', cleaned, flags=re.IGNORECASE)
        
        # Remove URLs (more comprehensive)
        cleaned = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', cleaned)
        cleaned = re.sub(r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),])+', '', cleaned)
        
        # Remove email addresses
        cleaned = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', cleaned)
        
        # Remove phone numbers
        cleaned = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '', cleaned)
        cleaned = re.sub(r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '', cleaned)
        
        # Remove social media handles
        cleaned = re.sub(r'@[A-Za-z0-9_]+', '', cleaned)
        
        # Remove excessive punctuation used in spam
        cleaned = re.sub(r'[!]{2,}', '!', cleaned)
        cleaned = re.sub(r'[?]{2,}', '?', cleaned)
        cleaned = re.sub(r'[.]{3,}', '...', cleaned)
        
        # Remove promotional punctuation patterns
        cleaned = re.sub(r'[*]{2,}', '', cleaned)  # Remove multiple asterisks
        cleaned = re.sub(r'[=]{2,}', '', cleaned)  # Remove multiple equals signs
        cleaned = re.sub(r'[-]{3,}', '', cleaned)  # Remove multiple dashes
        
        # Remove lines that are likely promotional (short lines with promotional keywords)
        lines = cleaned.split('\n')
        filtered_lines = []
        for line in lines:
            line = line.strip()
            if len(line) > 20:  # Keep substantial content
                # Check if line is likely promotional
                promo_indicators = ['follow', 'subscribe', 'click', 'visit', 'share', 'like', 'comment', 'download']
                if not any(indicator in line.lower() for indicator in promo_indicators):
                    filtered_lines.append(line)
            elif len(line) > 50:  # Keep longer lines even if they might have promo words
                filtered_lines.append(line)
        
        cleaned = ' '.join(filtered_lines)
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Remove sentences that are likely promotional (end with promotional calls to action)
        sentences = re.split(r'[.!?]+', cleaned)
        filtered_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 15:
                # Check if sentence ends with promotional language
                promo_endings = ['today', 'now', 'here', 'more', 'us', 'website', 'link', 'below']
                words = sentence.lower().split()
                if not (len(words) < 8 and any(ending in words[-2:] for ending in promo_endings)):
                    filtered_sentences.append(sentence)
        
        cleaned = '. '.join(filtered_sentences)
        if cleaned and not cleaned.endswith('.'):
            cleaned += '.'
            
        return cleaned

    def _adjust_summary_length(self, summary: str, original_content: str) -> str:
        """Adjust summary to be complete with liberal length requirements and avoid mid-sentence cuts."""
        words = summary.split()
        word_count = len(words)
        
        # Check if summary is within acceptable range
        if Config.MIN_SUMMARY_WORDS <= word_count <= Config.MAX_SUMMARY_WORDS:
            return self._fix_grammar(summary)
        elif word_count < Config.MIN_SUMMARY_WORDS:
            # Try to get more content by increasing sentence count
            try:
                parser = PlaintextParser.from_string(original_content, self.tokenizer)
                summarizer = LsaSummarizer(Stemmer(self.language))
                summarizer.stop_words = get_stop_words(self.language)
                
                # Gradually increase sentence count to get more words
                for sentence_count in [6, 7, 8, 9, 10]:
                    sentences = summarizer(parser.document, sentence_count)
                    extended_summary = ' '.join(str(sentence) for sentence in sentences)
                    extended_words = extended_summary.split()
                    
                    if len(extended_words) >= Config.MIN_SUMMARY_WORDS:
                        # Check if we need to trim, but ensure complete sentences
                        if len(extended_words) > Config.MAX_SUMMARY_WORDS:
                            final_summary = self._trim_to_complete_sentences(extended_summary, Config.MAX_SUMMARY_WORDS)
                        else:
                            final_summary = extended_summary
                        return self._fix_grammar(final_summary)
                
                # If we still don't have enough words, return what we have
                return self._fix_grammar(summary)
            except:
                return self._fix_grammar(summary)
        else:
            # Trim to complete sentences within MAX_SUMMARY_WORDS
            trimmed_summary = self._trim_to_complete_sentences(summary, Config.MAX_SUMMARY_WORDS)
            return self._fix_grammar(trimmed_summary)

    def _trim_to_complete_sentences(self, text: str, max_words: int) -> str:
        """Trim text to complete sentences within the word limit."""
        words = text.split()
        if len(words) <= max_words:
            return text
        
        # Find the last complete sentence within the word limit
        truncated_text = ' '.join(words[:max_words])
        
        # Find the last sentence ending before the word limit
        sentence_endings = ['.', '!', '?']
        last_sentence_end = -1
        
        for i in range(len(truncated_text) - 1, -1, -1):
            if truncated_text[i] in sentence_endings:
                # Make sure this isn't an abbreviation or decimal
                if i > 0 and truncated_text[i-1].isalpha():
                    last_sentence_end = i
                    break
        
        if last_sentence_end > 0:
            # Return text up to the last complete sentence
            complete_sentence_text = truncated_text[:last_sentence_end + 1]
            # Ensure we haven't made it too short
            if len(complete_sentence_text.split()) >= Config.MIN_SUMMARY_WORDS * 0.8:  # Allow 20% flexibility
                return complete_sentence_text
        
        # If we can't find a good sentence break, return the original truncated text
        # but try to end at a natural break point
        truncated_text = ' '.join(words[:max_words])
        
        # Look for natural break points (commas, semicolons) near the end
        for i in range(len(truncated_text) - 1, max(0, len(truncated_text) - 50), -1):
            if truncated_text[i] in [',', ';']:
                potential_text = truncated_text[:i + 1]
                if len(potential_text.split()) >= Config.MIN_SUMMARY_WORDS * 0.9:
                    return potential_text
        
        return truncated_text
    
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

# Reddit Bot class
class RedditBot:
    def __init__(self):
        self.extractor = ContentExtractor()
        self.summarizer = SumySummarizer()
        self.news_extractor = GoogleNewsExtractor()
        
        # Use refresh token authentication (no repeated login/logout)
        self.reddit = praw.Reddit(
            client_id=Config.REDDIT_CLIENT_ID,
            client_secret=Config.REDDIT_CLIENT_SECRET,
            refresh_token=Config.REDDIT_REFRESH_TOKEN,
            user_agent=Config.REDDIT_USER_AGENT
        )
        
        self.last_submission_time = time.time()  # Keep track of the latest processed submission time
        self.request_count = 0  # Track API requests for rate limiting
        self.last_request_time = time.time()

        # Authentication check (one-time verification)
        try:
            me = self.reddit.user.me()
            logger.info(f"Successfully authenticated as: {me.name}")
            logger.info("Using refresh token authentication - no repeated logins required")
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            logger.error("Please ensure your refresh token is valid and not expired")

    def _respect_rate_limits(self):
        """Implement intelligent rate limiting to respect Reddit's API limits."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        # Reddit allows 60 requests per minute for authenticated users
        # We'll be more conservative: max 30 requests per minute
        if self.request_count >= 30:
            if time_since_last_request < 60:
                sleep_time = 60 - time_since_last_request
                logger.info(f"Rate limit approaching. Sleeping for {sleep_time:.1f} seconds")
                time.sleep(sleep_time)
            self.request_count = 0
            self.last_request_time = time.time()
        
        self.request_count += 1
        self.last_request_time = current_time

    def run(self, subreddit_name: str):
        """Main loop to monitor the subreddit and process new submissions."""
        logger.info(f"Starting bot for subreddit: {subreddit_name}")
        logger.info(f"Rate limits: {Config.COMMENT_DELAY}s between comments, {Config.SUBMISSION_DELAY}s between checks")
        
        subreddit = self.reddit.subreddit(subreddit_name)
        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:
                self._respect_rate_limits()
                
                for submission in subreddit.new(limit=10):
                    if submission.created_utc > self.last_submission_time:
                        self._process_submission(submission)
                        self.last_submission_time = submission.created_utc
                        
                        # Sleep between submissions to respect rate limits
                        logger.info(f"Waiting {Config.SUBMISSION_DELAY} seconds before next submission check")
                        time.sleep(Config.SUBMISSION_DELAY)
                
                consecutive_errors = 0  # Reset error counter on successful loop
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in main loop (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical("Too many consecutive errors. Stopping bot.")
                    break
                
                # Exponential backoff for errors
                sleep_time = min(300, 60 * (2 ** consecutive_errors))  # Max 5 minutes
                logger.info(f"Sleeping for {sleep_time} seconds before retry")
                time.sleep(sleep_time)

    def _process_submission(self, submission):
        """Processes a single submission, extracts content, and posts a summary."""
        try:
            logger.info(f"Processing submission: {submission.title} (ID: {submission.id})")
            
            # Extract content from the submission URL
            content = self.extractor.extract_content(submission.url)
            summary = None
            
            if content:
                logger.info(f"Extracted content of length: {len(content)} characters")
                summary = self.summarizer.generate_summary(content)
            
            # Get related Africa-focused news (excluding the original submission URL)
            related_news = self.news_extractor.get_related_news(submission.title, submission.url)
            
            # Post comment if we have summary or related news
            if summary or related_news:
                if summary:
                    word_count = len(summary.split())
                    logger.info(f"Generated summary with {word_count} words: {summary[:60]}...")
                else:
                    logger.info("No content extracted, but found related news")
                    
                self._post_comment(submission, summary, related_news)
            else:
                logger.warning("Both summary generation and Africa-related news extraction failed")
                
        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}", exc_info=True)

    def _post_comment(self, submission, summary: Optional[str], related_news: List[Dict[str, str]]):
        """Posts a comment on the submission with the generated summary and related news."""
        try:
            # Respect rate limits before posting
            self._respect_rate_limits()
            
            # Format the comment according to the specified template
            formatted_comment = self._format_comment(submission.title, summary, related_news)
            
            submission.reply(formatted_comment)
            logger.info(f"Comment posted successfully on submission {submission.id}")
            
            # Extended delay between comments to respect rate limits
            logger.info(f"Waiting {Config.COMMENT_DELAY} seconds before next comment (rate limit compliance)")
            time.sleep(Config.COMMENT_DELAY)
            
        except Exception as e:
            logger.error(f"Failed to post comment on submission {submission.id}: {e}")
            # If comment fails due to rate limiting, wait longer
            if "rate limit" in str(e).lower():
                logger.warning("Rate limit detected, extending delay")
                time.sleep(Config.COMMENT_DELAY * 2)

    def _format_comment(self, title: str, summary: Optional[str], related_news: List[Dict[str, str]]) -> str:
        """Format the comment according to the specified template."""
        
        # Build the comment parts
        comment_parts = []
        
        # Header
        comment_parts.append(f'📰 **Summary for:** "{title}"')
        comment_parts.append("")  # Empty line
        comment_parts.append("---")
        comment_parts.append("")
        
        # Summary section (if available)
        if summary:
            comment_parts.append("💡 **Summary:**")
            comment_parts.append("")
            comment_parts.append(f"> {summary}")
            comment_parts.append("")
            comment_parts.append("")
        else:
            comment_parts.append("💡 **Summary:**")
            comment_parts.append("")
            comment_parts.append("> No content could be extracted from the original link for summarization.")
            comment_parts.append("")
            comment_parts.append("")
        
        comment_parts.append("---")
        comment_parts.append("")
        
        # Related news section
        comment_parts.append("📰 **Related News:**")
        comment_parts.append("")
        
        if related_news:
            for news_item in related_news:
                comment_parts.append(f"🔗 [{news_item['title']}]({news_item['url']})")
                comment_parts.append("")
                comment_parts.append("")
        else:
            comment_parts.append("🔗 No Africa-related news sources found at this time.")
            comment_parts.append("")
            comment_parts.append("")
        
        comment_parts.append("---")
        comment_parts.append("")
        comment_parts.append("🛠️ **This is a bot for r/AfricaVoice!**")
        
        return '\n'.join(comment_parts)

# Run the bot
if __name__ == "__main__":
    bot = RedditBot()
    bot.run("AfricaVoice")