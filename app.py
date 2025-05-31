# Reddit Bot Debugging and Fixes

import praw
import logging
import sys
import os
from typing import Optional

# Enhanced logging for debugging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more verbose output
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("reddit_bot_debug.log", mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DebugConfig:
    # Make sure these are properly set
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "u-lbcuDEyhW2KaUWCBG8MQ")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "CIsbZsyRF1Ympv029sqL4s6JbMNvCw")
    REDDIT_USER_AGENT = "AfricaVoiceBot/1.0 by Old-Star54"
    REDDIT_REFRESH_TOKEN = os.getenv("REDDIT_REFRESH_TOKEN")  # Must be set!
    REDDIT_REDIRECT_URI = "http://localhost:8080"

class RedditBotDebugger:
    """Debug version of the Reddit bot with extensive logging and error checking."""
    
    def __init__(self):
        self.reddit = None
        self.debug_checks()
    
    def debug_checks(self):
        """Run comprehensive debug checks."""
        logger.info("=" * 60)
        logger.info("REDDIT BOT DEBUGGING SESSION STARTED")
        logger.info("=" * 60)
        
        # Check 1: Configuration
        self.check_configuration()
        
        # Check 2: Dependencies
        self.check_dependencies()
        
        # Check 3: Reddit Authentication
        self.check_reddit_auth()
        
        # Check 4: Subreddit Access
        self.check_subreddit_access()
        
        # Check 5: Bot Permissions
        self.check_bot_permissions()
        
        logger.info("=" * 60)
        logger.info("DEBUG CHECKS COMPLETED")
        logger.info("=" * 60)
    
    def check_configuration(self):
        """Check if all required configuration is present."""
        logger.info("🔧 CHECKING CONFIGURATION...")
        
        config_issues = []
        
        # Check required fields
        required_fields = {
            'REDDIT_CLIENT_ID': DebugConfig.REDDIT_CLIENT_ID,
            'REDDIT_CLIENT_SECRET': DebugConfig.REDDIT_CLIENT_SECRET,
            'REDDIT_USER_AGENT': DebugConfig.REDDIT_USER_AGENT,
            'REDDIT_REFRESH_TOKEN': DebugConfig.REDDIT_REFRESH_TOKEN
        }
        
        for field_name, field_value in required_fields.items():
            if not field_value:
                config_issues.append(f"❌ {field_name} is missing or empty")
                logger.error(f"Missing: {field_name}")
            else:
                logger.info(f"✅ {field_name}: {'*' * min(len(str(field_value)), 10)}...")
        
        # Check client ID format
        if DebugConfig.REDDIT_CLIENT_ID and len(DebugConfig.REDDIT_CLIENT_ID) < 10:
            config_issues.append("❌ REDDIT_CLIENT_ID appears to be invalid (too short)")
        
        # Check client secret format
        if DebugConfig.REDDIT_CLIENT_SECRET and len(DebugConfig.REDDIT_CLIENT_SECRET) < 20:
            config_issues.append("❌ REDDIT_CLIENT_SECRET appears to be invalid (too short)")
        
        if config_issues:
            logger.error("CONFIGURATION ISSUES FOUND:")
            for issue in config_issues:
                logger.error(issue)
            return False
        else:
            logger.info("✅ Configuration looks good!")
            return True
    
    def check_dependencies(self):
        """Check if all required dependencies are installed."""
        logger.info("📦 CHECKING DEPENDENCIES...")
        
        required_packages = [
            'praw', 'requests', 'beautifulsoup4', 'sumy', 'lxml'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                if package == 'beautifulsoup4':
                    import bs4
                    logger.info(f"✅ BeautifulSoup4: {bs4.__version__}")
                elif package == 'praw':
                    import praw
                    logger.info(f"✅ PRAW: {praw.__version__}")
                elif package == 'requests':
                    import requests
                    logger.info(f"✅ Requests: {requests.__version__}")
                elif package == 'sumy':
                    import sumy
                    logger.info(f"✅ Sumy: Available")
                elif package == 'lxml':
                    import lxml
                    logger.info(f"✅ lxml: Available")
                else:
                    __import__(package)
                    logger.info(f"✅ {package}: Available")
            except ImportError:
                missing_packages.append(package)
                logger.error(f"❌ {package}: Missing")
        
        if missing_packages:
            logger.error(f"MISSING PACKAGES: {missing_packages}")
            logger.error("Install with: pip install " + " ".join(missing_packages))
            return False
        else:
            logger.info("✅ All dependencies are installed!")
            return True
    
    def check_reddit_auth(self):
        """Test Reddit authentication."""
        logger.info("🔐 CHECKING REDDIT AUTHENTICATION...")
        
        if not DebugConfig.REDDIT_REFRESH_TOKEN:
            logger.error("❌ No refresh token provided!")
            logger.error("You need to complete OAuth setup first.")
            self.show_oauth_setup_instructions()
            return False
        
        try:
            # Test with refresh token
            self.reddit = praw.Reddit(
                client_id=DebugConfig.REDDIT_CLIENT_ID,
                client_secret=DebugConfig.REDDIT_CLIENT_SECRET,
                user_agent=DebugConfig.REDDIT_USER_AGENT,
                refresh_token=DebugConfig.REDDIT_REFRESH_TOKEN
            )
            
            # Test authentication
            me = self.reddit.user.me()
            logger.info(f"✅ Successfully authenticated as: {me.name}")
            logger.info(f"✅ Account created: {me.created_utc}")
            logger.info(f"✅ Comment karma: {me.comment_karma}")
            logger.info(f"✅ Link karma: {me.link_karma}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            
            # Common authentication errors
            if "invalid_grant" in str(e).lower():
                logger.error("🔧 FIX: Your refresh token is invalid or expired. Re-run OAuth setup.")
            elif "unauthorized_client" in str(e).lower():
                logger.error("🔧 FIX: Your client ID or secret is incorrect.")
            elif "invalid_client" in str(e).lower():
                logger.error("🔧 FIX: Check your Reddit app configuration.")
            
            return False
    
    def check_subreddit_access(self):
        """Check if bot can access the target subreddit."""
        logger.info("📍 CHECKING SUBREDDIT ACCESS...")
        
        if not self.reddit:
            logger.error("❌ Cannot check subreddit - not authenticated")
            return False
        
        try:
            subreddit = self.reddit.subreddit("AfricaVoice")
            
            # Test basic access
            logger.info(f"✅ Subreddit found: r/{subreddit.display_name}")
            logger.info(f"✅ Subscribers: {subreddit.subscribers}")
            logger.info(f"✅ Description: {subreddit.public_description[:100]}...")
            
            # Test if we can read submissions
            submissions = list(subreddit.new(limit=5))
            logger.info(f"✅ Can read submissions: {len(submissions)} found")
            
            for i, submission in enumerate(submissions[:3]):
                logger.info(f"   {i+1}. {submission.title[:50]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Subreddit access failed: {str(e)}")
            
            if "private" in str(e).lower():
                logger.error("🔧 FIX: r/AfricaVoice might be private. Check subreddit settings.")
            elif "banned" in str(e).lower():
                logger.error("🔧 FIX: Your account might be banned from this subreddit.")
            elif "not found" in str(e).lower():
                logger.error("🔧 FIX: Subreddit r/AfricaVoice might not exist.")
            
            return False
    
    def check_bot_permissions(self):
        """Check if bot has necessary permissions."""
        logger.info("🔑 CHECKING BOT PERMISSIONS...")
        
        if not self.reddit:
            logger.error("❌ Cannot check permissions - not authenticated")
            return False
        
        try:
            subreddit = self.reddit.subreddit("AfricaVoice")
            
            # Try to check if we can comment (this is a read operation)
            # We'll try to get a submission and see if commenting would be possible
            submissions = list(subreddit.new(limit=1))
            
            if submissions:
                submission = submissions[0]
                logger.info(f"✅ Can access submissions for commenting")
                logger.info(f"✅ Test submission: {submission.title[:50]}...")
                
                # Check if submission allows comments
                if submission.locked:
                    logger.warning("⚠️  Test submission is locked")
                else:
                    logger.info("✅ Test submission allows comments")
                
                # Check if subreddit is restricted
                if subreddit.subreddit_type == "restricted":
                    logger.warning("⚠️  Subreddit is restricted - check if your account can post")
                elif subreddit.subreddit_type == "private":
                    logger.warning("⚠️  Subreddit is private")
                else:
                    logger.info("✅ Subreddit allows public participation")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Permission check failed: {str(e)}")
            return False
    
    def show_oauth_setup_instructions(self):
        """Show detailed OAuth setup instructions."""
        logger.info("")
        logger.info("🔧 OAUTH SETUP REQUIRED:")
        logger.info("1. Go to https://www.reddit.com/prefs/apps")
        logger.info("2. Click 'Create App' or 'Create Another App'")
        logger.info("3. Choose 'script' as the app type")
        logger.info("4. Set redirect URI to: http://localhost:8080")
        logger.info("5. Note down your client ID (under the app name)")
        logger.info("6. Note down your client secret")
        logger.info("")
        logger.info("Then run this OAuth setup code:")
        print("""
# OAuth Setup Code
from reddit_bot import RedditOAuth

oauth = RedditOAuth()
auth_url = oauth.get_authorization_url()
print(f"Visit: {auth_url}")

# After visiting URL and getting the code:
auth_code = input("Enter authorization code: ")
refresh_token, access_token = oauth.get_refresh_token(auth_code)
print(f"Your refresh token: {refresh_token}")

# Set this in your environment:
# export REDDIT_REFRESH_TOKEN="your_refresh_token_here"
        """)
    
    def test_content_extraction(self, test_url: str = "https://www.bbc.com/news"):
        """Test the content extraction functionality."""
        logger.info(f"🌐 TESTING CONTENT EXTRACTION with: {test_url}")
        
        try:
            from your_original_bot_file import ContentExtractor  # Adjust import
            extractor = ContentExtractor()
            content = extractor.extract_content(test_url)
            
            if content:
                logger.info(f"✅ Content extracted: {len(content)} characters")
                logger.info(f"✅ Sample: {content[:200]}...")
                return True
            else:
                logger.error("❌ No content extracted")
                return False
                
        except Exception as e:
            logger.error(f"❌ Content extraction failed: {str(e)}")
            return False
    
    def test_summarization(self, test_text: str = None):
        """Test the summarization functionality."""
        logger.info("📝 TESTING SUMMARIZATION...")
        
        if not test_text:
            test_text = """
            This is a test article about African development. The continent of Africa 
            is experiencing rapid growth in technology and innovation. Many countries 
            are investing in renewable energy and sustainable development. Nigeria, 
            Kenya, and South Africa are leading the way in fintech innovations. 
            The African Union continues to promote economic integration across the 
            continent. Mobile banking and digital payments are transforming how 
            people conduct business across Africa.
            """
        
        try:
            from your_original_bot_file import SumySummarizer  # Adjust import
            summarizer = SumySummarizer()
            summary = summarizer.generate_summary(test_text)
            
            if summary:
                logger.info(f"✅ Summary generated: {len(summary.split())} words")
                logger.info(f"✅ Summary: {summary}")
                return True
            else:
                logger.error("❌ No summary generated")
                return False
                
        except Exception as e:
            logger.error(f"❌ Summarization failed: {str(e)}")
            return False

# Quick diagnostic runner
def run_full_diagnostic():
    """Run all diagnostic checks."""
    debugger = RedditBotDebugger()
    
    # Additional tests
    logger.info("\n" + "=" * 60)
    logger.info("RUNNING ADDITIONAL TESTS")
    logger.info("=" * 60)
    
    # Test content extraction
    debugger.test_content_extraction()
    
    # Test summarization
    debugger.test_summarization()
    
    logger.info("\n" + "=" * 60)
    logger.info("DIAGNOSTIC COMPLETE - Check the logs above for issues")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_full_diagnostic()