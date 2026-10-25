# PsychEngine - Personal Psychology Learning System

## Project Specification Document

---

## 1. Overview

PsychEngine is a local-first web application that ingests a personal library of PDF books on human psychology, manipulation, persuasion, social dynamics, and personality theory, and transforms them into a unified, topic-based learning system.

Instead of reading books one by one, the system teaches by concept. A single topic like "Frame Control" pulls relevant content from multiple books, teaches it in progressive layers over days and weeks, and uses active learning techniques rooted in cognitive science to ensure deep retention and real-world application.

The system is built for one user. It runs locally on Linux. AI features are powered by Gemini API free tier (zero cost) with Ollama as an offline fallback. Development is done using Claude Code (VS Code extension). Every screen, interaction, and animation is designed to feel elite, not like a developer prototype.

---

## 2. Book Library

### 2.1 Initial Book List

| # | Title | Author | Cluster |
|---|-------|--------|---------|
| 1 | Dark Seduction and Persuasion Tactics | Emory Green | Dark Psychology |
| 2 | Seducing Women Manual | Owen Sparks | Social Dynamics |
| 3 | Get Inside Her | Marni Kinrys | Social Dynamics |
| 4 | Personality Theories | Barbara Engler | Psychology Theory |
| 5 | The Complete Memoirs of Jacques Casanova de Seingalt | Casanova | Social Dynamics / Historical |
| 6 | Theories of Personality | Feist, Roberts, Feist | Psychology Theory |
| 7 | Dark Psychology Secrets and Manipulation | Brandon Covert | Dark Psychology |
| 8 | Rules of the Game | Neil Strauss | Social Dynamics |
| 9 | Dark Psychology and Manipulation Secrets | Harvey Mind | Dark Psychology |
| 10 | The Game | Neil Strauss | Social Dynamics |
| 11 | Oooooh... Say it Again | Alan Roger Currie | Social Dynamics |
| 12 | Dark Psychology Secrets & Manipulation Techniques | Richard Gardner | Dark Psychology |
| 13 | The Dating Playbook For Men | Andrew Ferebee | Social Dynamics |
| 14 | Biological Psychology | James W. Kalat | Psychology Theory |
| 15 | Psychology (13th Edition) | David G. Myers, C. Nathan DeWall | Psychology Theory |
| 16 | Feel The Fear And Do It Anyway | Susan Jeffers | Mindset |
| 17 | Conversation Casanova | Dave Perrotta | Social Dynamics |
| 18 | Natural Attraction (2-Book Bundle) | Mateo Lambert | Social Dynamics |
| 19 | Double Your Dating | David DeAngelo | Social Dynamics |
| 20 | The Way of the Superior Man | David Deida | Mindset |
| 21 | Dark Psychology Secrets and Manipulation Techniques | John Clark | Dark Psychology |

### 2.2 Book Clusters

The library naturally groups into 4 clusters:

- **Dark Psychology / Manipulation** (5 books): tactics of influence, covert persuasion, psychological manipulation, defense against manipulation
- **Social Dynamics / Dating** (10+ books): attraction, conversation, frame control, social proof, confidence, approach strategies
- **Psychology Theory / Biology** (4 books): cognitive biases, personality theory, biological basis of behavior, perception, memory, emotion
- **Mindset / Self-Development** (2 books): fear management, masculine identity, inner confidence

The psychology theory cluster serves as the foundational "WHY" layer. Every tactic from the other clusters links back to a mechanism explained in these books.

### 2.3 Adding New Books

The system supports adding new books at any time. Workflow:

1. Drop a PDF into the designated upload folder (or use drag-and-drop in the web interface)
2. System extracts text, chunks it by chapter/section
3. System auto-suggests cluster and topic tags using AI
4. User reviews and corrects tags if needed
5. New chunks integrate into existing topic pages and the layered schedule

---

## 3. Core Architecture

### 3.1 Concept: Topic-First, Not Book-First

Traditional approach: read Book A cover to cover, then Book B, then Book C. Problem: you encounter the same concept 5 times across 5 books, but weeks apart, with no connection.

PsychEngine approach: the system defines 20-30 master topics. Each topic aggregates all relevant content from all books. You study "Reciprocity" once, pulling from Myers, Green, Covert, and Strauss simultaneously. Theory first (why it works), then tactics (how it is used), then defense (how to detect it), then practice (simulator).

### 3.2 Topic Taxonomy (Dynamic, Book-Driven)

The topic taxonomy is NOT predefined. It is discovered organically from the books themselves during ingestion.

#### 3.2.1 How Topics Are Born

During Phase 2 (book analysis), the system processes every chunk and builds the taxonomy bottom-up:

1. **Extraction**: AI reads each chunk and extracts key concepts, tactics, principles, and terms mentioned in it. Output: a flat list of raw concept mentions per chunk.
2. **Clustering**: raw concepts are clustered by semantic similarity. "Social proof," "herd mentality," "conformity pressure," and "bandwagon effect" all collapse into one topic cluster.
3. **Naming**: AI proposes a clean topic name for each cluster. User reviews and renames if needed.
4. **Merging and splitting**: user can merge two topics that are too similar or split one that is too broad. The system suggests merges/splits based on overlap.
5. **Hierarchy detection**: some topics are subtopics of others. "Negging" is a subtopic of "Frame Control." The system proposes a parent-child hierarchy that the user confirms.

#### 3.2.2 Topic Growth Over Time

When a new book is added later:
1. System extracts concepts from the new book
2. Matches against existing topics (most new concepts will fit existing clusters)
3. If new concepts do not fit, system proposes new topics
4. User reviews and approves
5. Existing topic pages automatically gain new content from the new book

The taxonomy is a living structure, not a static list. It grows and refines as the library grows.

#### 3.2.3 Topic Metadata

Each topic stores:
- Name
- Description (auto-generated, user-editable)
- Source books (which books contribute to this topic)
- Chunk count (how much content exists)
- Parent topic (if subtopic)
- Child topics (if parent)
- Visual anchor
- Dependency links (prerequisites)
- Date created
- Date last modified (when new content was added)

### 3.3 Concept Dependency Graph

Topics are not isolated. Some require understanding of others first. The system builds and maintains a directed dependency graph.

#### How Dependencies Are Discovered

1. **AI-suggested**: during topic creation, AI analyzes concept relationships and proposes "Topic A should come before Topic B because B builds on mechanisms explained in A"
2. **User-defined**: user can manually add or remove dependency links
3. **Performance-inferred**: if users consistently fail Layer 2 of Topic X but pass after studying Topic Y, the system suggests Y as a prerequisite for X

The graph is not static. It evolves as topics are added and as the system learns from the user's performance data.

The system uses this graph to suggest learning order and prevent studying advanced topics before prerequisites are solid.

### 3.4 Data Pipeline

```
PDF files
  --> Text extraction (PyMuPDF)
  --> Chapter/section detection
  --> Chunking (by chapter, with fallback to fixed-size ~1000 tokens)
  --> Metadata tagging (book, author, cluster, chunk index)
  --> SQLite storage

Then (Phase 2, AI-powered):
  --> Concept extraction per chunk (AI reads each chunk, outputs raw concepts)
  --> Concept clustering (group similar concepts into topic clusters)
  --> Topic naming and description (AI proposes, user confirms)
  --> Chunk-topic mapping stored in database
  --> Dependency graph proposed and stored
  --> Ready for all features

When a new book is added later:
  --> Same extraction and chunking pipeline
  --> Concept extraction matches against existing topics
  --> New concepts form new topics if they do not fit existing ones
  --> User reviews and approves
```

### 3.5 Tech Stack

