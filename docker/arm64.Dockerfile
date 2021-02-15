ARG PYSETUP_PATH=/opt/pysetup

FROM nvcr.io/nvidia/deepstream-l4t:5.0.1-20.09-samples as builder

ARG PYSETUP_PATH

ARG VERSION_PIP=20.2.2
ARG POETRY_VERSION=1.1.4

ARG DEBIAN_FRONTEND=noninteractive
# python
ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=${POETRY_VERSION} \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    \
    # paths
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH=${PYSETUP_PATH} \
    VENV_PATH="${PYSETUP_PATH}/.venv" \
    \
    # patches
    # this is required for clickit+python3.6.9 only, see https://github.com/python-poetry/poetry/issues/1427#issuecomment-537260307
    LANG=C.UTF-8

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

ADD setup/aptitude.build.list aptitude.build.list
ADD setup/aptitude.kivy.list aptitude.kivy.list
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        # deps for installing poetry
        curl \
        ca-certificates \
        # deps for building python deps
        build-essential \
        `cat aptitude.build.list | tr "\n" " "` \
        `cat aptitude.kivy.list | tr "\n" " "` \
        \
        # tools for development
        nano \
        tree

# install poetry - respects $POETRY_VERSION & $POETRY_HOME
RUN wget https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py -O /get-poetry.py \
    && python3 /get-poetry.py --no-modify-path --yes
# force poetry to use python3
RUN ln -s /usr/bin/python3 $POETRY_HOME/bin/python

# copy project requirement files here to ensure they will be cached.
WORKDIR $PYSETUP_PATH
RUN python -m venv $VENV_PATH
RUN pip install --no-cache-dir --upgrade pip==$VERSION_PIP wheel==0.35.1 setuptools==49.6.0



FROM builder as poetry

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt



FROM poetry as dev

COPY requirements.dev.txt requirements.dev.txt
RUN pip install --no-cache-dir -r requirements.dev.txt

COPY poetry.lock pyproject.toml  README.md ./
ADD ./src ./src
RUN poetry install -vvv -E ds -E cli
ADD . .





FROM poetry as installer
COPY poetry.lock pyproject.toml  README.md ./
ADD ./src ./src
RUN poetry install -vvv --no-dev -E ds -E cli


# `production` image used for runtime
# FIXME revert this to use `base` instead and copy necessary files from `samples`
#FROM nvcr.io/nvidia/deepstream-l4t:5.0.1-20.09-base as production
FROM nvcr.io/nvidia/deepstream-l4t:5.0.1-20.09-samples as production

ARG PYSETUP_PATH

ARG DEBIAN_FRONTEND=noninteractive

ENV PYSETUP_PATH=${PYSETUP_PATH}
ENV VENV_PATH="${PYSETUP_PATH}/.venv"

ADD setup/aptitude.run.list aptitude.run.list

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        `cat aptitude.run.list | tr "\n" " "` \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY --from=installer ${PYSETUP_PATH} ${PYSETUP_PATH}
ENV PATH="$VENV_PATH/bin:$PATH"
RUN ln -sf /usr/bin/python3 $VENV_PATH/bin/python
WORKDIR /app/

# FIXME move these
ENTRYPOINT [ "pythia" ]
CMD [ "videotestsrc" ]
