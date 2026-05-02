# CS2103T iP Assessment Criteria (reference)

This is the rubric the Rubric Mapper grounds against. It mirrors the public iP
assessment areas and is intentionally kept short so the LLM can reason over the
whole thing in one pass.

The mapper produces, for each criterion below, a list of files/methods in the
student's repo that demonstrate the criterion, plus a list of gaps where the
criterion is not yet evidenced.

Criteria are not independent — a strong submission satisfies several with the
same code. The mapper is allowed (and encouraged) to cite the same file under
multiple criteria.

## 1. Functional correctness

The chatbot implements the increments through the level the student claims to
have reached. Evidence:

- Each command works on the documented golden-path input.
- Errors do not crash the program (Level-5 onwards).
- Persistence works across runs (Level-7 onwards).
- Dates are stored and rendered as proper date types (Level-8 onwards).

The mapper looks at the most recent tag and considers all increments up to
that point. It does not attempt to score functionality by execution — that is
the Adversarial Tester's job.

## 2. Code quality

The codebase follows the CS2103T coding standard. Evidence:

- Naming, brace style, line length, imports comply.
- Methods stay around 30 lines or under.
- No `printStackTrace()` left in main flow.
- Custom exceptions are used for expected failure modes.

This criterion overlaps with the Code Quality reviewer; the mapper summarises
rather than re-runs that analysis.

## 3. Object-oriented design

After `A-MoreOOP`, the codebase is decomposed into classes with single,
named responsibilities. Evidence:

- A `Ui` (or equivalently named) class owns input/output.
- A `Parser` class owns string-to-command translation.
- A `TaskList` class owns the collection of tasks.
- A `Storage` class owns file I/O.
- The orchestrator class is small and delegates.

The mapper specifically calls out responsibility leaks: e.g., file I/O in the
main class, parsing happening inside `Ui`, etc.

## 4. Testing

There is meaningful test coverage. Evidence:

- At least two JUnit test classes under `src/test/`.
- Tests target non-trivial logic (parsing, list operations), not getters.
- `./gradlew test` passes.
- Optionally: text-UI tests exist (`A-TextUiTesting`).

## 5. Documentation

Public API surface is documented. Evidence:

- Public classes and public methods have JavaDoc.
- JavaDoc describes intent and behaviour, not the implementation.
- A reasonable README exists at the project root explaining how to run.

## 6. Process and project hygiene

Evidence:

- Tags are pushed for each completed increment.
- Commits are reasonably sized and have informative messages.
- No build artifacts (`.jar`, `.class`, `build/`) committed.
- The Gradle wrapper is present and the project builds.

This criterion is partly visible to the mapper (file presence) and partly not
(commit history is summarised separately if requested).

## 7. AI-Assisted Development reflection

If `A-AiAssisted` has been tagged, evidence includes:

- A reflection paragraph (in README, a markdown file, or a commit message).
- Clear marking of which parts were AI-assisted.

## What "gap" means

A gap is a criterion the repo does not yet evidence at the level expected for
the most recent tag. Gaps are framed as:

> "Criterion X — not yet evidenced. The closest existing code is `<file>`
> which does Y; consider whether Z would close the gap."

Not as marks lost. The mapper is not a grader.