- **Backend**: Python, Flask or FastAPI
- **Database**: SQLite (single file, portable, zero config)
- **PDF Processing**: PyMuPDF (fitz)
- **AI (Primary)**: Google Gemini API free tier (Gemini 2.0 Flash, 15 RPM, 1M tokens/day, zero cost)
- **AI (Offline Fallback)**: Ollama running a local model (Llama 3, Mistral, or Phi-3) for when there is no internet or rate limits are hit
- **Frontend**: HTML + CSS + vanilla JS (or Alpine.js for reactivity). Tailwind CSS for styling. Every page designed to feel premium, not like a dev prototype.
- **Development Tool**: Claude Code (VS Code extension) for building and iterating on the codebase
- **Local-first**: runs on localhost, no internet needed except for Gemini API calls
- **OS**: Linux

#### 3.5.1 Why Gemini Free Tier Works

Google offers Gemini 2.0 Flash for free with generous limits:
- 15 requests per minute
- 1 million tokens per day
- 1500 requests per day

For a single-user learning app, this is more than enough. The heaviest feature (Scenario Simulator) uses ~5-10 API calls per session. Quiz generation, tagging, and flashcards can be batched and cached. Estimated daily usage: 50-100 API calls, well within limits.

#### 3.5.2 Ollama Fallback

For offline mode or when rate limits are temporarily hit:
- Ollama runs locally, zero internet required
- Models like Llama 3 8B or Mistral 7B handle quiz generation, tagging, and basic Q&A well
- Simulator quality will be lower with local models, so Gemini is preferred for that feature
- System auto-switches: tries Gemini first, falls back to Ollama on failure

#### 3.5.3 Development with Claude Code

Claude Code (VS Code extension) is used as the development assistant:
- Code generation and iteration for all phases
- Debugging and refactoring
- Writing tests
- This is a development tool, not a runtime API. The app itself calls Gemini/Ollama, not Claude.

---

## 4. Layered Learning System

This is the core engine of PsychEngine. It is based on how the human brain actually encodes, consolidates, and retrieves information.

### 4.1 The Problem with Single-Session Learning

Reading an entire topic in one sitting creates a single encoding event. One encoding event produces one memory trace that decays rapidly. Within 48 hours, retention drops below 30%. Within a week, below 10%.

### 4.2 The Solution: 5-Layer Progressive Deepening

Every topic is split into 5 layers. Each layer is delivered at a specific interval. Each layer adds new depth, so the learner never feels like they are "reviewing," they are always learning something new about the same concept. Each revisit creates a new retrieval event that strengthens the memory trace exponentially.

#### Layer 1 - Day 1: WHAT (Introduction)

Goal: first encoding, build the basic schema.

Content and activities:
- Core definition in simple terms
- One book's perspective (the clearest, most accessible author on this topic)
- One real-world example
- Visual anchor (diagram or icon associated with this concept permanently)
- "Define Before You Read" prompt: system asks the user to write what they think this concept means BEFORE showing any book content. The contrast between the user's guess and the actual definition creates a strong memory trace. (Generation Effect)
- Basic 3-question quiz at the end
- Cliffhanger: "In 3 days, you will learn why this works at a biological level" (Zeigarnik Effect)

Duration: ~15 minutes

#### Layer 2 - Day 3: WHY (Mechanism)

Goal: connect the concept to deep psychological mechanisms, create elaborative encoding.

Content and activities:
- Morning Recall Check: 3 quick questions from Layer 1 (no new content yet, pure retrieval)
- Psychology mechanism behind the concept (from Myers, Kalat, Engler, or Feist)
- "Why It Works" breakdown: neuroscience or cognitive science explanation
- Second book's perspective on the same concept (adds a new angle)
- "Connect to Your Life" prompt: user writes a personal experience related to this concept. Saved alongside book content. (Self-Reference Effect)
- Tactic Identification Drill: 2-3 short dialogue snippets, user identifies if this concept is being used
- End with an open question for the next layer

Duration: ~20 minutes

#### Layer 3 - Day 7: HOW (Application)

Goal: move from knowledge to application, force cross-context transfer.

Content and activities:
- Pre-Session Retrieval: user explains this concept without looking (Teach-Back Mode). AI grades the explanation. (Generation Effect)
- Remaining books' perspectives on this concept
- Contradiction Finder: where do different authors disagree on this concept? User must think about which perspective makes more sense and why.
- Cross-Context Transfer Exercise: concept was introduced in one domain (e.g., dating), now apply it in a different domain (e.g., workplace negotiation, family conflict). (Contextual Variation)
- "This vs That" Discrimination Drill: system shows pairs of similar scenarios, user distinguishes which one uses this concept vs a related but different concept. (Interleaving)
- First Scenario Simulator session focused on this topic
- Personal Vulnerability Assessment: "Could this tactic work on you? When?"

Duration: ~25 minutes

#### Layer 4 - Day 30: STRESS TEST (Pressure)

Goal: test under realistic conditions, integrate with other concepts.

Content and activities:
- No warning pop quiz: mixed with questions from other topics (Interleaving). User must first identify WHICH concept is relevant, then answer.
- Advanced Scenario Simulator: harder AI persona, more subtle tactic usage, multi-layered conversation
- Counter-Tactic Training: now learn how to defend against and neutralize this concept when used on you
- Write Your Own Mental Model Card: user creates a compressed, structured one-card summary of this concept in their own words
- Mixed drill: this topic blended with 2-3 related topics in a single exercise
- Field Report Prompt: "Have you noticed this concept in real life since Day 7? What happened?" (Self-Reference Effect)

Duration: ~20 minutes

#### Layer 5 - Day 90: MASTERY (Ownership)

Goal: prove deep ownership, ability to teach and create.

Content and activities:
- Full Teach-Back: explain this concept as if writing a book chapter. AI grades for accuracy, completeness, nuance.
- Create Your Own Scenario: user designs a scenario where this concept is in play, for someone else to solve. This requires deep understanding.
- Complex Simulator: multi-tactic conversation where this concept appears alongside 2-3 others. User must identify all of them.
- Update Personal Susceptibility Map
- System marks topic as "Mastered" only if user passes this layer with a threshold score

Duration: ~15 minutes

### 4.3 Staggered Scheduling

The user is never studying just one topic. The system staggers topic introductions so that any given day has a mix of activities:

Example daily session:
```
Tuesday, Week 3:
  - Morning Recall (2 min): 5 quick questions from recent layers
  - Topic G, Layer 1 (15 min): NEW introduction
  - Topic E, Layer 2 (20 min): mechanism deep-dive (introduced 3 days ago)
  - Topic A, Layer 4 (20 min): stress test (introduced 30 days ago)
  - Mixed Practice (10 min): interleaved quiz from Topics B, C, D, F
  - End-of-Day Primer (2 min): preview of tomorrow
```

Total session: ~40-50 minutes (adjustable by user preference).

The system auto-generates the daily session based on:
- What layers are due today
- What new topics are ready to introduce
- Which old topics need interleaved review
- User's available time setting

### 4.4 Adaptive Spacing

The 1/3/7/30/90 day intervals are defaults. The system adjusts based on actual performance:

- User aces Layer 2 quiz (100%): push Layer 3 to Day 10 instead of Day 7. Strong encoding, let it consolidate longer.
- User fails Layer 3 badly (<50%): insert a Layer 2.5 at Day 14. Re-teach the mechanism with different examples before retrying application.
- User aces Layer 4 under pressure (>90%): move Layer 5 to Day 60 instead of Day 90.
- User fails a pop quiz on an old mastered topic: topic drops back to Layer 4 status, re-enters the schedule.

The system tracks a per-concept retention curve for the user, not a generic formula.

---

## 5. Feature Specification

### 5.1 Reading and Navigation

#### 5.1.1 Topic-Based Reading

The primary reading mode. Each topic has a dedicated page showing:

- Topic name, description, and visual anchor
- Dependency graph position (what you should know before this, what this unlocks)
- Current layer progress (which layer you are on, when next layer is due)
- All relevant book chunks, ordered: theory books first, then application books
- Cross-book connections highlighted inline
- "Why It Works" section linking to psychological mechanisms

