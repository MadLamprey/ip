# CS2103T Coding Standard (reference)

This is the standard the Code Quality reviewer checks against. It is a condensed
version of the official CS2103T coding standard. The reviewer cites violations
back as `file:line` references.

The standard is split into two layers: low-level style rules (mechanically
checkable) and design-level conventions (judgement calls). The reviewer prefers
to flag the former and ask questions about the latter.

## Naming

- Classes and interfaces: `UpperCamelCase`. Examples: `TaskList`, `Storage`.
- Methods, fields, parameters, local variables: `lowerCamelCase`. Examples:
  `markAsDone`, `taskCount`.
- Constants (`static final`): `UPPER_SNAKE_CASE`. Example: `MAX_TASKS`.
- Enum members: `UPPER_SNAKE_CASE`.
- Type parameters: a single uppercase letter (`T`, `K`, `V`).
- Names should be descriptive. Avoid `temp`, `data`, `obj`, `foo` as names of
  things that survive past the immediate line they're declared on.
- Boolean methods/fields read as predicates: `isDone`, `hasNext`, `canParse`.

## File and class layout

- One top-level class per file. The file name matches the class name.
- File length: keep under ~700 lines. Beyond that, the class is doing too much.
- Inside a class, order: constants, fields, constructors, public methods,
  private/helper methods, nested types.
- One blank line between methods. No blank line at the start or end of a method
  body.

## Methods

- Method length: aim for under ~30 lines. Methods longer than this almost always
  contain extractable sub-responsibilities.
- A method should do one thing at one level of abstraction. Mixing high-level
  control flow with low-level parsing inside one method is a common code smell.
- Use early returns over deep nesting where it reads more clearly.
- Avoid output parameters and side-effect-heavy returns. Prefer pure helpers.

## Indentation and braces

- Indent with 4 spaces, not tabs.
- Java brace style: opening brace on the same line as the declaration; closing
  brace on its own line.
- Always use braces for `if`, `else`, `for`, `while` — even for single-line
  bodies.

## Line length

- Limit lines to about 120 characters. Wrap before exceeding this where natural.

## Imports

- No wildcard imports (`import java.util.*` is not allowed).
- Each import on its own line.
- No unused imports.

## Comments and JavaDoc

- Public classes and public methods get a JavaDoc comment.
- The JavaDoc describes intent and behaviour, not the implementation. "Returns
  the task at index i" is fine; "Uses an ArrayList to look up the task" is not.
- Use `@param` and `@return` tags where applicable.
- Inline comments are reserved for explaining *why* something is unusual, not
  *what* is happening. Names should explain the what.

## Whitespace

- One space around binary operators: `a + b`, not `a+b`.
- No space between a method name and its opening paren: `foo()`, not `foo ()`.
- One space after keywords: `if (x)`, not `if(x)`.
- A trailing newline at the end of every file.

## Magic numbers and strings

- Repeated literal numbers or strings (other than `0`, `1`, `-1`, `""`) should
  be extracted as named constants.
- Command keywords like `"todo"` or `"deadline"` are good candidates for
  constants or, after `A-Enums`, enum members.

## Exceptions

- Catch the most specific exception type the situation warrants. `catch (Exception e)`
  as the only handler is a smell.
- Do not silently swallow exceptions. If you catch and ignore, leave a comment
  explaining why. Otherwise, log or rethrow.
- Custom exceptions for expected failure modes (e.g. `DukeException`) are
  preferred over re-using runtime exceptions.

## OOP and design (judgement-call layer)

- Single Responsibility: a class should have one reason to change. After
  `A-MoreOOP`, the iP expects roughly: `Ui` (I/O), `Parser` (string → command),
  `TaskList` (collection logic), `Storage` (file I/O), and a thin orchestrator.
- Information should live where it is used. If a `Parser` needs to know the
  data file path, that knowledge probably belongs in `Storage` instead.
- Prefer instance methods over static methods for core logic. Static is
  appropriate for pure utility functions.
- Avoid passing around primitive obsession (e.g. `int statusCode` everywhere).
  Lift it into a small type when the meaning matters.
- Avoid one-class-does-everything. If `Duke.java` contains parsing, storage,
  and rendering, the design has not yet earned the increment.

## Common iP-specific smells the reviewer watches for

- Hardcoded absolute paths (e.g. `/Users/...`) — fails portability and the
  Level-7 constraint.
- File I/O in the main class instead of `Storage`.
- Command parsing branching on raw strings deep inside `Duke.run()` after
  `A-MoreOOP` has been tagged.
- `printStackTrace()` left in production code paths.
- Public fields without getters, broken encapsulation.
- Catching `Exception` to silence a specific bug rather than diagnosing it.
