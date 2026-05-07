#import "@preview/touying:0.7.3": *
#import themes.simple: *

#show: simple-theme.with(aspect-ratio: "16-9")

= gman

== Project Overview

`gman` is a small CLI for batch operations across cloned git repositories.

How? It crawls your home directory for git repos, then lets you run commands across them with filters and output formatting.

== Problem & Technologies

Managing many repositories takes time. You might want to check status, pull updates, or run custom commands across all your repositories. You might want to find repositories with uncommitted changes, or those that haven't been updated in a while.

Solution: `gman`

Python, VS Code, the standard library, and `unittest` were used.

== OOP Principles
Encapsulation splits discovery, execution, output, and CLI logic.

Abstraction keeps the CLI working with high-level repository and printer interfaces.

Polymorphism lets output printers and selector operators change at runtime.

== Design Patterns
Strategy selects output formatters and filters from command-line arguments.

Factory helpers create the right printer or selector implementation.

Singleton-style execution keeps git commands centralized.

== Live Demo

Section left blank for live demo.

== Conclusion & Questions
`gman` reduces repetitive git work and keeps batch operations consistent.

Future work: parallel execution, more output formats, and better error handling, more interactive CLI, etc

Questions?
