"""Deterministic knowledge graph + seed data for the first structured project:

"Build a Simple Backend Framework in JavaScript".

This module is the single source of truth for what gets learned and in what
order. The AI mentor (app/agents/mentor_graph.py) never invents or reorders
this content — it only questions/hints/reviews within whatever the graph
currently allows (see app/services/curriculum_graph.py).

Each concept dict has:
    id, title, category, description
    learning_objectives: list[str]
    misconceptions: list[str] | list[dict]
    diagnostic_questions: list[str]   -- used for the optional prerequisite-skip quiz
    research_questions: list[str]    -- "research this before I explain it"
    resources: list[{"title", "url"}]
    hints: list[str]                 -- exactly 5, indices 0..4 =
                                          question / direction / concept /
                                          structure / targeted
    mastery_requirements: dict[str, bool] -- subset of
        {"research", "implementation", "testing", "explanation"}

Dependencies are declared as (concept_id, requires_concept_id, reason) so the
mentor can explain *why* a learner is being sent backward.
"""

from __future__ import annotations

from typing import Any

ConceptSpec = dict[str, Any]
DependencySpec = tuple[str, str, str]
MilestoneSpec = dict[str, Any]

MDN = "https://developer.mozilla.org"

CONCEPTS: list[ConceptSpec] = [
    # ---------------------------------------------------------------- FOUNDATION
    {
        "id": "programming.functions",
        "title": "Functions, parameters, callbacks, closures",
        "category": "foundation",
        "description": (
            "Functions as values: parameters, return values, passing a function "
            "as an argument (callback), and closures capturing outer variables."
        ),
        "learning_objectives": [
            "Explain what a callback is and why it lets code run 'later'",
            "Explain, in your own words, what a closure captures and why",
        ],
        "misconceptions": [
            {
                "id": "callback-runs-when-passed",
                "description": (
                    "The learner thinks passing a function as an argument immediately runs it."
                ),
                "signals": [
                    "runs immediately",
                    "as soon as you pass",
                    "when you pass it",
                    "passing executes",
                    "it runs because you passed",
                ],
                "diagnostic_questions": [
                    "Does the function run at the moment it is passed, or later?",
                    "Which line would you delete to stop the callback from ever running?",
                ],
                "remediation": {
                    "type": "trace_execution",
                    "script": (
                        "I think we've found the part that's unclear.\n\n"
                        "Passing a function and calling a function are two different events.\n\n"
                        "```javascript\n"
                        "function later(cb) {\n"
                        "  cb();\n"
                        "}\n"
                        "later(() => console.log('inside'));\n"
                        "```\n\n"
                        "Two separate answers, please:\n"
                        "1. Which line *passes* the function?\n"
                        "2. Which exact line *invokes* it?"
                    ),
                    "teach_script": (
                        "Passing a function only stores it. Calling it is what runs it.\n\n"
                        "`later(() => console.log('inside'))` gives `later` a function. "
                        "Nothing inside that arrow function runs yet.\n\n"
                        "`cb()` is the line that prints `inside`.\n\n"
                        "If you deleted `cb();`, would `inside` still print?"
                    ),
                    "retest_script": (
                        "Exactly. Passing and invoking are different events.\n\n"
                        "Now prove you can see that without the parameter being named `cb`:\n\n"
                        "```javascript\n"
                        "function run(operation) {\n"
                        "  console.log('start');\n"
                        "  operation();\n"
                        "  console.log('end');\n"
                        "}\n"
                        "run(() => console.log('work'));\n"
                        "```\n\n"
                        "Two separate answers:\n"
                        "1. Which line passes the function?\n"
                        "2. Which line invokes it?"
                    ),
                },
            },
            {
                "id": "callback-caller-confusion",
                "description": (
                    "The learner confuses passing a callback with invoking it: they think "
                    "the caller of the outer function is what executes the callback."
                ),
                "signals": [
                    "the person who called",
                    "who called myfunction",
                    "the caller of myfunction",
                    "the one that called myfunction",
                    "the person who called myfunction",
                    "because we have the callback function line called next",
                    "the caller executes the callback",
                    "the callback runs because it appears as an argument",
                ],
                "diagnostic_questions": [
                    "Which line passes the function?",
                    "Which line invokes the function?",
                    "What happens if cb() is removed?",
                ],
                "remediation": {
                    "type": "trace_execution",
                    "script": (
                        "I think we've found the part that's unclear.\n\n"
                        "You're distinguishing when `myFunction` is called, but we're asking "
                        "when the *callback itself* is called. Those are two different events.\n\n"
                        "```javascript\n"
                        "function myFunction(cb) {\n"
                        "  console.log('before');\n"
                        "  cb();\n"
                        "  console.log('after');\n"
                        "}\n"
                        "myFunction(() => console.log('inside'));\n"
                        "```\n\n"
                        "Two separate answers, please — don't merge them:\n"
                        "1. What does `myFunction(() => console.log('inside'))` do?\n"
                        "2. What does the `cb();` line do?\n\n"
                        "If the execution order (before → inside → after) was already clear, "
                        "keep that. The remaining error is *who invokes* the callback."
                    ),
                    "retest_script": (
                        "Exactly. Passing and invoking are different events.\n\n"
                        "Now prove you can see that without the parameter being named `cb`:\n\n"
                        "```javascript\n"
                        "function run(operation) {\n"
                        "  console.log('start');\n"
                        "  operation();\n"
                        "  console.log('end');\n"
                        "}\n"
                        "run(() => console.log('work'));\n"
                        "```\n\n"
                        "Two separate answers:\n"
                        "1. Which line passes the function?\n"
                        "2. Which line invokes it?"
                    ),
                    "teach_script": (
                        "You traced the order correctly: before → inside → after.\n\n"
                        "That order is the mechanism. Passing and invoking are different events.\n\n"
                        "`myFunction(() => console.log('inside'))` only gives `myFunction` a function. "
                        "Nothing inside that arrow function runs yet.\n\n"
                        "`cb()` is the later. That is the line that prints `inside`.\n\n"
                        "A callback can run 'later' because the function is stored until some other "
                        "line invokes it. Closures are a different idea — we will do those next.\n\n"
                        "One check: if you deleted the `cb();` line, would `inside` still print?"
                    ),
                },
            },
            {
                "id": "closure-copies-values",
                "description": (
                    "The learner thinks a closure copies outer variables instead of capturing them."
                ),
                "signals": [
                    "copies the variable",
                    "copies the value",
                    "snapshot of the variable",
                    "saves a copy",
                ],
                "diagnostic_questions": [
                    "If the outer variable changes after the inner function is created, what does the inner function see?",
                ],
                "remediation": {
                    "type": "targeted_question",
                    "script": (
                        "I think we've found the part that's unclear.\n\n"
                        "A closure does not copy the outer variable. It keeps a live link to it.\n\n"
                        "If `let n = 1` and an inner function reads `n`, then later `n = 2`, "
                        "what does the inner function print when you call it?"
                    ),
                },
            },
        ],
        "diagnostic_questions": [
            "What is a callback function?",
            "If a function returns another function that reads an outer variable, what happens to that variable?",
        ],
        "research_questions": [
            "What is a higher-order function?",
            "What does 'a function is a first-class value' mean in JavaScript?",
        ],
        "resources": [
            {"title": "MDN: Functions", "url": f"{MDN}/en-US/docs/Web/JavaScript/Guide/Functions"},
            {"title": "MDN: Closures", "url": f"{MDN}/en-US/docs/Web/JavaScript/Closures"},
        ],
        "hints": [
            "What does the function you're writing actually receive as input, and what does it hand back?",
            "Try writing the smallest possible function that takes another function as an argument and calls it.",
            "A callback is just a function passed as data — it runs when *you* call it, not when it's passed.",
            "Structure: `function outer(cb) { /* ... */ cb(value); }` — trace who calls `cb` and when.",
            "Run your snippet and add a `console.log` right before and after the callback call to see the order.",
        ],
        "mastery_requirements": {"explanation": True},
        "mentor_scripts": {
            "application_prompt": (
                "That explanation is enough to treat this as explained — not yet verified.\n\n"
                "Use it: a router stores a function when you register a path and runs it later "
                "when a request matches. Which moment is passing, and which is invoking?"
            ),
            "transfer_prompt": (
                "Same distinction, new names — don't reuse the previous wording.\n\n"
                "```javascript\n"
                "queue.push(job);\n"
                "job();\n"
                "```\n\n"
                "Which line passes the function, and which line invokes it?"
            ),
        },
    },
    {
        "id": "programming.objects",
        "title": "Objects, properties, methods, references",
        "category": "foundation",
        "description": (
            "Object literals, dot/bracket property access, methods as functions "
            "attached to objects, and argument passing: JavaScript passes arguments "
            "by value. When the value is an object reference, the parameter receives "
            "a copy of that reference, so mutating the object through one variable is "
            "visible through the other."
        ),
        "learning_objectives": [
            "Explain the difference between an object's property and its method",
            "Explain why mutating an object through a function parameter is visible to the caller: the parameter holds a copy of the object reference, not a copy of the object",
        ],
        "misconceptions": [
            "Thinking objects are copied (the object itself) when passed into functions",
            "Treating 'objects are passed by reference' as the complete model — JavaScript copies the reference value",
            "Confusing `this` inside a method with the function's own scope variables",
        ],
        "diagnostic_questions": [
            "What's the difference between a property and a method on an object?",
            "If you pass an object into a function and the function changes a property, does the caller see that change? Why, without saying 'passed by reference' as the whole story?",
        ],
        "research_questions": [
            "JavaScript passes arguments by value. When that value is an object reference, what does the parameter receive?",
            "What is object destructuring and why might you use it?",
        ],
        "resources": [
            {"title": "MDN: Working with objects", "url": f"{MDN}/en-US/docs/Web/JavaScript/Guide/Working_with_objects"},
        ],
        "hints": [
            "How would you store 'a name and an age together' as one value?",
            "Try defining an object literal with two properties and one method, then call the method.",
            "A method is just a function stored as a property — nothing more.",
            "Structure: `const obj = { field: value, method() { /* uses this.field */ } };`",
            "Log `obj` before and after calling a method that mutates a field — compare the two.",
        ],
        "mastery_requirements": {"explanation": True},
    },
    {
        "id": "programming.arrays",
        "title": "Arrays, iteration, searching, collections",
        "category": "foundation",
        "description": (
            "Arrays as ordered collections; iterating with for/of or array "
            "methods; finding an element that matches a condition."
        ),
        "learning_objectives": [
            "Explain how to find the first element in an array matching a condition",
            "Explain why an array of objects is a reasonable way to store a 'table' of records",
        ],
        "misconceptions": [
            "Using an index-based loop when `.find()`/`.filter()` would be clearer",
            "Forgetting that `.find()` returns `undefined`, not throwing, when nothing matches",
        ],
        "diagnostic_questions": [
            "How would you find the first item in a list that matches some condition?",
            "What does an array method return when nothing matches?",
        ],
        "research_questions": [
            "What's the difference between `Array.prototype.find` and `Array.prototype.filter`?",
        ],
        "resources": [
            {"title": "MDN: Array.prototype.find", "url": f"{MDN}/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/find"},
        ],
        "hints": [
            "If you had a list of objects, how would you pick out just the one you need?",
            "Try storing three objects in an array, then write one line that finds one by a property value.",
            "`.find()` scans in order and stops at the first match — think about what 'first' means for your data.",
            "Structure: `array.find(item => item.someField === target)`",
            "Log what `.find()` returns when you search for something that isn't in the array.",
        ],
        "mastery_requirements": {"explanation": True},
    },
    # ---------------------------------------------------------------- NETWORKING
    {
        "id": "networking.client_server",
        "title": "Client / server / request / response",
        "category": "networking",
        "description": (
            "The basic model: a server listens and handles requests; a client "
            "initiates a request and waits for a response."
        ),
        "learning_objectives": [
            "Explain, at a high level, what a server does that a plain script doesn't",
            "Explain the difference between a client and a server in one sentence each",
        ],
        "misconceptions": [
            "Thinking the server 'pushes' data to clients without being asked (for plain HTTP)",
            "Confusing the browser (a client) with the machine hosting the site (a server)",
        ],
        "diagnostic_questions": [
            "What does it mean for a program to 'listen' for connections?",
            "Who initiates a request — the client or the server?",
        ],
        "research_questions": [
            "What happens, conceptually, when you type a URL into a browser and press enter?",
        ],
        "resources": [
            {"title": "MDN: How the web works", "url": f"{MDN}/en-US/docs/Learn/Common_questions/Web_mechanics/How_does_the_Internet_work"},
        ],
        "hints": [
            "What does a backend framework actually do — think about who asks and who answers.",
            "Sketch (in words) the two participants and which one waits, and which one initiates.",
            "A server is a long-running process that waits; a client sends a request and waits for a reply.",
            "Structure: client --request--> server --response--> client. Nothing happens until the client asks.",
            "Not a code hint — describe out loud what happens between you pressing enter and seeing a page.",
        ],
        "mastery_requirements": {"research": True, "explanation": True},
    },
    {
        "id": "networking.tcp",
        "title": "TCP: connections, ports, listening",
        "category": "networking",
        "description": (
            "TCP at a high level: reliable, ordered byte streams over a "
            "connection identified by an IP + port; a server listens on a port."
        ),
        "learning_objectives": [
            "Explain why an HTTP server needs a network transport underneath it",
            "Explain what a port number identifies",
        ],
        "misconceptions": [
            "Thinking HTTP and TCP are the same thing",
            "Thinking a port is a physical thing rather than a numbered logical endpoint",
        ],
        "diagnostic_questions": [
            "What does a server listen on?",
            "Why does HTTP need something like TCP underneath it?",
        ],
        "research_questions": [
            "What is TCP, at a level you could explain to a teammate in two sentences?",
            "What is a port, and why can two servers on the same machine use different ports?",
        ],
        "resources": [
            {"title": "MDN: What is a URL / ports", "url": f"{MDN}/en-US/docs/Learn/Common_questions/Web_mechanics/What_is_a_URL"},
        ],
        "hints": [
            "HTTP messages have to travel somehow — what carries the bytes reliably in order?",
            "Look up: what problem does TCP solve that raw packet-sending doesn't?",
            "TCP gives you an ordered, reliable stream between two endpoints identified by IP+port.",
            "Structure: connection = (client IP, client port) <-> (server IP, server port). One process, one port, many clients.",
            "Don't write code yet — explain in one sentence why 'listening on a port' is necessary.",
        ],
        "mastery_requirements": {"research": True, "explanation": True},
    },
    {
        "id": "networking.socket",
        "title": "Sockets: accept, receive, send, lifecycle",
        "category": "networking",
        "description": (
            "A socket is the OS-level handle for one connection: accepting it, "
            "reading incoming bytes, writing outgoing bytes, and closing it."
        ),
        "learning_objectives": [
            "Explain what object/handle represents 'one connection' in code",
            "Describe the lifecycle: accept -> data -> respond -> close",
        ],
        "misconceptions": [
            "Thinking one socket represents the whole server rather than one connection",
        ],
        "diagnostic_questions": [
            "What happens when a client connects, at the socket level?",
            "What is a socket?",
        ],
        "research_questions": [
            "In Node.js, what event does a TCP server emit when a new client connects?",
        ],
        "resources": [
            {"title": "Node.js docs: net.Server", "url": "https://nodejs.org/api/net.html#class-netserver"},
        ],
        "hints": [
            "Find out: what does Node.js hand you when a new client connects to a TCP server?",
            "Research Node's `net` module — what event fires on a new connection, and what argument does it get?",
            "A socket is the handle for exactly one connection — it can emit 'data' and be written to.",
            "Structure: `server.on('connection', socket => { socket.on('data', chunk => {...}); })`",
            "Create the smallest `net.createServer` you can and log every event the socket emits.",
        ],
        "mastery_requirements": {"research": True, "explanation": True},
    },
    # ---------------------------------------------------------------- HTTP
    {
        "id": "http.protocol",
        "title": "HTTP as a protocol",
        "category": "http",
        "description": (
            "HTTP is a text-based request/response protocol built on top of "
            "TCP: methods, status codes, headers, and a body."
        ),
        "learning_objectives": [
            "List the parts of an HTTP request and an HTTP response",
            "Explain what a status code communicates",
        ],
        "misconceptions": [
            "Thinking HTTP is a binary protocol rather than (historically) text-based",
            "Confusing status codes with HTTP methods",
        ],
        "diagnostic_questions": [
            "What is HTTP?",
            "Name two things an HTTP response needs to include besides the body.",
        ],
        "research_questions": [
            "What is HTTP?",
            "What do the 2xx/4xx/5xx status code ranges roughly mean?",
        ],
        "resources": [
            {"title": "MDN: HTTP overview", "url": f"{MDN}/en-US/docs/Web/HTTP/Overview"},
        ],
        "hints": [
            "What structure does every HTTP message share, on both the request and response side?",
            "Look up the 5 parts of an HTTP request and the 3 parts of an HTTP response.",
            "HTTP is request/response: method+path+headers+body going one way, status+headers+body coming back.",
            "Write down (plain text, no code) one example request and one example response for `GET /`.",
            "Explain, without notes, what a 404 vs a 500 status code each mean.",
        ],
        "mastery_requirements": {"research": True, "explanation": True},
    },
    {
        "id": "http.request",
        "title": "HTTP request structure",
        "category": "http",
        "description": "METHOD, PATH, HEADERS, BODY — what each part of a request means.",
        "learning_objectives": [
            "Explain what the method and path each communicate",
            "Explain what headers are for, with one concrete example",
        ],
        "misconceptions": [
            "Thinking the path includes the query string as part of 'the path' without distinction",
        ],
        "diagnostic_questions": [
            "What does the HTTP method tell the server?",
            "What is a header, and give one example.",
        ],
        "research_questions": [
            "What are the most common HTTP methods and what does each conventionally mean?",
        ],
        "resources": [
            {"title": "MDN: HTTP request methods", "url": f"{MDN}/en-US/docs/Web/HTTP/Methods"},
        ],
        "hints": [
            "If you saw `GET /users/42 HTTP/1.1`, what does each token tell you?",
            "Look up 3-4 HTTP methods and what each conventionally means.",
            "Method = action intent, path = resource, headers = metadata, body = payload (for some methods).",
            "Write out, by hand, the request your browser would send for `GET /users`.",
            "Explain the difference between `GET` and `POST` in one sentence, without using the word 'get' or 'post'.",
        ],
        "mastery_requirements": {"research": True, "explanation": True},
    },
    {
        "id": "http.response",
        "title": "HTTP response structure",
        "category": "http",
        "description": "STATUS, HEADERS, BODY — what each part of a response means.",
        "learning_objectives": [
            "Explain what a status line communicates versus the body",
        ],
        "misconceptions": [
            "Thinking the body is required on every response",
        ],
        "diagnostic_questions": [
            "What three things make up an HTTP response?",
        ],
        "research_questions": [
            "What is the `Content-Type` header for, and why does it matter to a client?",
        ],
        "resources": [
            {"title": "MDN: HTTP responses", "url": f"{MDN}/en-US/docs/Web/HTTP/Messages#http_responses"},
        ],
        "hints": [
            "When your browser gets a page, what three kinds of information came back with it?",
            "Look up what `Content-Type` and `Content-Length` headers are for.",
            "Status communicates outcome; headers describe the body; body is the actual payload (optional).",
            "Write out, by hand, a plausible response for a successful JSON API call.",
            "Explain why a `DELETE` response might have no body at all.",
        ],
        "mastery_requirements": {"research": True, "explanation": True},
    },
    {
        "id": "http.raw_request",
        "title": "What a raw HTTP request looks like on the wire",
        "category": "http",
        "description": (
            "Seeing the literal text bytes of a request before any parsing — "
            "the input a server actually receives."
        ),
        "learning_objectives": [
            "Identify method/path/headers/body inside an unparsed request string",
        ],
        "misconceptions": [
            "Assuming the runtime automatically gives you a structured object for free",
        ],
        "diagnostic_questions": [
            "Given a raw request block of text, which line is the method and path?",
        ],
        "research_questions": [
            "If you opened a raw TCP connection and typed an HTTP request by hand, what would the first line look like?",
        ],
        "resources": [
            {"title": "MDN: HTTP messages", "url": f"{MDN}/en-US/docs/Web/HTTP/Messages"},
        ],
        "hints": [
            "Given:\n  GET /users HTTP/1.1\n  Host: localhost:3000\n  Accept: application/json\n\nWhat information can you identify in this?",
            "Which line is the request line, and which lines are headers? What separates them?",
            "The first line is method+path+version; each following line up to a blank line is a header.",
            "Structure: `<line1: METHOD PATH VERSION>\\r\\n<header lines>\\r\\n\\r\\n<optional body>`",
            "Use `net`/`http` in Node to log the raw incoming data before you parse anything — compare it to this example.",
        ],
        "mastery_requirements": {"research": True, "explanation": True},
    },
    {
        "id": "http.parsing",
        "title": "Parsing a raw request into structured data",
        "category": "http",
        "description": (
            "Transforming raw request text/bytes into a structured object: "
            "{ method, path, headers, body }."
        ),
        "learning_objectives": [
            "Implement a function that extracts method/path/headers from raw text",
            "Explain the design of the resulting object",
        ],
        "misconceptions": [
            "Trying to parse the body before finding the header/body boundary",
            "Assuming headers always arrive lower-cased or in a fixed order",
        ],
        "diagnostic_questions": [
            "What information do we need to extract from the raw request?",
            "How would you represent that information in JavaScript?",
        ],
        "research_questions": [
            "How does Node's built-in `http` module expose the parsed request to you already?",
        ],
        "resources": [
            {"title": "Node.js docs: http.IncomingMessage", "url": "https://nodejs.org/api/http.html#class-httpincomingmessage"},
        ],
        "hints": [
            "What information do we need to extract from the raw request, and how would you represent it in JavaScript?",
            "Try writing a function signature first: what does it take in, what does it return?",
            "You need method, path, headers (as an object), and body — nothing more, nothing less, to start.",
            "Structure: split on the first blank line to separate headers from body; split the first line on spaces for method/path.",
            "Test your parser against the exact raw example from http.raw_request and print the resulting object.",
        ],
        "mastery_requirements": {"research": True, "implementation": True, "testing": True, "explanation": True},
    },
    # ---------------------------------------------------------------- SERVER
    {
        "id": "server.listen",
        "title": "Creating a server and listening",
        "category": "server",
        "description": "Creating a server, listening on a port, accepting connections, receiving request data.",
        "learning_objectives": [
            "Start a Node.js server that accepts a connection and logs something",
        ],
        "misconceptions": [
            "Forgetting the process needs to stay alive/listening to accept more than one connection",
        ],
        "diagnostic_questions": [
            "What does 'listening' mean for a server process?",
        ],
        "research_questions": [
            "How do you create a TCP or HTTP server in Node.js and have it listen on a port?",
        ],
        "resources": [
            {"title": "Node.js docs: http.createServer", "url": "https://nodejs.org/api/http.html#httpcreateserveroptions-requestlistener"},
        ],
        "hints": [
            "Create the smallest Node.js server you can that accepts a connection. Don't use Express.",
            "Look up Node's `http` (or `net`) module — what's the minimum call sequence to listen on a port?",
            "You need: create the server object, register a handler, call `.listen(port)`.",
            "Structure: `require('http').createServer((req, res) => { ... }).listen(3000)`",
            "Run it and hit it with `curl localhost:3000` — what do you see in your terminal on both sides?",
        ],
        "mastery_requirements": {"research": True, "implementation": True, "testing": True, "explanation": True},
    },
    {
        "id": "server.lifecycle",
        "title": "The request lifecycle end-to-end",
        "category": "server",
        "description": (
            "start server -> receive connection -> receive data -> interpret "
            "request -> produce response -> send response."
        ),
        "learning_objectives": [
            "Trace one request through every stage of the lifecycle in your own server",
        ],
        "misconceptions": [
            "Treating 'receiving data' and 'interpreting the request' as the same step",
        ],
        "diagnostic_questions": [
            "Put these in order: send response, receive connection, interpret request, produce response, receive data.",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "Walk through, in order, everything that happens between a client connecting and getting a reply.",
            "Where does your parser (http.parsing) fit into this sequence? Where does the response get written?",
            "start -> connection -> data -> parse -> decide response -> write response -> (maybe) close.",
            "Add a `console.log` at each of the 6 lifecycle stages in your actual server code.",
            "Run one request and paste the ordered log output — does it match the lifecycle diagram?",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    # ---------------------------------------------------------------- ROUTING
    {
        "id": "routing.problem",
        "title": "The problem routing solves",
        "category": "routing",
        "description": "path + method -> handler: how does the server know which function to run?",
        "learning_objectives": [
            "Articulate routing as a lookup problem before writing any routing code",
        ],
        "misconceptions": [
            "Assuming a single if/else chain doesn't count as 'routing' when it's exactly the first version of it",
        ],
        "diagnostic_questions": [
            "If the server receives GET /users, how does your application know which function should execute?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "If the server receives GET /users, how does your application know which function should execute?",
            "What two pieces of information from the request would you need to make that decision?",
            "Routing is a lookup: (method, path) -> handler function.",
            "Before any data structure: write, in comments, what an if/else chain checking method+path would look like.",
            "Now write that if/else chain for two routes by hand — that IS a (bad) router.",
        ],
        "mastery_requirements": {"explanation": True},
    },
    {
        "id": "routing.registration",
        "title": "Registering routes",
        "category": "routing",
        "description": 'A mechanism for registering routes, e.g. router.get("/users", handler).',
        "learning_objectives": [
            "Design and implement a data structure that stores (method, path, handler) triples",
        ],
        "misconceptions": [
            "Storing only the handler and forgetting to key it by both method and path",
        ],
        "diagnostic_questions": [
            "What does your router need to store about each registered route?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "What does your router need to remember about every route someone registers?",
            "Try writing `get(path, handler)` first — what does it need to do with its arguments?",
            "Each registration needs at least: method, path, handler — stored somewhere you can search later.",
            "Structure: an array of `{ method, path, handler }` objects, appended to on every `get()`/`post()` call.",
            "Register two routes, then log your storage structure — does it contain what you expect?",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    {
        "id": "routing.matching",
        "title": "Matching an incoming request to a route",
        "category": "routing",
        "description": "incoming request -> method + path -> matching route -> handler.",
        "learning_objectives": [
            "Implement lookup that finds the right handler for an incoming method+path",
        ],
        "misconceptions": [
            "Matching on path only and ignoring method (so GET and POST /users collide)",
        ],
        "diagnostic_questions": [
            "Given a request's method and path, how do you find the matching registered route?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "How would you search your registered routes to find the one that matches an incoming request?",
            "You already have a way to store routes (routing.registration) — what search does 'find the match' need?",
            "Match requires both method AND path to be equal — neither alone is enough.",
            "Structure: `routes.find(r => r.method === req.method && r.path === req.path)`",
            "Wire this into your server's request handler and test both a matching and a non-matching request.",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    {
        "id": "routing.not_found",
        "title": "Handling unmatched routes (404)",
        "category": "routing",
        "description": "No route matched -> respond 404, instead of crashing or hanging.",
        "learning_objectives": [
            "Return a proper 404 response when no route matches",
        ],
        "misconceptions": [
            "Letting the request hang with no response when nothing matches",
        ],
        "diagnostic_questions": [
            "What should happen when no registered route matches the incoming request?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "What happens right now in your code if nothing in routing.matching finds a match?",
            "Where in your request handler would you check 'did I find a route or not'?",
            "No match found is not an error in your code — it's a normal case that needs its own response.",
            "Structure: `if (!route) { res.statusCode = 404; res.end('Not Found'); return; }`",
            "Test by requesting a path you never registered — confirm you get 404, not a hang or a crash.",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    {
        "id": "routing.parameters.problem",
        "title": "The problem of dynamic route segments",
        "category": "routing",
        "description": 'How can /users/:id understand that 123 in /users/123 is the value of "id"?',
        "learning_objectives": [
            "Articulate what a route pattern with a dynamic segment represents",
        ],
        "misconceptions": [
            "Thinking `:id` needs to literally match the string `:id` in the URL",
        ],
        "diagnostic_questions": [
            "What does `/users/:id` represent to you?",
            "If the incoming URL is `/users/42`, what parts of that URL stay the same and what part changes?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "Given `/users/:id` and an incoming `/users/123`, how could your router understand that 123 is the value of id?",
            "Split both the pattern and the incoming path on `/` — now compare the pieces position by position.",
            "A segment starting with `:` is a placeholder — its position tells you what to name the captured value.",
            "Structure: `pattern.split('/')` vs `path.split('/')`, same length, compare piece-by-piece, collect `:name` matches.",
            "Trace by hand: pattern `/users/:id` vs path `/users/123` — write out the two split arrays side by side.",
        ],
        "mastery_requirements": {"explanation": True},
    },
    {
        "id": "routing.parameters.extraction",
        "title": "Extracting route parameters",
        "category": "routing",
        "description": 'Implementing extraction so req.params.id === "123" for a route like /users/:id.',
        "learning_objectives": [
            "Implement parameter extraction and expose it as req.params",
        ],
        "misconceptions": [
            "Extracting the parameter but not attaching it anywhere the handler can read it",
        ],
        "diagnostic_questions": [
            "Once you've matched a route with a `:param` segment, how do you get the actual value out?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "You can already tell a pattern segment is a placeholder — how do you capture the real value at that position?",
            "Extend your matching function to also return the captured params, not just true/false.",
            "For each `:name` segment, the value at the same position in the real path is `params[name]`.",
            "Structure: `if (patternPart.startsWith(':')) params[patternPart.slice(1)] = pathPart;`",
            "Test with `/users/:id` against `/users/123` and confirm `params.id === '123'` (string, not number).",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    # ---------------------------------------------------------------- REQUEST/RESPONSE
    {
        "id": "request.object",
        "title": "Designing the request object",
        "category": "request_response",
        "description": "A convenience object handlers receive: method, path, headers, body, params, query.",
        "learning_objectives": [
            "Design and implement the shape of the request object handlers receive",
        ],
        "misconceptions": [
            "Re-parsing the raw request inside every handler instead of doing it once upstream",
        ],
        "diagnostic_questions": [
            "Which information will route handlers repeatedly need from a request?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "Which information will route handlers repeatedly need? List it before writing any object.",
            "You already produce most of these pieces separately (parsing, params) — where would you combine them?",
            "The request object is just a container: attach `params` (from matching) onto the parsed request.",
            "Structure: `const req = { ...parsed, params };` built once per request, before calling the handler.",
            "Log `req` right before calling a handler for a parameterized route — confirm every field is present.",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    {
        "id": "response.object",
        "title": "Designing the response object",
        "category": "request_response",
        "description": "A convenience object with send(), json(), status() methods wrapping the raw response.",
        "learning_objectives": [
            "Design and implement send/json/status without an external framework",
        ],
        "misconceptions": [
            "Calling `res.json()` and `res.send()` on the same response and not handling the double-write",
        ],
        "diagnostic_questions": [
            "What methods would make responding easy for a handler author, without exposing raw headers/body plumbing?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "If you were the one writing route handlers, what one-line methods would you want to call to respond?",
            "Try `res.send(text)` first — what does it need to set and write on the underlying raw response?",
            "`send` writes a plain body, `json` sets a Content-Type and stringifies, `status` sets the code and returns `this`.",
            "Structure: attach these as methods on (or wrapping) Node's raw `http.ServerResponse` for each request.",
            "Test: call `res.status(201).json({ id: 1 })` from a handler and confirm headers + body are correct.",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    # ---------------------------------------------------------------- MIDDLEWARE
    {
        "id": "middleware.problem",
        "title": "The problem middleware solves",
        "category": "middleware",
        "description": "Cross-cutting behavior (e.g. logging) that every route would otherwise need to duplicate.",
        "learning_objectives": [
            "Articulate why per-handler duplication of cross-cutting logic doesn't scale",
        ],
        "misconceptions": [
            "Thinking middleware is only for logging, not a general 'run before/after' mechanism",
        ],
        "diagnostic_questions": [
            "Imagine every route needs logging. Would you rather add logging manually to every handler?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "Imagine every route needs logging. Would you rather add logging manually to every handler? Why not?",
            "What would happen to your codebase if you needed to add auth checks to 20 routes the same way?",
            "Repeating the same code in every handler is a sign you need a layer that runs for ALL requests.",
            "Sketch (in words) a function that runs before every handler, given the request and response.",
            "No code yet — name two more cross-cutting concerns besides logging that fit this same shape.",
        ],
        "mastery_requirements": {"explanation": True},
    },
    {
        "id": "middleware.concept",
        "title": "Middleware pipeline concept",
        "category": "middleware",
        "description": "request -> middleware -> middleware -> handler -> response, with next() and short-circuiting.",
        "learning_objectives": [
            "Explain execution order, next(), request/response modification, and stopping the pipeline",
        ],
        "misconceptions": [
            "Assuming middleware runs automatically without something explicitly calling next()",
        ],
        "diagnostic_questions": [
            "What does calling next() actually do?",
            "What happens if a middleware function never calls next()?",
        ],
        "research_questions": [
            "How does Express's middleware model (req, res, next) work, at a conceptual level?",
        ],
        "resources": [],
        "hints": [
            "If middleware runs 'before' the handler, what mechanism hands control from one middleware to the next?",
            "Research the (req, res, next) middleware signature — what is `next` actually?",
            "`next` is just a callback — calling it invokes the next thing in your pipeline.",
            "Structure: middleware = `(req, res, next) => { ...; next(); }` — a chain of these, then the handler.",
            "Trace on paper: 2 middlewares + 1 handler — write the exact call order if each calls `next()` once.",
        ],
        "mastery_requirements": {"research": True, "explanation": True},
    },
    {
        "id": "middleware.pipeline",
        "title": "Implementing the middleware pipeline",
        "category": "middleware",
        "description": "Executing a list of middleware functions in order, each able to call next() or stop.",
        "learning_objectives": [
            "Implement middleware registration (app.use) and sequential execution",
        ],
        "misconceptions": [
            "Running all middleware in a for-loop without waiting for each to call next()",
        ],
        "diagnostic_questions": [
            "How does control move from one middleware function to the next in your implementation?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "How does control move from one middleware function to the next in your implementation?",
            "Try writing a function that, given an index into your middleware array, calls that middleware with a `next` that advances the index.",
            "Each `next()` call should invoke the *next* middleware (or the handler once the list is exhausted).",
            "Structure: `function run(i) { if (i === list.length) return handler(req,res); list[i](req, res, () => run(i+1)); }`",
            "Add a middleware that never calls `next()` and confirm the handler is correctly never reached.",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    # ---------------------------------------------------------------- ERROR HANDLING
    {
        "id": "error.problem",
        "title": "Where should failures be handled?",
        "category": "error",
        "description": "Handler throws, route doesn't exist, request is malformed — where does each get handled?",
        "learning_objectives": [
            "Enumerate the different kinds of failure a framework must anticipate",
        ],
        "misconceptions": [
            "Assuming a thrown error inside a handler automatically produces a clean HTTP response",
        ],
        "diagnostic_questions": [
            "If a route handler throws an exception, what happens to the request right now in your code?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "Handler throws an error, route doesn't exist, request is malformed — where should each failure be handled?",
            "Try throwing inside one of your existing handlers — what actually happens to the HTTP response?",
            "An uncaught throw inside a handler can crash the process or hang the request unless something catches it.",
            "Sketch where a catch-all needs to sit relative to your middleware pipeline and handler call.",
            "No code yet — explain, out loud, the difference between a 4xx (client's fault) and 5xx (server's fault) failure.",
        ],
        "mastery_requirements": {"explanation": True},
    },
    {
        "id": "error.middleware",
        "title": "Implementing error-handling middleware",
        "category": "error",
        "description": "A dedicated mechanism that catches handler/middleware errors and converts them to a response.",
        "learning_objectives": [
            "Implement a catch-all that turns a thrown error into a clean HTTP response",
        ],
        "misconceptions": [
            "Wrapping only the final handler in try/catch and missing errors thrown inside middleware",
        ],
        "diagnostic_questions": [
            "Where in your pipeline execution would you place a try/catch to cover both middleware and handlers?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "Where in your pipeline execution would a single try/catch cover both middleware and the final handler?",
            "Try wrapping the call that runs each pipeline step and see what you need to catch.",
            "One try/catch around the whole per-request dispatch, not one per handler, catches everything uniformly.",
            "Structure: `try { run(0); } catch (err) { res.statusCode = 500; res.end('Internal Error'); }`",
            "Make a handler throw on purpose and confirm the client gets a clean 500 instead of a hang or crash.",
        ],
        "mastery_requirements": {"implementation": True, "testing": True, "explanation": True},
    },
    # ---------------------------------------------------------------- TESTING
    {
        "id": "testing.problem",
        "title": "Why manual testing isn't enough",
        "category": "testing",
        "description": "Manually curling GET /, GET /users, GET /users/123 doesn't scale or catch regressions.",
        "learning_objectives": [
            "Explain what manual testing misses that automated testing catches",
        ],
        "misconceptions": [
            "Believing 'it worked when I tried it' is equivalent to 'it's correct'",
        ],
        "diagnostic_questions": [
            "What's the risk of only testing your server by hand with curl before each change?",
        ],
        "research_questions": [],
        "resources": [],
        "hints": [
            "You've been testing GET /, GET /users, GET /users/123 by hand — what happens once you add middleware and it breaks an old route?",
            "Think about how long manual re-checking takes as the number of routes grows.",
            "Manual testing only checks what you remember to check, right now — automated tests check everything, every time.",
            "List (in words) the exact scenarios from testing.integration's list that you'd want checked automatically.",
            "Not a code hint — explain what a regression is, using your own framework as the example.",
        ],
        "mastery_requirements": {"explanation": True},
    },
    {
        "id": "testing.integration",
        "title": "Automated integration tests for the framework",
        "category": "testing",
        "description": (
            "Automated tests: server starts, GET works, POST works, 404 works, "
            "parameters work, middleware works, errors are handled."
        ),
        "learning_objectives": [
            "Write automated tests covering the framework's core behaviors using Node's built-in test runner",
        ],
        "misconceptions": [
            "Testing only the happy path and skipping 404/error scenarios",
        ],
        "diagnostic_questions": [
            "Which part of your implementation is responsible for parsing?" ,
            "Which specific behaviors from your framework need their own test?",
        ],
        "research_questions": [
            "How does Node's built-in `node --test` runner work, and what does an `assert`-based test look like?",
        ],
        "resources": [
            {"title": "Node.js docs: Test runner", "url": "https://nodejs.org/api/test.html"},
        ],
        "hints": [
            "List every behavior you'd want to be confident still works after any change — that list is your test plan.",
            "Look up Node's built-in `node --test` and `assert` modules — no external framework needed.",
            "Each test should: start (or reuse) your server, make one request, assert on the response.",
            "Structure: `test('GET / responds 200', async () => { const res = await fetch(...); assert.equal(res.status, 200); });`",
            "Run `node --test` and read the failure output carefully — which assertion, which line, what was expected vs actual?",
        ],
        "mastery_requirements": {"research": True, "implementation": True, "testing": True, "explanation": True},
    },
]

DEPENDENCIES: list[DependencySpec] = [
    ("programming.objects", "programming.functions",
     "Objects build on function fundamentals: methods are functions attached to data."),
    ("programming.arrays", "programming.objects",
     "Arrays of routes/middleware are collections of objects/functions; object literals come first."),
    ("networking.client_server", "programming.functions",
     "A server handling a request is a function call triggered remotely — think in functions first."),
    ("networking.tcp", "networking.client_server",
     "TCP is the transport that makes the client/server model work over a real network."),
    ("networking.socket", "networking.tcp",
     "A socket is the concrete handle TCP gives you for a connection — the TCP mental model comes first."),
    ("http.protocol", "networking.client_server",
     "HTTP is a text protocol layered on top of the client/server request/response model."),
    ("http.request", "http.protocol",
     "You cannot describe a request's structure without first knowing HTTP is a request/response protocol."),
    ("http.response", "http.protocol",
     "Response structure only makes sense once you know the protocol shape."),
    ("http.raw_request", "http.request",
     "Seeing the raw bytes only makes sense once you know what a request conceptually contains."),
    ("http.parsing", "http.raw_request",
     "You can't design a parser until you've looked at what raw input actually looks like."),
    ("http.parsing", "programming.objects",
     "The parsed result is represented as an object — object literals are required to model it."),
    ("server.listen", "networking.socket",
     "Listening is literally accepting socket connections — the OS-level concept must come first."),
    ("server.listen", "http.protocol",
     "You're listening in order to speak HTTP — the protocol context motivates the server."),
    ("server.lifecycle", "server.listen",
     "The lifecycle wraps around a server that can already accept connections."),
    ("server.lifecycle", "http.parsing",
     "Interpreting the request is a lifecycle stage — parsing must exist first."),
    ("server.lifecycle", "http.response",
     "Producing a response is a lifecycle stage."),
    ("routing.problem", "server.lifecycle",
     "Routing decides what happens during the 'interpret request' stage of the lifecycle."),
    ("routing.problem", "http.parsing",
     "You need a parsed method+path before you can ask which handler should run."),
    ("routing.problem", "programming.functions",
     "A route handler is just a function — dispatch is reasoned about in terms of functions."),
    ("routing.registration", "routing.problem",
     "You can't design storage for routes until you understand what problem routing solves."),
    ("routing.registration", "programming.arrays",
     "A route table is a collection — arrays store the registered routes."),
    ("routing.registration", "programming.objects",
     "Each registered route is naturally represented as an object (method, path, handler)."),
    ("routing.matching", "routing.registration",
     "You can't match a route against a table that doesn't exist yet."),
    ("routing.not_found", "routing.matching",
     "404 is the 'no match found' branch of the matching logic."),
    ("routing.not_found", "http.response",
     "Returning 404 requires knowing how to shape an HTTP response."),
    ("routing.parameters.extraction", "routing.matching",
     "Extracting a dynamic segment happens during matching — matching must exist first."),
    ("routing.parameters.extraction", "routing.parameters.problem",
     "You need to understand what :id represents before extracting its value."),
    ("routing.parameters.problem", "routing.matching",
     "Dynamic segments are an extension of matching — matching must exist first."),
    ("request.object", "http.parsing",
     "The request object is built from the parsed raw request."),
    ("request.object", "programming.objects",
     "The request object is an object with properties handlers will read."),
    ("response.object", "http.response",
     "The response abstraction wraps the raw status/headers/body concepts."),
    ("response.object", "programming.objects",
     "The response object's methods (send/json/status) are just object methods."),
    ("middleware.problem", "request.object",
     "The 'logging in every handler' pain point only makes sense once handlers receive a request object."),
    ("middleware.problem", "response.object",
     "Middleware would touch the response too, so the response abstraction must exist first."),
    ("middleware.concept", "middleware.problem",
     "You need to feel the pain point before the middleware solution makes sense."),
    ("middleware.concept", "request.object",
     "Middleware reads/modifies the request object."),
    ("middleware.concept", "response.object",
     "Middleware reads/modifies the response object."),
    ("middleware.concept", "routing.matching",
     "Middleware sits between the raw request and the matched handler — matching must exist."),
    ("middleware.pipeline", "middleware.concept",
     "You must understand next()/ordering conceptually before implementing the pipeline."),
    ("middleware.pipeline", "programming.functions",
     "next() is just a callback function — the pipeline is built from function composition."),
    ("error.problem", "middleware.pipeline",
     "Errors need somewhere to be caught — that's the middleware pipeline you just built."),
    ("error.middleware", "middleware.pipeline",
     "Error handling is implemented as a wrapper around the same pipeline execution."),
    ("error.middleware", "routing.not_found",
     "Error handling and not-found handling are sibling 'failure path' concerns in the same dispatch code."),
    ("testing.problem", "error.middleware",
     "You need enough moving parts (including error handling) to feel why manual testing breaks down."),
    ("testing.integration", "routing.parameters.extraction",
     "Route parameter extraction is one of the behaviors integration tests must cover."),
    ("testing.integration", "request.object",
     "The request abstraction is one of the behaviors integration tests must cover."),
    ("testing.integration", "response.object",
     "The response abstraction is one of the behaviors integration tests must cover."),
    ("testing.integration", "middleware.pipeline",
     "Middleware execution is one of the behaviors integration tests must cover."),
    ("testing.integration", "error.middleware",
     "Error handling is one of the behaviors integration tests must cover."),
    ("testing.integration", "testing.problem",
     "You need to understand why manual testing is insufficient before writing automated tests."),
]

MILESTONES: list[MilestoneSpec] = [
    {
        "id": "M01",
        "title": "Understand the Problem",
        "description": (
            "Before writing any code: what does a backend framework actually do, "
            "and what programming fundamentals will you lean on to build one?"
        ),
        "instructions": (
            "What to do:\n"
            "1. Write your own current understanding of what a backend framework does — "
            "before researching anything.\n"
            "2. Answer the mentor's follow-up questions about the layers involved "
            "between a request arriving and a response leaving.\n"
            "3. Confirm you can explain functions/callbacks, objects, and arrays "
            "well enough to build with them — the mentor will ask, not lecture."
        ),
        "success_criteria": (
            "You can explain, in your own words, what happens between a client's "
            "request and a server's response, and you're fluent in functions, "
            "objects, and arrays."
        ),
        "concepts": ["programming.functions", "programming.objects", "programming.arrays"],
    },
    {
        "id": "M02",
        "title": "Networking Fundamentals",
        "description": "Enough TCP/socket understanding to explain why an HTTP server needs a network transport.",
        "instructions": (
            "What to do:\n"
            "1. Research what happens when a client connects to a server (TCP, ports, sockets).\n"
            "2. Explain it back in your own words — no copy-pasted definitions.\n"
            "3. Do not write server code yet — this milestone is understanding only."
        ),
        "success_criteria": (
            "You can explain client/server, TCP, and sockets well enough that a "
            "teammate would understand why your HTTP server needs them underneath."
        ),
        "concepts": ["networking.client_server", "networking.tcp", "networking.socket"],
    },
    {
        "id": "M03",
        "title": "Create a Raw HTTP Server",
        "description": "Stand up the smallest possible server and understand HTTP's request/response shape.",
        "instructions": (
            "What to do:\n"
            "1. Research HTTP's request/response structure (method/path/headers/body; status/headers/body).\n"
            "2. Create the smallest Node.js server you can that accepts a connection — no Express.\n"
            "3. Confirm it runs and responds to a request from curl or your terminal."
        ),
        "success_criteria": (
            "A minimal Node.js server accepts a connection and you can explain the "
            "structure of the HTTP request/response it's handling."
        ),
        "concepts": ["http.protocol", "http.request", "http.response", "http.raw_request", "server.listen"],
    },
    {
        "id": "M04",
        "title": "Understand and Parse HTTP",
        "description": "Turn the raw request into structured data, and trace the full request lifecycle.",
        "instructions": (
            "What to do:\n"
            "1. Look at a raw request and identify method/path/headers/body by hand.\n"
            "2. Implement a parser that returns { method, path, headers, body }.\n"
            "3. Trace and log every stage of your server's request lifecycle."
        ),
        "success_criteria": (
            "Your parser correctly extracts method/path/headers/body from a real "
            "request, and you can point to where each lifecycle stage happens in your code."
        ),
        "concepts": ["http.parsing", "server.lifecycle"],
    },
    {
        "id": "M05",
        "title": "Build the Request/Response Layer",
        "description": "Design convenience objects handlers will actually use.",
        "instructions": (
            "What to do:\n"
            "1. Design (before coding) which fields handlers will repeatedly need on the request.\n"
            "2. Implement the request object.\n"
            "3. Implement a response object with send()/json()/status()."
        ),
        "success_criteria": (
            "A handler can read a clean request object and respond with "
            "res.send()/res.json()/res.status() without touching raw Node APIs directly."
        ),
        "concepts": ["request.object", "response.object"],
    },
    {
        "id": "M06",
        "title": "Build Routing",
        "description": "Register routes, match them against incoming requests, and handle unmatched ones.",
        "instructions": (
            "What to do:\n"
            "1. Explain what problem routing solves before writing code.\n"
            "2. Implement route registration (e.g. app.get(path, handler)).\n"
            "3. Implement matching: incoming method+path -> registered route -> handler.\n"
            "4. Return 404 for unmatched routes."
        ),
        "success_criteria": (
            "Registered GET/POST routes are matched and invoked correctly, and "
            "unmatched requests return 404 instead of hanging or crashing."
        ),
        "concepts": ["routing.problem", "routing.registration", "routing.matching", "routing.not_found"],
    },
    {
        "id": "M07",
        "title": "Add Route Parameters",
        "description": "Support dynamic segments like /users/:id.",
        "instructions": (
            "What to do:\n"
            "1. Explain what /users/:id represents versus /users/123.\n"
            "2. Extend matching to recognize :param segments.\n"
            "3. Implement extraction so req.params.id is available in the handler."
        ),
        "success_criteria": "req.params.id === '123' for a route /users/:id matched against /users/123.",
        "concepts": ["routing.parameters.problem", "routing.parameters.extraction"],
    },
    {
        "id": "M08",
        "title": "Build Middleware",
        "description": "A pipeline for cross-cutting behavior like logging, running before the handler.",
        "instructions": (
            "What to do:\n"
            "1. Identify a piece of logic that would otherwise be duplicated in every handler.\n"
            "2. Explain next()/ordering/short-circuiting conceptually.\n"
            "3. Implement app.use(middleware) and sequential pipeline execution."
        ),
        "success_criteria": (
            "Registered middleware runs in order before the matched handler, and a "
            "middleware that doesn't call next() correctly stops the pipeline."
        ),
        "concepts": ["middleware.problem", "middleware.concept", "middleware.pipeline"],
    },
    {
        "id": "M09",
        "title": "Add Error Handling",
        "description": "Catch thrown errors and malformed requests, and turn them into clean responses.",
        "instructions": (
            "What to do:\n"
            "1. Identify the failure scenarios your framework needs to survive.\n"
            "2. Implement a catch-all around pipeline/handler execution.\n"
            "3. Verify a thrown error produces a clean 500, not a hang or crash."
        ),
        "success_criteria": "A handler that throws results in a clean HTTP 500 response, not a crash or a hang.",
        "concepts": ["error.problem", "error.middleware"],
    },
    {
        "id": "M10",
        "title": "Add Testing",
        "description": "Replace manual curl-testing with automated integration tests.",
        "instructions": (
            "What to do:\n"
            "1. Explain what manual testing has been missing.\n"
            "2. Write automated tests (Node's built-in test runner) covering: server "
            "starts, GET works, POST works, 404 works, parameters work, middleware "
            "runs, errors are handled.\n"
            "3. Run the tests and fix any real failures yourself."
        ),
        "success_criteria": "node --test passes, covering GET/POST, 404, params, middleware, and error handling.",
        "concepts": ["testing.problem", "testing.integration"],
    },
    {
        "id": "M11",
        "title": "Refactor the Framework",
        "description": (
            "No new concepts — revisit your own code with the mentor acting as a "
            "senior engineer doing a design review."
        ),
        "instructions": (
            "What to do:\n"
            "1. Re-read your own implementation end to end.\n"
            "2. Identify at least one thing you'd structure differently now that you "
            "understand the whole system.\n"
            "3. Make that refactor without changing observable behavior — your tests "
            "from M10 must still pass."
        ),
        "success_criteria": "At least one real structural improvement is made and all M10 tests still pass.",
        "concepts": [],
    },
    {
        "id": "M12",
        "title": "Final Engineering Review",
        "description": "A technical defense of the framework you built, based on your actual implementation.",
        "instructions": (
            "What to do:\n"
            "1. Be ready to explain your router, middleware pipeline, and error "
            "handling from memory, referencing your own code.\n"
            "2. Answer the mentor's defense questions (complexity, concurrency, "
            "extensibility, what you'd rewrite).\n"
            "3. This is graded on your understanding, not on adding new features."
        ),
        "success_criteria": "You can defend every design decision in your framework without looking anything up.",
        "concepts": [],
    },
]

PROJECT_SPEC: dict[str, Any] = {
    "title": "Build a Simple Backend Framework in JavaScript",
    "description": (
        "Progressively build a small backend framework from scratch in "
        "JavaScript: HTTP server, request parsing, routing, route parameters, "
        "request/response objects, middleware, error handling, and tests."
    ),
    "objective": (
        "By the end, you will have built (and be able to explain and defend, "
        "unaided) a minimal framework supporting roughly:\n"
        "  const app = framework();\n"
        "  app.get('/', (req, res) => res.send('Hello World'));\n"
        "  app.get('/users/:id', (req, res) => res.json({ id: req.params.id }));\n"
        "  app.use(logger);\n"
        "  app.listen(3000);\n"
        "You must not be shown this implementation up front — it is the destination, "
        "discovered progressively, one milestone at a time."
    ),
    "difficulty": "intermediate",
    "prerequisites": [
        "JavaScript fundamentals (functions, objects, arrays)",
        "Comfort with a terminal",
    ],
    "expected_outcome": (
        "A working, from-scratch Node.js backend framework (no Express) "
        "supporting routing, route parameters, middleware, error handling, "
        "and passing your own automated tests — that you can explain and "
        "defend without AI assistance."
    ),
    "skills": [
        "Raw HTTP request/response handling in Node.js",
        "Parsing unstructured text into structured data",
        "Designing a routing table and matcher",
        "Middleware pipeline design (next(), short-circuiting)",
        "Error handling as a cross-cutting concern",
        "Writing automated integration tests",
    ],
    "constraints": [
        "No Express, Koa, Fastify, or any other web framework",
        "No AI-generated implementation — you design and write every line",
        "Use Node.js built-in modules only (http/net) plus, later, the built-in test runner",
    ],
    "tests": [
        "Server starts and accepts a connection",
        "GET route matches and responds",
        "POST route matches and responds",
        "Unmatched route returns 404",
        "Route parameters are extracted correctly",
        "Middleware runs in order and can short-circuit the pipeline",
        "A thrown handler error produces a clean 500, not a crash",
    ],
    "evaluation_criteria": [
        "All 12 milestones completed with evidence (not self-report)",
        "Automated tests pass via node --test",
        "Learner can pass the final engineering defense unaided",
    ],
    "extension_challenges": [
        "Support async middleware/handlers",
        "Add wildcard or regex route patterns",
        "Add a simple static-file-serving middleware",
        "Support route grouping / sub-routers",
    ],
    "recommended_resources": [
        {"title": "Node.js docs: http", "url": "https://nodejs.org/api/http.html"},
        {"title": "Node.js docs: net", "url": "https://nodejs.org/api/net.html"},
        {"title": "Node.js docs: Test runner", "url": "https://nodejs.org/api/test.html"},
        {"title": "MDN: HTTP overview", "url": f"{MDN}/en-US/docs/Web/HTTP/Overview"},
    ],
    "runtime": {
        "language": "javascript",
        "sandbox_image": "socratic-sandbox-node:latest",
        "run": ["node", "{file}"],
        "test_command": ["node", "--test"],
        "entry_globs": ["*.js", "*.mjs"],
    },
}
