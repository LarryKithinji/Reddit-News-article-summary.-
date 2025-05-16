from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words


LANGUAGE = "english"
SENTENCES_COUNT = 5

TEXT = """NEW DELHI: The government, after verbally backing the concept of net neutrality for some months, is all set to put it in writing. It is likely to make public this week the telecom department's report on the subject, which sources say will back the Centre's stance that the internet should be completely free with equitable access and without any obstruction or prioritization.

The Department of Telecom report - prepared by a team of six officials - is currently with the Prime Minister's Office (PMO), and will form framework for the government policy on 'net neutrality' along with recommendations of the telecom regulator, which are yet to be submitted to DoT. The principle of net neutrality guarantees consumers equal and non-discriminatory access to all data, apps and services on internet, with no discrimination on the basis of tariffs or speed.

"A panel has the taken the views of all the stakeholders before submitting it to the telecom minister. There were a few critical points of debate such as allowing zero rating plans or not. The report will back the government's stand unequivocally," a person familiar with the matter said.
...
Supporters of net neutrality though say any move to regulate content providers will stifle innovation. They add that the security rules proposal indirectly seeks to burden innovative application providers by increasing cost of providing services.

"Do you really want the government to decide which app should be allowed to offer services in the country? Do you think Whatsapp could have grown in this country if it had to take permission from the Indian government?" Pahwa asks."""

def summarize_text(text: str, sentence_count: int = SENTENCES_COUNT) -> str:
    stemmer = Stemmer(LANGUAGE)
    parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
    summarizer = Summarizer(stemmer)
    summarizer.stop_words = get_stop_words(LANGUAGE)

    summary = ""
    for sentence in summarizer(parser.document, sentence_count):
        summary += f"> * {sentence}\n\n"
    return summary

if __name__ == '__main__':
    result = summarize_text(TEXT)
    print(result)