# Contributing

Thank you for helping. This page explains how to make a change that is easy to accept.

## What we ask of every change

1. Use plain English in anything a person reads. Short sentences. No jargon. If a technical word is needed, explain it in the same place.
2. Never put a password, key, address of your own, or personal name in the code, the docs or a test. The checks will stop it.
3. Never change a setting in a person's own app without showing it first. The preview and the What changes page exist for this reason.
4. Never weaken the download safety rules.
5. Test on a throwaway setup, never on a server you depend on.

## Where things are

1. wizard/app holds the program. Read docs/How it works.md first.
2. wizard/app/static holds the page you see in the browser.
3. docs holds the written help. extras holds optional tools for people who run their own server.

## Running the checks

You need Python 3 and Node. From the top folder:

1. python3 tools/check.py

This compiles every Python file, checks the page script, checks the shell scripts, and looks for anything that looks like a secret. The same checks run on every pull request.

## Trying a change safely

Use a different project name and different ports, so your real apps are not touched. Set the STACK_PROJECT setting to something like test, and start the setup with it. Throwaway apps are the best way to test the part that changes a person's own apps.

## Sending a change

1. Make a branch.
2. Keep the change small and about one thing.
3. Run the checks.
4. Open a pull request. Say what changed, why, and how you tested it.

## Reporting a problem

Open an issue and choose the right form. Say what you expected and what happened. Never paste passwords or keys. If you are not sure whether something is private, leave it out.
