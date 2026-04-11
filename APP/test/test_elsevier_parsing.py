import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapping.search import _clean_discovered_url
from scrapping.extract import _normalize_input_url


def test_clean_discovered_url_extracts_elsevier_scopus_endpoint():
    noisy = (
        "https://api.elsevier.com/content/abstract/scopus_id/105029085471"
        "https://api.elsevier.com/content/abstract/scopus_id/105029085471"
        "SCOPUS_ID:1050290854712-s2.0-1050290854711true"
    )
    assert _clean_discovered_url(noisy) == "https://api.elsevier.com/content/abstract/scopus_id/105029085471"


def test_normalize_input_url_extracts_elsevier_scopus_endpoint():
    noisy = (
        "Title: No title URL: https://api.elsevier.com/content/abstract/scopus_id/105029085471 "
        "SCOPUS_ID:1050290854712-s2.0-1050290854711true"
    )
    assert _normalize_input_url(noisy) == "https://api.elsevier.com/content/abstract/scopus_id/105029085471"
