import praw
import requests
from newspaper import Article
import textwrap
import os
import time
import argparse
from dotenv import load_dotenv
import logging
import traceback
from transformers import pipeline

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("summarizer.log"), logging.StreamHandler()]
)
logger = logging.getLogger("Reddit News Summarizer")

# --- Load environment variables ---
load_dotenv()

# --- Global summarizer model ---
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# --- Reddit client setup ---
def setup_reddit_client():
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD"),
            user_agent=os.getenv("REDDIT_USER_AGENT", "NewsArticleSummarizer v1.0")
        )
        logger.info(f"Authenticated as {reddit.user.me()}")
        return reddit
    except Exception as e:
        logger.error(f"Failed to authenticate with Reddit:\n{traceback.format_exc()}")
        raise
# --- Subreddits to monitor 
def main():
    subreddit_name = "AfricaVoice"  # hardcoded subreddit
    monitor = True  # set to True to monitor continuously

    if monitor:
        logger.info(f"Monitoring r/{subreddit_name}...")
        process_new_submissions(subreddit_name)
    else:
        logger.info(f"Running one-time for r/{subreddit_name}...")
        # one-time processing logic...

# --- Article extraction ---
def extract_article_content(url):
    try:
        article = Article(url)
        article.download()
        article.parse()

        if len(article.text) < 100:
            logger.warning(f"Article too short ({len(article.text)} characters). Might be poorly extracted.")
        
        return {
            "title": article.title,
            "text": article.text,
            "authors": article.authors,
            "publish_date": article.publish_date,
            "top_image": article.top_image
        }
    except Exception as e:
        logger.error(f"Error extracting article from {url}:\n{traceback.format_exc()}")
        return None

# --- Summarization ---
def summarize_text(text, max_length=150, min_length=40):
    try:
        max_chunk_size = 1024
        chunks = textwrap.wrap(text, max_chunk_size)
        summaries = []

        for chunk in chunks:
            if len(chunk) < 50:
                continue
            result = summarizer(chunk, max_length=max_length, min_length=min_length, do_sample=False)
            if result:
                summaries.append(result[0]['summary_text'])

        final_summary = " ".join(summaries)
        if len(final_summary) > 9500:
            final_summary = final_summary[:9500] + "..."

        return final_summary
    except Exception as e:
        logger.error(f"Failed to summarize text:\n{traceback.format_exc()}")
        return "Error generating summary."

# --- Comment formatting ---
def format_reddit_comment(article_data, summary):
    comment = f"# {article_data['title']}\n\n"

    if article_data.get('authors'):
        comment += f"**Authors:** {', '.join(article_data['authors'])}\n\n"

    if article_data.get('publish_date'):
        try:
            comment += f"**Published:** {article_data['publish_date'].strftime('%Y-%m-%d')}\n\n"
        except Exception:
            pass

    comment += "## Summary\n\n"
    comment += summary + "\n\n"
    comment += "---\n"
    comment += "*This summary was automatically generated. I am a bot.*"

    return comment

# --- Process submissions ---
def process_new_submissions(subreddit_name, processed_ids_file="processed_ids.txt"):
    processed_ids = set()
    if os.path.exists(processed_ids_file):
        with open(processed_ids_file, "r") as f:
            processed_ids = set(line.strip() for line in f)

    reddit = setup_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)

    logger.info(f"Monitoring r/{subreddit_name} for new submissions...")

    for submission in subreddit.stream.submissions(skip_existing=True):
        if submission.id in processed_ids or submission.is_self:
            continue

        url = submission.url
        if any(ext in url for ext in ['.com/', '.org/', '.net/', '.gov/', '.edu/']):
            logger.info(f"Processing: {submission.title} - {url}")
            article_data = extract_article_content(url)

            if not article_data or not article_data['text']:
                logger.warning(f"Failed to extract content from {url}")
                continue

            summary = summarize_text(article_data['text'])
            comment_text = format_reddit_comment(article_data, summary)

            try:
                submission.reply(comment_text)
                logger.info(f"Comment posted to: {submission.title}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error posting comment:\n{traceback.format_exc()}")

        processed_ids.add(submission.id)
        with open(processed_ids_file, "a") as f:
            f.write(f"{submission.id}\n")

# --- Main function ---
def main():
    parser = argparse.ArgumentParser(description='Reddit News Article Summarizer')
    parser.add_argument('--subreddit', '-s', type=str, required=True, help='Subreddit name (without the r/)')
    parser.add_argument('--monitor', '-m', action='store_true', help='Continuously monitor subreddit')

    args = parser.parse_args()

    if args.monitor:
        logger.info(f"Continuous monitoring mode for r/{args.subreddit}")
        try:
            process_new_submissions(args.subreddit)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Exiting...")
        except Exception as e:
            logger.error(f"Monitoring failed:\n{traceback.format_exc()}")
    else:
        logger.info(f"One-time check for r/{args.subreddit}")
        reddit = setup_reddit_client()
        subreddit = reddit.subreddit(args.subreddit)
        latest = list(subreddit.new(limit=1))

        if latest:
            submission = latest[0]
            if not submission.is_self and any(ext in submission.url for ext in ['.com/', '.org/', '.net/', '.gov/', '.edu/']):
                logger.info(f"Processing: {submission.title} - {submission.url}")
                article_data = extract_article_content(submission.url)
                if article_data and article_data['text']:
                    summary = summarize_text(article_data['text'])
                    comment_text = format_reddit_comment(article_data, summary)
                    try:
                        submission.reply(comment_text)
                        logger.info(f"Comment posted to: {submission.title}")
                    except Exception as e:
                        logger.error(f"Failed to post comment:\n{traceback.format_exc()}")
        logger.info("Finished one-time run.")

# --- Run script ---
if __name__ == "__main__":
    main()