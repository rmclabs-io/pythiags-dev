# pythia requirements

to be used with aptitude, see usage in `../docker/Dockerfile`:

```console
# apt-get update \
  && apt-get install --no-install-recommends -y \
  $(cat apt.<stage>.list | tr '\n' ' ') \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
```
where stage is one of `dev`, `build`, `runtime`.

```console
* `apt.build.list`: used by poetry (for development), or pip (to construct and popullate the venv)
* `apt.runtime.list`: runtime  dependencies for the venv as created by pip