#### 5.1.2 Linear Book Reader

Secondary mode for when the user wants to read a single book cover to cover.

- Standard chapter-by-chapter reading
- Topic coverage overlay: each section shows which topics it maps to and which layers have been completed
- Visual markers:
  - Green check: this section was fully covered in topic-based study
  - Yellow: partially covered (some layers done)
  - No marker: not yet studied in topic mode
- User can click a topic marker to jump to the topic page

Example display inside the book reader:
```
Chapter 5: Social Proof and Compliance
[Topic: Social Proof | Layer 3 covered | Layer 4 in 12 days]

Chapter 6: Authority and Obedience
[Topic: Power Dynamics | Layer 1 covered | Layer 2 in 2 days]

Chapter 7: Scarcity
[Topic: Scarcity Tactics | Not yet started]
```

#### 5.1.3 Bidirectional Progress Tracking

The system maintains a coverage matrix: Books x Topics.

- From the topic view: see which books contributed content and how much you have covered from each
- From the book view: see which topics each chapter maps to and your progress on those topics
- Progress dashboard: overall completion percentage, active topics, upcoming layers, streak data

#### 5.1.4 Full-Text Search

Search across all books simultaneously. Returns results with:
- Matching text snippet with context (50 words before and after)
- Book title, chapter, page reference
- Topic tags for that chunk
- Click-through to full context in either book reader or topic view

---

### 5.2 Practice and Simulation

#### 5.2.1 Scenario Simulator

An AI-powered chat module where the AI plays a dynamically generated persona. The user practices identifying tactics and applying conversational techniques in real-time.

##### Dynamic Persona System

Personas are NOT hardcoded. They are built dynamically from book content and evolve with the user's progress.

**How personas are generated:**

1. **Tactic-driven construction**: the system selects 1-3 tactics from the user's current study topics. It then constructs a persona whose personality naturally uses those tactics. Example: if the current topic is "guilt manipulation" + "false scarcity," the system generates a persona like "a friend who constantly guilt-trips you into helping them with urgent deadlines that turn out to be fake."

2. **Book-sourced behavior patterns**: persona dialogue style, manipulation patterns, and responses are drawn from specific book content. If Strauss describes a specific push-pull technique in The Game, the persona's behavior mirrors that exact pattern. The debrief cites the source.

3. **Context variety**: personas span different relationship contexts:
   - Workplace (manager, coworker, client)
   - Personal (friend, romantic interest, family member)
   - Transactional (salesperson, negotiator, landlord)
   - Social (group dynamics, party, networking event)
   The context is varied to force cross-context transfer.

4. **Difficulty-adaptive**: persona subtlety scales with the user's layer:
   - Layer 3: persona uses one tactic, fairly obvious, limited adaptation
   - Layer 4: persona uses 2-3 tactics, subtle, changes strategy if user catches on
   - Layer 5: persona is highly realistic, adapts in real-time, uses multi-layered tactics, applies emotional pressure

5. **Persona memory and storage**: successful persona configurations (ones that challenged the user effectively) are saved. The system can bring back a particularly effective persona type weeks later for a re-test. Each stored persona records:
   - Personality description
   - Tactics used
   - Context type
   - Difficulty level
   - User's score against this persona
   - Date last used

6. **Iterative persona evolution**: as the user masters basic personas, the system combines multiple tactic clusters into complex personas. A Layer 5 persona might simultaneously use rapport building (from Perrotta), scarcity pressure (from Green), and gaslighting (from Covert), all sourced from specific book passages.

**How a session works:**

1. System generates a persona based on current study topics, user's weak areas, and difficulty level
2. Brief context is shown: "You are at a work meeting. A colleague is trying to get you to take on their project deadline." The persona's tactics are NOT revealed.
3. User enters the conversation via chat interface
4. AI persona uses the assigned tactics within natural conversation
5. User must identify the tactic(s) AND respond appropriately
6. Conversation runs for 8-15 exchanges or until user ends it
7. Post-conversation debrief:
   - Which tactics were used (with book source citations)
   - Which ones the user caught vs missed
   - What the ideal responses would have been (sourced from book content)
   - Where the user's responses were strong
   - Score and Layer credit
   - Persona saved to library if it was effective

The simulator should create mild emotional stakes. The AI persona should push, frustrate, and challenge. Mild stress during practice improves performance under real stress. (Emotional Tagging)

#### 5.2.2 Tactic Identification Drills

Standalone drill mode. System presents short dialogue snippets (2-5 lines) and the user must identify which tactic is being used.

Modes:
- Multiple choice: pick from 4 options
- Open response: type the tactic name
- Timed mode: 15 seconds per snippet
- Mixed mode: snippets from multiple topics interleaved (Interleaving)

Snippets are generated by AI from book concepts, not pulled verbatim from books.

#### 5.2.3 Counter-Tactic Training

Reverse of identification: system names a tactic or shows it in action, and the user must describe or select the appropriate counter.

Progression:
1. Multiple choice counters
2. Write your own counter-response
3. Live simulator where you must counter the tactic in conversation

Counter-tactics are sourced from book content, especially the dark psychology defense sections and the psychology theory books.

#### 5.2.4 Conversation Replay Analysis

User pastes a real conversation (text messages, WhatsApp, email, any text).

System analyzes:
- Which tactics or patterns appear in the conversation
- Who used them (the user or the other person)
- Missed opportunities where the user could have applied a technique
- Specific book references for each identified pattern
- Suggested alternative responses with reasoning

This is powered by Gemini with book chunks as context (RAG approach).

#### 5.2.5 Field Report Journal

A personal log where the user records real-world interactions and observations.

Entry structure:
- Date and context (situation description)
- What happened
- What tactics or concepts you noticed (tag from topic list)
- What you tried
- What worked, what did not
- AI feedback: system reads the entry and connects it to book concepts, suggests what could have been done differently

Over time, this becomes a personal case study library. The system can reference past field reports during study sessions: "Last month you encountered social proof pressure at work. Here is what you could try next time."

#### 5.2.6 "This vs That" Discrimination Drills

System presents pairs of similar scenarios. User must distinguish between related but different concepts:

Examples:
- Negging vs genuine teasing
- Persuasion vs manipulation
- Confidence vs arrogance
- Rapport building vs love bombing
- Genuine scarcity vs false urgency
- Frame control vs domineering behavior
- Empathy vs manipulation through faked empathy

This sharpens the user's ability to make fine distinctions in real situations, not just recognize broad categories.

---

### 5.3 Cognitive Science Features

These features are designed around specific, evidence-based learning principles.

#### 5.3.1 Visual Anchors (Dual Coding Theory)

Every concept gets a persistent visual identity:
- A small icon or color code
- A concept diagram showing how the tactic works step by step
- These visuals appear everywhere the concept is referenced (topic pages, quizzes, simulator debriefs)
- Over time, the user's brain associates the visual with the concept before reading the word

#### 5.3.2 "Define Before You Read" (Generation Effect)

Before showing book content on any new concept, the system asks the user to write their own definition or understanding first. Then the book content appears. The contrast between the user's version and the author's creates a much stronger memory trace than passive reading alone.

#### 5.3.3 Teach-Back Mode (Generation Effect)

After studying a topic, the system prompts: "Explain this concept as if teaching a 15-year-old." The user writes freely. AI grades the explanation for:
- Accuracy
- Completeness
- Clarity
- Whether key mechanisms were mentioned

This is used at Layer 3 (first teach-back), Layer 5 (full mastery teach-back), and randomly during mixed practice sessions.

#### 5.3.4 "Connect to Your Life" Prompts (Self-Reference Effect)

