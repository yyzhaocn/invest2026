# Chapter 16: NLP and LLM Foundations

## Core Idea
The text-analytics ladder for finance: raw text → tokens → vocabulary → numerical representations (bag-of-words, TF-IDF, dense embeddings) → classical classifiers → transformers/self-attention → pretrained LLMs and RAG workflows — with evaluation, robustness, and limitation awareness.

## Frameworks Introduced
- **Tokenization pipeline**: lowercase → strip non-alphanumerics (keep numbers/tickers) → split; build sorted vocab + token→id mapping; model-specific tokenizers for pretrained transformers.
- **Numerical representations ladder**: bag-of-words (counts) → TF-IDF (term frequency × inverse document frequency) → dense embeddings (contextual, from pretrained models).
- **Classical text models**: scikit-learn classifiers on TF-IDF features — strong baselines for headlines/filings classification.
- **Self-attention (toy example)**: query×key scores → softmax weights → weighted value sum; visualize attention weights.
- **Pretrained LLMs**: summarize transcripts via CLI (e.g. ollama/llama) and call from Python; **RAG**: retrieve relevant document chunks → put in prompt context → grounded answers.
- **Evaluation & limitations**: measure, test robustness, be explicit about hallucination/context limits.

## Key Concepts
- **Finance text sources**: news headlines, regulatory filings, broker notes, earnings-call transcripts, internal tickets — each with different cleaning needs (keep tickers vs @mentions).
- **Bag-of-words ignores order**; TF-IDF downweights common terms; dense embeddings capture semantics.
- **Vocabulary → integer IDs** is the bridge to any model input.

## Mental Models
- Use X when Y: *TF-IDF + linear classifier when* you need a fast, interpretable baseline; *dense embeddings when* semantics matter; *pretrained LLM when* generation/extraction/summarization needed; *RAG when* answering from a document corpus.
- Think of self-attention as *each token deciding how much to listen to every other token*.

## Anti-patterns
- **Raw text without cleaning** — case/punctuation noise degrades bag-of-words.
- **Ignoring evaluation** — LLM outputs need measurement (accuracy, relevance, failure cases).
- **Unbounded context** — RAG retrieval bounds what the model sees; don't stuff whole corpora into prompts.
- **Treating embeddings as free** — model-specific tokenizers/vocabularies matter.

## Code Examples
```python
import re

def simple_tokenize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text.split()

headlines = ["AAPL beats earnings expectations, shares jump",
             "Bank stocks slide as rates outlook shifts"]
tokens = [simple_tokenize(h) for h in headlines]
vocab = sorted(set(t for t_list in tokens for t in t_list))
token_to_id = {t: i for i, t in enumerate(vocab)}
encoded = [[token_to_id[t] for t in t_list] for t_list in tokens]

# TF-IDF + classifier baseline
from sklearn.feature_extraction.text import TfidfVectorizer
X = TfidfVectorizer().fit_transform(headlines)
```
- **What it demonstrates**: tokenize → vocab → encode; TF-IDF vectorization.

## Worked Example
Transcript summarization: feed an earnings-call transcript chunk to a pretrained LLM (CLI or Python) → structured summary; then RAG: embed document chunks, retrieve top-k by similarity for a question, generate grounded answer with citations to chunks. Evaluate summary quality on a small labeled set.

## Key Takeaways
1. Clean + tokenize → vocab → numeric: the universal NLP entry.
2. TF-IDF + linear models are strong, interpretable baselines.
3. Pretrained LLMs: use for generation/extraction; RAG for grounded Q&A.
4. Always evaluate and be explicit about limitations.

## Connects To
- **Ch 15**: ML patterns reused for text
- **Ch 19**: text-derived signals into portfolios
- **Ch 2**: GenAI collaboration discipline
