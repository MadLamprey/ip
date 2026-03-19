# Proposal: AI-Powered Increment Reviewer for CS2103T iP

**Prepared by:** Aditya Misra  
**Course:** CS2103T Software Engineering  
**Semester:** AY2526 S2

---

## 1. Problem

The iP gives students a fast-paced incremental workflow — a new set of increments every week, each building on the last. The formal feedback loop, however, is slow: TA reviews and peer evaluations happen at fixed points, often days after the code was written. By then, a student may have built several more increments on top of a misunderstood concept.

This means two things are true simultaneously:
- Students who are going wrong don't find out until it's too late to easily fix it.
- Students who are going right get no reinforcement until the same delayed point.

Neither outcome is ideal for a course whose explicit goal is to build good SE habits gradually and repeatedly over the semester.

---

## 2. Proposed Solution

A lightweight GitHub Action — **iP Increment Reviewer** — that triggers every time a student pushes an increment tag (`Level-N`, `A-Xxx`, `B-Xxx`) to their fork. It automatically posts a short code review as a commit comment within ~30 seconds of the push.

The reviewer:
1. Detects which increment was just tagged from the pushed tag name
2. Computes a `git diff` of the student's code since their previous increment tag
3. Fetches the official requirements for that increment live from the course website
4. Calls an LLM (Anthropic Claude) with the diff and requirements
5. Posts the review as a GitHub commit comment — visible directly on the student's commit page

The review is structured into three short sections:
- **Requirements check** — does the code appear to satisfy what the increment asks for?
- **Observations** — correctness or design concerns, framed as questions not corrections
- **One thing done well** — a specific positive from the diff

---

## 3. Pedagogical Design

The tool is deliberately constrained to preserve the learning that the iP is designed to produce.

| Constraint | Rationale |
|---|---|
| Posts observations and questions, never corrected code | Students must still think through fixes themselves |
| Triggers on every tag push, not on demand | Feedback is tied to the natural workflow rhythm — unavoidable without being intrusive |
| Fetches requirements from the live course website | Review is always grounded in what the course actually asks, not a stale hardcoded copy |
| Non-blocking — a comment, not a failing check | Students can disagree with it, which is itself a learning decision |
| Covers only the diff since the previous tag | Keeps feedback scoped and actionable, not overwhelming |

The framing given to the LLM in the system prompt is explicit: *"Never provide corrected code or complete solutions. Frame observations as questions or point to concepts."* This is the critical design constraint that separates the tool from a code-completion assistant.

---

## 4. Architecture

```
Student pushes tag  →  GitHub Actions triggers
                              │
                    ┌─────────▼──────────┐
                    │   review.py        │
                    │                    │
                    │  1. git diff       │
                    │     (prev → curr)  │
                    │                    │
                    │  2. fetch page     │
                    │     (course site)  │
                    │                    │
                    │  3. call LLM API   │
                    │                    │
                    │  4. post comment   │
                    └─────────┬──────────┘
                              │
                    Commit comment posted
                    on student's GitHub
```

**Files added to each student's repo:**
```
.github/
  workflows/
    ip-reviewer.yml     ← triggers on tag push
  scripts/
    review.py           ← all logic; ~200 lines of Python
```

**Dependencies:** Python 3.11 (pre-installed on GitHub Actions runners), `anthropic`, `requests`, `beautifulsoup4`.

**LLM backend:** Anthropic Claude (`claude-opus-4-5`). The backend is isolated to a single function in `review.py` and can be swapped to the GitHub Models API (which uses the student's existing `GITHUB_TOKEN` — no separate key needed) with a single function replacement.

---

## 5. Integration with the Existing iP Workflow

The tool requires no change to how students work. The iP already requires students to:
- Tag each completed increment (`git tag Level-5`)
- Push tags to their fork (`git push --tags`)

The reviewer activates on exactly those existing actions. There is no new step, no new command, no new interface to learn. Students simply notice a comment appearing on their commit after each push.

---

## 6. What This Is Not

To be explicit about scope:

- It does **not** grade the student or feed into any automated grading pipeline
- It does **not** block pushes or fail the build
- It does **not** write code for students or complete their increments
- It does **not** replace TA reviews or peer evaluations
- It does **not** require students to interact with any AI tool directly

It is a faster feedback loop, not a replacement for any existing part of the course.

---

## 7. Limitations and Mitigations

| Limitation | Mitigation |
|---|---|
| LLM may occasionally misread the diff or give inaccurate feedback | Disclaimer posted with every comment: *"This is an automated review — use your own judgement and check with your TA if unsure"* |
| Course website unreachable at action runtime | Graceful fallback: comment explains requirements fetch failed; review proceeds without them |
| API cost per push | Estimated < SGD 0.05 per review at current Claude pricing; manageable at course scale or can use GitHub Models (free with Copilot) |
| `TAG_URLS` map needs updating each semester | Map is ~30 lines, clearly documented, takes ~10 minutes to update |
| Students could push meaningless tags to farm reviews | Reviews are informational only and not graded; no incentive to game |

---

## 8. Setup Per Student

1. Copy `.github/workflows/ip-reviewer.yml` and `.github/scripts/review.py` into their fork
2. Add `ANTHROPIC_API_KEY` as a GitHub Actions secret in their repo settings
3. Push as normal — the reviewer activates on the next tag push

Total setup time: approximately 5 minutes.

---

## 9. Example Output

The following is an illustrative example of the comment posted after a student pushes `Level-7`:

---

> ## 🤖 iP Increment Review — `Level-7`
>
> **Requirements check** — Partially. The code saves tasks to a file on shutdown and loads on startup, which is the core ask. However, the file path appears to be hardcoded as an absolute path (`C:/Users/john/data/tasks.txt`), which the requirements specifically warn against.
>
> **Observations** — Your `Storage` class reads and writes the file correctly. Have you considered what happens if the `data/` directory doesn't exist yet when the app runs for the first time? The requirements mention the app should handle this gracefully — which exception might be relevant here?
>
> **One thing done well** — The separation of file I/O into a dedicated `Storage` class is exactly the kind of OOP decomposition the course is pushing towards. It will make Level-9's refactoring step much easier.
>
> 📖 [Official requirements for Level-7](https://nus-cs2103-ay2526-s2.github.io/...)
>
> *This is an automated review. It may not be 100% accurate — use your own judgement and ask your TA if unsure.*

---

## 10. Future Extensions

The same architecture can be extended in later semesters:

- **tP support** — trigger on PR creation rather than tag push; review against tP feature requirements
- **Trend summary** — a weekly digest comment summarising patterns across all of a student's increment reviews
- **TA dashboard** — aggregate reviews across all students to surface common misconceptions for the teaching team to address in tutorials