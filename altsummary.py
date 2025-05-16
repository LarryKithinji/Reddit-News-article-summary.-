# -*- coding: utf-8 -*-
from sumy.parsers.html import HtmlParser
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

LANGUAGE = "english"
SENTENCES_COUNT = 5

text = """NEW DELHI: The government, after verbally backing the concept of net neutrality for some months, is all set to put it in writing. It is likely to make public this week the telecom departme[...] (etc)"""

def summary(text):
    stemmer = Stemmer(LANGUAGE)
    parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
    summarizer = Summarizer(stemmer)
    summarizer.stop_words = get_stop_words(LANGUAGE)
    short = ""
    for sentence in summarizer(parser.document, SENTENCES_COUNT):
        short = short + ">* " + str(sentence) + "\n\n"
    return short

if __name__ == '__main__':
    print(summary(text))