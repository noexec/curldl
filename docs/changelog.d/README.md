# Maintaining CHANGELOG


## Adding a Changelog item

Fragment of type _doc_ for pull request #123:

```shell
towncrier create -c "Test fragment" 123.doc.md
```

Without a pull request ID:

```shell
towncrier create -c "Test fragment" +description.doc.md
```

Supported (default) fragment types:
* `feature` — new feature
* `bugfix` — bug fix
* `doc` — documentation improvement
* `removal` — removal/deprecation of API
* `misc` — not of interest to users


## Updating the Changelog before a release

```shell
towncrier build --draft --name curldl --version 1.0.1
```