After each layer, the system asks: "Write about a time you experienced this or saw it happen." The personal example is saved alongside book content. During future reviews, the user sees THEIR story, not just theory. Information connected to personal experience is retained 2-3x better than abstract knowledge.

#### 5.3.5 Personal Vulnerability Assessment (Self-Reference Effect)

System asks: "Which of these tactics would work on you? When have you fallen for something similar?" This forces honest self-reflection and anchors the concept to the user's identity. Over time, builds a Personal Susceptibility Map (see 5.3.8).

#### 5.3.6 Cross-Context Transfer Exercises (Contextual Variation)

A concept learned in one domain is applied to another:
- "Frame control" learned from dating books, now applied in a workplace negotiation scenario
- "Reciprocity" learned from persuasion theory, now applied in a friendship conflict
- "Scarcity" learned from dark psychology, now detected in a sales pitch

Each concept has context tags: dating, workplace, friendship, family, negotiation, sales, conflict. Transfer exercises cross these boundaries.

#### 5.3.7 Cliffhanger Sessions (Zeigarnik Effect)

Study sessions deliberately end with a topic 80% complete. "Tomorrow you will learn the counter to this tactic." The brain keeps processing unfinished tasks during idle time and sleep. Open questions at the end of each session create mental tension that drives recall.

#### 5.3.8 Personal Susceptibility Map

Built over time from quiz failures, self-assessments, and vulnerability prompts. A visual map showing:
- Which tactics the user is strong against (high quiz scores, good simulator performance)
- Which tactics the user is weak against (low scores, self-reported vulnerabilities)
- Improvement trajectory over time

This becomes the user's personal improvement target list. The system prioritizes weak areas in scheduling.

#### 5.3.9 Consequence Previews (Emotional Tagging)

Before learning a new tactic, system shows a brief scenario: "Here is what happens when someone misses this tactic in real life." A short, vivid example of the negative outcome. Creates emotional salience, which moves the concept into priority memory storage.

#### 5.3.10 Framework First, Details Later (Schema Building)

Every topic starts with a 3-5 point skeleton. A simple framework that the brain can use as scaffolding. Details are added onto this structure over subsequent layers. The user always has the "big picture" before any details. This prevents the common failure mode where someone knows many facts but cannot organize them into a usable mental model.

#### 5.3.11 Mental Model Cards (Chunking)

Each major concept gets a one-card summary:
- Concept name
- 3-5 key points
- When it is used
- When it fails
- Primary counter
- Visual anchor

The user builds these cards themselves (guided by the system). The act of compression forces deep processing. Cards become a quick-reference deck for real-world situations.

#### 5.3.12 Pre-Reading Activation (Retrieval Practice)

Before starting any new topic or new layer, the system asks: "What do you already know about X?" User writes freely. This activates existing knowledge and creates mental hooks for new information to attach to. New information sticks dramatically better when the brain has already activated related prior knowledge.

#### 5.3.13 Random Pop Quizzes During Reading (Retrieval Practice)

Mid-chapter, the system interrupts with a quick question about something the user read 10-15 minutes ago. Not at the end of the session, during active reading. This forces retrieval while context is fresh and the memory trace is still forming.

#### 5.3.14 Delayed Hints (Desirable Difficulty)

When the user is stuck on a quiz or drill:
1. First: a vague hint (which topic area?)
2. After 30 seconds: a stronger hint (which specific concept?)
3. After 60 seconds: the answer with explanation

Each struggle attempt strengthens the eventual memory trace. Immediate answers produce weak encoding.

#### 5.3.15 End-of-Day Review (Sleep Consolidation)

At session end, the system presents a 2-minute review: the 3-5 most important concepts from today's session. No new content. Light retrieval only. This primes the brain for overnight memory consolidation.

#### 5.3.16 Morning Recall Check (Sleep Consolidation)

Next day, first interaction: 3-5 quick questions from yesterday's session. Measures overnight retention. If retention is strong, great. If weak, those concepts get flagged for tighter spacing.

#### 5.3.17 Progressive Difficulty

Per-topic difficulty scaling across all activities:
- Level 1: Multiple choice (recognition)
- Level 2: Fill in the blank (recall)
- Level 3: Scenario-based (application)
- Level 4: Open-ended, create your own example (synthesis)

System pushes the user up only when lower levels are consistently passed. Prevents the illusion of competence that multiple-choice-only testing creates.

---

### 5.4 Time Awareness and Decay Tracking

The system makes the passage of time visible and actionable. You should always know how long it has been since you last engaged with any concept.

#### 5.4.1 Decay Indicator (Visual Rust)

Every topic card, in every view (dashboard, topic list, book reader overlay), has a color that reflects recency of engagement:

- **Bright green** (0-3 days): freshly studied, strong retention
- **Green** (4-7 days): recently studied, retention holding
- **Yellow** (8-14 days): starting to fade, review soon
- **Orange** (15-30 days): fading, retrieval needed
- **Red** (31-60 days): going cold, significant decay likely
- **Dark red / grey** (60+ days): in the attic, major re-learning may be needed

The color transitions are smooth (CSS gradient based on days since last interaction), not stepped. A topic at day 12 looks noticeably different from day 8. This creates a constant, ambient awareness of what is decaying without requiring the user to check numbers.

#### 5.4.2 "Days Ago" Badge

Every topic card shows a human-readable time badge:

- "studied today"
- "studied 3 days ago"
- "studied 2 weeks ago"
- "last touched 47 days ago"
- "never studied"

This appears on: topic list page, topic detail page, dashboard active topics, book reader topic overlay, pattern library entries, and flashcard categories.

#### 5.4.3 Forgetting Curve Sparkline

Each topic card includes a small sparkline graph (50x20px) showing the predicted retention curve:

- X-axis: time (last 90 days)
- Y-axis: estimated retention (0-100%)
- Line drops after each study session, spikes back up on review
- Current retention percentage shown as a number next to the sparkline

The curve is calculated using a modified Ebbinghaus formula, adjusted for the user's actual performance data on that topic (quiz scores, teach-back grades, simulator results).

#### 5.4.4 Calendar Heat Map

A GitHub-style contribution grid showing study activity:

- One cell per day, covering the last 6 months
- Color intensity = how much study was done that day
- Hovering a cell shows: date, topics studied, total time, session score
- Filterable by topic (show only days when Topic X was studied)
- Shows patterns: "I study every weekday but skip weekends" or "I had a 2-week gap in March"

Available on dashboard and on individual topic detail pages.

#### 5.4.5 "Going Cold" and "In the Attic" Alerts

Proactive notifications on the dashboard:

- **Going Cold** (30+ days untouched): "Frame Control is going cold. Last studied 34 days ago. Your estimated retention is 28%. Quick review?"
- **In the Attic** (60+ days untouched): "Gaslighting Detection has been in the attic for 67 days. Estimated retention is below 15%. Schedule a Layer 4 re-test?"

These are not just notifications, they are actionable. Clicking them adds the topic to today's session or schedules a review.

#### 5.4.6 Session History Timeline

Per-topic timeline showing every interaction ever:

```
Frame Control - Full History
|----- Day 1 (Jan 15): Layer 1 Introduction - Score: 85%
|----- Day 3 (Jan 17): Layer 2 Mechanism - Score: 72%
|----- Day 5 (Jan 19): Pop Quiz during reading - Score: 100%
|----- Day 7 (Jan 21): Layer 3 Application - Score: 68%
|      |- Scenario Simulator: scored 3/5 tactic identifications
|      |- Teach-Back: graded B+
|----- Day 14 (Jan 28): Mixed Drill - Score: 80%
|----- Day 30 (Feb 13): Layer 4 Stress Test - Score: 91%
|      |- Counter-tactic training completed
|      |- Mental Model Card created
|----- Day 90 (Apr 14): Layer 5 Mastery - PASSED
|----- Day 142 (Jun 5): Pop Quiz - Score: 75% (decay detected)
|----- Day 143 (Jun 6): Refresher session scheduled
```

