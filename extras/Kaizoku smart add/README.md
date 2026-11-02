# Kaizoku smart add

Adds a manga to Kaizoku so that only the next chapters are downloaded, from the best source, with the other sources kept as back-ups.

1. It searches every source, then reads what is already in your manga folder (it understands names like `Ch.230`, `Vol.23 Ch.229` and `Title 231.cbz`, and ignores volume numbers and years).
2. It ranks the sources by how far they go, how many whole chapters they have and how recently they updated. Dead sources, and sources that stop far below what you own, are skipped.
3. The best source becomes permanent, the others back-ups. Kaizoku only takes chapters from a back-up that the permanent source does not have.
4. If the folder holds only a few chapters, it will not guess: it asks you to choose `--from 0` (everything) or `--from N`.

```bash
python3 kaizoku_smart_add.py "Chainsaw Man" --library /path/to/Manga          # shows the plan
python3 kaizoku_smart_add.py "Chainsaw Man" --library /path/to/Manga --apply  # adds it
python3 kaizoku_smart_add.py --selftest
```
