# Q&A — plain answers

For explaining the system to someone who isn't going to check your maths. Short answers,
ordinary words. Numbers only where the number *is* the answer.

---

## The classifier

**What does the classifier do?**
It reads the ticket and guesses four things: what kind of issue it is, which team should get it,
how urgent it is, and what language it's written in. Each guess comes with a confidence.

**How does it decide?**
Two views of the same ticket. One counts words and phrases — tickets saying "invoice" tend to be
billing. The other is a meaning-based view that catches tickets saying the same thing in
different words, or in German. It learns from 22,000 already-resolved tickets which patterns go
with which answer.

**Why not a neural network or a large language model?**
Three reasons. It runs in milliseconds, so the console feels instant. It gives honest confidence
numbers, which the safety gate needs to make decisions. And it trains in about a minute, so we
could try ten versions and keep the best. A bigger model would have been slower, less honest
about its uncertainty, and we'd have had time to train it once.

**What does "confidence" actually mean here?**
How sure the model is. We checked that the number is truthful — when it says 70%, it's right
about 70% of the time. That matters because the gate uses it: an unreliable confidence would
make the whole safety logic meaningless.

**Why is picking the right team harder than picking the issue type?**
There are ten teams, some tiny, and they genuinely overlap. Technical Support, Product Support
and IT Support receive similar tickets, and even a person would disagree about some of them.
The model is partly being marked wrong for a judgement call with no single right answer.

**Why is urgency hard?**
Because in this data, urgency isn't really in the words. Urgent and routine tickets look much
the same — the share marked high is about the same whatever the issue type. We tuned the model
to lean toward calling things urgent anyway, because missing a real outage costs more than
looking at one calm ticket too many.

---

## Retrieval (the RAG part)

**What is RAG, in one sentence?**
Before the AI writes anything, we find real resolved tickets that match the new one, and the AI
is only allowed to answer using those.

**Why bother? Why not just let the AI answer?**
Because then it's answering from general knowledge, and it will confidently invent things your
company never offered — refund terms, integrations, timelines. Giving it your actual past
resolutions means the answer comes from what your team really did before.

**What's an embedding?**
A way of turning text into a list of numbers that captures meaning, so that two tickets about
the same problem end up with similar numbers even if they share no words — including across
languages. Searching is then just "which stored ticket's numbers are closest to this one's".

**So it's not keyword search?**
No. Keyword search would miss a German ticket describing an English-documented problem, or a
customer saying "can't log in" when the precedent says "authentication failure". The
meaning-based view catches both.

**What happens if nothing good matches?**
The system says so and stops. It escalates to a human rather than stretching a loosely related
ticket into an answer. Showing an empty draft with a reason is better than a confident wrong one.

**What stops it making things up?**
The AI has to name which past tickets it used, and we check every one of them against what we
actually gave it. If it names a ticket that wasn't there, we catch it. We also scan for numbers
— prices, percentages, timeframes — and flag any that don't appear in the source tickets, because
those are the things it would be most tempted to invent.

**Can it learn from new tickets?**
Yes, but only when a human resolves one and writes the answer. That resolution becomes a new
precedent the next similar ticket can find. An AI draft never becomes a precedent — otherwise
the system would start learning from its own guesses.

---

## The escalation gate

**What is the gate?**
The thing that decides whether a ticket gets an AI-drafted reply or goes straight to a person.

**How does it decide?**
Plain rules, checked in order. Is this likely a serious incident? Is the model unsure what this
even is? Did we find anything similar enough to answer from? Is the customer asking for something
we have no precedent for — a refund, a legal commitment? Is someone trying to manipulate the
system? Any one of those sends it to a human.

**Why rules instead of letting an AI decide?**
Because we have to be able to explain every escalation, and because the thing we're guarding
against is exactly an AI being confidently wrong. Each rule reports its own reason on screen, so
an operator sees "no similar precedent found" rather than a black-box verdict.

**What's the most important rule?**
The one that catches serious incidents even when the model has mislabelled the ticket. Rather
than waiting for it to say "urgent" and "outage" together, we look at how *likely* it thinks both
are. That catches the dangerous ones the labels alone would miss.

**Why doesn't an escalated ticket get a draft anyway, for the human to edit?**
Because then someone will send it. If we've decided this ticket is too risky to answer
automatically, putting a ready-made reply next to that warning invites exactly the mistake we
just prevented.

**Isn't it escalating a lot?**
Yes, and that's a dial, not an accident. We can tune it toward answering more or stopping more,
and we measured both directions. We've set it where benign tickets get answered while anything
that looks like a real incident or an attack still stops. Someone running this in production
would set that dial by what a missed outage costs them.

**What about prompt injection — someone typing "ignore your instructions"?**
Caught before the AI is involved. There's a set of patterns for instruction-override attempts,
credential requests, destructive actions and legal threats, in both English and German. Those
tickets escalate and no draft is written at all. We test every one of them on every run.

---

## If you only remember three things

1. **The AI never answers from general knowledge.** It answers from your resolved tickets, and
   it has to say which ones.
2. **The gate is rules, not judgement.** Every escalation has a reason you can read.
3. **It only learns from humans.** A person's resolution becomes a precedent; the AI's own draft
   never does.