This gives complete visibility into the engagement history for every topic.

#### 5.4.7 Aggregate Decay Dashboard

A dedicated view showing all topics ranked by urgency:

- Sorted by: estimated current retention (lowest first)
- Columns: topic name, decay indicator color, days since last studied, estimated retention %, next scheduled review, action button
- Filterable by cluster (dark psych, social dynamics, theory, mindset)
- One-click to add any topic to today's session

#### 5.4.8 Per-Book Freshness View

In the book library view, each book shows aggregate freshness:

- "The Game - 73% of content is fresh (studied in last 14 days), 15% fading, 12% cold"
- Visual bar showing the freshness distribution
- Clicking drills down to chapter-level freshness

---

### 5.5 Knowledge Architecture

#### 5.5.1 Concept Dependency Graph

A directed graph showing which topics depend on which others. Displayed visually, interactive, clickable.

Functions:
- Suggests optimal learning order
- Prevents studying advanced topics before prerequisites are solid
- Shows the user where they are in the overall knowledge structure
- Highlights unlocked topics (prerequisites met) vs locked topics

#### 5.5.2 Contradiction Finder

The system identifies and flags where different books disagree on the same concept.

Display:
- Topic page shows a "Debate" section
- Book A says X, Book B says Y
- User is prompted to think about which perspective is more valid and why
- No resolution provided, the point is to develop critical thinking

These contradictions are some of the highest-value learning moments. They force the user out of passive absorption and into active evaluation.

#### 5.5.3 "Why It Works" Psychology Layer

Every tactic and technique links back to its psychological mechanism.

Example:
```
Tactic: Scarcity pressure ("Only 2 spots left")
Mechanism: Loss aversion (Myers, Ch.12), Prospect Theory
Biology: Amygdala activation under perceived threat of loss (Kalat, Ch.8)
Personality factor: Higher anxiety = more susceptible (Engler, Ch.5)
```

This layer connects the applied books (dark psychology, dating) to the theoretical books (Myers, Kalat, Engler, Feist). The theory books become the foundation, not separate reading.

#### 5.5.4 Pattern Library

A searchable personal database of every tactic, technique, and principle across all books.

Each entry:
- Name
- Category (persuasion, manipulation, attraction, defense, etc.)
- Short description
- Which books mention it (with direct chunk links)
- Psychological mechanism
- When to use / when it appears
- When it fails / limitations
- Known counters
- Context tags (dating, workplace, negotiation, conflict, etc.)
- User's personal notes and examples
- Mastery status

This is the user's personal encyclopedia of human psychology tactics.

#### 5.5.5 Connection Discovery

AI surfaces non-obvious connections between concepts across books and clusters:

Example:
"The concept of 'push-pull' in dating (Strauss) maps directly to 'intermittent reinforcement' in behavioral psychology (Myers), which is also the mechanism behind 'trauma bonding' discussed in the dark psychology books (Covert). Same mechanism, three completely different contexts."

These cross-domain connections are surfaced:
- Proactively on topic pages
- During study sessions as "insight cards"
- When the user completes certain layer combinations that make the connection relevant

#### 5.5.6 Knowledge Gap Detector

Based on quiz scores, layer completion, and topic coverage, the system identifies:
- Strong areas (high mastery, fast progression)
- Weak areas (failed quizzes, slow progression, avoided topics)
- Untouched areas (topics not yet started)
- Lopsided knowledge (strong on theory but weak on application, or vice versa)

Displayed as a visual heat map on the topic taxonomy. Red = weak, green = strong, grey = untouched.

System uses this to prioritize scheduling: weak areas get more frequent practice, strong areas get longer spacing.

---

### 5.6 Personality and People Reading

#### 5.6.1 Personality Profile Builder

Based on Engler and Feist's personality theory content, the system lets the user:
- Study different personality type frameworks (Big Five, Jungian types, attachment styles, dark triad)
- Build profiles: "Type A person responds to X tactic this way, Type B responds differently"
- Practice adapting approach based on personality type in the simulator

#### 5.6.2 Emotion State Mapping

A reference system mapping emotional states to tactic effectiveness:
- Angry: vulnerable to X, resistant to Y
- Insecure: vulnerable to A, responsive to B
- Overconfident: can be countered with C
- Anxious: susceptible to D, but E will backfire

Built from book content across all clusters. User can look up an emotional state and see which tactics and counter-tactics are relevant.

#### 5.6.3 Subcommunication Reference Cards

Quick-reference cards for body language and nonverbal signals, sourced from book content:
- Open vs closed posture
- Eye contact patterns and what they indicate
- Voice tone and pacing signals
- Micro-expressions (where covered in books)
- Touch escalation ladders (from social dynamics books)

Tagged to relevant topics, so they appear contextually during study.

---

### 5.7 Active Learning Features

#### 5.7.1 Auto-Generated Flashcards

For every chunk processed, Gemini generates 3-5 flashcard pairs:
- Term / Definition
- Scenario / Correct Response
- Tactic / Counter

Flashcards are tagged to topics and integrated into the spaced repetition system.

#### 5.7.2 Quizzes

Per-topic quizzes generated after each layer, plus mixed quizzes pulling from multiple topics.

Question types:
- Multiple choice (recognition)
- Short answer (recall)
- Scenario-based (application)
- Open response graded by AI (synthesis)

#### 5.7.3 Adaptive Spaced Repetition

Beyond the 5-layer system, individual flashcards and quiz questions have their own repetition schedule:
- Correct answer: interval expands (2 days, 5 days, 14 days, 30 days, 90 days)
- Wrong answer: interval contracts back to 1 day
- System tracks per-card performance and adjusts individually
- Forgetting Curve Alerts: system notifies when a concept is predicted to drop below retention threshold

#### 5.7.4 Highlights and Notes

User can highlight any text in both topic view and book reader. Highlights are saved with:
- Source (book, chapter, page)
- Topic association
- User note (optional)
- Timestamp

All highlights are accessible from a dedicated page, filterable by book, topic, or date.

#### 5.7.5 Bookmarks

Save a position in any book or topic page. Quick jump back.

---

### 5.8 Daily Session Engine

The system auto-generates a study session each day.

#### 5.8.1 Session Structure

```
1. Morning Recall (2 min)
   - 3-5 quick questions from yesterday's session and recent layers
   - Measures overnight retention

2. New Layer or New Topic (15-20 min)
   - One topic's next scheduled layer
   - Full layer experience with all associated activities

3. Mixed Practice (10 min)
   - Interleaved quiz pulling from multiple topics at various stages
   - Forces discrimination and retrieval across domains

4. Scenario or Field Report (10 min)
   - One simulator session (if a topic is at Layer 3+)
   - OR one field report entry and analysis

5. End-of-Day Primer (2 min)
   - Preview of tomorrow's key concepts
   - Primes overnight consolidation
```

Total: ~40-50 minutes per session. User can configure shorter or longer sessions.

#### 5.8.2 Session Generation Logic

