import re
from os import path
from typing import Any

import pdfplumber
from nltk import FreqDist
from nltk.corpus import names, stopwords
from nltk.stem.snowball import SnowballStemmer
from nltk.tokenize import word_tokenize
from textblob import TextBlob
from textblob.inflect import singularize

from scrape.textanalyzer import AnalysisResult, TextAnalyser

STOP_WORDS: set[str] = {*stopwords.words("english")}

NAME_WORDS: set[str] = {*names.words()}

stemmer = SnowballStemmer("english", ignore_stopwords=True)


def unpack_txt_files(txtfile: str):
    """unpacks_txt_files takes a txt_file containing indended words.

    Args:
        wordset ([type]): [description]
        __encoding (str, optional): [description]. Defaults to "utf-8".

    Returns:
        set[str]: a set of words
    """
    with open(txtfile, encoding="utf8") as _iowrapper:
        textlines = _iowrapper.readlines()
        _unstemmed = [word.strip().strip("\n").lower() for word in textlines]
        return {stemmer.stem(word) for word in _unstemmed}


def guess_doi(path_name: str) -> str:
    """Guesses the digital identifier for the paper based on the filename"""
    basename: str = path.basename(path_name)
    doi = basename[7:-4]
    return f"{doi[:7]}/{doi[7:]}"


def compute_filtered_tokens(text: list[str]) -> set[str]:
    """Takes a lowercase string, now removed of its non-alphanumeric characters.
    It returns (as a list comprehension) a parsed and tokenized
    version of the text, with stopwords and names removed.
    """
    word_tokens = word_tokenize("\n".join(text))
    return {w for w in word_tokens if w not in STOP_WORDS & NAME_WORDS}


def most_common_words(word_set: set[str], n: int) -> list[tuple[str, int]]:
    """most_common_words _summary_

    Args:
        word_set (set[str]): _description_
        n (int): _description_

    Returns:
        list[tuple[str, int]]: _description_
    """
    return FreqDist(word_set).most_common(n)


class PDFScraper(TextAnalyser):
    """PDFScraper _summary_

    Args:
        Scraper (_type_): _description_
    """

    def __init__(
        self, target_path, bycatch_path, research_path, digi_path, solutions_path
    ):
        self.target_words = unpack_txt_files(target_path)
        self.bycatch_words = unpack_txt_files(bycatch_path)
        self.research_words = unpack_txt_files(research_path)
        self.tech_words = unpack_txt_files(digi_path)
        self.solutions_words = unpack_txt_files(solutions_path)

    def analyze(self, text_query: str) -> AnalysisResult:
        """analyze _summary_

        Args:
            text_query (str): _description_

        Returns:
            AnalysisResult: _description_
        """
        preprints: list[str] = []
        with pdfplumber.open(text_query) as study:
            pages: list[Any] = study.pages
            study_length: int = len(pages)
            pages_to_check: list[Any] = [*pages][:study_length]
            for page_number, page in enumerate(pages_to_check):
                page: str = pages[page_number].extract_text(
                    x_tolerance=3, y_tolerance=3
                )
                print(
                    f"[sciscraper]: Processing Page {page_number} of {study_length-1} | {text_query}...",
                    end="\r",
                )
                preprints.append(
                    page
                )  # Each page's string gets appended to preprint []

            manuscripts = [str(preprint).strip().lower() for preprint in preprints]
            # The preprints are stripped of extraneous characters and all made lower case.
            postprints = [re.sub(r"\W+", " ", manuscript) for manuscript in manuscripts]
            # The ensuing manuscripts are stripped of lingering whitespace and non-alphanumeric characters.
            all_words = compute_filtered_tokens(postprints)

            doi = guess_doi(text_query)

            tech_overlap = self.tech_words.intersection(all_words)
            solution_overlap = self.solutions_words.intersection(all_words)
            target_overlap = self.target_words.intersection(all_words)
            bycatch_overlap = self.bycatch_words.intersection(all_words)
            research_overlap = self.research_words.intersection(all_words)

            wordscore = len(target_overlap) - len(bycatch_overlap)
            mode_words = most_common_words(all_words, 5)
            research = most_common_words(research_overlap, 3)
            tech_freq = most_common_words(tech_overlap, 3)
            solution = most_common_words(solution_overlap, 3)

            return AnalysisResult(
                wordscore,
                mode_words,
                research,
                solution,
                tech_freq,
                digital_object_id=doi,
            )


class PaperSummarizer(TextAnalyser):
    """PDFScraper _summary_

    Args:
        Scraper (_type_): _description_
    """

    def __init__(
        self,
        target_path: str,
        bycatch_path: str,
        research_path: str,
        digi_path: str,
        solutions_path: str,
    ):
        self.target_words = unpack_txt_files(target_path)
        self.bycatch_words = unpack_txt_files(bycatch_path)
        self.research_words = unpack_txt_files(research_path)
        self.tech_words = unpack_txt_files(digi_path)
        self.solutions_words = unpack_txt_files(solutions_path)

    def analyze(self, text_query: str) -> AnalysisResult:
        """analyze _summary_

        Args:
            text_query (str): _description_

        Returns:
            AnalysisResult: _description_
        """

        blob = TextBlob(text_query.lower())
        all_words = [
            stemmer.stem(word)
            for word in blob.words
            if word not in STOP_WORDS and NAME_WORDS
        ]
        tech_overlap = self.tech_words.intersection(all_words)
        solution_overlap = self.solutions_words.intersection(all_words)
        target_overlap = self.target_words.intersection(all_words)
        bycatch_overlap = self.bycatch_words.intersection(all_words)
        research_overlap = self.research_words.intersection(all_words)

        wordscore = (
            len(target_overlap) + len(solution_overlap) + len(tech_overlap)
        ) - (len(bycatch_overlap) * 3)

        target_freq = most_common_words(target_overlap, 4)
        mode_words = most_common_words(all_words, 4)
        research = most_common_words(research_overlap, 4)
        tech_freq = most_common_words(tech_overlap, 4)
        solution = most_common_words(solution_overlap, 4)
        pos_matches = len([match for match in target_freq if match[1] >= 5])
        neg_matches = len([match for match in target_freq if match[1] <= -5])
        print(f"There are {pos_matches} promising papers.\n")
        print(f"At least {neg_matches} papers seem irrelevant.\n")

        return AnalysisResult(
            wordscore=wordscore,
            matching_terms=target_freq,
            mode_words=mode_words,
            research=research,
            solution=solution,
            tech=tech_freq,
        )
