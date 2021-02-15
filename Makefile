
.DEFAULT_GOAL := help

ds=/opt/nvidia/deepstream/deepstream/
data=data
stream=${ds}/samples/streams/sample_720p.h264
venv=.venv

models_src=${ds}/samples/models
configs_src=${ds}/samples/configs/deepstream-app
models=${data}/models

dockertag=pythia-build
target=production

export
MODELS=${models}/Primary_Detector ${models}/Secondary_CarColor
CONFIGS=${models}/Primary_Detector/config_infer_primary.txt ${models}/Secondary_CarColor/config_infer_secondary_carcolor.txt

# =============================================================
help:                        ##:    help: This help dialog.
	@echo "Usage: make [target]"
	@echo "  Available targets:"
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | grep -oP '(?<=##:).*'

perf:                       ##:    perf: run a sample pipeline and measure performance.
	bash -c "\
	export DISPLAY=:0 \
	&& mkdir -p tmp \
	&& cd tmp \
	&& rm gstnvdsinfer* \
	; rm counts.txt \
	; rm -rf 2020* \
	; poetry run python -m pythia.perf |& tee perf.log\
	"

all: install data            ##:    all: Install the venv and configure sample data (models, config, images)
install: .check venv         ##:     ├─ install: Ensure prerequisites are met, then install pythia to virtualenv
venv: ${venv}                ##:     │     └─ venv   : Install the venv and pythia in editable mode
data: models configs images  ##:     └─ data: Configure sample data (models, config, images)
models: $(MODELS)            ##:            ├─ models: Copy models from deespstream source, so .engine persist
configs: $(CONFIGS)          ##:            ├─ configs: Copy config from deespstream source, with some minor edits
images: ${data}/cars         ##:            └─ images: Create sample frames from deesptream sample stream (cars video).
docker:                      ##:    docker: build docker image 
	docker build \
		--target=${target} \
		--tag=${dockertag}-${target} \
		--file docker/jetson.Dockerfile \
		.
	. ./check
#	touch ${XAUTH}
#	xauth nlist ${DISPLAY} | sed -e 's/^..../ffff/' | xauth -f ${XAUTH} nmerge -
	# docker run \
	# 	--rm \
	# 	-it \
	# 	--net=host \
	# 	--runtime nvidia \
    #     --volume=${XSOCK}:${XSOCK}:rw \
    #     --volume=${XAUTH}:${XAUTH}:rw \
    #     --volume="/etc/group:/etc/group:ro" \
    #     --volume="/etc/passwd:/etc/passwd:ro" \
    #     --volume="/etc/shadow:/etc/shadow:ro" \
    #     --volume="/etc/sudoers.d:/etc/sudoers.d:ro" \
    #     --user=$(id -u $USER):$(id -g $USER) \
    #     --privileged \
	# 	--env-file=.env \
	# 	pythia-build:latest
#		pythia-build:latest \
#		python -m pythia videotestsrc

docker-ctx:                  ##:    docker-ctx: build docker image
	docker build -f docker/context.Dockerfile -t test/buildcontext .

kivy:                        ##:    kivy: build kivy docker image
	docker build -f docker/kivy.Dockerfile -t test/kivy .
	docker run \
	    --rm \
		-it \
	    --name=kivy \
	    --net=host \
	    --runtime nvidia \
	    --env="DISPLAY" \
	    --env="QT_X11_NO_MITSHM=1" \
	    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
	    --env-file=.env \
		-v `pwd`/out:/out \
	    test/kivy:latest

# =============================================================

.check:
	@ echo "===== Installing Prerequisites ====="
	sudo apt install -yq `cat setup/aptitude.build.list | tr "\n" " "` `cat setup/aptitude.run.list | tr "\n" " "`
	@ echo "===== Checking Prerequisites ====="
	@ echo "===Deepstream==="
	@cat /opt/nvidia/deepstream/deepstream/version | fgrep "Version: 5.0" && exit 0 \
		|| echo "please install deepstream" && exit 1

	@ echo "===python version==="
	@python3 -V | grep 3.6.9 && exit 0 \
		|| echo "python3.6.9 required" && exit 1
	@ echo "======== Prerequisites OK ========"

${venv}:
	poetry config --local virtualenvs.create true
	poetry config --local virtualenvs.in-project true
	poetry install -E ds -E cli \
	&& echo "Venv succesfully configured. Activate it by running 'poetry shell'"

$(MODELS):
	mkdir -p `dirname $@`
	cp -r ${models_src}/`basename $@` $@

$(CONFIGS):
	mkdir -p `dirname $@`
	cp ${configs_src}/`basename $@` $@
	@if `echo "$@" | grep -q config_infer_secondary_carcolor` ; \
	then \
		echo `echo "gie-unique-id=2" >> $@` ; \
		echo `echo "classifier-async-mode=0" >> $@` ; \
	fi

${data}/cars:
	@$(MAKE) .check-ffmpeg
	mkdir -p $@
	ffmpeg \
		-i ${stream} \
		-start_number 0 \
		-vframes 1088 \
		${data}/cars/%012d.jpg

.check-ffmpeg:
	@ echo "===== Checking Prerequisites ====="
	@ echo "===ffmpeg location==="
	@which ffmpeg && exit 0 \
		|| echo "please install ffmpeg first" && exit 1
	@ echo "======== Prerequisites OK ========"


clean:
	-rm -r ${data}
	-rm -rf ${venv}

.PHONY: all install data models images configs .check .check-ffmpeg clean help perf docker
