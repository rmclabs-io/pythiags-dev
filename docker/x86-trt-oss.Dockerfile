FROM nvcr.io/nvidia/deepstream:6.1.1-devel

ARG PORT=9465
ADD docker/trt-oss/install.sh /tmp/entrypoint
EXPOSE ${PORT}

RUN /tmp/entrypoint ${PORT}
