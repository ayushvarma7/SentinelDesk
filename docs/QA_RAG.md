# Q&A prep — retrieval and embeddings

Every number here is in `reports/`. If you don't remember a figure, say so and name the file —
that reads better than a guess.

---

## Embeddings

**Which model, and why that one?**
`intfloat/multilingual-e5-small` — 384 dimensions, 118M parameters. Three reasons: it handles
English and German in one model, so we never route by language; it's small enough to encode the
whole 22,863-ticket KB in about five minutes on a laptop GPU; and the same vector serves the
classifier, the retrieval query and the index, so there's one model in memory, not two.

**Did you fine-tune it?**
No. The ticket bodies are short — median 386 characters, p95 about 92 words — and off-the-shelf
e5 already gives top-1 same-type agreement of 0.888 against a ~40% base rate. Fine-tuning would
have cost an hour we'd have taken from the gate and the console, for a signal that was already
strong enough to be the *second* input to the gate rather than the only one.

**Why not OpenAI or Cohere embeddings?**
Latency and cost per ticket, and an outage would take retrieval down with it. Local encoding is
about 11 ms per ticket after warm-up. The LLM is already a network dependency; we didn't want a
second one on the path that still has to work when the LLM is unavailable.

**Why 384 dimensions? Isn't that small?**
It's enough here. A 22,863 × 384 float32 matrix is 33 MB and an exact search over it is ~0.9 ms,
so we never needed approximate search. Larger vectors would have bought accuracy we couldn't
use — the gate treats similarity as weak evidence for reasons below.

**Do you chunk the documents?**
No, and deliberately. A ticket is already the unit of retrieval: one problem, one resolution.
Median body is 386 characters, so nothing approaches the 512-token window. Chunking would split
a problem from its answer, which is exactly the pairing we want to retrieve.

**Why are there two embedding files?**
`kb_embeddings.npy` is the KB encoded with e5's `passage:` prefix — that's the retrieval index.
`kb_query_embeddings.npy` is the same KB encoded with `query:` — those are the classifier's
training features. At inference the classifier sees a query-prefixed vector, so it has to be
trained on query-prefixed vectors. Crossing them would silently desync the model from what it
learned on.

**Why does the query use a different prefix from the index?**
That's e5's convention: asymmetric search expects `query:` on one side and `passage:` on the
other. We follow it for retrieval. The classifier is a separate job and uses `query:` on both
sides, which is why the second file exists.

---

## Retrieval

**Why numpy and not a vector database?**
Honest answer: faiss crashes. On macOS faiss and torch each bundle libomp, and importing faiss
before torch aborts the process with `OMP: Error #15`. Our pipeline imports torch, so faiss was
out. At this scale an exact matmul is 0.9 ms, so nothing was lost — and it turned out to be an
advantage, because a plain matrix grows with `np.vstack` while a built index would need
rebuilding. That's what makes the live learning loop cost 11 ms instead of five minutes.

**How do you choose top-k?**
k=5. Enough for the model to triangulate, few enough to fit on screen and in a prompt without
diluting. We also deduplicate at cosine ≥ 0.98, because the dataset's answers are templated and
five copies of one resolution would look like five independent sources.

**Do you rerank?**
No cross-encoder. Two cheaper things instead: a queue filter that narrows to the predicted
department, and a reserved cross-lingual slot. The queue filter only engages when the predicted
queue has at least 4k candidates — queue macro-F1 is 0.61, so a wrong prediction must never
starve retrieval down to two weak precedents.

**How do you know retrieval is actually good?**
Measured on 500 holdout tickets, in `reports/retrieval_check.json`:
top-1 shares the true type 88.8% of the time against a ~40% base rate, and the true queue 73.6%
against a classifier that manages 61%. Retrieval is a better queue predictor than our classifier.

**What happens when there's no good precedent?**
The gate escalates on `min_top1_similarity` and the system drafts nothing. We'd rather show an
empty draft panel with a reason than a confident answer with no evidence behind it.

---

## The hard questions

**"Your similarities are all 0.85 to 0.95. Isn't that signal meaningless?"**
Largely, yes, and we treat it that way. Measured bands on hand-typed tickets: in-domain
0.869–0.906, off-domain 0.855–0.864, gibberish 0.833. The separation is about 0.005, so
similarity is weak evidence and carries correspondingly little weight in the gate —
`critical_score`, which is a probability from the classifier, carries safety instead. e5 vectors
are anisotropic; everything in one domain scores high against everything else.

**"How do you know the model used the precedents instead of inventing an answer?"**
We don't trust the prompt for that. Two code checks run after generation: every cited ticket ID
must be in the set we retrieved, and any number carrying a currency symbol, a percentage or a
time unit that appears in no precedent is flagged. Only 0.3% of KB answers contain such a
figure, so the figure guard almost never false-positives. Measured over 20 holdout tickets:
citation rate 1.00, fabricated citations 0.00, invented figures 0.00.

**"Does cross-lingual retrieval actually work?"**
Not on its own, and we found that the hard way. Our first measurement said 16.3% of top-5 hits
crossed languages. That was wrong — it counted the dataset's language *label*, and about 15% of
labels disagree with the text. Measured against detected language it's 2.8%. e5 strongly prefers
same-language neighbours. So we force it: one slot in the top-5 is reserved, and a second search
runs restricted to the other language. A reserved slot alone wasn't enough, because the
unrestricted top-30 for a German query is thirty German tickets.

**"How do I know the test answers aren't in your index?"**
Structurally, not by promise. `prepare_data.py` writes the holdout as two files:
`test_inputs.parquet` has only ticket_id, subject and body; the labels and answers live in a
separate file that only `evaluate.py` opens. The inference path can't read a label because those
columns aren't in the dataframe it loads. The index holds exactly the 22,863 KB rows, with zero
holdout IDs in it, and you can check that in one line.

**"You embed the test tickets though — isn't that leakage?"**
Embedding is a read, indexing is a write. A holdout ticket is encoded into a query vector, used
to search, and discarded. Nothing writes it into the index or the live store, and both eval
scripts abort if the live store isn't empty.

**"What stops the knowledge base degrading as it learns?"**
Only human-written resolutions become precedents. `resolved_by` is required and recorded with a
timestamp, and the console additionally refuses an unedited AI draft. If a draft could become a
precedent, the next draft would be grounded in the previous guess and the one after that in the
guess about the guess.

**"Why does the KB not have an answer for my question?"**
It often does — the issue is usually our gate, not coverage. Password reset retrieves a relevant
precedent at 0.909 and drafts. But the dataset is synthetic and its answers are generic, so for
anything narrow the nearest precedents can be topically adjacent without answering. When that
happens the model reports it isn't grounded and we escalate rather than improvise.

**"Would a bigger embedding model fix the weak separation?"**
Possibly some of it, but we'd be fixing the wrong layer. The separation problem comes from the
data being synthetic and templated — every ticket in one domain reads like every other. A larger
encoder on the same corpus would still see that. The architectural answer is what we did: stop
leaning on similarity and let a calibrated classifier probability carry the safety decision.
