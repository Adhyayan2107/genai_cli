# MEMORY.md

> _This file is a static design artifact._
> Earlier versions of vibe-coder maintained live long-term memory here:
> per-host site facts, user preferences, and a FIFO run log. The current
> build keeps the format and the writer code as documentation but does not
> read or write this file at runtime.

## User preferences
<!-- budget: 500 tokens -->
_(static — not read at runtime)_

## Site knowledge
<!-- budget: 1500 tokens. Sub-bucketed by '### host'. -->
_(static — not read at runtime)_

## Run log
<!-- budget: 1000 tokens, FIFO -->
_(static — not read at runtime)_
