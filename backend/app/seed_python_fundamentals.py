"""Deterministic knowledge graph for the Python fundamentals track:

Learn Python (syntax through objects and errors), then build a small
stdlib-only CLI notebook as a capstone.

Concept ids are namespaced ``python.*`` so they never collide with the
JavaScript backend-framework graph.
"""

from __future__ import annotations

from typing import Any

from app.services.runtime import PYTHON_RUNTIME

ConceptSpec = dict[str, Any]
DependencySpec = tuple[str, str, str]
MilestoneSpec = dict[str, Any]

PY = "https://docs.python.org/3"


def _task(
    task_id: str,
    filename: str,
    prompt: str,
    *,
    stdout_contains: list[str] | None = None,
    run: list[str] | None = None,
    rubric: str = "",
    exit_code: int = 0,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "filename": filename,
        "prompt": prompt,
        "run": run or ["python", filename],
        "expect": {
            "exit_code": exit_code,
            "stdout_contains": list(stdout_contains or []),
        },
        "rubric": rubric,
    }


CONCEPTS: list[ConceptSpec] = [
    {
        "id": "python.scripts",
        "title": "Scripts, print, and running a file",
        "category": "foundation",
        "description": (
            "A Python file is a script: the interpreter reads it top to bottom. "
            "`print` writes to standard output. You run a file with `python path.py`, "
            "which is different from typing code into a REPL."
        ),
        "learning_objectives": [
            "Explain the difference between a .py file and the interactive REPL",
            "Write a script that prints a value when run",
        ],
        "misconceptions": [
            {
                "id": "python-print-returns",
                "description": "The learner thinks print() is how a function returns a value.",
                "signals": [
                    "print returns",
                    "print sends it back",
                    "print is the return",
                ],
                "diagnostic_questions": [
                    "If a function prints 5 but returns nothing, what does the caller receive?",
                ],
                "remediation": {
                    "type": "targeted_question",
                    "script": (
                        "Printing and returning are different events.\n\n"
                        "`print(x)` writes `x` to the terminal. The function still returns `None` "
                        "unless it has a `return` statement.\n\n"
                        "If `def f(): print(5)` and you write `n = f()`, what is `n`?"
                    ),
                },
            }
        ],
        "diagnostic_questions": [
            "What happens when you run `python hello.py`?",
            "Where does `print('hi')` send the text?",
        ],
        "research_questions": [
            "What is the difference between a Python script and the REPL?",
        ],
        "resources": [
            {"title": "Python tutorial: Using the interpreter", "url": f"{PY}/tutorial/interpreter.html"},
        ],
        "hints": [
            "What file will the interpreter open, and what is the first line it will run?",
            "Create the smallest file that prints one line, then run it.",
            "A script is just statements in a file, executed from top to bottom.",
            "Structure: a file named `practice/hello.py` with one `print(...)` statement.",
            "Run `python practice/hello.py` and look at stdout — that is the proof.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "hello",
                "practice/hello.py",
                "Write a script that prints exactly `Hello, Python` when you run it.",
                stdout_contains=["Hello, Python"],
                rubric="The file runs as a script and prints the required line. Do not require a function yet.",
            )
        ],
    },
    {
        "id": "python.names_and_types",
        "title": "Names, assignment, and types",
        "category": "foundation",
        "description": (
            "A name is bound to an object with assignment. Objects have types "
            "(int, str, bool, float). `type(x)` reports the type; names themselves "
            "are not typed in the C sense — the object is."
        ),
        "learning_objectives": [
            "Explain that assignment binds a name to an object",
            "Name the types of integers, strings, and booleans",
        ],
        "misconceptions": [
            {
                "id": "python-name-is-the-box",
                "description": "The learner thinks a variable is a typed box that holds a copy of a value forever.",
                "signals": [
                    "the variable is an int",
                    "the box is a string",
                    "it can only hold",
                ],
                "diagnostic_questions": [
                    "If you do `n = 1` then `n = 'hi'`, is that allowed? Why?",
                ],
                "remediation": {
                    "type": "targeted_question",
                    "script": (
                        "A name is a label stuck on an object, not a typed box.\n\n"
                        "`n = 1` labels an int. `n = 'hi'` peels the label off and sticks it on a string.\n\n"
                        "After those two lines, what does `type(n)` report, and why is that allowed?"
                    ),
                },
            }
        ],
        "diagnostic_questions": [
            "What does assignment do — copy a value into a box, or bind a name to an object?",
            "What is the type of `True`?",
        ],
        "research_questions": [
            "What does `type(x)` return, and what is an object in Python?",
        ],
        "resources": [
            {"title": "Python tutorial: Using Python as a calculator", "url": f"{PY}/tutorial/introduction.html"},
        ],
        "hints": [
            "How would you store your age and then print both the value and its type?",
            "Bind a name, then print the name and `type(...)` of it.",
            "Assignment does not copy a typed box — it labels an object.",
            "Structure: `age = 21` then `print(age, type(age))`.",
            "Run the file and check that stdout shows both the number and `<class 'int'>`.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "types",
                "practice/types.py",
                "Bind `age` to an integer and `label` to a string. Print each value and its type.",
                stdout_contains=["int", "str"],
                rubric="Uses assignment, prints values, and shows types via type(). Does not claim variables are C-style typed boxes.",
            )
        ],
    },
    {
        "id": "python.expressions",
        "title": "Expressions and operators",
        "category": "foundation",
        "description": (
            "Expressions produce values: arithmetic (`+`, `-`, `*`, `/`, `//`, `%`), "
            "comparison (`==`, `<`, `>`), and boolean (`and`, `or`, `not`). "
            "Integer division `//` is not the same as `/`."
        ),
        "learning_objectives": [
            "Predict the result of a small arithmetic expression",
            "Explain the difference between `/` and `//`",
        ],
        "misconceptions": [
            "Treating `/` as integer division the way some languages do",
            "Thinking `=` tests equality",
        ],
        "diagnostic_questions": [
            "What is `7 / 2` versus `7 // 2`?",
            "Which operator tests equality?",
        ],
        "research_questions": [
            "What operators does Python provide for arithmetic and comparison?",
        ],
        "resources": [
            {"title": "Python FAQ: Arithmetic", "url": f"{PY}/faq/programming.html"},
        ],
        "hints": [
            "What two results do you get if you divide 7 by 2 two different ways?",
            "Print both `7 / 2` and `7 // 2`.",
            "`/` always produces a float; `//` floors toward -infinity.",
            "Structure: two print statements, one for each operator.",
            "Run the file and confirm stdout shows `3.5` and `3`.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "divide",
                "practice/divide.py",
                "Print `7 / 2` and `7 // 2` so a reader can see both results.",
                stdout_contains=["3.5", "3"],
                rubric="Shows both true division and floor division. Does not confuse = with ==.",
            )
        ],
    },
    {
        "id": "python.conditionals",
        "title": "Conditionals: if, elif, else",
        "category": "control",
        "description": (
            "A boolean condition chooses which indented block runs. "
            "`elif` is an exclusive alternative; `else` is the remainder. "
            "Indentation is syntax, not decoration."
        ),
        "learning_objectives": [
            "Write an if/elif/else that classifies a number",
            "Explain why indentation defines a block",
        ],
        "misconceptions": [
            {
                "id": "python-elif-all-run",
                "description": "The learner thinks every matching elif also runs after a true if.",
                "signals": [
                    "all of them run",
                    "elif also runs",
                    "every branch executes",
                ],
                "diagnostic_questions": [
                    "If the `if` condition is true, does an `elif` below it still run?",
                ],
                "remediation": {
                    "type": "targeted_question",
                    "script": (
                        "`if` / `elif` / `else` is one chain. The first true condition owns the rest.\n\n"
                        "```python\n"
                        "n = 5\n"
                        "if n > 0:\n"
                        "    print('pos')\n"
                        "elif n > 3:\n"
                        "    print('big')\n"
                        "```\n\n"
                        "What prints, and why does `big` not print even though 5 > 3?"
                    ),
                },
            }
        ],
        "diagnostic_questions": [
            "If the `if` is true, does a later `elif` still run?",
            "What happens if none of the conditions are true and there is no `else`?",
        ],
        "research_questions": [
            "How does Python decide which indented block belongs to an `if`?",
        ],
        "resources": [
            {"title": "Python tutorial: if statements", "url": f"{PY}/tutorial/controlflow.html#if-statements"},
        ],
        "hints": [
            "How would you label a number as negative, zero, or positive?",
            "Write a function or script that prints one word for a chosen integer.",
            "Only the first true branch in an if/elif/else chain runs.",
            "Structure: `if n < 0: ... elif n == 0: ... else: ...`",
            "Run it with a positive number and confirm only one label prints.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "sign",
                "practice/sign.py",
                "Set `n` to an integer. Print `negative`, `zero`, or `positive` using if/elif/else. Use `n = 4` so the file prints `positive`.",
                stdout_contains=["positive"],
                rubric="Uses if/elif/else, prints exactly one label for n=4, and does not run multiple branches.",
            )
        ],
    },
    {
        "id": "python.loops",
        "title": "Loops: for, while, range",
        "category": "control",
        "description": (
            "`for item in iterable` walks values. `range(n)` produces 0..n-1. "
            "`while` repeats until a condition is false. Loops can overshoot if "
            "you forget to update the condition."
        ),
        "learning_objectives": [
            "Write a for-loop over range that accumulates a total",
            "Explain when you would choose while instead of for",
        ],
        "misconceptions": [
            "Off-by-one: thinking range(5) includes 5",
            "Forgetting to update a while-loop condition",
        ],
        "diagnostic_questions": [
            "What numbers does `range(5)` produce?",
            "What happens if a `while` condition never becomes false?",
        ],
        "research_questions": [
            "How does `range` differ from a list of those numbers?",
        ],
        "resources": [
            {"title": "Python tutorial: for statements", "url": f"{PY}/tutorial/controlflow.html#for-statements"},
        ],
        "hints": [
            "How would you add the integers from 1 through 5?",
            "Use a running total and a for-loop over range.",
            "`range(5)` is 0,1,2,3,4 — not 1..5 and not including 5.",
            "Structure: `total = 0` then `for n in range(1, 6): total += n` then print.",
            "Run it and confirm stdout is `15`.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "sum-range",
                "practice/sum_range.py",
                "Print the sum of integers from 1 through 5 (inclusive).",
                stdout_contains=["15"],
                rubric="Uses a loop (for or while). Does not hardcode print(15) with no loop.",
            )
        ],
    },
    {
        "id": "python.functions",
        "title": "Functions, arguments, return, and scope",
        "category": "foundation",
        "description": (
            "`def` creates a function object. Parameters receive arguments when "
            "the function is called. `return` sends a value back to the caller. "
            "Names assigned inside the function are local unless declared otherwise."
        ),
        "learning_objectives": [
            "Write a function that takes a parameter and returns a value",
            "Explain the difference between returning and printing",
        ],
        "misconceptions": [
            {
                "id": "python-print-instead-of-return",
                "description": "The learner prints inside the function and thinks the caller received the value.",
                "signals": [
                    "print gives it back",
                    "the caller gets the print",
                    "print is enough",
                ],
                "diagnostic_questions": [
                    "If greet prints but does not return, what is `msg = greet('Ada')`?",
                ],
                "remediation": {
                    "type": "targeted_question",
                    "script": (
                        "The caller only receives what you `return`.\n\n"
                        "```python\n"
                        "def greet(name):\n"
                        "    print(f'Hello, {name}!')\n"
                        "msg = greet('Ada')\n"
                        "```\n\n"
                        "What is `msg` after this runs? What would you change so `msg` is the greeting string?"
                    ),
                },
            }
        ],
        "diagnostic_questions": [
            "When does the body of a function run — at `def` or at the call?",
            "What does the caller get if there is no `return`?",
        ],
        "research_questions": [
            "What does 'scope' mean for a name assigned inside a function?",
        ],
        "resources": [
            {"title": "Python tutorial: Defining functions", "url": f"{PY}/tutorial/controlflow.html#defining-functions"},
        ],
        "hints": [
            "What goes in, what comes out, and who prints it?",
            "Define `greet(name)` that returns a string, then print the result of a call.",
            "Returning is handing a value to the caller; printing is writing to the terminal.",
            "Structure: `def greet(name): return f'Hello, {name}!'` then `print(greet('Ada'))`.",
            "Run the file — stdout should show `Hello, Ada!` from printing the return value.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "greet",
                "practice/greet.py",
                "Write `greet(name)` that returns `Hello, {name}!`. When the file runs, print `greet('Ada')`.",
                stdout_contains=["Hello, Ada!"],
                rubric="Defines greet, uses the parameter, returns a string, and does not hardcode Ada inside the function body.",
            )
        ],
    },
    {
        "id": "python.lists",
        "title": "Lists: index, append, iterate",
        "category": "collections",
        "description": (
            "A list is an ordered, mutable sequence. Index from 0. "
            "`append` adds at the end. You iterate with `for item in items`."
        ),
        "learning_objectives": [
            "Build a list and iterate over it",
            "Explain what happens if you index past the last item",
        ],
        "misconceptions": [
            "1-based indexing",
            "Thinking lists are copied when you iterate",
        ],
        "diagnostic_questions": [
            "What is `items[0]` for `items = ['a', 'b']`?",
            "What exception do you get for `items[2]` on a two-item list?",
        ],
        "research_questions": [
            "How is a list different from a tuple?",
        ],
        "resources": [
            {"title": "Python tutorial: Lists", "url": f"{PY}/tutorial/introduction.html#lists"},
        ],
        "hints": [
            "How would you collect unique-looking values from a small list?",
            "Start with a list of numbers and print each one.",
            "Indexing starts at 0; `append` mutates the same list.",
            "Structure: a list literal, a loop, `print` of each value.",
            "Run and confirm every item appears on stdout.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "unique",
                "practice/unique.py",
                "From `values = [1, 2, 2, 3, 1]`, print each unique number once, in first-seen order.",
                stdout_contains=["1", "2", "3"],
                rubric="Walks the list (loop or equivalent) and avoids printing duplicates. Order should be 1 then 2 then 3.",
            )
        ],
    },
    {
        "id": "python.dicts",
        "title": "Dictionaries: keys and lookup",
        "category": "collections",
        "description": (
            "A dict maps keys to values. Lookup is `d[key]` or `d.get(key)`. "
            "Keys must be hashable. Iterating a dict yields keys by default."
        ),
        "learning_objectives": [
            "Store and look up a value by key",
            "Explain KeyError versus using get",
        ],
        "misconceptions": [
            "Treating dicts as lists of pairs you index by number",
            "Assuming missing keys return None without .get",
        ],
        "diagnostic_questions": [
            "What happens if you look up a key that is not in the dict with `d[key]`?",
            "How do you get a default when the key is missing?",
        ],
        "research_questions": [
            "Why must dict keys be hashable?",
        ],
        "resources": [
            {"title": "Python tutorial: Dictionaries", "url": f"{PY}/tutorial/datastructures.html#dictionaries"},
        ],
        "hints": [
            "How would you look up a person's age by name?",
            "Build a tiny dict and print one lookup.",
            "`d[key]` raises KeyError if missing; `.get` can return a default.",
            "Structure: `ages = {'Ada': 36}` then print `ages['Ada']`.",
            "Run and confirm stdout shows 36.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "lookup",
                "practice/lookup.py",
                "Create a dict mapping `'Ada'` to `36`. Print the age looked up by that key.",
                stdout_contains=["36"],
                rubric="Uses a dict and a key lookup, not a list index.",
            )
        ],
    },
    {
        "id": "python.strings",
        "title": "Strings: slicing and formatting",
        "category": "collections",
        "description": (
            "Strings are immutable sequences of characters. Slice with `[start:end]`. "
            "f-strings interpolate values. Concatenation with `+` builds a new string."
        ),
        "learning_objectives": [
            "Format a string with an f-string",
            "Explain why `s[0] = 'x'` is illegal",
        ],
        "misconceptions": [
            "Thinking strings can be mutated in place",
        ],
        "diagnostic_questions": [
            "What does `f'Hello, {name}!'` do?",
            "Why can't you assign to `s[0]`?",
        ],
        "research_questions": [
            "What is the difference between concatenating strings and using an f-string?",
        ],
        "resources": [
            {"title": "Python tutorial: Strings", "url": f"{PY}/tutorial/introduction.html#strings"},
        ],
        "hints": [
            "How do you put a name into a sentence without `+` glue?",
            "Use an f-string and print it.",
            "f-strings evaluate expressions inside `{...}`.",
            "Structure: `name = 'Ada'` then `print(f'Hello, {name}!')`.",
            "Run and confirm the interpolated name appears.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "format",
                "practice/format_name.py",
                "Bind `name = 'Ada'` and print `Hello, Ada!` using an f-string (not only concatenation).",
                stdout_contains=["Hello, Ada!"],
                rubric="Uses an f-string (or format) with the name variable, not a fully hardcoded sentence with no interpolation.",
            )
        ],
    },
    {
        "id": "python.files",
        "title": "Files: open, read, write, with",
        "category": "io",
        "description": (
            "`with open(path, mode) as f` acquires a file and closes it. "
            "Read with `read`/`readlines`; write with `write`. Text mode is the default."
        ),
        "learning_objectives": [
            "Write text to a file and read it back",
            "Explain why `with` is preferred over a bare `open`",
        ],
        "misconceptions": [
            "Forgetting to close a file",
            "Assuming write also reads the previous contents",
        ],
        "diagnostic_questions": [
            "What does the `with` statement do for a file besides opening it?",
            "Does `'w'` append or replace?",
        ],
        "research_questions": [
            "What file modes exist, and what does `'w'` do to an existing file?",
        ],
        "resources": [
            {"title": "Python tutorial: Reading and writing files", "url": f"{PY}/tutorial/inputoutput.html#reading-and-writing-files"},
        ],
        "hints": [
            "How would you save one line to a file and then print that file's contents?",
            "Write, then open again to read.",
            "`with` closes the file even if an error happens.",
            "Structure: `with open('practice/note.txt', 'w') as f: f.write('saved\\n')` then read it back and print.",
            "Run and confirm stdout shows `saved`.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "roundtrip",
                "practice/file_roundtrip.py",
                "Write `saved` to `practice/note.txt`, then read the file and print its contents.",
                stdout_contains=["saved"],
                rubric="Uses with open (or equivalent) to write then read. Prints the file contents, not only a hardcoded string.",
            )
        ],
    },
    {
        "id": "python.modules",
        "title": "Modules and import",
        "category": "io",
        "description": (
            "A `.py` file is a module. `import json` loads the standard-library json module. "
            "`from json import dumps` binds a name. Your own files import the same way if they are on the path."
        ),
        "learning_objectives": [
            "Import a stdlib module and use a function from it",
            "Explain the difference between `import json` and `from json import dumps`",
        ],
        "misconceptions": [
            "Thinking import copies source into the file",
            "Confusing the module name with a filename that must be typed every call",
        ],
        "diagnostic_questions": [
            "After `import json`, how do you call `dumps`?",
            "What object does `import json` bind the name `json` to?",
        ],
        "research_questions": [
            "What is the Python standard library, and how do you find a module in it?",
        ],
        "resources": [
            {"title": "Python tutorial: Modules", "url": f"{PY}/tutorial/modules.html"},
        ],
        "hints": [
            "How would you turn a dict into a JSON string using the standard library?",
            "Import `json` and dump a tiny dict.",
            "`import json` binds the module; you call `json.dumps(...)`.",
            "Structure: `import json` then `print(json.dumps({'ok': True}))`.",
            "Run and confirm stdout is valid JSON with `ok`.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "dumps",
                "practice/use_json.py",
                "Import `json` and print `json.dumps({'ok': True})`.",
                stdout_contains=["ok"],
                rubric="Imports json and uses dumps (or dump). Does not hand-write JSON without the module.",
            )
        ],
    },
    {
        "id": "python.classes",
        "title": "Classes, __init__, self, and methods",
        "category": "objects",
        "description": (
            "A class is a blueprint for objects. `__init__` runs when you construct an instance. "
            "`self` is the instance the method was called on. Attributes live on the instance."
        ),
        "learning_objectives": [
            "Define a small class with __init__ and one method",
            "Explain what self refers to",
        ],
        "misconceptions": [
            {
                "id": "python-self-is-the-class",
                "description": "The learner thinks self is the class, not the instance.",
                "signals": [
                    "self is the class",
                    "self means Note",
                    "self is the blueprint",
                ],
                "diagnostic_questions": [
                    "If you construct two Note objects, do they share the same self?",
                ],
                "remediation": {
                    "type": "targeted_question",
                    "script": (
                        "`self` is the instance the method was called on — one object, not the class.\n\n"
                        "```python\n"
                        "class Note:\n"
                        "    def __init__(self, text):\n"
                        "        self.text = text\n"
                        "a = Note('one')\n"
                        "b = Note('two')\n"
                        "```\n\n"
                        "Is `a.self` a thing? Do `a` and `b` share one `self`? What is `a.text`?"
                    ),
                },
            }
        ],
        "diagnostic_questions": [
            "When does `__init__` run?",
            "What is `self` inside a method?",
        ],
        "research_questions": [
            "What is the difference between a class attribute and an instance attribute?",
        ],
        "resources": [
            {"title": "Python tutorial: Classes", "url": f"{PY}/tutorial/classes.html"},
        ],
        "hints": [
            "How would you represent one notebook entry as an object with text?",
            "Define a class with `__init__(self, text)` and a method that returns the text.",
            "`self` is the instance; `__init__` stores attributes on that instance.",
            "Structure: `class Note:` with `__init__` and `def render(self): return self.text`.",
            "Construct `Note('hi')`, print `render()`, and confirm `hi`.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "note-class",
                "practice/note.py",
                "Define `class Note` with `__init__(self, text)` storing `text`. Add `render(self)` that returns the text. Print `Note('hi').render()`.",
                stdout_contains=["hi"],
                rubric="Defines a class, uses self, constructs an instance, and returns (not only prints inside __init__).",
            )
        ],
    },
    {
        "id": "python.exceptions",
        "title": "Exceptions: try, except, raise",
        "category": "errors",
        "description": (
            "Errors are objects. `raise ValueError('msg')` throws. "
            "`try`/`except` catches a type of error so the program can recover. "
            "Bare `except:` hides bugs — catch the type you mean."
        ),
        "learning_objectives": [
            "Catch a specific exception and print a user-facing message",
            "Explain why a bare except is a bad default",
        ],
        "misconceptions": [
            "Catching Exception (or bare except) to 'make it work'",
            "Thinking print is enough to stop a traceback from a raise you did not catch",
        ],
        "diagnostic_questions": [
            "What happens if you `raise ValueError('no')` and nobody catches it?",
            "Why is `except:` dangerous?",
        ],
        "research_questions": [
            "What is the difference between catching ValueError and catching Exception?",
        ],
        "resources": [
            {"title": "Python tutorial: Errors and exceptions", "url": f"{PY}/tutorial/errors.html"},
        ],
        "hints": [
            "How would you look up a missing dict key without crashing the program?",
            "Use try/except KeyError and print a friendly line.",
            "Catch the specific type; do not use a bare except.",
            "Structure: `try: print(d['missing']) except KeyError: print('not found')`.",
            "Run and confirm stdout is `not found` with exit code 0.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "catch-key",
                "practice/catch_key.py",
                "With `data = {'ok': 1}`, look up `'missing'` and catch `KeyError` so the program prints `not found` and exits 0.",
                stdout_contains=["not found"],
                rubric="Catches KeyError specifically (not a bare except). Does not crash.",
            )
        ],
    },
    {
        "id": "python.capstone.model",
        "title": "Capstone: a Note model",
        "category": "capstone",
        "description": (
            "Represent one notebook entry as a class with an id, text, and a way "
            "to turn it into a plain dict (for later JSON persistence)."
        ),
        "learning_objectives": [
            "Design a small Note class that can round-trip to a dict",
        ],
        "misconceptions": [
            "Putting all CLI parsing inside the Note class",
        ],
        "diagnostic_questions": [
            "What fields does one note need so you can save and reload it?",
        ],
        "research_questions": [
            "Why separate the data model from the command-line parser?",
        ],
        "resources": [
            {"title": "Python tutorial: Classes", "url": f"{PY}/tutorial/classes.html"},
        ],
        "hints": [
            "What is the smallest object you can save?",
            "A Note with id and text, plus to_dict / from_dict.",
            "Keep argparse out of this class — it is data, not the CLI.",
            "Structure: `notebook.py` with `class Note` and helpers to serialize.",
            "Write a tiny `if __name__ == '__main__'` that constructs one note and prints its dict.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "model",
                "notebook.py",
                "In `notebook.py`, define `Note` with `id` and `text`, plus `to_dict()`. When run, print one note's dict containing the text `first`.",
                stdout_contains=["first"],
                rubric="Note is a class with instance attributes. Printing a dict/json of the note is enough for this step; CLI can come later.",
            )
        ],
        "mentor_scripts": {
            "application_prompt": (
                "You explained the model. Apply it: if two notes have the same text "
                "but different ids, are they the same note? Why?"
            )
        },
    },
    {
        "id": "python.capstone.persistence",
        "title": "Capstone: JSON persistence",
        "category": "capstone",
        "description": (
            "Save a list of notes to a JSON file and load them back. "
            "Handle a missing file by starting with an empty list."
        ),
        "learning_objectives": [
            "Write load/save functions around a JSON file",
        ],
        "misconceptions": [
            "Assuming the file always exists",
        ],
        "diagnostic_questions": [
            "What should load() return if notes.json does not exist yet?",
        ],
        "research_questions": [
            "How do you convert between dicts and JSON strings with the json module?",
        ],
        "resources": [
            {"title": "json — JSON encoder and decoder", "url": f"{PY}/library/json.html"},
        ],
        "hints": [
            "What is the file format, and who opens it?",
            "load() / save() using json and a with-open.",
            "Missing file → empty list; do not crash.",
            "Structure: functions `load_notes(path)` and `save_notes(path, notes)` in notebook.py.",
            "When run, save one note and load it back, then print the text.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True},
        "practice_tasks": [
            _task(
                "persist",
                "notebook.py",
                "Add load/save for a JSON file (e.g. `notes.json`). Running the file should save a note with text `persisted` and print that text after loading.",
                stdout_contains=["persisted"],
                rubric="Uses the json module and files. Missing-file case should not be a crash in the design, even if this run creates the file.",
            )
        ],
    },
    {
        "id": "python.capstone.cli",
        "title": "Capstone: argparse commands",
        "category": "capstone",
        "description": (
            "Expose `add` and `list` commands with argparse so a human can use the notebook "
            "from the terminal without editing Python."
        ),
        "learning_objectives": [
            "Wire argparse to add and list notes",
        ],
        "misconceptions": [
            "Parsing sys.argv by hand with no error messages",
        ],
        "diagnostic_questions": [
            "Which object should parse argv — the Note class or a CLI function?",
        ],
        "research_questions": [
            "How does argparse define subcommands?",
        ],
        "resources": [
            {"title": "argparse — Parser for command-line options", "url": f"{PY}/library/argparse.html"},
        ],
        "hints": [
            "What two verbs does a notebook need first?",
            "Subcommands add and list.",
            "Keep parsing in a `main()` (or similar), not on Note.",
            "Structure: `python notebook.py add --text hello` and `python notebook.py list`.",
            "Implement add so running list afterwards shows the text.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True, "testing": True},
        "practice_tasks": [
            _task(
                "cli-list",
                "notebook.py",
                "Support listing notes. After adding a note in code or via CLI, `python notebook.py list` (or running the file) should print `listed`. You may seed that text for this check, but argparse should exist.",
                stdout_contains=["listed"],
                run=["python", "notebook.py", "list"],
                rubric="Uses argparse (or equivalent CLI). list command prints notes. Temporary seed of a note with text listed is acceptable if load/save is wired.",
            )
        ],
    },
    {
        "id": "python.capstone.errors",
        "title": "Capstone: user-facing errors",
        "category": "capstone",
        "description": (
            "Bad input (empty text, unknown command, corrupt JSON) should become a clear "
            "message and a non-zero or handled exit — not a raw traceback the user cannot act on."
        ),
        "learning_objectives": [
            "Turn invalid input into a readable error without a traceback for expected cases",
        ],
        "misconceptions": [
            "Letting JSONDecodeError crash the CLI",
        ],
        "diagnostic_questions": [
            "What should the program print if someone adds an empty note?",
        ],
        "research_questions": [
            "When should a CLI exit with code 1 versus catch and continue?",
        ],
        "resources": [
            {"title": "Python tutorial: Errors and exceptions", "url": f"{PY}/tutorial/errors.html"},
        ],
        "hints": [
            "Which failures are expected from a human, versus bugs in your code?",
            "Validate empty text; catch JSON errors on load.",
            "User-facing messages go to stderr or stdout; expected errors should not dump a stack.",
            "Structure: raise or catch ValueError for empty text; catch json.JSONDecodeError on load.",
            "Write a small demo path that prints `empty note` when text is missing.",
        ],
        "mastery_requirements": {"explanation": True, "implementation": True, "testing": True},
        "practice_tasks": [
            _task(
                "empty-note",
                "notebook.py",
                "If add is given empty text, print a user-facing `empty note` message instead of a traceback.",
                stdout_contains=["empty note"],
                run=["python", "notebook.py", "add", "--text", ""],
                rubric="Empty text is handled. No uncaught traceback for this case.",
            )
        ],
    },
]

DEPENDENCIES: list[DependencySpec] = [
    ("python.names_and_types", "python.scripts", "You need a running file before names mean anything on screen."),
    ("python.expressions", "python.names_and_types", "Operators produce objects that names can be bound to."),
    ("python.conditionals", "python.expressions", "if tests the boolean result of an expression."),
    ("python.loops", "python.conditionals", "A loop still decides whether to continue using a condition."),
    ("python.functions", "python.loops", "You will call functions from loops; return vs print should already be distinct."),
    ("python.lists", "python.functions", "You will pass lists into functions and iterate them."),
    ("python.dicts", "python.lists", "Dicts are another collection; lookup is not the same as list indexing."),
    ("python.strings", "python.functions", "f-strings and return values show up together in real functions."),
    ("python.files", "python.strings", "You write strings into files."),
    ("python.modules", "python.files", "json and other stdlib modules are how you persist structured text."),
    ("python.classes", "python.functions", "A method is a function bound to an instance."),
    ("python.classes", "python.dicts", "Objects often expose themselves as dicts for saving."),
    ("python.exceptions", "python.dicts", "KeyError is the natural error of a missing lookup."),
    ("python.capstone.model", "python.classes", "The notebook entry is a class."),
    ("python.capstone.model", "python.exceptions", "Construction and serialization will need honest errors later."),
    ("python.capstone.persistence", "python.capstone.model", "You persist the model you just designed."),
    ("python.capstone.persistence", "python.modules", "JSON persistence uses the json module and files."),
    ("python.capstone.cli", "python.capstone.persistence", "Commands read and write the saved notes."),
    ("python.capstone.errors", "python.capstone.cli", "User-facing errors wrap the commands you already exposed."),
]

MILESTONES: list[MilestoneSpec] = [
    {
        "id": "M01",
        "title": "First programs",
        "description": "Run a file, bind names, and print values — the loop of writing Python.",
        "instructions": (
            "What to do:\n"
            "1. Explain what happens when you run a .py file.\n"
            "2. Complete the practice files the mentor names (hello, types, divide).\n"
            "3. Do not jump to classes or a whole app yet."
        ),
        "success_criteria": "You can run a script and explain names, types, and `/` vs `//`.",
        "concepts": ["python.scripts", "python.names_and_types", "python.expressions"],
    },
    {
        "id": "M02",
        "title": "Decisions and loops",
        "description": "Control which lines run, and how many times.",
        "instructions": (
            "What to do:\n"
            "1. Write an if/elif/else classifier and a summing loop.\n"
            "2. Be able to say what range(5) produces."
        ),
        "success_criteria": "Conditionals take one branch; a loop computes a total without hardcoding the answer only.",
        "concepts": ["python.conditionals", "python.loops"],
    },
    {
        "id": "M03",
        "title": "Functions",
        "description": "Package behavior behind a name, with arguments and return values.",
        "instructions": (
            "What to do:\n"
            "1. Write greet(name) that returns a string.\n"
            "2. Explain return vs print."
        ),
        "success_criteria": "A function returns a value the caller can print; the greeting is not hardcoded inside the function.",
        "concepts": ["python.functions"],
    },
    {
        "id": "M04",
        "title": "Collections",
        "description": "Lists, dicts, and strings as data you pass around.",
        "instructions": (
            "What to do:\n"
            "1. Deduplicate a list in first-seen order.\n"
            "2. Look up a dict by key.\n"
            "3. Format a string with an f-string."
        ),
        "success_criteria": "You can iterate a list, look up a dict key, and interpolate a string.",
        "concepts": ["python.lists", "python.dicts", "python.strings"],
    },
    {
        "id": "M05",
        "title": "Files and modules",
        "description": "Talk to the disk and the standard library.",
        "instructions": (
            "What to do:\n"
            "1. Write and read a small text file with `with open`.\n"
            "2. Use json.dumps on a dict."
        ),
        "success_criteria": "A file round-trips text; json is imported and used.",
        "concepts": ["python.files", "python.modules"],
    },
    {
        "id": "M06",
        "title": "Objects",
        "description": "Build a tiny class and use self honestly.",
        "instructions": (
            "What to do:\n"
            "1. Define Note (or equivalent) with __init__ and a method.\n"
            "2. Explain what self is."
        ),
        "success_criteria": "An instance stores data on self and a method returns it.",
        "concepts": ["python.classes"],
    },
    {
        "id": "M07",
        "title": "Errors",
        "description": "Catch the error you mean; do not hide bugs.",
        "instructions": (
            "What to do:\n"
            "1. Catch KeyError on a missing lookup and print a friendly message.\n"
            "2. Explain why a bare except is a bad default."
        ),
        "success_criteria": "Expected missing-key cases do not crash; the except is specific.",
        "concepts": ["python.exceptions"],
    },
    {
        "id": "M08",
        "title": "Capstone: CLI notebook",
        "description": "A file-backed personal notebook using only the standard library.",
        "instructions": (
            "What to do:\n"
            "1. Model a note, persist JSON, expose add/list via argparse.\n"
            "2. Give a clear message for empty text.\n"
            "3. You may add pytest tests under tests/ as you go."
        ),
        "success_criteria": "python notebook.py list works against saved notes; empty add is handled; pytest -q can pass if you added tests.",
        "concepts": [
            "python.capstone.model",
            "python.capstone.persistence",
            "python.capstone.cli",
            "python.capstone.errors",
        ],
    },
    {
        "id": "M09",
        "title": "Review and defense",
        "description": "Re-read your notebook and defend the design: model vs CLI vs persistence.",
        "instructions": (
            "What to do:\n"
            "1. Refactor one thing without changing observable behavior.\n"
            "2. Answer defense questions from your actual code."
        ),
        "success_criteria": "You can explain load/save, argparse, and error handling from your files.",
        "concepts": [],
    },
]

PROJECT_SPEC: dict[str, Any] = {
    "title": "Learn Python: Language and a CLI Notebook",
    "description": (
        "Learn Python from scripts and types through functions, collections, files, "
        "classes, and exceptions, then build a small file-backed command-line notebook "
        "using only the standard library."
    ),
    "objective": (
        "By the end you can write and run Python files, explain core language ideas "
        "in your own words, and ship a tiny CLI that stores notes in JSON — that you "
        "can defend without copying a framework."
    ),
    "difficulty": "beginner",
    "prerequisites": [
        "Comfort with a terminal",
        "No prior Python required",
    ],
    "expected_outcome": (
        "A working stdlib CLI notebook (add/list, JSON file, user-facing errors) "
        "plus completed practice snippets for each language concept."
    ),
    "skills": [
        "Running Python scripts",
        "Functions, collections, and classes",
        "Files and the json module",
        "argparse CLIs",
        "Catching specific exceptions",
    ],
    "constraints": [
        "Standard library only — no Flask, FastAPI, Django, or requests",
        "No AI-generated implementation — you write every line",
        "Practice snippets live under practice/; the capstone is notebook.py",
    ],
    "tests": [
        "practice snippets run and print the required output",
        "notebook.py can list notes from JSON",
        "empty add is handled without a traceback",
        "optional pytest -q passes when tests exist",
    ],
    "evaluation_criteria": [
        "All language concepts have explanation + implementation evidence",
        "Capstone files exist and run",
        "Learner can defend model vs persistence vs CLI",
    ],
    "extension_challenges": [
        "Add a delete command by id",
        "Add tags on notes",
        "Write pytest tests for load/save",
    ],
    "recommended_resources": [
        {"title": "Python tutorial", "url": f"{PY}/tutorial/index.html"},
        {"title": "argparse", "url": f"{PY}/library/argparse.html"},
        {"title": "json", "url": f"{PY}/library/json.html"},
    ],
    "runtime": dict(PYTHON_RUNTIME),
}