The system decides what to include based on:
- Layer due dates (which topics have layers due today)
- New topic introduction rate (default: 1 new topic every 3-4 days)
- Knowledge gap priorities (weak areas get more attention)
- Time budget (user's configured session length)
- Interleaving requirements (mix old and new, mix clusters)

---

### 5.9 Library Management

#### 5.9.1 Book Dashboard

Shows all books with:
- Cover/title
- Cluster tag
- Reading progress (linear mode)
- Topic coverage percentage (how much of this book has been covered via topic-based study)
- Number of chunks, chapters, topics mapped

#### 5.9.2 Add New Book

Workflow:
1. Drag and drop PDF into upload area (or place in designated folder)
2. System processes: extract text, detect chapters, chunk
3. AI suggests cluster assignment and topic tags
4. User reviews and confirms/edits
5. New chunks merge into existing topics and become available in the next session

#### 5.9.3 Manual Tag Editing

User can override any auto-generated tag:
- Change a chunk's topic assignment
- Change a book's cluster
- Create new topics
- Merge topics

---

### 5.10 Quality of Life

#### 5.10.1 Dark Mode and Reading Mode

- Dark mode: dark background, light text, reduced eye strain for long sessions
- Reading mode: simplified view, larger text, no distracting UI elements
- Toggle between modes at any time

#### 5.10.2 Export

Export options:
- All notes and highlights as Markdown
- All flashcards as Markdown or Anki-compatible format
- Mental Model Cards as PDF
- Field Report Journal as Markdown
- Pattern Library as Markdown or JSON

#### 5.10.3 Offline-First

All reading, quizzes, and flashcards work without internet. Only features requiring Gemini (simulator, conversation replay, AI-generated quizzes, teach-back grading) need connectivity. System caches AI responses where possible to minimize API calls.

---

## 6. User Interface Structure

### 6.1 Pages

```
/                       - Dashboard (today's session, progress overview, streak, decay alerts)
/topics                 - Topic taxonomy grid with mastery heat map and decay indicators
/topics/:id             - Individual topic page (layered content, drills, progress, timeline)
/topics/:id/history     - Full engagement history timeline for a topic
/books                  - Book library (all books, cluster filter, coverage stats, freshness bars)
/books/:id              - Linear book reader with topic overlay and freshness markers
/books/:id/chapter/:ch  - Chapter reader
/practice               - Practice hub (simulator, drills, quizzes)
/practice/simulator     - Scenario Simulator with dynamic personas
/practice/drills        - Tactic Identification and Counter-Tactic Drills
/practice/this-vs-that  - Discrimination Drills
/practice/replay        - Conversation Replay Analysis
/journal                - Field Report Journal
/patterns               - Pattern Library (searchable tactic database)
/graph                  - Concept Dependency Graph (interactive visual)
/decay                  - Aggregate Decay Dashboard (all topics sorted by urgency)
/calendar               - Calendar Heat Map (study activity over time)
/profile                - Personal Susceptibility Map, Knowledge Gap Heat Map
/settings               - Session length, new topic rate, spacing config, AI engine config, book management
/search                 - Global search across all books
```

### 6.2 Dashboard

The home page shows:
- Today's Session: auto-generated, click to start. Animated session card.
- Streak counter (consecutive days studied) with milestone celebrations
- Active topics with layer progress bars and decay indicator colors
- Upcoming layers due this week (with day badges)
- "Going Cold" alerts: topics that need attention, sorted by urgency
- Knowledge gap summary (quick view of weak areas as a mini heat map)
- Recent field reports (last 3, with quick-add button)
- Calendar heat map (last 30 days, compact view)
- Quick stats: total topics mastered, total study hours, books completed percentage

---

## 7. AI Integration (Zero Cost)

### 7.1 Primary: Gemini API Free Tier

Google Gemini 2.0 Flash is available for free with sufficient limits for this project.

Free tier limits:
- 15 requests per minute
- 1,500 requests per day
- 1 million tokens per day
- Model: gemini-2.0-flash

These limits comfortably handle single-user daily usage. The heaviest features (Scenario Simulator, Conversation Replay) use ~5-15 API calls per session. All other features (quiz generation, tagging, flashcards) are batch-processed and cached.

### 7.2 Fallback: Ollama (Local, Offline)

When internet is unavailable or Gemini rate limits are hit:
- Ollama runs locally on the user's Linux machine
- Recommended models: Llama 3 8B (general), Mistral 7B (good at instruction following), Phi-3 (lightweight)
- Handles: quiz generation, topic tagging, flashcard creation, basic Q&A
- Not recommended for: Scenario Simulator (requires conversational quality that smaller local models lack)
- System auto-detects: tries Gemini first, transparent fallback to Ollama on failure
- User can also force local-only mode in settings

### 7.3 Where AI Is Used

| Feature | AI Role | Preferred Engine |
|---------|---------|-----------------|
| Topic discovery from books | Reads chunks, extracts concepts, clusters into topics | Gemini (batch) |
| Topic tagging new books | Reads chunks, maps to existing topics | Gemini or Ollama |
| Quiz generation | Generates quiz questions from book chunks | Gemini or Ollama |
| Flashcard generation | Creates flashcard pairs from book content | Gemini or Ollama |
| Scenario Simulator | Plays dynamic personas, evaluates user responses | Gemini only |
| Teach-Back grading | Evaluates user's explanations for accuracy | Gemini (preferred) |
| Conversation Replay | Analyzes pasted conversations for tactics | Gemini only |
| Connection Discovery | Surfaces cross-domain links between concepts | Gemini (batch) |
| Contradiction Finder | Identifies disagreements between books | Gemini (batch) |
| Field Report feedback | Reads journal entries, connects to book concepts | Gemini or Ollama |
| "Define Before You Read" evaluation | Compares user's guess to book content | Gemini or Ollama |
| Counter-Tactic suggestions | Generates appropriate counters for tactics | Gemini or Ollama |
| Dynamic persona generation | Constructs persona from book tactics | Gemini only |

### 7.4 RAG Approach

For most AI features, the system uses a lightweight RAG (Retrieval Augmented Generation) approach:

1. User's query or context identifies relevant topics
2. System retrieves relevant chunks from SQLite (by topic tag)
3. Chunks are sent as context to Gemini alongside the prompt
4. Gemini responds grounded in book content

No vector database needed initially. Topic tags + full-text search provide sufficient retrieval for a library of this size (~20 books). Vector embeddings can be added later if retrieval quality needs improvement.

### 7.5 Prompt Engineering

Each Gemini interaction has a specific system prompt tailored to the feature:
- Simulator: persona description, tactic to use, difficulty level, evaluation criteria
- Quiz generation: topic context, difficulty level, question type requirements
- Teach-back grading: concept definition from books, grading rubric
- Conversation replay: full tactic taxonomy as reference, analysis framework

### 7.6 API Usage Optimization (Staying Within Free Limits)

- Cache generated quizzes and flashcards in SQLite (regenerate only when new books are added)
- Batch process topic discovery and tagging during book ingestion (not real-time)
- Pre-generate quiz banks per topic per layer (one Gemini batch run produces weeks of quiz content)
- Simulator sessions are the primary API cost, limit to 2-3 per day by default
- Morning recall and pop quizzes use pre-generated cached questions, zero API calls
- Persona templates are cached after generation, only the live conversation uses real-time API
- Offline fallback: if no internet, use Ollama for generation and cached questions for quizzes
- Estimated daily API usage: 50-150 calls, well within 1,500/day free limit
- Estimated daily token usage: 100K-300K tokens, well within 1M/day free limit

---

## 8. Data Model

### 8.1 SQLite Schema (Core Tables)

```
books
  - id (PK)
  - title
  - author
  - cluster (dark_psychology | social_dynamics | psychology_theory | mindset)
  - file_path
  - total_chunks
  - added_date

chunks
  - id (PK)
  - book_id (FK -> books)
  - chapter_name
  - chunk_index
  - text
  - page_start
  - page_end

topics
  - id (PK)
  - name
  - description
  - visual_anchor_path
  - dependency_ids (JSON array of prerequisite topic IDs)

chunk_topics (many-to-many)
  - chunk_id (FK -> chunks)
  - topic_id (FK -> topics)
  - relevance_score (0-1)

user_progress
  - id (PK)
  - topic_id (FK -> topics)
  - current_layer (1-5)
  - layer_1_date
  - layer_2_date
  - layer_3_date
  - layer_4_date
  - layer_5_date
  - next_layer_due
  - mastery_score (0-100)
  - status (not_started | active | mastered)

quiz_results
  - id (PK)
  - topic_id (FK -> topics)
  - layer
  - question_type
  - question_text
  - user_answer
  - correct_answer
  - is_correct
  - timestamp

flashcards
  - id (PK)
  - topic_id (FK -> topics)
  - chunk_id (FK -> chunks)
  - front
  - back
  - next_review_date
  - interval_days
  - ease_factor
  - review_count

highlights
  - id (PK)
  - chunk_id (FK -> chunks)
  - topic_id (FK -> topics, nullable)
  - highlighted_text
  - user_note
  - timestamp

field_reports
  - id (PK)
  - date
  - context
  - description
  - tactics_observed (JSON array of topic IDs)
  - what_worked
  - what_failed
  - ai_feedback

personal_examples
  - id (PK)
  - topic_id (FK -> topics)
  - layer (which layer prompted this)
  - user_text
  - timestamp

mental_model_cards
  - id (PK)
  - topic_id (FK -> topics)
  - key_points (JSON)
  - when_used
  - when_fails
  - primary_counter
  - user_created_date

susceptibility_map
  - id (PK)
  - topic_id (FK -> topics)
  - vulnerability_score (0-100, higher = more vulnerable)
  - last_assessed
  - notes

reading_progress
  - id (PK)
  - book_id (FK -> books)
  - chunk_id (FK -> chunks)
  - read_in_linear_mode (boolean)
  - read_in_topic_mode (boolean)
  - read_date

daily_sessions
  - id (PK)
  - date
  - planned_activities (JSON)
  - completed_activities (JSON)
  - morning_recall_score
  - session_duration_minutes

streak_data
  - id (PK)
  - date
  - session_completed (boolean)
  - current_streak
  - longest_streak

simulator_personas
  - id (PK)
  - personality_description
  - context_type (workplace | personal | transactional | social)
  - tactic_ids (JSON array of topic IDs used as primary tactics)
  - difficulty_level (layer_3 | layer_4 | layer_5)
  - source_chunks (JSON array of chunk IDs that informed this persona's behavior)
  - times_used
  - avg_user_score
  - last_used_date
  - is_effective (boolean, true if consistently challenged the user)
  - created_date

simulator_sessions
  - id (PK)
  - persona_id (FK -> simulator_personas)
  - topic_id (FK -> topics)
  - layer
  - conversation_log (JSON array of messages)
  - tactics_used (JSON array)
  - tactics_caught (JSON array)
  - tactics_missed (JSON array)
  - score
  - debrief_text
  - timestamp

topic_engagement_log
  - id (PK)
  - topic_id (FK -> topics)
  - engagement_type (layer_1 | layer_2 | layer_3 | layer_4 | layer_5 | pop_quiz | mixed_drill | simulator | flashcard_review | field_report)
  - score (nullable)
  - duration_seconds
  - timestamp

topic_decay_state
  - id (PK)
  - topic_id (FK -> topics)
  - last_engaged_date
  - days_since_engagement (computed/cached)
  - estimated_retention (0-100, computed from forgetting curve model)
  - decay_status (fresh | holding | fading | cold | attic)
  - retention_history (JSON array of {date, retention_pct} for sparkline)

concept_extraction_log
  - id (PK)
  - chunk_id (FK -> chunks)
  - raw_concepts (JSON array of extracted concept strings)
  - mapped_topic_ids (JSON array of topic IDs after clustering)
  - ai_engine_used (gemini | ollama)
  - processed_date
  - user_reviewed (boolean)
```

---

## 9. Build Phases

### Phase 1: Data Foundation (PDF Ingestion + Storage)

- PDF text extraction pipeline using PyMuPDF
- Chapter/section detection
- Chunking logic
- SQLite database setup with core schema
- CLI tool to ingest a folder of PDFs
- Basic validation: view extracted text, verify chunk quality

Deliverable: all 21 books ingested, chunked, and stored in SQLite. Queryable.

### Phase 2: Topic Discovery and Taxonomy Building

- Build AI-powered concept extraction pipeline: for each chunk, extract raw concepts and terms
- Concept clustering: group similar raw concepts into topic clusters using semantic similarity
- AI proposes topic names, descriptions, and parent-child relationships
- User review interface (web page to approve, rename, merge, split topics)
- Chunk-topic mapping stored in database
- Dependency graph proposed by AI, confirmed by user
- Pipeline re-runs when new books are added, mapping new chunks to existing topics or proposing new ones

Deliverable: a living topic taxonomy discovered from the actual book content. Every chunk tagged.

### Phase 3: Core Web Interface

- Flask app with routing
- Dashboard page
- Topic list page with mastery heat map
- Topic detail page (shows all relevant chunks from all books, ordered by cluster)
- Linear book reader with topic overlay markers
- Full-text search
- Progress tracking (read/unread per chunk, per topic, per book)
- Dark mode, reading mode

Deliverable: a working local web app where you can study by topic or by book.

### Phase 4: Layered Learning Engine

- Layer scheduling logic (1/3/7/30/90 intervals)
- Daily session generator
- Layer-specific content delivery (each layer shows different activities)
- "Define Before You Read" prompts
- Cliffhanger logic at session end
- Morning recall and end-of-day review
- Staggered topic introduction
- Adaptive spacing based on quiz scores

Deliverable: the system teaches you with a structured daily session using the 5-layer model.

### Phase 5: Active Learning (Quizzes, Flashcards, Drills)

- AI-powered quiz generation per topic per layer (Gemini with Ollama fallback)
- Flashcard generation and spaced repetition engine
- Tactic Identification Drills
- "This vs That" Discrimination Drills
- Counter-Tactic Training
- Progressive difficulty (Level 1-4)
- Delayed hints
- Pop quizzes during reading
- Pre-reading activation prompts

Deliverable: full active learning system integrated into daily sessions.

### Phase 6: Scenario Simulator and Practice Tools

- Chat-based simulator using Gemini
- Dynamic persona generation from book content and tactic clusters
- Persona storage and evolution system
- Difficulty scaling (Layer 3/4/5) with adaptive persona complexity
- Post-conversation debrief and scoring with book source citations
- Conversation Replay Analysis (paste external conversations)
- Field Report Journal with AI feedback

Deliverable: practice tools for real-world application.

### Phase 7: Knowledge Architecture and Time Awareness

- Interactive concept dependency graph (visual, clickable)
- Contradiction Finder (auto-detected, displayed on topic pages)
- Connection Discovery (AI-surfaced cross-domain links)
- "Why It Works" layer linking tactics to mechanisms
- Pattern Library (searchable tactic database)
- Knowledge Gap Detector with heat map
- Personal Susceptibility Map
- Decay Indicator (visual rust) on all topic cards
- "Days Ago" badges and forgetting curve sparklines
- Calendar heat map (study activity over time)
- "Going Cold" and "In the Attic" alerts
- Session history timeline per topic
- Aggregate decay dashboard
- Per-book freshness view

Deliverable: deep knowledge tools, cross-concept connections, and full time awareness across the system.

### Phase 8: Cognitive Science Features

- Visual anchors per concept
- Teach-Back Mode with AI grading
- "Connect to Your Life" prompts with saved personal examples
- Cross-Context Transfer Exercises
- Consequence Previews
- Mental Model Card builder
- Framework-first topic introductions
- Morning/evening session bookends

Deliverable: all brain-science-based features integrated into the layer system.

### Phase 9: Elite Design Polish

- Full UI/UX pass across every page (see Section 13: Design Quality Standards)
- Personality Profile Builder
- Emotion State Mapping
- Subcommunication Reference Cards
- Export (Markdown, PDF, Anki)
- Book management (add, re-tag, remove)
- Session length configuration
- Streak tracking and gamification
- Micro-animations and transitions
- Typography, color, and spacing refinement
- Mobile-responsive layout
- Performance optimization (lazy loading, query optimization)

Deliverable: a complete, polished, elite-quality system that feels premium to use.

---

## 10. Estimated Effort

| Phase | Estimated Time |
|-------|---------------|
| Phase 1: Data Foundation | 3-4 hours |
| Phase 2: Topic Discovery | 4-6 hours |
| Phase 3: Core Web Interface | 8-10 hours |
| Phase 4: Layered Learning Engine | 6-8 hours |
| Phase 5: Active Learning | 6-8 hours |
| Phase 6: Simulator and Practice | 10-12 hours |
| Phase 7: Knowledge Architecture + Time Awareness | 8-10 hours |
| Phase 8: Cognitive Science Features | 6-8 hours |
| Phase 9: Elite Design Polish | 8-10 hours |
| **Total** | **~60-80 hours** |

Each phase is independently deployable. You can start using the system after Phase 3 and progressively add capabilities. Design quality is baked into every phase, not just Phase 9, but Phase 9 is the final pass to make everything feel elite.

---

## 11. Open Decisions

These need to be decided during implementation:

1. **Gemini model version**: Gemini 2.0 Flash is the current free tier model. If Google updates the free tier, switch to the newest model.
2. **Ollama model choice**: Llama 3 8B vs Mistral 7B vs Phi-3 for offline fallback. Depends on user's hardware (RAM, GPU).
3. **Chunk size tuning**: optimal chunk size depends on PDF quality, may need adjustment after Phase 1
4. **Topic granularity**: the dynamic taxonomy might produce too many or too few topics. Threshold for merging/splitting needs calibration.
5. **Visual framework**: D3.js for dependency graph and heat maps, Chart.js for sparklines, or a unified library
6. **Session length default**: 40 minutes suggested, but user preference may differ
7. **New topic introduction rate**: 1 per 3-4 days suggested, adjustable
8. **Frontend framework**: vanilla JS + Alpine.js for reactivity, or upgrade to Svelte/Vue for more complex interactivity. Decide during Phase 3 based on complexity.
9. **CSS framework**: Tailwind CSS for utility classes, with a custom design system on top for the elite look

---

## 12. Design Principles

1. **Topic-first, not book-first**: the system exists to teach concepts, not to be a PDF reader
2. **Active over passive**: every interaction should require the user to produce something (write, choose, explain), not just consume
3. **Spaced over crammed**: no topic is ever taught in a single session
4. **Interleaved over blocked**: practice sessions mix topics, forcing discrimination
5. **Personal over generic**: the system adapts to the user's retention curve, not a one-size-fits-all formula
6. **Connected over isolated**: every concept links to mechanisms, counters, related concepts, and real-world examples
7. **Local-first**: the user's data never leaves their machine (except Gemini API calls for processing)
8. **Zero cost**: no paid APIs, no subscriptions. Gemini free tier + Ollama cover everything.
9. **Living taxonomy**: topics are discovered from books, not predefined. The system evolves as the library grows.
10. **Elite by default**: every screen, every interaction, every animation is designed to feel premium. No prototype-quality UI at any phase.

---

## 13. Design Quality Standards

The system must look and feel elite at every level. This is not a developer tool or a prototype. It is a personal learning system the user will spend hours in daily. Every detail matters.

### 13.1 Visual Identity

- **Color palette**: dark-first design. Deep navy or charcoal base with carefully chosen accent colors. Not pure black (#000), use rich dark tones (#0f1117, #1a1d27). Accent colors are vivid but not neon. Think: deep blue, emerald, warm amber.
- **Typography**: a distinctive, readable body font (not Inter, not Roboto, not Arial). Something with character that remains legible at long reading sessions. Paired with a clean display font for headings. Example pairings: IBM Plex Serif + IBM Plex Sans, Source Serif Pro + Source Sans Pro, Lora + Nunito Sans.
- **Spacing**: generous whitespace. Content breathes. Nothing feels cramped. Padding and margins are consistent across all pages (use a spacing scale: 4, 8, 12, 16, 24, 32, 48, 64px).
- **Border radius**: subtle, consistent. Not sharp corners, not overly rounded. 6-8px on cards, 4px on buttons.

### 13.2 Component Quality

- **Cards**: topic cards, book cards, quiz cards, all have subtle shadows, smooth hover effects, and clear visual hierarchy. No flat, lifeless boxes.
- **Buttons**: clear primary/secondary/ghost hierarchy. Primary buttons are confident (solid accent color). Hover and active states feel responsive.
- **Progress indicators**: never a plain grey bar. Custom-styled progress bars with gradients, smooth animations, and clear labeling.
- **Forms and inputs**: styled consistently. Focus states are visible and attractive. No browser-default form styling.
- **Loading states**: skeleton screens, not spinners. Content areas show placeholder shapes that match the layout while data loads.
- **Empty states**: when a section has no data yet (no field reports, no flashcards), show an attractive empty state with a clear call to action, not just "nothing here."

### 13.3 Micro-Animations

- **Page transitions**: smooth fade or slide between pages. Not instant hard cuts.
- **Card hover**: subtle lift effect (translateY + shadow increase) on hover.
- **Progress updates**: when a score changes or progress advances, animate the transition (number counts up, bar slides, color shifts).
- **Decay indicator**: color transitions are smooth CSS transitions, not instant jumps.
- **Quiz feedback**: correct answers get a satisfying green flash, wrong answers get a subtle shake.
- **Streak counter**: animated on increment, with a small celebration effect for milestones (7 days, 30 days).
- **Session start**: a brief, elegant animation when starting a daily session, builds anticipation.

### 13.4 Reading Experience

- **Book reader**: clean, distraction-free. Generous margins. Good line-height (1.6-1.8). Max line width of 70-75 characters for readability.
- **Topic view**: clear visual separation between chunks from different books. Book source shown as a subtle tag, not a loud header.
- **Code-like sections** (examples, frameworks): styled in a distinct monospace block with a dark background, clear from body text.
- **Highlights**: when user highlights text, the highlight color is attractive (not browser-default yellow). Multiple highlight colors available.
- **Night reading**: true dark mode that is carefully designed, not just inverted colors. Reduced contrast for comfort, darker backgrounds, slightly muted text.

### 13.5 Data Visualization

- **Heat maps**: custom color scales, not default charting library colors. Match the app's palette.
- **Sparklines**: thin, elegant, integrated into cards naturally. Not chunky chart widgets bolted on.
- **Dependency graph**: interactive, zoomable, with smooth pan and zoom. Nodes are styled to match the app. Not a raw D3 output.
- **Calendar heat map**: custom-styled cells matching the app palette. Hover tooltips are styled, not browser-default.
- **Charts**: minimal chrome. No gridlines unless needed. Labels are readable. Colors match the system palette.

### 13.6 Simulator Chat Interface

- **Chat bubbles**: clean, modern. User messages on one side, AI persona on the other. Distinct colors.
- **Typing indicator**: subtle animation when AI is "thinking."
- **Debrief view**: clear, structured breakdown with color-coded sections (tactics caught = green, missed = amber).
- **Persona introduction**: brief, stylized card showing the scenario context before conversation starts.

### 13.7 Responsive Design

- **Desktop-first** but mobile-usable for quick reviews and flashcard sessions
- **Breakpoints**: 1200px (full), 768px (tablet), 480px (mobile)
- **Mobile**: simplified navigation, swipeable cards, touch-friendly button sizes (min 44px tap target)
- **Reading on mobile**: full-width text, no sidebars, swipe between chapters/chunks

### 13.8 Consistency

- **Design tokens**: all colors, fonts, spacing, shadows, and border radii defined as CSS custom properties. Changed in one place, reflected everywhere.
- **Component library**: reusable components (Card, Button, Badge, Progress, Modal, Tooltip) styled once and used everywhere.
- **No inconsistency**: if a card looks one way on the dashboard, it looks the same way on the topic page. No one-off styling.
