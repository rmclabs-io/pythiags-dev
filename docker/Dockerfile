ARG BASE_IMG

FROM ${BASE_IMG} as deepstream_python_apps

LABEL maintainer="Pablo Woolvett <pablowoolvett@gmail.com>"
LABEL org.label-schema.schema-version="1.0"
LABEL org.label-schema.description="Pythonic Deepstream"
LABEL org.label-schema.url="https://dev.rmclabs.io/pythia"
LABEL org.label-schema.vcs-url="https://github.com/rmclabs-io/pythiags"

ARG DEBIAN_FRONTEND=noninteractive

#region common - shared between prod-builder and dev
FROM deepstream_python_apps as common 

COPY ./reqs/apt.build.list /tmp/deps/apt.build.list
RUN apt-get update \
  && apt-get install --no-install-recommends -y \
  $(cat /tmp/deps/apt.build.list | tr '\n' ' ') \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /tmp/deps

RUN python3 -m venv /opt/rmclabs/pythia-venv
ENV PATH="/opt/rmclabs/pythia-venv/bin:${PATH}" 
ENV VIRTUAL_ENV="/opt/rmclabs/pythia-venv" \
    PS1="(pythia) ${PS1:-}" \
    PYTHONHOME=""

WORKDIR /opt/rmclabs/pythia
#endregion common

#region build - intermadiate stage for production
FROM common as build

COPY ./reqs/apt.build.list /tmp/deps/apt.build.list
RUN apt-get update \
  && apt-get install --no-install-recommends -y \
  $(cat /tmp/deps/apt.build.list | tr '\n' ' ') \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/rmclabs/pythia

ADD ./src/ ./pyproject.toml ./poetry.lock README.md ./
ADD ./src ./src
RUN pip install --no-cache-dir .[cli]

#endregion build

#region prod - production stage with minimal runtime deps
FROM deepstream_python_apps as prod

COPY ./reqs/apt.runtime.list /tmp/deps/apt.runtime.list
RUN apt-get update \
  && apt-get install --no-install-recommends -y \
  $(cat /tmp/deps/apt.runtime.list | tr '\n' ' ') \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /tmp/deps

ENV PATH="/opt/rmclabs/pythia-venv/bin:${PATH}" 
COPY --from=build /opt/rmclabs/pythia-venv/ /opt/rmclabs/pythia-venv/

ARG VCS_REF
ARG BUILD_DATE
ARG BUILD_VERSION
ARG PYTHIA_TAG
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.build-date=$BUILD_DATE
LABEL org.label-schema.version=$BUILD_VERSION
LABEL org.label-schema.name=$PYTHIA_TAG
LABEL org.label-schema.docker.cmd="docker run --rm -it -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY $PYTHIA_TAG"

#endregion prod

#region dev - development image
FROM common as dev-common

RUN cd /opt/nvidia/deepstream/deepstream/sources/ \
  && git clone \
  -b feat/iterators \
  https://github.com/rmclabs-io/deepstream_python_apps \
  && cd deepstream_python_apps \
  && git checkout e93472f9b9e7cfeaaa45ad32a0b2fe6ba7f7bf05 \
  \
  && scripts/install trt \
  && scripts/install peoplesegnet

ARG POETRY_HOME=/opt/poetry
ARG POETRY_NO_INTERACTION=1

ENV PATH="$POETRY_HOME/bin:$PATH"

RUN curl -sSL https://install.python-poetry.org | python3
COPY ./pyproject.toml ./poetry.lock  ./

RUN poetry install --no-root

ADD ./pyproject.toml ./poetry.lock README.md ./
ADD ./src ./src
RUN poetry install -E cli -E jinja -E opencv -E redis -E kafka
COPY . .

FROM dev-common as dev
ARG VCS_REF
ARG BUILD_DATE
ARG BUILD_VERSION
ARG PYTHIA_TAG
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.build-date=$BUILD_DATE
LABEL org.label-schema.version=$BUILD_VERSION
LABEL org.label-schema.name=$PYTHIA_TAG
LABEL org.label-schema.docker.cmd="docker run --rm -it -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY $PYTHIA_TAG"

#endregion dev

#region devcode - devconatiner base image
FROM dev-common as dev-code
ARG DOCKER_GROUP_ID
COPY ./reqs/apt.devcontainer.list /tmp/deps/apt.devcontainer.list
RUN apt-get update \
  && apt-get install --no-install-recommends -y \
  $(cat /tmp/deps/apt.devcontainer.list | tr '\n' ' ') \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /tmp/deps
RUN echo 'root:root' | chpasswd
RUN adduser rmclabsdev \
  && chmod +x `which poetry` \
  && chown -R rmclabsdev:rmclabsdev /opt/rmclabs/pythia \
  && chown -R rmclabsdev:rmclabsdev /opt/rmclabs/pythia-venv \
  && chown -R rmclabsdev:rmclabsdev /opt/nvidia/deepstream/deepstream/samples/models/
ENV VIRTUAL_ENV="/opt/rmclabs/pythia-venv" \
    PS1="(pythia) ${PS1:-}" \
    PYTHONHOME=""
RUN groupadd -g "$DOCKER_GROUP_ID" docker \
  && usermod -aG docker rmclabsdev
#endregion devcode
