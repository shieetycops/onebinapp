"""AI-tool categories (SPEC_AI.md section 4): coding, data, web, files, devops, search, memory, other.
Matched against GitHub topics first, then repo name + description words; first category in CATEGORY_IDS order wins.
Nothing matched -> 'other'."""
import re

CATEGORY_IDS = ['memory', 'search', 'devops', 'data', 'files', 'web', 'coding', 'other']


def _s(x): return frozenset(x.split())


TOPICS = {
    'memory': _s('memory knowledge-graph long-term-memory vector-database embeddings rag second-brain'),
    'search': _s('search web-search search-engine brave-search tavily exa perplexity'),
    'devops': _s('devops docker kubernetes k8s terraform aws azure gcp cloud ci-cd github-actions monitoring observability sre cloudflare'),
    'data': _s('database sql sqlite postgres postgresql mysql mongodb redis data data-analysis analytics pandas spreadsheet excel bigquery snowflake duckdb'),
    'files': _s('filesystem file-system files pdf documents markdown obsidian notion google-drive notes'),
    'web': _s('browser browser-automation playwright puppeteer scraping web-scraping crawler web web-automation selenium http api'),
    'coding': _s('coding code developer-tools git github gitlab ide vscode debugging testing refactoring code-review programming claude-code codex cursor'),
}
WORDS = {k: _s(v) for k, v in {
    'memory': 'memory memories remember knowledge',
    'search': 'search searching',
    'devops': 'docker kubernetes deploy deployment infrastructure terraform aws azure cloud devops',
    'data': 'database sql sqlite postgres mysql mongodb data analytics csv',
    'files': 'file files filesystem pdf document documents folder',
    'web': 'browser web scrape scraping crawl crawler website playwright puppeteer',
    'coding': 'code coding git github debug test testing review programming developer',
}.items()}


def categorize_ai(topics, name='', desc=''):
    ts = {t.lower() for t in topics or []}
    for cid in CATEGORY_IDS[:-1]:
        if ts & TOPICS[cid]: return cid
    words = set(re.findall(r'[a-z0-9]+', ((name or '') + ' ' + (desc or '')).lower()))
    for cid in CATEGORY_IDS[:-1]:
        if words & WORDS[cid]: return cid
    return 'other'
